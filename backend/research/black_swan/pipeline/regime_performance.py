"""Test-period (2023-2026) error by market regime known at the start of each week (not ex-post labels).

Reads the saved test predictions of the v2 experiments and the regime labels of the pattern library;
reports MAE per regime with the number of weeks and of regime spells, and a week-block bootstrap 95% CI
of the MAE difference vs the zero baseline. Descriptive; no model is refitted.

    python pipeline/regime_performance.py  ->  output/model_selection_v2/regime_performance.csv
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
DEST = ROOT / "output" / "model_selection_v2"
RUNS = {"forecast_v2": "ridge", "scenario_s5": "ridge", "scenario_s5_cond": "ridge", "forecast_v1_knn": "knn_analogue"}
N_BOOT, SEED = 2000, 20261011


def main() -> pd.DataFrame:
    lib = json.loads((REPO / "data" / "patterns" / "pattern_library_v1.json").read_text(encoding="utf-8"))
    w = pd.DataFrame(lib["weekly"]["rows"], columns=lib["weekly"]["columns"])
    targs = [c for c in w.columns if c.startswith("y_")]
    rng = np.random.default_rng(SEED)
    rows = []
    for run, model in RUNS.items():
        tp = pd.read_csv(DEST / run / "test_predictions.csv").merge(
            w[["week_start", "volatility_regime", "trend_regime", *targs]], on="week_start", validate="one_to_one")
        for dim in ("volatility_regime", "trend_regime"):
            for lab, g in tp.groupby(dim):
                Y = g[targs].to_numpy()
                P = g[[f"{model}__{t}" for t in targs]].to_numpy()
                m = np.isfinite(Y)
                ae, ae0 = np.abs(P - Y), np.abs(Y)
                diffs = []
                for _ in range(N_BOOT):
                    i = rng.integers(0, len(Y), len(Y))
                    mm = m[i]
                    diffs.append(ae[i][mm].mean() - ae0[i][mm].mean())
                spells = int((tp[dim].ne(tp[dim].shift())).loc[g.index].sum())
                rows.append({"experiment": run, "model": model, "dimension": dim, "regime": lab, "n_weeks": len(g),
                             "n_spells": spells, "n_values": int(m.sum()), "mae_model": round(float(ae[m].mean()), 4),
                             "mae_zero": round(float(ae0[m].mean()), 4),
                             "diff_ci95": [round(float(x), 4) for x in np.percentile(diffs, [2.5, 97.5])]})
    df = pd.DataFrame(rows)
    df.to_csv(DEST / "regime_performance.csv", index=False)
    return df


if __name__ == "__main__":
    print(main().to_string())
