"""Train and evaluate candidate models on output/model_training_final.csv (the CSV is read, never modified).

Protocol (fixed before any test-set evaluation):
* Features: the 14 x_* columns, in file order. Targets: the 18 y_* columns (5-NSE-session % returns).
* Hyperparameters are tuned ONLY on the train partition (week_end <= 2022) with expanding-window
  chronological folds: validate on 2019, 2020, 2021, 2022, each fitted on all earlier train rows.
* Model selection: lowest pooled validation MAE; a model must beat the zero-return baseline on
  validation to be selected, otherwise the zero baseline is selected.
* The test partition (week_end >= 2023) is evaluated ONCE per tuned candidate, after selection.
* Missing targets (2 NaN in y_niftypharma_5d_ret_pct, both in test) are never imputed: per-target
  models are fitted on that target's observed rows; metrics are computed on observed rows only.
* Preprocessing (median imputer + standard scaler for ridge) is fitted inside each training fold.
* Episode holdout: leave-one-event-group-out over every cv_group that contains an EVENT or
  BLACK_SWAN row, with the selected hyperparameters fixed and a purge of the 4 rows after the held-out
  block (their trailing features contain the held-out returns). This uses later periods for training
  and therefore measures cross-episode generalisation, not a realistic forecast.

    python pipeline/train_candidates.py
"""

from __future__ import annotations

import hashlib
import itertools
import json
import platform
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

HERE = Path(__file__).resolve().parents[1]
CSV = HERE / "output" / "model_training_final.csv"
DEST = HERE / "output" / "model_selection"
MODEL_DIR = HERE.parents[1] / "data" / "models"
SEED = 20261011
VAL_YEARS = [2019, 2020, 2021, 2022]
PURGE_ROWS = 4
N_BOOT = 2000

GRIDS = {
    "ridge": [{"alpha": a} for a in (0.1, 1, 10, 100, 1000, 10000)],
    "random_forest": [{"max_depth": d, "min_samples_leaf": l, "max_features": f}
                      for d, l, f in itertools.product((2, 3, 5, None), (5, 10, 20), ("sqrt", 0.5, 1.0))],
    "xgboost": [{"max_depth": d, "learning_rate": lr, "n_estimators": n, "min_child_weight": w}
                for d, lr, n, w in itertools.product((1, 2, 3), (0.03, 0.1), (100, 300), (5, 20))],
}
# Optional extra candidate (not in the default baseline run): k-nearest-neighbour analogue average,
# i.e. the historical-analogue method used as a predictor (standardised features, uniform weights).
EXTRA_GRIDS = {"knn_analogue": [{"n_neighbors": k} for k in (10, 20, 40, 80)]}


# ----------------------------------------------------------------------------------- model factories
def make(kind: str, p: dict):
    """Returns (estimator, shared). shared=True: one multi-output model for all targets."""
    if kind == "ridge":
        return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                         ("model", Ridge(alpha=p["alpha"]))]), False
    if kind == "random_forest":
        return Pipeline([("impute", SimpleImputer(strategy="median")),
                         ("model", RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=1, **p))]), True
    if kind == "random_forest_per_target":
        return Pipeline([("impute", SimpleImputer(strategy="median")),
                         ("model", RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=1, **p))]), False
    if kind == "knn_analogue":
        return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                         ("model", KNeighborsRegressor(n_neighbors=p["n_neighbors"]))]), True
    if kind == "xgboost":
        return XGBRegressor(subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, n_jobs=1,
                            tree_method="hist", **p), False
    raise ValueError(kind)


class FittedModel:
    """Uniform fit/predict over shared multi-output or per-target estimators, masking NaN targets."""

    def __init__(self, kind: str, params: dict, targets: list[str]):
        self.kind, self.params, self.targets = kind, params, targets
        self.est, self.shared = make(kind, params)
        self.models: dict[str, object] = {}

    def fit(self, X: pd.DataFrame, Y: pd.DataFrame) -> "FittedModel":
        if self.shared:
            rows = Y.notna().all(axis=1)  # multi-output trees need complete target rows
            self.models["__shared__"] = clone(self.est).fit(X[rows], Y[rows])
        else:
            for t in self.targets:
                m = Y[t].notna()
                self.models[t] = clone(self.est).fit(X[m], Y.loc[m, t])
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.shared:
            return np.asarray(self.models["__shared__"].predict(X))
        return np.column_stack([self.models[t].predict(X) for t in self.targets])


# ------------------------------------------------------------------------------------------ metrics
def metrics(y: np.ndarray, p: np.ndarray, zero: bool = False) -> dict:
    m = np.isfinite(y)
    y, p = y[m], p[m]
    e = p - y
    nz = y != 0
    return {"n": int(m.sum()), "mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e ** 2))),
            "directional_accuracy": None if zero else float(np.mean(np.sign(p[nz]) == np.sign(y[nz]))),
            "n_directional": int(nz.sum())}


def block_bootstrap_mae_diff(Y: np.ndarray, P: np.ndarray, P0: np.ndarray, rng) -> dict:
    """95% CI of pooled MAE(model) - MAE(zero), resampling whole weeks (assets in a week are correlated)."""
    ae, ae0 = np.abs(P - Y), np.abs(P0 - Y)
    m = np.isfinite(Y)
    n = len(Y)
    diffs = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, n)
        mm = m[idx]
        diffs.append(ae[idx][mm].mean() - ae0[idx][mm].mean())
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"mae_diff_vs_zero": float(ae[m].mean() - ae0[m].mean()), "ci95": [float(lo), float(hi)],
            "share_of_bootstrap_draws_better_than_zero": float(np.mean(np.array(diffs) < 0)), "n_weeks": n}


# --------------------------------------------------------------------------------------------- main
def main(frame: pd.DataFrame | None = None, feats: list[str] | None = None, dest: Path = DEST,
         grids: dict | None = None, label: str = "baseline", source_files: list[Path] | None = None) -> dict:
    """Default call reproduces the baseline run. Other experiments pass their own frame / features / dest."""
    warnings.filterwarnings("ignore", category=UserWarning)
    dest.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(CSV) if frame is None else frame
    feats = feats or [c for c in df.columns if c.startswith("x_")]
    grids = grids or GRIDS
    source_files = source_files or [CSV]
    targs = [c for c in df.columns if c.startswith("y_")]
    year = pd.to_datetime(df.week_end).dt.year
    train, test = df[df.split == "train"].reset_index(drop=True), df[df.split == "test"].reset_index(drop=True)
    ytr = year[df.split == "train"].reset_index(drop=True)
    assert len(targs) == 18 and len(train) == 308 and len(test) == 185
    assert frame is not None or len(feats) == 14

    # ---- 1. validation on train only -------------------------------------------------------------
    def cv_score(kind: str, p: dict) -> dict:
        Ys, Ps = [], []
        for vy in VAL_YEARS:
            fit_m, val_m = ytr < vy, ytr == vy
            fm = FittedModel(kind, p, targs).fit(train.loc[fit_m, feats], train.loc[fit_m, targs])
            Ys.append(train.loc[val_m, targs].to_numpy())
            Ps.append(fm.predict(train.loc[val_m, feats]))
        Y, P = np.vstack(Ys), np.vstack(Ps)
        return metrics(Y.ravel(), P.ravel())

    val_rows = []
    Yv = np.vstack([train.loc[ytr == vy, targs].to_numpy() for vy in VAL_YEARS])
    zero_val = metrics(Yv.ravel(), np.zeros(Yv.size), zero=True)
    mean_val_P = np.vstack([np.tile(train.loc[ytr < vy, targs].mean().to_numpy(), ((ytr == vy).sum(), 1)) for vy in VAL_YEARS])
    mean_val = metrics(Yv.ravel(), mean_val_P.ravel())
    val_rows += [{"model": "zero_baseline", "params": "{}", **zero_val}, {"model": "train_mean_baseline", "params": "{}", **mean_val}]
    best: dict[str, tuple[dict, dict]] = {}
    for kind, grid in grids.items():
        for p in grid:
            s = cv_score(kind, p)
            val_rows.append({"model": kind, "params": json.dumps(p), **s})
            if kind not in best or s["mae"] < best[kind][1]["mae"]:
                best[kind] = (p, s)
        print(f"validated {kind}: best {best[kind][0]} MAE {best[kind][1]['mae']:.4f} (zero {zero_val['mae']:.4f})")
    # shared vs per-target random forest, at the best shared-RF hyperparameters
    rf_pt = None
    if "random_forest" in best:
        rf_p = best["random_forest"][0]
        rf_pt = cv_score("random_forest_per_target", rf_p)
        val_rows.append({"model": "random_forest_per_target", "params": json.dumps(rf_p), **rf_pt})
    pd.DataFrame(val_rows).to_csv(dest / "validation_results.csv", index=False)

    candidates = {k: v for k, v in best.items()}
    beats = {k: v[1]["mae"] < zero_val["mae"] for k, v in candidates.items()}
    selected = min((k for k in candidates if beats[k]), key=lambda k: candidates[k][1]["mae"], default="zero_baseline")
    print("selected on validation:", selected)

    # ---- 2. single test evaluation of every tuned candidate ----------------------------------------
    Yt = test[targs].to_numpy()
    preds = {"zero_baseline": np.zeros_like(Yt), "train_mean_baseline": np.tile(train[targs].mean().to_numpy(), (len(test), 1))}
    fitted = {}
    for kind, (p, _) in candidates.items():
        fitted[kind] = FittedModel(kind, p, targs).fit(train[feats], train[targs])
        preds[kind] = fitted[kind].predict(test[feats])
    summary, per_asset, by_regime = {}, [], []
    for name, P in preds.items():
        z = name == "zero_baseline"
        summary[name] = {"pooled": metrics(Yt.ravel(), P.ravel(), zero=z)}
        if not z:
            summary[name]["vs_zero_bootstrap"] = block_bootstrap_mae_diff(Yt, P, preds["zero_baseline"], rng)
        for j, t in enumerate(targs):
            per_asset.append({"model": name, "target": t, **metrics(Yt[:, j], P[:, j], zero=z),
                              "zero_mae": metrics(Yt[:, j], np.zeros(len(Yt)), zero=True)["mae"]})
        for reg in ("NORMAL", "EVENT", "BLACK_SWAN"):
            m = (test.regime == reg).to_numpy()
            if m.any():
                by_regime.append({"model": name, "regime": reg, "n_weeks": int(m.sum()),
                                  **metrics(Yt[m].ravel(), P[m].ravel(), zero=z),
                                  "zero_mae": metrics(Yt[m].ravel(), np.zeros(Yt[m].size), zero=True)["mae"]})
            else:
                by_regime.append({"model": name, "regime": reg, "n_weeks": 0, "n": 0, "note": "no rows in test partition"})
    pa = pd.DataFrame(per_asset)
    pa["beats_zero"] = pa.mae < pa.zero_mae
    pa.to_csv(dest / "test_per_asset.csv", index=False)
    pd.DataFrame(by_regime).to_csv(dest / "test_by_regime.csv", index=False)
    tp = test[["week_start", "week_end"]].copy()
    for name, P in preds.items():
        for j, t in enumerate(targs):
            tp[f"{name}__{t}"] = P[:, j]
    tp.to_csv(dest / "test_predictions.csv", index=False)

    # ---- 3. leave-one-event-group-out (selected hyperparameters fixed) ------------------------------
    ev_groups = sorted(df.loc[df.regime != "NORMAL", "cv_group"].unique())
    ep_rows = []
    for kind in ["zero_baseline", *candidates]:
        for g in ev_groups:
            hold = (df.cv_group == g).to_numpy()
            idx = np.flatnonzero(hold)
            purge = np.zeros(len(df), bool)
            for i in idx:
                purge[i + 1:i + 1 + PURGE_ROWS] = True
            fit_m = ~hold & ~purge
            Yh = df.loc[hold, targs].to_numpy()
            P = (np.zeros_like(Yh) if kind == "zero_baseline" else
                 FittedModel(kind, candidates[kind][0], targs).fit(df.loc[fit_m, feats], df.loc[fit_m, targs]).predict(df.loc[hold, feats]))
            regimes = df.loc[hold, "regime"]
            ep_rows.append({"model": kind, "cv_group": g, "n_weeks": int(hold.sum()),
                            "n_black_swan_weeks": int((regimes == "BLACK_SWAN").sum()),
                            "split_of_rows": ";".join(sorted(df.loc[hold, "split"].unique())),
                            "abs_err_sum": float(np.nansum(np.abs(P - Yh))), **metrics(Yh.ravel(), P.ravel(), zero=kind == "zero_baseline")})
    ep = pd.DataFrame(ep_rows)
    ep.to_csv(dest / "episode_holdout.csv", index=False)
    ep_sum = {}
    for kind, g in ep.groupby("model"):
        bs = g[g.n_black_swan_weeks > 0]
        ep_sum[kind] = {"all_event_groups": {"n_groups": len(g), "n": int(g.n.sum()), "mae": float(g.abs_err_sum.sum() / g.n.sum())},
                        "black_swan_groups": {"groups": bs.cv_group.tolist(), "n_weeks": int(bs.n_weeks.sum()), "n": int(bs.n.sum()),
                                              "mae": float(bs.abs_err_sum.sum() / bs.n.sum())}}
    zg = ep[ep.model == "zero_baseline"].set_index("cv_group").mae
    for kind in candidates:
        mg = ep[ep.model == kind].set_index("cv_group").mae
        ep_sum[kind]["groups_beating_zero"] = f"{int((mg < zg).sum())}/{len(zg)}"

    out = {
        "label": label,
        "dataset": {"file": str(source_files[0].relative_to(HERE)), "sha256": hashlib.sha256(source_files[0].read_bytes()).hexdigest(),
                    "source_files": {str(f.relative_to(HERE)): hashlib.sha256(f.read_bytes()).hexdigest() for f in source_files},
                    "rows": len(df), "train_rows": len(train), "test_rows": len(test), "features": feats, "targets": targs},
        "protocol": __doc__.split("Protocol (fixed before any test-set evaluation):")[1].split("python pipeline")[0].strip(),
        "validation": {"zero_baseline": zero_val, "train_mean_baseline": mean_val,
                       **{k: {"best_params": v[0], **v[1], "beats_zero": beats[k]} for k, v in candidates.items()},
                       "random_forest_per_target_at_shared_best": rf_pt},
        "selected_model": selected,
        "test": summary,
        "episode_holdout": ep_sum,
        "environment": {"python": platform.python_version(), "sklearn": sklearn.__version__, "xgboost": xgboost.__version__,
                        "numpy": np.__version__, "pandas": pd.__version__, "seed": SEED},
    }
    (dest / "model_selection_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    # No pickle is written: the selected model is exported as a JSON artifact by export_forecast_v2.py.
    return out


if __name__ == "__main__":
    r = main()
    print(json.dumps({"validation": r["validation"], "selected": r["selected_model"],
                      "test": {k: v["pooled"] | ({"boot": v["vs_zero_bootstrap"]} if "vs_zero_bootstrap" in v else {})
                               for k, v in r["test"].items()},
                      "episode_holdout": r["episode_holdout"]}, indent=1))
