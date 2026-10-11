"""Request-level pattern analysis shared by the market-patterns API and the simulator.

Two matching modes over the weekly pattern library:
* scenario   - match hypothetical shocks against historical same-week moves (s_ columns), optionally
               together with current/explicit pre-conditions; outcomes are the SAME 5 sessions
               (co-movement during comparable weeks, not a forecast).
* conditions - match market conditions at the start of a week (trailing x_ features); outcomes are
               the NEXT 5 sessions after comparable conditions.
User shock values are assumptions; they are only compared with historical observations, never stored
as observations.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.errors import InvalidRequestError
from app.services.patterns import analogues
from app.services.patterns.library import PatternLibrary
from app.services.patterns.regimes import RULES, classify, spells
from app.services.simulation.scenarios import ScenarioCatalog

DEFAULT_CONDITIONS = ["x_nifty_prev_20d_vol_ann_pct", "x_nifty_prev_60d_ret_pct", "x_nifty_drawdown_from_60d_peak_pct",
                      "x_vix_level_at_start", "x_brent_20d_ret_pct", "x_usdinr_20d_ret_pct"]
SCENARIO_CONDITIONS = ["x_nifty_prev_20d_vol_ann_pct", "x_nifty_prev_60d_ret_pct"]
SUPPORTED_HORIZONS = [5]
OUTCOME_SEMANTICS = {
    "scenario": "Returns over the SAME 5 NSE sessions in which the historical shock occurred (co-movement, not a forecast).",
    "conditions": "Returns over the NEXT 5 NSE sessions after weeks that started in comparable conditions.",
}


def _targets(lib: PatternLibrary, assets: list[str] | None) -> list[dict]:
    if not assets:
        return lib.targets
    found, unknown = [], []
    for a in assets:
        t = next((t for t in lib.targets if a in (t["symbol"], t["kb_asset_id"], t["column"])), None)
        (found.append(t) if t else unknown.append(a))
    if unknown:
        raise InvalidRequestError("Unsupported assets", details={"errors": [{"field": "assets", "error": "unsupported_asset",
                                                                              "values": unknown,
                                                                              "supported": [t["symbol"] for t in lib.targets]}]})
    return found


def _conditions(lib: PatternLibrary, spec: str | dict | None, features: list[str] | None, default: list[str]) -> dict[str, float]:
    if spec in (None, "none"):
        return {}
    allowed = set(lib.features_of("condition"))
    feats = features or default
    bad = [f for f in feats if f not in allowed]
    if bad:
        raise InvalidRequestError("Unknown condition features", details={"errors": [{"field": "condition_features",
                                                                                     "error": "unknown_feature", "values": bad}]})
    if spec == "latest":
        vals = lib.latest["values"]
        missing = [f for f in feats if vals.get(f) is None]
        if missing:
            raise InvalidRequestError("Latest conditions lack some features", details={"errors": [{"field": "conditions",
                                                                                                    "error": "missing_indicator", "values": missing}]})
        return {f: float(vals[f]) for f in feats}
    if isinstance(spec, dict):
        bad = [f for f in spec if f not in allowed]
        if bad:
            raise InvalidRequestError("Unknown condition features", details={"errors": [{"field": "conditions", "error": "unknown_feature", "values": bad}]})
        return {f: float(v) for f, v in spec.items()}
    raise InvalidRequestError("conditions must be 'latest', 'none' or an object of feature values")


def search(lib: PatternLibrary, catalog: ScenarioCatalog, mode: str, shocks: dict[str, float] | None,
           conditions: str | dict | None, condition_features: list[str] | None, assets: list[str] | None,
           k: int, horizon_days: int) -> dict[str, Any]:
    if horizon_days not in SUPPORTED_HORIZONS:
        raise InvalidRequestError("Unsupported horizon", details={"errors": [{"field": "horizon_days", "error": "unsupported_horizon",
                                                                              "value": horizon_days, "supported": SUPPORTED_HORIZONS}]})
    targets = _targets(lib, assets)
    cond_spec = conditions if mode == "scenario" else (conditions or "latest")
    used_latest = cond_spec == "latest"
    warnings: list[dict] = []
    query: dict[str, float] = {}
    assumptions = []
    if mode == "scenario":
        unmatched = []
        for name, value in (shocks or {}).items():
            p = catalog.parameters.get(name)
            if p is None:
                raise InvalidRequestError("Unknown parameter", details={"errors": [{"field": f"shocks.{name}", "error": "unsupported_parameter",
                                                                                    "supported": sorted(catalog.parameters)}]})
            lo, hi = p.input_range
            if not lo <= value <= hi:
                raise InvalidRequestError("Out of accepted range", details={"errors": [{"field": f"shocks.{name}", "error": "out_of_accepted_range",
                                                                                        "value": value, "accepted_range": [lo, hi]}]})
            assumptions.append({"parameter": name, "value": value, "unit": p.unit, "source": "user_assumption"})
            if p.model_feature and p.model_feature in lib.feature_meta:
                query[p.model_feature] = float(value)
            else:
                unmatched.append(name)
        if unmatched:
            warnings.append({"code": "parameter_has_no_historical_series", "parameters": unmatched,
                             "message": "No historical weekly series exists for these parameters; they are not used for matching."})
        if not query:
            raise InvalidRequestError("No matchable shock parameters", details={"errors": [{"field": "shocks", "error": "no_matchable_parameters",
                                                                                           "matchable": [n for n, p in catalog.parameters.items() if p.model_feature]}]})
        query.update(_conditions(lib, cond_spec, condition_features, SCENARIO_CONDITIONS))
    elif mode == "conditions":
        if shocks:
            raise InvalidRequestError("shocks are only valid in scenario mode")
        query = _conditions(lib, cond_spec, condition_features, DEFAULT_CONDITIONS)
        if not query:
            raise InvalidRequestError("conditions mode needs conditions ('latest' or explicit values)")
    else:
        raise InvalidRequestError(f"unknown mode '{mode}'")

    outcome_cols = [t["column"] for t in targets] + lib.features_of("outcome_descriptor")
    as_of = date.fromisoformat(lib.latest["as_of_session"])
    res = analogues.search(lib.weekly, query, list(query), outcome_cols, k, as_of)
    names = {e["event_id"]: e["event_name"] for e in lib.events}
    for a in res.analogues:
        a["events_in_window"] = [{"event_id": i, "event_name": names.get(i)} for i in a.pop("event_ids_in_window").split(";") if i]
        a["events_public_at_start"] = [{"event_id": i, "event_name": names.get(i)} for i in a["events_public_at_start"].split(";") if i]
        row = next(r for r in lib.weekly if r["week_start"] == a["week_start"])
        a["regime_at_start"] = {"volatility_regime": row["volatility_regime"], "trend_regime": row["trend_regime"]}
    query_regime = classify({**lib.latest["values"], **query}) if used_latest else None
    return {
        "mode": mode, "horizon_trading_days": horizon_days, "outcome_semantics": OUTCOME_SEMANTICS[mode],
        "assumptions": assumptions,
        "query": {f: {"value": v, "unit": lib.feature_meta[f]["unit"], "group": lib.feature_meta[f]["group"],
                      "source": ("user_assumption" if lib.feature_meta[f]["group"] == "shock"
                                 else "latest_observed" if used_latest else "user_supplied")}
                  for f, v in query.items()},
        "conditions_as_of": lib.latest["as_of_session"] if used_latest else None,
        "query_regime": query_regime,
        "matching": {"method": "standardised root-mean-square distance (pool mean/SD, past observations only)",
                     "features": list(query), "pool_size": res.pool_size, "excluded_missing_features": res.excluded_missing,
                     "k": k, "distance_bands": {"close": f"< {analogues.CLOSE}", "moderate": f"< {analogues.MODERATE}", "weak": f">= {analogues.MODERATE}"},
                     "feature_ranges": res.feature_ranges},
        "analogues": res.analogues,
        "n_analogues": len(res.analogues), "n_independent_clusters": res.n_clusters,
        "sample_statistics": res.statistics, "statistics_withheld_reason": res.statistics_withheld_reason,
        "statistics_note": "Historical sample statistics of the analogue weeks; not probabilities or forecasts.",
        "targets": targets,
        "warnings": warnings + res.warnings,
        "library_version": lib.version,
    }


def regime_summary(lib: PatternLibrary, asset: str | None) -> dict[str, Any]:
    target = _targets(lib, [asset] if asset else ["NIFTY50"])[0]
    out = {}
    for dim in ("volatility_regime", "trend_regime"):
        labels = [r[dim] for r in lib.weekly]
        groups = {}
        for lab in sorted({x for x in labels if x}):
            rows = [r for r in lib.weekly if r[dim] == lab]
            groups[lab] = {
                "n_weeks": len(rows), "n_spells": spells([x if x == lab else None for x in labels]),
                "next_5_session_return": analogues.describe([r[target["column"]] for r in rows]),
                "window_max_drawdown_pct": analogues.describe([r["o_nifty_window_max_drawdown_pct"] for r in rows]),
                "window_realized_vol_ann_pct": analogues.describe([r["o_nifty_window_realized_vol_ann_pct"] for r in rows]),
                "weeks_with_dataset_events": sum(1 for r in rows if r.get("event_ids")),
            }
        out[dim] = groups
    return {"asset": target, "rules": RULES, "latest": {"as_of_session": lib.latest["as_of_session"],
                                                        "volatility_regime": lib.latest["volatility_regime"],
                                                        "trend_regime": lib.latest["trend_regime"],
                                                        "indicators": {f: lib.latest["values"].get(f) for f in
                                                                       ("x_nifty_prev_20d_vol_ann_pct", "x_nifty_prev_60d_ret_pct",
                                                                        "x_nifty_max_drawdown_60d_pct", "x_nifty_rebound_from_60d_trough_pct",
                                                                        "x_nifty_drawdown_from_60d_peak_pct")}},
            "regimes": out,
            "note": ("Labels use only information at the start of each week. Statistics describe what followed in the "
                     "historical sample (n_spells = runs of consecutive weeks, closer to independent episodes than n_weeks); "
                     "they are not causal effects or probabilities."),
            "library_version": lib.version}
