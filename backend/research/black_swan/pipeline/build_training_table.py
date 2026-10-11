"""Build the ready-to-train tables: the price timeline with every day/week labelled NORMAL / EVENT / BLACK_SWAN.

How a day gets its label:
  Each event's reaction period = its first post-event NSE session up to the 5th post-event session
  (dates taken from event_market_returns.csv, NIFTY50 rows). Days inside a reaction period get the
  event's id and class; class A events are labelled BLACK_SWAN, all other classes EVENT. Every other
  day is NORMAL. If two events overlap, both ids are listed and the most severe label wins.

Outputs:
  output/daily_training_table.csv   one row per NSE trading day (research period)
  output/weekly_training_table.csv  one row per non-overlapping 5-session block (recommended for training)
"""

from __future__ import annotations

import sys
from datetime import date, datetime, time as dtime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from compute import DATA_END, RESEARCH_START, load_series  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
REACTION_SESSIONS = 5
TARGETS = ["NIFTY50", "NIFTYBANK", "NIFTYIT", "NIFTYPHARMA", "ONGC", "IOC", "BPCL", "RELIANCE", "INDIGO",
           "ASIANPAINT", "SBIN", "ICICIBANK", "HDFCBANK", "TCS", "INFY", "LT", "HINDALCO", "SUNPHARMA"]
RANK = {"NORMAL": 0, "EVENT": 1, "BLACK_SWAN": 2}


def event_days(nse_days: list[date]) -> dict[date, list[dict]]:
    em = pd.read_csv(OUT / "events_master.csv")
    ret = pd.read_csv(OUT / "event_market_returns.csv")
    n = ret[(ret.asset_symbol == "NIFTY50") & (ret.window_trading_days == 1)].set_index("event_id")
    out: dict[date, list[dict]] = {}
    for e in em.itertuples():
        start = n.loc[e.event_id, "window_start_date"]
        if not isinstance(start, str):
            continue
        start = date.fromisoformat(start)
        if start not in nse_days:
            continue
        i = nse_days.index(start)
        label = "BLACK_SWAN" if e.black_swan_classification.startswith("A") else "EVENT"
        for k, d in enumerate(nse_days[i:i + REACTION_SESSIONS], start=1):
            out.setdefault(d, []).append({"event_id": e.event_id, "label": label, "cls": e.black_swan_classification[0],
                                          "category": e.event_category, "country": e.country, "day": k,
                                          "vg": e.validation_group, "episode": e.episode_id})
    return out


def _label_cols(evs: list[dict] | None) -> dict:
    if not evs:
        return {"regime": "NORMAL", "is_event": 0, "is_black_swan": 0, "event_ids": "", "event_classes": "",
                "event_categories": "", "event_countries": "", "days_since_event_start": None,
                "event_validation_group": "", "event_episode_ids": ""}
    top = max(evs, key=lambda x: RANK[x["label"]])
    uniq = lambda key: ";".join(dict.fromkeys(x[key] for x in evs))  # noqa: E731
    return {"regime": top["label"], "is_event": 1, "is_black_swan": int(top["label"] == "BLACK_SWAN"),
            "event_ids": uniq("event_id"), "event_classes": uniq("cls"), "event_categories": uniq("category"),
            "event_countries": uniq("country"), "days_since_event_start": min(x["day"] for x in evs),
            "event_validation_group": uniq("vg"), "event_episode_ids": uniq("episode")}


def _asof(s: pd.Series, d: date, strictly_before: bool):
    sub = s[s.index < d] if strictly_before else s[s.index <= d]
    return float(sub.iloc[-1]) if len(sub) else np.nan


def daily_table(series) -> pd.DataFrame:
    nifty = series["NIFTY50"]
    days = [d for d in nifty.index if RESEARCH_START <= d <= DATA_END]
    all_days = list(nifty.index)
    evd = event_days(all_days)
    rows = []
    for d in days:
        prev = all_days[all_days.index(d) - 1]
        r = {"date": d.isoformat(), "year": d.year}
        # Inputs known BEFORE the Indian open on day d (foreign data dated before d).
        for sym, col in (("SP500", "sp500"), ("BRENT", "brent"), ("USDINR", "usdinr"), ("GOLD", "gold")):
            s = series[sym]
            a, b = _asof(s, prev, True), _asof(s, d, True)
            r[f"x_{col}_prev_ret_pct"] = round((b / a - 1) * 100, 4) if a and b and a > 0 and b > 0 else None
        u = series["UST10Y"]
        r["x_ust10y_prev_chg_bp"] = round((_asof(u, d, True) - _asof(u, prev, True)) * 100, 2)
        r["x_vix_prev_level"] = _asof(series["VIX"], d, True)
        prev2 = all_days[all_days.index(prev) - 1]
        r["x_nifty_prev_ret_pct"] = round((nifty[prev] / nifty[prev2] - 1) * 100, 4)
        # Targets: same-day close-to-close returns of Indian assets.
        for t in TARGETS:
            s = series[t]
            r[f"y_{t.lower()}_ret_pct"] = round((s[d] / s[prev] - 1) * 100, 4) if d in s.index and prev in s.index else None
        r.update(_label_cols(evd.get(d)))
        rows.append(r)
    return pd.DataFrame(rows)



# =====================================================================================================
# Weekly forecasting table (model_training_final.csv) - leakage-audited version (audit 2026-10-11)
# =====================================================================================================
# Timeline of one row (all NSE sessions):
#
#   p = d0 - 5 sessions        d0 = week_start                 d1 = week_end = d0 + 5 sessions
#   |---- feature window ----->|--------- target window -------->|
#                              ^ prediction timestamp = NSE close (15:30 IST) on d0
#
# * Targets  y_<asset>_5d_ret_pct = 100 * (close[d1] / close[d0] - 1)   (unchanged definition)
# * Shocks   x_<series>_5d_*     = change between the last observation DATED BEFORE p and the last
#   observation DATED BEFORE d0. Foreign closes dated d0 (US close, Brent London assessment, NY-noon FX)
#   occur after 15:30 IST on d0, so they are excluded; observations dated d0-1 occurred before the
#   prediction timestamp.
# * Event flags use only events whose information time is <= the prediction timestamp and > the
#   prediction timestamp of p (i.e. the event became public during the feature window).
#   DATE_ONLY events are treated as public only at the END of their date (23:59:59 UTC).
# * The previous (pre-audit) shock values measured over the TARGET window are kept, renamed s_..., in
#   model_training_final_scenario_inputs.csv for what-if analysis only - never as forecasting inputs.
NSE_TZ = ZoneInfo("Asia/Kolkata")
NSE_CLOSE = dtime(15, 30)
SHOCKS = [("BRENT", "brent", "ret"), ("SP500", "sp500", "ret"), ("USDINR", "usdinr", "ret"), ("GOLD", "gold", "ret"),
          ("UST10Y", "ust10y", "chg_bp")]
CLASS_FLAGS = (("B", "geopolitical"), ("C", "macro_policy"), ("D", "financial_crisis"),
               ("E", "commodity_supply"), ("F", "other_shock"))
TEST_FROM_YEAR = 2023


def prediction_ts(d: date) -> datetime:
    return datetime.combine(d, NSE_CLOSE, NSE_TZ).astimezone(timezone.utc)


def _asof_obs(s: pd.Series, d: date):
    """Last observation dated strictly before d (calendar date)."""
    sub = s[s.index < d]
    return (sub.index[-1], float(sub.iloc[-1])) if len(sub) else (None, np.nan)


def public_events() -> list[dict]:
    em = pd.read_csv(OUT / "events_master.csv")
    out = []
    for e in em.itertuples():
        t = datetime.fromisoformat(e.info_time_utc.replace("Z", "+00:00"))
        if e.time_precision == "DATE_ONLY":
            t = datetime.combine(t.date(), dtime(23, 59, 59), timezone.utc)
        out.append({"event_id": e.event_id, "public_at": t, "precision": e.time_precision,
                    "cls": e.black_swan_classification[0], "vg": e.validation_group, "episode": e.episode_id})
    return out


def weekly_table(series) -> pd.DataFrame:
    nifty = series["NIFTY50"]
    all_days = list(nifty.index)
    pos = {d: k for k, d in enumerate(all_days)}
    evd = event_days(all_days)
    pub = public_events()
    days = [d for d in all_days if RESEARCH_START <= d <= DATA_END]
    rows = []
    for i in range(0, len(days) - REACTION_SESSIONS, REACTION_SESSIONS):
        d0, d1 = days[i], days[i + REACTION_SESSIONS]
        j = pos[d0]
        p = all_days[j - REACTION_SESSIONS]
        t_pred, t_prev = prediction_ts(d0), prediction_ts(p)
        r = {"week_start_close": d0.isoformat(), "week_end_close": d1.isoformat(), "year": d1.year,
             "feature_window_start_session": p.isoformat(), "prediction_timestamp_utc": t_pred.isoformat(),
             "target_end_timestamp_utc": prediction_ts(d1).isoformat()}
        # --- trailing (pre-prediction) shocks ---------------------------------------------------------
        for sym, col, kind in SHOCKS:
            s = series[sym]
            da, a = _asof_obs(s, p)
            db, b = _asof_obs(s, d0)
            r[f"obs_{col}_start_date"], r[f"obs_{col}_end_date"] = str(da), str(db)
            if kind == "chg_bp":
                r[f"x_{col}_5d_chg_bp"] = round((b - a) * 100, 2) if np.isfinite(a) and np.isfinite(b) else None
            else:
                r[f"x_{col}_5d_ret_pct"] = round((b / a - 1) * 100, 4) if a > 0 and b > 0 else None
        # --- realised shocks inside the TARGET window (pre-audit definition; scenario use only) -------
        for sym, col, kind in SHOCKS:
            s = series[sym]
            a, b = _asof(s, d0, False), _asof(s, d1, False)
            if kind == "chg_bp":
                r[f"s_{col}_5d_chg_bp_in_target_window"] = round((b - a) * 100, 2)
            else:
                r[f"s_{col}_5d_ret_pct_in_target_window"] = round((b / a - 1) * 100, 4) if a > 0 and b > 0 else None
        # --- state known at the prediction timestamp (unchanged) -------------------------------------
        dv, v = _asof_obs(series["VIX"], d0)
        r["x_vix_level_at_start"], r["obs_vix_date"] = v, str(dv)
        r["x_nifty_prev_20d_ret_pct"] = round((nifty[d0] / nifty[all_days[j - 20]] - 1) * 100, 4) if j >= 20 else None
        dr = nifty.pct_change().loc[all_days[max(0, j - 19)]:d0]
        r["x_nifty_prev_20d_vol_ann_pct"] = round(float(dr.std() * np.sqrt(252) * 100), 3)
        # --- targets (unchanged) ----------------------------------------------------------------------
        for t in TARGETS:
            s = series[t]
            r[f"y_{t.lower()}_5d_ret_pct"] = round((s[d1] / s[d0] - 1) * 100, 4) if d0 in s.index and d1 in s.index else None
        # --- events public during the feature window (forecasting features) --------------------------
        known = [e for e in pub if t_prev < e["public_at"] <= t_pred]
        r["x_is_event"] = int(bool(known))
        for letter, name in CLASS_FLAGS:
            r[f"x_event_{name}"] = int(any(e["cls"] == letter for e in known))
        r["known_event_ids"] = ";".join(e["event_id"] for e in known)
        r["known_event_public_at_utc"] = ";".join(e["public_at"].isoformat() for e in known)
        r["known_event_precisions"] = ";".join(e["precision"] for e in known)
        r["known_event_validation_groups"] = ";".join(dict.fromkeys(e["vg"] for e in known))
        # --- events reacting INSIDE the target window (evaluation labels only, never features) -------
        evs = [x for d in days[i + 1:i + REACTION_SESSIONS + 1] for x in evd.get(d, [])]
        lab = _label_cols(evs or None)
        lab.pop("days_since_event_start")
        r.update(lab)
        rows.append(r)
    df = pd.DataFrame(rows)
    # CV group: target-window event group, else feature-window event group, else NORMAL_<year>.
    tgt_vg = df["event_validation_group"].fillna("")
    known_vg = df["known_event_validation_groups"].fillna("")
    df["cv_group"] = np.where(tgt_vg != "", tgt_vg, np.where(known_vg != "", known_vg, "NORMAL_" + df.year.astype(str)))
    return df


FEATURES = ["x_brent_5d_ret_pct", "x_sp500_5d_ret_pct", "x_usdinr_5d_ret_pct", "x_gold_5d_ret_pct",
            "x_ust10y_5d_chg_bp", "x_vix_level_at_start", "x_nifty_prev_20d_ret_pct", "x_nifty_prev_20d_vol_ann_pct",
            "x_is_event", "x_event_geopolitical", "x_event_macro_policy", "x_event_financial_crisis",
            "x_event_commodity_supply", "x_event_other_shock"]


def final_table(w: pd.DataFrame) -> pd.DataFrame:
    """model_training_final.csv: row ids, split, cv_group, 14 features (x_), 18 targets (y_), eval metadata."""
    f = pd.DataFrame({"week_start": w.week_start_close, "week_end": w.week_end_close})
    f["split"] = np.where(w.year >= TEST_FROM_YEAR, "test", "train")  # chronological, never shuffled
    f["cv_group"] = w.cv_group
    for c in FEATURES:
        f[c] = w[c]
    for c in [c for c in w.columns if c.startswith("y_")]:
        f[c] = w[c]
    f["regime"] = w.regime                       # label of the TARGET window (evaluation only)
    f["event_ids"] = w.event_ids.fillna("")      # events reacting inside the target window (evaluation only)
    f["known_event_ids"] = w.known_event_ids     # events public at prediction time (provenance of x_event_*)
    return f


def audit_table(w: pd.DataFrame) -> pd.DataFrame:
    cols = ["week_start_close", "week_end_close", "feature_window_start_session", "prediction_timestamp_utc",
            "target_end_timestamp_utc", *[c for c in w.columns if c.startswith("obs_")], "known_event_ids",
            "known_event_public_at_utc", "known_event_precisions", "event_ids", "event_validation_group",
            "event_episode_ids", "cv_group"]
    return w[cols].rename(columns={"event_ids": "target_window_event_ids",
                                   "event_validation_group": "target_window_validation_group",
                                   "event_episode_ids": "target_window_episode_ids"})


def scenario_table(w: pd.DataFrame) -> pd.DataFrame:
    cols = ["week_start_close", "week_end_close", *[c for c in w.columns if c.startswith("s_")], "regime", "event_ids"]
    return w[cols].rename(columns={"week_start_close": "week_start", "week_end_close": "week_end"})


SHOCK_DESC = {"brent": ("Brent spot (FRED DCOILBRENTEU)", "%"), "sp500": ("S&P 500 (Yahoo ^GSPC)", "%"),
              "usdinr": ("USD/INR noon NY (FRED DEXINUS); + = rupee weaker", "%"), "gold": ("Gold front-month future (Yahoo GC=F)", "%"),
              "ust10y": ("US 10Y Treasury yield (FRED DGS10)", "bp")}
PRED_TIME = "prediction timestamp = NSE close 15:30 IST on week_start"


def schema_table(f: pd.DataFrame) -> pd.DataFrame:
    rows = [("week_start", "row_id", "date", "-", "NSE session whose close is the prediction time (P_reference)", "-", "-", "never missing", "unchanged"),
            ("week_end", "row_id", "date", "-", "5th NSE session after week_start (P_future)", "-", "-", "never missing", "unchanged"),
            ("split", "split", "category", "-", "train if year(week_end) <= 2022 else test (chronological)", "-", "-", "never missing", "unchanged"),
            ("cv_group", "validation_group", "category", "-", "Event validation group of the target-window event, else of the feature-window event, else NORMAL_<year>", "-", "-", "never missing", "audit: feature-window events added (6 rows changed)")]
    for name, (desc, unit) in SHOCK_DESC.items():
        col = f"x_{name}_5d_chg_bp" if unit == "bp" else f"x_{name}_5d_ret_pct"
        rows.append((col, "feature", "float", unit, f"Change in {desc} between the last observation dated before feature_window_start_session and the last observation dated before week_start",
                     "5 NSE sessions before week_start", PRED_TIME + " (observations dated week_start or later are excluded)",
                     "NA kept; fit any imputer on training rows only", "audit: CORRECTED - previously measured over the target window (leakage); old values moved to model_training_final_scenario_inputs.csv"))
    rows += [
        ("x_vix_level_at_start", "feature", "float", "index pts", "CBOE VIX close (FRED VIXCLS) of the last US session dated before week_start", "1 observation", PRED_TIME, "NA kept", "verified causal; unchanged"),
        ("x_nifty_prev_20d_ret_pct", "feature", "float", "%", "NIFTY 50 return from 20 sessions before week_start to the week_start close", "20 NSE sessions ending at week_start", PRED_TIME, "NA kept", "verified causal; unchanged"),
        ("x_nifty_prev_20d_vol_ann_pct", "feature", "float", "% p.a.", "Annualised SD of the 20 NIFTY 50 daily returns ending at the week_start close", "20 NSE sessions ending at week_start", PRED_TIME, "NA kept", "verified causal; unchanged"),
        ("x_is_event", "feature", "int 0/1", "-", "1 if any dataset event became public after the prediction time of feature_window_start_session and at or before this row's prediction time", "feature window", PRED_TIME + "; DATE_ONLY events count as public at 23:59:59 UTC of their date", "0 is a verified value (no event public in window)", "audit: CORRECTED - previously flagged events reacting inside the target window (leakage)"),
    ]
    for letter, name in CLASS_FLAGS:
        rows.append((f"x_event_{name}", "feature", "int 0/1", "-", f"1 if an event of class {letter} became public in the feature window (overlapping events: flags OR-ed)", "feature window", PRED_TIME, "0 is a verified value", "audit: CORRECTED - same timing fix as x_is_event"))
    for c in [c for c in f.columns if c.startswith("y_")]:
        rows.append((c, "target", "float", "%", "100 * (close[week_end] / close[week_start] - 1); Yahoo adjusted close for stocks, price index for indices",
                     "next 5 NSE sessions after the prediction time", "known only at week_end close", "NA kept; never imputed; masked per target in training", "verified; unchanged"))
    rows += [("regime", "eval_metadata", "category", "-", "NORMAL / EVENT / BLACK_SWAN label of the TARGET window (ex-post; never a feature)", "target window", "after week_end", "never missing", "unchanged"),
             ("event_ids", "eval_metadata", "string", "-", "Events whose 5-session reaction period falls in the target window (ex-post; never a feature)", "target window", "after week_end", "empty = no event", "unchanged"),
             ("known_event_ids", "provenance", "string", "-", "Events public at prediction time that set x_is_event / x_event_* (see model_training_final_audit.csv for timestamps)", "feature window", PRED_TIME, "empty = no event", "audit: new column")]
    return pd.DataFrame(rows, columns=["column", "role", "dtype", "unit", "definition", "window", "availability", "missing_policy", "audit_status"])


def report_tables(f: pd.DataFrame, sch: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Missing-value report and event / Black Swan distribution report for model_training_final.csv."""
    roles = sch.set_index("column").role
    mv = pd.DataFrame({"column": f.columns, "role": [roles[c] for c in f.columns], "n_missing": f.isna().sum().values,
                       "n_missing_train": f[f.split == "train"].isna().sum().values,
                       "n_missing_test": f[f.split == "test"].isna().sum().values, "reason_and_policy": ""})
    mv.loc[mv.column == "y_niftypharma_5d_ret_pct", "reason_and_policy"] = (
        "Provider (Yahoo ^CNXPHARMA) has no bar for 2026-01-01 although NSE traded (NIFTY 50 has it); rows with "
        "week_start 2025-12-24 and 2026-01-01 cannot be computed. Kept NA; masked for this target only; the other 17 "
        "targets of these rows are used.")
    mv.loc[mv.column.isin(["event_ids", "known_event_ids"]), "reason_and_policy"] = "Empty = no event (verified meaning); metadata, not a feature."
    ids = lambda s: ";".join(sorted({x for v in s.fillna("") for x in v.split(";") if x}))  # noqa: E731
    dist = [{"split": sp, "regime": rg, "rows": len(g), "independent_cv_groups": g.cv_group.nunique() if rg != "NORMAL" else None,
             "event_ids": ids(g.event_ids)} for (sp, rg), g in f.groupby(["split", "regime"])]
    dist += [{"split": sp, "regime": "x_is_event=1 (event public at prediction time)", "rows": int(g.x_is_event.sum()),
              "independent_cv_groups": g[g.x_is_event == 1].cv_group.nunique(), "event_ids": ids(g.known_event_ids)}
             for sp, g in f.groupby("split")]
    return mv, pd.DataFrame(dist)


def _write(df: pd.DataFrame, name: str) -> None:
    try:
        df.to_csv(OUT / name, index=False)
    except PermissionError:
        print(f"WARNING: {name} is open in another program and was NOT updated - close it and re-run.")


def main() -> None:
    series = load_series()
    d = daily_table(series)
    w = weekly_table(series)
    _write(d, "daily_training_table.csv")
    _write(w, "weekly_training_table.csv")
    f = final_table(w)
    _write(f, "model_training_final.csv")
    _write(audit_table(w), "model_training_final_audit.csv")
    _write(scenario_table(w), "model_training_final_scenario_inputs.csv")
    sch = schema_table(f)
    assert list(sch.column) == list(f.columns), "schema must describe every column, in order"
    _write(sch, "model_training_final_schema.csv")
    mv, dist = report_tables(f, sch)
    _write(mv, "model_training_final_missing_values.csv")
    _write(dist, "model_training_final_event_distribution.csv")
    print("final ", f.shape, f.split.value_counts().to_dict(), f.regime.value_counts().to_dict())


if __name__ == "__main__":
    main()
