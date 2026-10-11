"""Export the pattern library used by the backend (data/patterns/pattern_library_v1.json).

Combines, without modifying any source:
  model_training_final.csv                 baseline rows: dates, cv_group, 14 x_ features, 18 y_ targets
  market_features_weekly.csv               new trailing x_ features + o_ outcome descriptors
  model_training_final_scenario_inputs.csv same-week s_ shocks (historical moves, for conditional matching)
  market_features_daily.csv                latest available market conditions
  historical_event_responses.csv           per-event responses

Column groups: condition (known at week_start), shock (move during the 5-session window),
target (5-session return during the window), outcome_descriptor (window drawdown/volatility),
metadata. The ex-post event regime label is kept only as metadata ("event_regime_ex_post").

    python pipeline/pattern_library.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from app.services.patterns.regimes import RULES, classify  # noqa: E402
from build_training_table import CLASS_FLAGS, prediction_ts, public_events  # noqa: E402
from export_models import SCENARIO_FEATURES, _targets  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "output"
DEST = REPO / "data" / "patterns" / "pattern_library_v1.json"
SOURCES = ["model_training_final.csv", "market_features_weekly.csv", "model_training_final_scenario_inputs.csv",
           "market_features_daily.csv", "historical_event_responses.csv"]


def _sha(name: str) -> str:
    return hashlib.sha256((OUT / name).read_bytes()).hexdigest()


def _table(df: pd.DataFrame) -> dict:
    clean = df.astype(object).where(pd.notna(df), None)
    return {"columns": list(df.columns), "rows": clean.values.tolist()}


def main() -> dict:
    base = pd.read_csv(OUT / "model_training_final.csv")
    feats = pd.read_csv(OUT / "market_features_weekly.csv")
    scen = pd.read_csv(OUT / "model_training_final_scenario_inputs.csv")
    daily = pd.read_csv(OUT / "market_features_daily.csv")
    events = pd.read_csv(OUT / "historical_event_responses.csv")
    bschema = pd.read_csv(OUT / "model_training_final_schema.csv").set_index("column")
    fschema = pd.read_csv(OUT / "market_features_schema.csv").set_index("column")
    assert (base.week_start == feats.week_start).all() and (base.week_start == scen.week_start).all()

    bx = [c for c in base.columns if c.startswith("x_")]
    ys = [c for c in base.columns if c.startswith("y_")]
    nx = [c for c in fschema.index if fschema.loc[c, "role"] == "feature"]
    oc = [c for c in fschema.index if fschema.loc[c, "role"] == "outcome_descriptor"]
    sx = [f[0] for f in SCENARIO_FEATURES]
    w = pd.concat([base[["week_start", "week_end", "split", "cv_group", "event_ids", "known_event_ids", *bx, *ys]]
                   .rename(columns={}), feats[nx + oc], scen[sx]], axis=1)
    w.insert(4, "event_regime_ex_post", base.regime)
    labels = [classify(r) for r in w[nx + bx].to_dict("records")]
    w["volatility_regime"] = [x["volatility_regime"] for x in labels]
    w["trend_regime"] = [x["trend_regime"] for x in labels]

    meta: dict[str, dict] = {}
    for c in bx:
        meta[c] = {"group": "condition", "unit": bschema.loc[c, "unit"], "definition": bschema.loc[c, "definition"],
                   "timing": bschema.loc[c, "availability"], "source": "model_training_final.csv"}
    for c in nx:
        meta[c] = {"group": "condition", "unit": fschema.loc[c, "unit"], "definition": fschema.loc[c, "formula"],
                   "timing": fschema.loc[c, "timing"], "source": "market_features_weekly.csv"}
    for col, param, unit, desc in SCENARIO_FEATURES:
        meta[col] = {"group": "shock", "unit": unit, "definition": desc, "scenario_parameter": param,
                     "timing": "realised over the same 5 NSE sessions as the targets (known only at week_end)",
                     "source": "model_training_final_scenario_inputs.csv"}
    for c in ys:
        meta[c] = {"group": "target", "unit": "%", "definition": bschema.loc[c, "definition"],
                   "timing": "known only at week_end close", "source": "model_training_final.csv"}
    for c in oc:
        meta[c] = {"group": "outcome_descriptor", "unit": fschema.loc[c, "unit"], "definition": fschema.loc[c, "formula"],
                   "timing": "known only at week_end close", "source": "market_features_weekly.csv"}

    last = daily.iloc[-1]
    cond_cols = [c for c in meta if meta[c]["group"] == "condition"]
    latest_vals = {c: float(last[c]) for c in cond_cols if c in daily.columns and pd.notna(last[c])}
    # event flags for the latest session, with the baseline's own rule: events public in (p5, d0]
    sessions = list(pd.to_datetime(daily.date).dt.date)
    d0 = sessions[-1]
    lo, hi = prediction_ts(sessions[-1 - 5]), prediction_ts(d0)
    known = [e for e in public_events() if lo < e["public_at"] <= hi]
    latest_vals["x_is_event"] = float(bool(known))
    for letter, name in CLASS_FLAGS:
        latest_vals[f"x_event_{name}"] = float(any(e["cls"] == letter for e in known))
    missing = [c for c in cond_cols if c not in latest_vals]
    assert not missing, missing
    latest = {"as_of_session": last["date"], "values": latest_vals,
              "source_observation_dates": {c: last[c] for c in daily.columns if c.startswith("src_")},
              "events_public_in_feature_window": [e["event_id"] for e in known],
              **classify(latest_vals),
              "note": "Conditions as of the NSE close on as_of_session; foreign series use observations dated before it."}

    ev_cols = [c for c in events.columns if not c.endswith("__status")] + [c for c in events.columns if c.endswith("__status")]
    body = {
        "library_version": "pattern_library_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "regime_rules": RULES,
        "targets": _targets(ys),
        "feature_meta": meta,
        "weekly": _table(w),
        "latest_conditions": latest,
        "event_responses": _table(events[ev_cols]),
        "provenance": {"sources": {s: _sha(s) for s in SOURCES}, "builder": "research/black_swan/pipeline/pattern_library.py"},
    }
    digest = hashlib.sha256(json.dumps({k: v for k, v in body.items() if k != "created_at_utc"}, sort_keys=True,
                                       default=str).encode()).hexdigest()[:12]
    body["library_version"] = f"pattern_library_v1+{digest}"
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(body, default=lambda o: float(o) if isinstance(o, np.floating) else str(o)), encoding="utf-8")
    return {"path": str(DEST), "version": body["library_version"], "weekly_rows": len(w), "events": len(events),
            "latest": latest["as_of_session"], "latest_regimes": (latest["volatility_regime"], latest["trend_regime"]),
            "bytes": DEST.stat().st_size}


if __name__ == "__main__":
    print(main())
