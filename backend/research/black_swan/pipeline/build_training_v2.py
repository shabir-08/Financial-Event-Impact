"""Phase E: experimental training dataset output/model_training_v2.csv (baseline is never modified).

= every column of model_training_final.csv, unchanged and in the same order, followed by the new
trailing features from market_features_weekly.csv (same rows, matched on week_start/week_end).
Targets, horizon (5 NSE sessions), units, dates, split and cv_group are the baseline's.

Redundancy rule (train rows only): a new feature is dropped if |Pearson r| >= 0.95 with an earlier
feature. Outcome descriptors (o_) and scenario shocks (s_) are NOT included: they are measured
during the target window and would leak.

    python pipeline/build_training_v2.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "output"
REDUNDANCY_R = 0.95


def main() -> dict:
    base = pd.read_csv(OUT / "model_training_final.csv")
    feats = pd.read_csv(OUT / "market_features_weekly.csv")
    fschema = pd.read_csv(OUT / "market_features_schema.csv")
    if not ((base.week_start == feats.week_start).all() and (base.week_end == feats.week_end).all()):
        raise SystemExit("row alignment with the baseline failed")
    new = fschema[fschema.role == "feature"].column.tolist()
    bx = [c for c in base.columns if c.startswith("x_")]
    train = base.split == "train"
    kept, dropped = [], []
    for c in new:
        earlier = bx + kept
        r = pd.concat([base.loc[train, bx], feats.loc[train, kept]], axis=1)[earlier].corrwith(feats.loc[train, c]).abs()
        (dropped.append({"feature": c, "max_abs_r": float(r.max()), "with": r.idxmax()}) if r.max() >= REDUNDANCY_R else kept.append(c))
    v2 = pd.concat([base, feats[kept]], axis=1)
    v2.to_csv(OUT / "model_training_v2.csv", index=False)
    bs = pd.read_csv(OUT / "model_training_final_schema.csv")
    extra = fschema[fschema.column.isin(kept)].rename(columns={"formula": "definition", "timing": "availability"})
    extra = extra.assign(role="feature", dtype="float", missing_policy="NA kept; never imputed with 0",
                         audit_status="new in v2 (pipeline/market_features.py)")[bs.columns.intersection(extra.columns.union(
                             ["role", "dtype", "missing_policy", "audit_status"]))]
    pd.concat([bs, extra], ignore_index=True).to_csv(OUT / "model_training_v2_schema.csv", index=False)
    prov = {"baseline_sha256": hashlib.sha256((OUT / "model_training_final.csv").read_bytes()).hexdigest(),
            "market_features_weekly_sha256": hashlib.sha256((OUT / "market_features_weekly.csv").read_bytes()).hexdigest(),
            "model_training_v2_sha256": hashlib.sha256((OUT / "model_training_v2.csv").read_bytes()).hexdigest(),
            "shape": list(v2.shape), "baseline_features": len(bx), "new_features_kept": kept, "dropped_as_redundant": dropped,
            "redundancy_rule": f"|r| >= {REDUNDANCY_R} on train rows with an earlier feature"}
    (OUT / "model_training_v2_provenance.json").write_text(json.dumps(prov, indent=1), encoding="utf-8")
    return prov


if __name__ == "__main__":
    p = main()
    print(p["shape"], "kept", len(p["new_features_kept"]), "dropped", p["dropped_as_redundant"])
