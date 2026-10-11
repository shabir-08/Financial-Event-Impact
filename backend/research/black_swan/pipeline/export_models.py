"""Export versioned, backend-loadable model artefacts (JSON) for the Black Swan simulator.

Two models, both masked multi-output ridge (pipeline/train_model.py::MaskedRidge):

1. forecast_trailing_v1  - the audited forecasting model on model_training_final.csv (trailing features).
   Its inputs describe the PAST 5 sessions, so it cannot take hypothetical future shocks. Exported for
   provenance and so the backend can explain why it is not used for scenario sliders.

2. scenario_conditional_v1 - conditional association model: 5-session asset returns regressed on
   shocks realised over the SAME 5 sessions (model_training_final_scenario_inputs.csv). It answers
   "historically, when Brent / USD-INR / S&P 500 / gold / US10Y moved like this within a week, how did the
   Indian targets move in that week?" It is NOT a forecast and NOT causal.
   * lambda chosen by inner chronological validation (fit <=2020, validate 2021-22)
   * walk-forward evaluation: for each test year 2019..2026 fit on earlier target-end years only
   * prediction intervals = empirical quantiles of those out-of-sample residuals, per target
   * deployed coefficients are refit on all rows (2016-10..2026-10)

Writes to <repo>/data/models/*.json (the backend loads from there).
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
from assets import BY_SYMBOL  # noqa: E402
from train_model import LAMBDAS, MaskedRidge, score  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
REPO = ROOT.parents[1]
MODELS = REPO / "data" / "models"

# research target symbol -> backend knowledge-base asset id (None = not in the knowledge graph)
KB_ASSET = {"NIFTY50": "asset:nifty50", "ONGC": "asset:ongc_ns", "IOC": "asset:ioc_ns", "BPCL": "asset:bpcl_ns",
            "RELIANCE": "asset:reliance_ns", "INDIGO": "asset:indigo_ns", "ASIANPAINT": "asset:asianpaint_ns",
            "HDFCBANK": "asset:hdfcbank_ns"}
SCENARIO_FEATURES = [
    ("s_brent_5d_ret_pct_in_target_window", "oil_price_change_pct", "%", "Brent spot (FRED DCOILBRENTEU) change over the same 5 NSE sessions"),
    ("s_sp500_5d_ret_pct_in_target_window", "sp500_change_pct", "%", "S&P 500 change over the same 5 NSE sessions"),
    ("s_usdinr_5d_ret_pct_in_target_window", "usdinr_change_pct", "%", "USD/INR (FRED DEXINUS) change; + = rupee weaker"),
    ("s_gold_5d_ret_pct_in_target_window", "gold_change_pct", "%", "Gold front-month future change"),
    ("s_ust10y_5d_chg_bp_in_target_window", "us10y_change_bp", "bp", "US 10Y Treasury yield change"),
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _targets(Y_cols: list[str]) -> list[dict]:
    out = []
    for c in Y_cols:
        sym = c[2:].replace("_5d_ret_pct", "").upper()
        a = BY_SYMBOL[sym]
        out.append({"column": c, "symbol": sym, "name": a.name, "asset_class": a.asset_class, "currency": a.currency,
                    "kb_asset_id": KB_ASSET.get(sym), "unit": "% simple return over 5 NSE trading sessions"})
    return out


def _choose_lambda(df: pd.DataFrame, X: list[str], Y: list[str]) -> tuple[float, dict]:
    yr = pd.to_datetime(df.week_end).dt.year
    tr, va = df[yr <= 2020], df[(yr >= 2021) & (yr <= 2022)]
    res = {}
    for lam in LAMBDAS:
        m = MaskedRidge().fit(tr[X].values, tr[Y].values, lam)
        res[lam] = score(va[Y].values, m.predict(va[X].values))["MAE"]
    best = min(res, key=res.get)
    return best, {str(k): v for k, v in res.items()}


def _artifact(model: MaskedRidge, X: list[str], fit_df: pd.DataFrame) -> dict:
    return {"feature_order": X,
            "standardization": {"mean": [float(v) for v in model.mu], "sd": [float(v) for v in model.sd],
                                "fitted_on": "the model's own fitting rows only"},
            "coefficients": {"intercept": [float(v) for v in model.W[0]],
                             "weights_per_standardized_feature": [[float(v) for v in row] for row in model.W[1:]]},
            "feature_domain": {c: {"min": float(fit_df[c].min()), "p01": float(fit_df[c].quantile(0.01)),
                                   "p99": float(fit_df[c].quantile(0.99)), "max": float(fit_df[c].max())} for c in X},
            "n_rows_used_per_target": model.n_used}


def scenario_model(final: pd.DataFrame, scen: pd.DataFrame, Y: list[str]) -> dict:
    df = final[["week_start", "week_end", *Y]].merge(scen, on=["week_start", "week_end"], validate="one_to_one")
    X = [f[0] for f in SCENARIO_FEATURES]
    lam, lam_scores = _choose_lambda(df, X, Y)
    yr = pd.to_datetime(df.week_end).dt.year
    oos_y, oos_p, oos_years = [], [], []
    for y in range(2019, int(yr.max()) + 1):
        tr, te = df[yr < y], df[yr == y]
        if te.empty:
            continue
        m = MaskedRidge().fit(tr[X].values, tr[Y].values, lam)
        oos_y.append(te[Y].values); oos_p.append(m.predict(te[X].values)); oos_years += [y] * len(te)
    Yo, Po = np.vstack(oos_y), np.vstack(oos_p)
    resid = Yo - Po
    per_target, intervals = {}, {}
    for k, c in enumerate(Y):
        ok = ~np.isnan(Yo[:, k])
        r, yv = resid[ok, k], Yo[ok, k]
        mae_m, mae_z = float(np.mean(np.abs(r))), float(np.mean(np.abs(yv)))
        r2 = 1 - float(np.sum(r ** 2)) / float(np.sum((yv - yv.mean()) ** 2))
        per_target[c] = {"n_oos": int(ok.sum()), "mae_model": round(mae_m, 4), "mae_zero_baseline": round(mae_z, 4),
                         "oos_r2": round(r2, 4), "beats_zero_baseline": bool(mae_m < mae_z)}
        intervals[c] = {q: round(float(np.quantile(r, qq)), 4) for q, qq in
                        (("q05", .05), ("q10", .10), ("q50", .5), ("q90", .9), ("q95", .95))}
    final_model = MaskedRidge().fit(df[X].values, df[Y].values, lam)
    test_mask = np.array(oos_years) >= 2023
    return {
        "model_id": "scenario_conditional_v1", "kind": "scenario_conditional",
        "supports_hypothetical_shocks": True,
        "interpretation": ("Conditional association: estimated 5-session return of each Indian target GIVEN the specified "
                           "shocks occur over the same 5 sessions, from 2016-2026 weekly history. Not a forecast; not causal."),
        "horizon_trading_days": 5,
        "features": [{"column": c, "scenario_parameter": p, "unit": u, "definition": d} for c, p, u, d in SCENARIO_FEATURES],
        "targets": _targets(Y), "lambda": lam, "lambda_selection_inner_chronological_MAE": lam_scores,
        **_artifact(final_model, X, df),
        "training": {"rows": int(len(df)), "period": f"{df.week_start.min()}..{df.week_end.max()}",
                     "deployed_fit": "all rows (refit after evaluation)"},
        "evaluation": {"method": "walk-forward by target-end year 2019..2026 (fit on earlier years only)",
                       "all_oos": score(Yo, Po), "all_oos_zero_baseline": score(Yo, np.zeros_like(Po)),
                       "test_2023_onward": score(Yo[test_mask], Po[test_mask]),
                       "test_2023_onward_zero_baseline": score(Yo[test_mask], np.zeros_like(Po[test_mask])),
                       "per_target": per_target},
        "prediction_intervals": {"method": "empirical quantiles of walk-forward out-of-sample residuals (2019-2026), added to the point estimate",
                                 "residual_quantiles": intervals},
        "limitations": [
            "Assumes the shocks happen within the same 5 trading sessions as the return; unspecified shocks are held at 0 change (an explicit scenario assumption).",
            "Linear model: responses scale linearly; behaviour outside the training range is extrapolation and is refused by the backend.",
            "Fitted mostly on ordinary weeks (411 of 493 are NORMAL); only 2 independent Black Swan episodes exist in the data.",
            "Intervals come from historical residuals and assume similar error behaviour; they are not guarantees.",
            "No inflation input exists; inflation sliders cannot affect this model."],
    }


def forecast_model(final: pd.DataFrame, X: list[str], Y: list[str]) -> dict:
    rep = json.loads((OUT / "model_validation_report.json").read_text())
    tr = final[final.split == "train"]
    lam = rep["lambda"]
    m = MaskedRidge().fit(tr[X].values, tr[Y].values, lam)
    a = rep["A_chronological_test"]["all"]
    return {
        "model_id": "forecast_trailing_v1", "kind": "forecast_trailing", "supports_hypothetical_shocks": False,
        "interpretation": ("Forecast of the next 5 NSE sessions from information known at the prediction time (trailing "
                           "5-session shocks, VIX, NIFTY momentum/volatility, events already public)."),
        "unsupported_reason": ("Its shock inputs describe the PAST 5 sessions. A slider describing a hypothetical future "
                               "move cannot be fed into them without changing their meaning; on the 2023-2026 test it does "
                               "not beat the zero or training-mean baselines."),
        "horizon_trading_days": 5, "features": [{"column": c} for c in X], "targets": _targets(Y), "lambda": lam,
        **_artifact(m, X, tr),
        "training": {"rows": int(len(tr)), "period": f"{tr.week_start.min()}..{tr.week_end.max()}"},
        "evaluation": {"test_2023_onward": a["model"], "zero_baseline": a["baseline_zero"],
                       "train_mean_baseline": a["baseline_train_mean"]},
    }


def main() -> None:
    MODELS.mkdir(parents=True, exist_ok=True)
    final = pd.read_csv(OUT / "model_training_final.csv")
    scen = pd.read_csv(OUT / "model_training_final_scenario_inputs.csv")[
        ["week_start", "week_end", *[f[0] for f in SCENARIO_FEATURES]]]
    schema = pd.read_csv(OUT / "model_training_final_schema.csv")
    X = schema[schema.role == "feature"].column.tolist()
    Y = schema[schema.role == "target"].column.tolist()
    prov = {"exported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_dataset": "research/black_swan/output/model_training_final.csv",
            "source_dataset_sha256": _sha(OUT / "model_training_final.csv"),
            "scenario_inputs_sha256": _sha(OUT / "model_training_final_scenario_inputs.csv"),
            "exporter": "research/black_swan/pipeline/export_models.py", "estimator": "masked multi-output ridge (numpy)"}
    for art in (scenario_model(final, scen, Y), forecast_model(final, X, Y)):
        art["provenance"] = prov
        art["model_version"] = f"{art['model_id']}+{prov['source_dataset_sha256'][:12]}"
        path = MODELS / f"{art['model_id']}.json"
        path.write_text(json.dumps(art, indent=1))
        ev = art["evaluation"]
        print(art["model_id"], "lambda", art["lambda"], "->", path.relative_to(REPO))
        print("   ", {k: v for k, v in ev.items() if k != "per_target"})
        if "per_target" in ev:
            print("    beats zero:", [k for k, v in ev["per_target"].items() if v["beats_zero_baseline"]])


if __name__ == "__main__":
    main()
