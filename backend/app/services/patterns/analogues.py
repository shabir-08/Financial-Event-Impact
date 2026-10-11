"""Historical analogue search: which past weeks looked most like a query, and what happened in them.

Method (transparent, no fitted model):
* Candidate pool = weekly rows whose outcome window ended on or before `as_of` (no future outcomes).
* Each matching feature is standardised with the POOL's mean and SD (past data only), so features
  with large numeric scales cannot dominate.
* Distance = root-mean-square of the standardised differences over the matching features
  (comparable across different numbers of features; 1.0 ~ one SD apart on average).
* The k nearest rows are returned with their observed outcomes. Rows lacking any matching feature are
  excluded and counted. Adjacent weeks / the same event group are grouped into clusters because they
  are not independent episodes; sample statistics are withheld when there are too few clusters.

Historical similarity does not imply causation or a similar future outcome; statistics are
descriptive sample statistics, not probabilities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

CLOSE, MODERATE = 0.5, 1.0          # RMS distance bands (pool SD units) for match-quality labels
CLUSTER_GAP_DAYS = 21               # analogues within 3 weeks of each other count as one episode
MIN_CLUSTERS_FOR_STATS = 5
MIN_ROWS_FOR_STATS = 8


@dataclass
class SearchResult:
    analogues: list[dict]
    pool_size: int
    excluded_missing: int
    n_clusters: int
    statistics: dict[str, Any] | None
    statistics_withheld_reason: str | None
    warnings: list[dict] = field(default_factory=list)
    feature_ranges: dict[str, dict] = field(default_factory=dict)


def _quality(d: float) -> str:
    return "close" if d < CLOSE else "moderate" if d < MODERATE else "weak"


def _clusters(rows: list[dict]) -> int:
    """Union adjacent weeks (<= CLUSTER_GAP_DAYS apart) and rows sharing an event cv_group."""
    n = len(rows)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            a, b = rows[i], rows[j]
            gap = abs((date.fromisoformat(a["week_start"]) - date.fromisoformat(b["week_start"])).days)
            same_event = a.get("cv_group") == b.get("cv_group") and not str(a.get("cv_group", "")).startswith("NORMAL")
            if gap <= CLUSTER_GAP_DAYS or same_event:
                parent[find(i)] = find(j)
    return len({find(i) for i in range(n)})


def describe(values: list[float]) -> dict[str, float | int]:
    v = np.asarray([x for x in values if x is not None and math.isfinite(x)], dtype=float)
    if not len(v):
        return {"n": 0}
    q25, med, q75 = np.percentile(v, [25, 50, 75])
    return {"n": int(len(v)), "mean": round(float(v.mean()), 3), "median": round(float(med), 3),
            "sd": round(float(v.std(ddof=1)), 3) if len(v) > 1 else None,
            "iqr": [round(float(q25), 3), round(float(q75), 3)], "min": round(float(v.min()), 3), "max": round(float(v.max()), 3),
            "share_positive": round(float((v > 0).mean()), 3), "share_negative": round(float((v < 0).mean()), 3)}


def search(rows: list[dict], query: dict[str, float], features: list[str], outcome_cols: list[str], k: int,
           as_of: date) -> SearchResult:
    """rows: weekly records (dicts) with week_start, week_end, cv_group and feature / outcome values."""
    pool = [r for r in rows if date.fromisoformat(r["week_end"]) <= as_of]
    usable = [r for r in pool if all(r.get(f) is not None and math.isfinite(r[f]) for f in features)]
    excluded = len(pool) - len(usable)
    warnings: list[dict] = []
    if not usable:
        return SearchResult([], len(pool), excluded, 0, None, "no historical rows have all matching features",
                            [{"code": "no_comparable_data", "message": "No historical observations with the requested features."}])
    X = np.array([[r[f] for f in features] for r in usable], dtype=float)
    mu, sd = X.mean(axis=0), X.std(axis=0, ddof=1)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    q = np.array([query[f] for f in features], dtype=float)
    ranges = {}
    for j, f in enumerate(features):
        lo, hi = float(X[:, j].min()), float(X[:, j].max())
        inside = bool(lo <= q[j] <= hi)
        ranges[f] = {"query": float(q[j]), "historical_min": lo, "historical_max": hi, "pool_mean": float(mu[j]),
                     "pool_sd": float(sd[j]), "query_z": float((q[j] - mu[j]) / sd[j]), "within_historical_range": inside}
        if not inside:
            warnings.append({"code": "outside_historical_range", "feature": f, "value": float(q[j]),
                             "historical_range": [lo, hi],
                             "message": f"{f}={q[j]:g} is outside every historical observation [{lo:.2f}, {hi:.2f}]; "
                                        "the nearest analogues are not comparable on this dimension."})
    Z = (X - mu) / sd
    zq = (q - mu) / sd
    dist = np.sqrt(np.mean((Z - zq) ** 2, axis=1))
    order = np.argsort(dist, kind="stable")[:k]
    out = []
    for i in order:
        r = usable[i]
        zdiff = Z[i] - zq
        out.append({
            "week_start": r["week_start"], "week_end": r["week_end"], "distance": round(float(dist[i]), 4),
            "match_quality": _quality(float(dist[i])), "cv_group": r.get("cv_group"),
            "matched_features": {f: {"query": float(q[j]), "historical": float(X[i, j]),
                                     "difference_in_sd": round(float(zdiff[j]), 3)} for j, f in enumerate(features)},
            "important_differences": [f for j, f in enumerate(features) if abs(zdiff[j]) >= 1.0],
            "outcomes": {c: (None if r.get(c) is None or not math.isfinite(r[c]) else round(float(r[c]), 4)) for c in outcome_cols},
            "event_ids_in_window": r.get("event_ids") or "", "events_public_at_start": r.get("known_event_ids") or "",
        })
    n_clusters = _clusters(out)
    if out and out[0]["distance"] >= MODERATE:
        warnings.append({"code": "weak_analogues", "nearest_distance": out[0]["distance"],
                         "message": "Even the closest historical week differs by about one standard deviation or more per feature."})
    stats, reason = None, None
    if len(out) < MIN_ROWS_FOR_STATS or n_clusters < MIN_CLUSTERS_FOR_STATS:
        reason = (f"only {len(out)} analogue weeks in {n_clusters} independent cluster(s); at least {MIN_ROWS_FOR_STATS} "
                  f"weeks in {MIN_CLUSTERS_FOR_STATS} clusters are required for sample statistics")
        warnings.append({"code": "insufficient_sample", "message": reason})
    else:
        stats = {c: describe([a["outcomes"][c] for a in out]) for c in outcome_cols}
    return SearchResult(out, len(pool), excluded, n_clusters, stats, reason, warnings, ranges)
