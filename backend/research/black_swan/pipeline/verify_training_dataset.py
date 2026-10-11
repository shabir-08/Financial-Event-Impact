"""Independent verification of output/model_training_final.csv (read-only; the CSV is never modified).

Recomputes every market feature and every target directly from data/raw/*.csv with code written
separately from build_training_table.py, re-derives event-flag timing from events_master.csv, and
checks window alignment, overlap, duplicates, missing values and split boundaries.

    python pipeline/verify_training_dataset.py   ->  output/model_selection/dataset_verification.json
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
RAW, OUT = HERE / "data" / "raw", HERE / "output"
DEST = OUT / "model_selection"
CSV = OUT / "model_training_final.csv"

MARKET_FEATURES = {"x_brent_5d_ret_pct": ("BRENT", "ret"), "x_sp500_5d_ret_pct": ("SP500", "ret"),
                   "x_usdinr_5d_ret_pct": ("USDINR", "ret"), "x_gold_5d_ret_pct": ("GOLD", "ret"),
                   "x_ust10y_5d_chg_bp": ("UST10Y", "bp")}
CLASS_FLAG = {"B": "x_event_geopolitical", "C": "x_event_macro_policy", "D": "x_event_financial_crisis",
              "E": "x_event_commodity_supply", "F": "x_event_other_shock"}


def raw(sym: str) -> pd.Series:
    df = pd.read_csv(RAW / f"{sym}.csv", parse_dates=["date"])
    return df.set_index(df["date"].dt.date)["value"].astype(float).sort_index()


def last_before(s: pd.Series, d: date) -> tuple[date | None, float]:
    """Last observation with calendar date strictly before d."""
    k = s.index.searchsorted(d) - 1  # index is sorted dates
    return (s.index[k], float(s.iloc[k])) if k >= 0 else (None, np.nan)


def pred_ts(d: date) -> datetime:  # NSE close 15:30 IST
    return datetime.combine(d, time(15, 30), ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)


def main() -> dict:
    DEST.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(CSV)
    out: dict = {"file": str(CSV.relative_to(HERE)), "sha256": hashlib.sha256(CSV.read_bytes()).hexdigest(),
                 "shape": list(df.shape)}
    feats = [c for c in df.columns if c.startswith("x_")]
    targs = [c for c in df.columns if c.startswith("y_")]
    out["features"], out["targets"] = feats, targs
    out["dtypes"] = {c: str(t) for c, t in df.dtypes.items()}
    out["split_counts"] = df.split.value_counts().to_dict()
    out["date_ranges"] = {s: {"week_start_min": g.week_start.min(), "week_end_max": g.week_end.max()}
                          for s, g in df.groupby("split")}
    out["regime_by_split"] = pd.crosstab(df.regime, df.split).to_dict()
    out["duplicates"] = {"full_rows": int(df.duplicated().sum()), "week_start": int(df.week_start.duplicated().sum()),
                         "feature_vectors": int(df[feats].duplicated().sum())}
    na = df[feats + targs].isna().sum()
    out["missing_values"] = {c: int(v) for c, v in na.items() if v}
    out["missing_rows"] = df.loc[df[targs + feats].isna().any(axis=1), ["week_start", "week_end", "split"]].to_dict("records")

    # ---- windows: NSE sessions from the NIFTY 50 calendar ------------------------------------------------
    nifty = raw("NIFTY50")
    sessions = list(nifty.index)
    pos = {d: i for i, d in enumerate(sessions)}
    ws = [date.fromisoformat(x) for x in df.week_start]
    we = [date.fromisoformat(x) for x in df.week_end]
    gaps = [pos[b] - pos[a] for a, b in zip(ws, we)]
    contiguous = [we[i] == ws[i + 1] for i in range(len(df) - 1)]
    out["windows"] = {"target_window_sessions": sorted(set(gaps)),
                      "consecutive_rows_contiguous_non_overlapping": all(contiguous),
                      "non_contiguous_pairs": [(str(we[i]), str(ws[i + 1])) for i, c in enumerate(contiguous) if not c]}
    tr, te = df[df.split == "train"], df[df.split == "test"]
    out["split_boundary"] = {"last_train_week_end": tr.week_end.max(), "first_test_week_start": te.week_start.min(),
                             "target_windows_overlap": tr.week_end.max() > te.week_start.min(),
                             "train_rule_holds": bool((pd.to_datetime(tr.week_end).dt.year <= 2022).all()
                                                      and (pd.to_datetime(te.week_end).dt.year >= 2023).all()),
                             "cv_groups_in_both_splits": sorted(set(tr.cv_group) & set(te.cv_group))}

    # ---- recompute market features (feature window = 5 sessions before week_start) ----------------------
    rec: dict[str, dict] = {}
    obs_after_pred = 0
    for col, (sym, kind) in MARKET_FEATURES.items():
        s = raw(sym)
        vals = []
        for d0 in ws:
            p = sessions[pos[d0] - 5]
            da, a = last_before(s, p)
            db, b = last_before(s, d0)
            obs_after_pred += int(db is not None and db >= d0)
            vals.append((b - a) * 100 if kind == "bp" else (b / a - 1) * 100)
        diff = np.abs(np.array(vals) - df[col].to_numpy())
        rec[col] = {"max_abs_diff": float(np.nanmax(diff)), "n_compared": int(np.isfinite(diff).sum())}
        # same-week (target-window) move of the same series, to show the feature is NOT that
        same = [(lambda a, b: (b - a) * 100 if kind == "bp" else (b / a - 1) * 100)(
            float(s[s.index <= d0].iloc[-1]), float(s[s.index <= d1].iloc[-1])) for d0, d1 in zip(ws, we)]
        prev_same = np.array([np.nan, *same[:-1]])
        m = np.isfinite(prev_same) & df[col].notna().to_numpy()
        rec[col]["corr_with_same_week_move"] = round(float(np.corrcoef(df[col].fillna(0), np.nan_to_num(same))[0, 1]), 4)
        rec[col]["corr_with_previous_row_target_window_move"] = round(float(np.corrcoef(df[col][m], prev_same[m])[0, 1]), 4)
    vix = raw("VIX")
    d_vix = np.abs(np.array([last_before(vix, d0)[1] for d0 in ws]) - df.x_vix_level_at_start.to_numpy())
    rec["x_vix_level_at_start"] = {"max_abs_diff": float(np.nanmax(d_vix))}
    r20 = np.array([(nifty[d0] / nifty[sessions[pos[d0] - 20]] - 1) * 100 for d0 in ws])
    rec["x_nifty_prev_20d_ret_pct"] = {"max_abs_diff": float(np.nanmax(np.abs(r20 - df.x_nifty_prev_20d_ret_pct)))}
    rets = nifty.pct_change()
    v20 = np.array([rets.loc[sessions[pos[d0] - 19]:d0].std() * np.sqrt(252) * 100 for d0 in ws])
    rec["x_nifty_prev_20d_vol_ann_pct"] = {"max_abs_diff": float(np.nanmax(np.abs(v20 - df.x_nifty_prev_20d_vol_ann_pct)))}
    out["feature_recompute"] = rec
    out["feature_observations_dated_on_or_after_week_start"] = obs_after_pred

    # ---- recompute targets --------------------------------------------------------------------------------
    trec = {}
    for col in targs:
        s = raw(col[2:].split("_5d")[0].upper())
        v = np.array([(s[b] / s[a] - 1) * 100 if a in s.index and b in s.index else np.nan for a, b in zip(ws, we)])
        diff = np.abs(v - df[col].to_numpy())
        trec[col] = {"max_abs_diff": float(np.nanmax(diff)), "recomputed_nan": int(np.isnan(v).sum()),
                     "csv_nan": int(df[col].isna().sum())}
    out["target_recompute"] = trec
    pharma = raw("NIFTYPHARMA")
    out["niftypharma_missing_detail"] = [
        {"week_start": str(a), "week_end": str(b), "start_in_raw": a in pharma.index, "end_in_raw": b in pharma.index,
         "raw_dates_between": [str(x) for x in pharma.index if a <= x <= b]}
        for a, b, y in zip(ws, we, df.y_niftypharma_5d_ret_pct) if pd.isna(y)]

    # ---- event flags from events_master.csv -----------------------------------------------------------------
    em = pd.read_csv(OUT / "events_master.csv")
    pub = []
    for e in em.itertuples():
        t = datetime.fromisoformat(str(e.info_time_utc).replace("Z", "+00:00"))
        if e.time_precision == "DATE_ONLY":
            t = datetime.combine(t.date(), time(23, 59, 59), timezone.utc)
        pub.append((e.event_id, t, e.black_swan_classification[0]))
    mism = []
    for i, d0 in enumerate(ws):
        lo, hi = pred_ts(sessions[pos[d0] - 5]), pred_ts(d0)
        known = [x for x in pub if lo < x[1] <= hi]
        exp = {"x_is_event": int(bool(known)), **{c: int(any(k[2] == l for k in known)) for l, c in CLASS_FLAG.items()}}
        got = {c: int(df.iloc[i][c]) for c in exp}
        if exp != got:
            mism.append({"week_start": str(d0), "expected": exp, "csv": got})
    out["event_flag_recompute"] = {"rows_mismatched": len(mism), "examples": mism[:5],
                                   "rows_flagged": int(df.x_is_event.sum())}

    # ---- crisis episodes behind regime labels -------------------------------------------------------------
    ev = em.set_index("event_id")
    bs = df[df.regime == "BLACK_SWAN"]
    out["black_swan_rows"] = [{"week_start": r.week_start, "split": r.split, "cv_group": r.cv_group, "event_ids": r.event_ids,
                               "episodes": sorted({str(ev.loc[e, "episode_id"]) for e in r.event_ids.split(";") if e in ev.index})}
                              for r in bs.itertuples()]
    ev_rows = df[df.regime != "NORMAL"]
    out["event_groups"] = {"n_cv_groups_with_events": int(ev_rows.cv_group.nunique()),
                           "black_swan_cv_groups": sorted(bs.cv_group.unique()),
                           "event_rows_by_split": ev_rows.split.value_counts().to_dict(),
                           "rows_per_event_group": ev_rows.cv_group.value_counts().describe().round(2).to_dict()}
    (DEST / "dataset_verification.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in ("shape", "split_counts", "duplicates", "missing_values", "windows", "split_boundary",
                                         "feature_observations_dated_on_or_after_week_start", "event_flag_recompute",
                                         "niftypharma_missing_detail", "black_swan_rows", "event_groups")}, indent=1, default=str))
    print(json.dumps(r["feature_recompute"], indent=1))
    print("max target diff:", max(v["max_abs_diff"] for v in r["target_recompute"].values()))
