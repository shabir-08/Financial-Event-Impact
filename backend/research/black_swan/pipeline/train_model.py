"""Train and validate the shared multi-output model on output/model_training_final.csv.

Leakage controls
  * feature list comes from model_training_final_schema.csv (role == "feature"); ids, dates, split,
    cv_group, regime and event-id metadata can never enter X
  * standardisation means/SDs are fitted on TRAINING rows only (re-fitted inside every fold)
  * ridge lambda is chosen by an inner chronological validation INSIDE the training period
  * targets are never imputed: each output column is fitted on the rows where it is present
    (masked multi-output ridge - one shared feature map, per-asset coefficients)
  * weekly blocks are non-overlapping and the split is by target-end year, so no target window
    crosses the train/test boundary (verified below; no purge gap needed - reported)

Evaluations
  A  chronological: train <= 2022 (by target end), test 2023+, overall and by regime
  B  event-episode holdout: each event validation group held out in turn; training excludes that
     group and +/-1 adjacent week (purge). Non-chronological diagnostic only.
  C  baselines: zero return; training-mean return
Outputs: output/model_validation_report.json, output/model_feature_ranges.json, output/model_coefficients.csv
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
LAMBDAS = [0.1, 1.0, 3.0, 10.0, 30.0, 100.0]


def load():
    df = pd.read_csv(OUT / "model_training_final.csv")
    schema = pd.read_csv(OUT / "model_training_final_schema.csv")
    X_cols = schema[schema.role == "feature"].column.tolist()
    Y_cols = schema[schema.role == "target"].column.tolist()
    assert not set(X_cols) & set(Y_cols)
    assert all(c.startswith("x_") for c in X_cols) and all(c.startswith("y_") for c in Y_cols)
    return df, X_cols, Y_cols


class MaskedRidge:
    """Multi-output ridge; standardisation fitted on the rows passed to fit(); NaN targets masked."""

    def fit(self, X: np.ndarray, Y: np.ndarray, lam: float):
        self.mu = np.nanmean(X, axis=0)
        self.sd = np.nanstd(X, axis=0)
        self.sd[self.sd == 0] = 1.0
        Z = np.column_stack([np.ones(len(X)), (X - self.mu) / self.sd])
        P = np.eye(Z.shape[1]) * lam
        P[0, 0] = 0
        self.W = np.zeros((Z.shape[1], Y.shape[1]))
        self.n_used = []
        for k in range(Y.shape[1]):
            ok = ~np.isnan(Y[:, k]) & ~np.isnan(Z).any(axis=1)
            self.W[:, k] = np.linalg.solve(Z[ok].T @ Z[ok] + P, Z[ok].T @ Y[ok, k])
            self.n_used.append(int(ok.sum()))
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.column_stack([np.ones(len(X)), (X - self.mu) / self.sd]) @ self.W


def score(Y: np.ndarray, P: np.ndarray) -> dict:
    ok = ~np.isnan(Y)
    e = (P - Y)[ok]
    yv, pv = Y[ok], P[ok]
    nz = yv != 0
    return {"n_values": int(ok.sum()), "MAE": round(float(np.mean(np.abs(e))), 4),
            "RMSE": round(float(np.sqrt(np.mean(e ** 2))), 4),
            "directional_accuracy": round(float(np.mean(np.sign(yv[nz]) == np.sign(pv[nz]))), 4)}


def choose_lambda(df_train: pd.DataFrame, X_cols, Y_cols) -> tuple[float, dict]:
    """Inner chronological validation: fit on target-end years <= 2020, validate on 2021-2022."""
    yr = pd.to_datetime(df_train.week_end).dt.year
    inner_tr, inner_va = df_train[yr <= 2020], df_train[yr >= 2021]
    res = {}
    for lam in LAMBDAS:
        m = MaskedRidge().fit(inner_tr[X_cols].values, inner_tr[Y_cols].values, lam)
        res[lam] = score(inner_va[Y_cols].values, m.predict(inner_va[X_cols].values))["MAE"]
    best = min(res, key=res.get)
    return best, {str(k): v for k, v in res.items()}


def main() -> None:
    df, X_cols, Y_cols = load()
    tr, te = df[df.split == "train"], df[df.split == "test"]
    # Boundary check: last training target window must end no later than the first test prediction time.
    boundary_ok = pd.to_datetime(tr.week_end).max() <= pd.to_datetime(te.week_start).min()
    lam, lam_scores = choose_lambda(tr, X_cols, Y_cols)
    model = MaskedRidge().fit(tr[X_cols].values, tr[Y_cols].values, lam)
    Yte, Pte = te[Y_cols].values, model.predict(te[X_cols].values)
    train_mean = np.nanmean(tr[Y_cols].values, axis=0)

    def block(mask) -> dict:
        Yb, Pb = Yte[mask], Pte[mask]
        if mask.sum() == 0:
            return {"n_rows": 0, "note": "no rows in this regime in the test period"}
        return {"n_rows": int(mask.sum()), "model": score(Yb, Pb), "baseline_zero": score(Yb, np.zeros_like(Pb)),
                "baseline_train_mean": score(Yb, np.tile(train_mean, (len(Yb), 1)))}

    reg = te.regime.values
    per_target = {}
    for k, c in enumerate(Y_cols):
        per_target[c] = {"model": score(Yte[:, [k]], Pte[:, [k]]), "baseline_zero": score(Yte[:, [k]], np.zeros((len(te), 1))),
                         "n_train_rows_used": model.n_used[k]}

    # B: event-episode holdout (diagnostic)
    df = df.reset_index(drop=True)
    ev_groups = sorted(g for g in df.cv_group.unique() if not str(g).startswith("NORMAL_"))
    eg = {"model": [], "zero": []}
    Y_all = []
    P_all = []
    for g in ev_groups:
        idx = df.index[df.cv_group == g]
        purge = set(idx) | {i - 1 for i in idx} | {i + 1 for i in idx}
        trn = df.drop(index=[i for i in purge if i in df.index])
        m = MaskedRidge().fit(trn[X_cols].values, trn[Y_cols].values, lam)
        Y_all.append(df.loc[idx, Y_cols].values)
        P_all.append(m.predict(df.loc[idx, X_cols].values))
    Yg, Pg = np.vstack(Y_all), np.vstack(P_all)
    bs_groups = sorted({g for g, r in zip(df.cv_group, df.regime) if r == "BLACK_SWAN"})

    report = {
        "dataset": {"rows": int(len(df)), "train_rows": int(len(tr)), "test_rows": int(len(te)),
                    "n_features": len(X_cols), "features": X_cols, "n_targets": len(Y_cols),
                    "train_period": f"{tr.week_start.min()}..{tr.week_end.max()}",
                    "test_period": f"{te.week_start.min()}..{te.week_end.max()}",
                    "train_test_boundary_ok_no_overlapping_target_windows": bool(boundary_ok),
                    "purge_gap_applied": "none needed: weekly target windows are non-overlapping and the split is on target-end year",
                    "test_regime_counts": te.regime.value_counts().to_dict(),
                    "train_regime_counts": tr.regime.value_counts().to_dict()},
        "lambda_selection_inner_chronological_MAE": lam_scores, "lambda": lam,
        "A_chronological_test": {"all": block(np.ones(len(te), bool)), "NORMAL": block(reg == "NORMAL"),
                                 "EVENT": block(reg == "EVENT"), "BLACK_SWAN": block(reg == "BLACK_SWAN")},
        "A_per_target": per_target,
        "B_event_episode_holdout": {
            "n_event_groups": len(ev_groups), "n_rows": int(len(Yg)),
            "model": score(Yg, Pg), "baseline_zero": score(Yg, np.zeros_like(Pg)),
            "black_swan_groups": bs_groups,
            "note": "Each event group held out with +/-1 week purge; training uses ALL other weeks including later ones, "
                    "so this is a non-chronological diagnostic, not a deployment estimate. Black Swan behaviour rests on "
                    f"{len(bs_groups)} independent group(s) - reliable Black Swan performance cannot be established."},
    }
    (OUT / "model_validation_report.json").write_text(json.dumps(report, indent=2, default=str))

    # Feature ranges from TRAINING rows (for the simulator's out-of-range guard)
    ranges = {c: {"min": float(np.nanmin(tr[c])), "p01": float(np.nanpercentile(tr[c], 1)),
                  "p99": float(np.nanpercentile(tr[c], 99)), "max": float(np.nanmax(tr[c]))} for c in X_cols}
    (OUT / "model_feature_ranges.json").write_text(json.dumps({"source": "training rows only", "features": ranges}, indent=2))
    coef = pd.DataFrame(model.W, index=["intercept", *X_cols], columns=Y_cols)
    coef.to_csv(OUT / "model_coefficients.csv")
    a = report["A_chronological_test"]["all"]
    print("lambda", lam, "| test all: model", a["model"], "| zero", a["baseline_zero"], "| mean", a["baseline_train_mean"])
    for rg in ("NORMAL", "EVENT", "BLACK_SWAN"):
        b = report["A_chronological_test"][rg]
        print(rg, b.get("n_rows"), b.get("model", b.get("note")), b.get("baseline_zero", ""))
    print("episode holdout:", report["B_event_episode_holdout"]["model"], "zero", report["B_event_episode_holdout"]["baseline_zero"])


if __name__ == "__main__":
    main()
