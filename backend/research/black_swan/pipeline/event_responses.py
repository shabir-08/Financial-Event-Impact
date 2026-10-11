"""Phase 3: event-level historical response dataset (output/historical_event_responses.csv).

One row per event in events_master.csv (51 events; events_master.csv is not modified, no events are
added). Responses are taken from event_market_returns.csv, which already applies the documented
convention: baseline = last session whose close is at or before the event information time; window k
ends at the close of the k-th later session. Values whose window has not elapsed / is not published
stay NA with their status.

Added per event:
* pre-event conditions: market_features_daily.csv as of the NIFTY 50 baseline session (only
  information known at that close; foreign data dated before it);
* recovery: NIFTY 50 max drawdown over the 20 sessions after the baseline and the number of sessions
  until NIFTY first closes at or above the baseline close again (NA if no close below baseline in
  that span, or not recovered within 250 sessions / by data end);
* overlap: concurrent dataset events in the 5-session window and the confounding note.

    python pipeline/event_responses.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from compute import load_series  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
RECOVERY_MAX_SESSIONS = 250
# events_master.csv uses two spellings for two categories; normalised here only (source file unchanged).
CATEGORY_NORMALISATION = {"Major economic policy change": "Major economic policy changes",
                          "Major technology-sector or financial-market crash": "Major technology-sector or financial-market crashes"}

RESPONSES = [  # (asset, window, value column, output name)
    ("NIFTY50", 1, "percentage_return", "nifty_1d_return_pct"),
    ("NIFTY50", 5, "percentage_return", "nifty_5d_return_pct"),
    ("NIFTY50", 20, "percentage_return", "nifty_20d_return_pct"),
    ("NIFTY50", 60, "percentage_return", "nifty_60d_return_pct"),
    ("NIFTY50", 5, "car_market_model_pct", "nifty_5d_car_market_model_pct"),
    ("NIFTYBANK", 5, "percentage_return", "niftybank_5d_return_pct"),
    ("NIFTYIT", 5, "percentage_return", "niftyit_5d_return_pct"),
    ("NIFTYPHARMA", 5, "percentage_return", "niftypharma_5d_return_pct"),
    ("BRENT", 5, "percentage_return", "brent_5d_change_pct"),
    ("USDINR", 5, "percentage_return", "usdinr_5d_change_pct"),
    ("UST10Y", 5, "change_bp", "ust10y_5d_change_bp"),
    ("VIX", 5, "percentage_return", "cboe_vix_5d_change_pct"),
    ("SP500", 5, "percentage_return", "sp500_5d_return_pct"),
]
PRE = ["x_nifty_prev_20d_ret_pct", "x_nifty_prev_60d_ret_pct", "x_nifty_prev_20d_vol_ann_pct",
       "x_nifty_drawdown_from_60d_peak_pct", "x_vix_level_at_start", "x_brent_20d_ret_pct", "x_usdinr_20d_ret_pct"]
META = ["event_id", "event_name", "event_category", "event_subcategory", "black_swan_classification", "event_start_date",
        "info_time_utc", "time_precision", "country", "countries_involved", "economic_channels", "india_relevance",
        "oil_market_relevance", "currency_market_relevance", "episode_id", "validation_group", "severity_tier", "source_urls"]


def recovery(nifty: pd.Series, base_date) -> tuple[float, float]:
    s = nifty.dropna()
    i = s.index.get_loc(base_date)
    base = s.iloc[i]
    after = s.iloc[i + 1:i + 1 + RECOVERY_MAX_SESSIONS]
    first20 = after.iloc[:20]
    mdd = float((first20 / base - 1).min() * 100) if len(first20) else np.nan
    below = np.flatnonzero(after.to_numpy() < base)
    if not len(below):
        return mdd, np.nan  # never closed below the baseline: recovery not applicable
    back = np.flatnonzero(after.to_numpy()[below[0]:] >= base)
    return mdd, float(below[0] + back[0] + 1) if len(back) else np.nan


def main() -> pd.DataFrame:
    em = pd.read_csv(OUT / "events_master.csv")
    er = pd.read_csv(OUT / "event_market_returns.csv")
    daily = pd.read_csv(OUT / "market_features_daily.csv").set_index("date")
    nifty = load_series()["NIFTY50"]
    rows = []
    for e in em.itertuples():
        r = {k: getattr(e, k) for k in META}
        ev = er[er.event_id == e.event_id]
        for sym, w, col, name in RESPONSES:
            hit = ev[(ev.asset_symbol == sym) & (ev.window_trading_days == w)]
            if hit.empty:
                r[name], r[f"{name}__status"] = np.nan, "NO_ROW"
                continue
            h = hit.iloc[0]
            r[name] = h[col] if h.window_status == "AVAILABLE" else np.nan
            r[f"{name}__status"] = h.window_status
        n5 = ev[(ev.asset_symbol == "NIFTY50") & (ev.window_trading_days == 5)]
        if not n5.empty:
            h = n5.iloc[0]
            r.update(nifty_baseline_date=h.baseline_date, nifty_5d_window_end=h.window_end_date,
                     data_quality_flag=h.data_quality_flag,
                     concurrent_events_in_5d_window="" if pd.isna(h.concurrent_events_in_window) else h.concurrent_events_in_window,
                     confounding_note="" if pd.isna(h.confounding_note) else h.confounding_note)
            for c in PRE:
                r[f"pre_{c[2:]}"] = daily.loc[h.baseline_date, c] if h.baseline_date in daily.index else np.nan
            r["nifty_20d_max_drawdown_after_pct"], r["nifty_sessions_to_recover_baseline"] = recovery(
                nifty, pd.Timestamp(h.baseline_date).date())
        rows.append(r)
    df = pd.DataFrame(rows)
    df.insert(3, "event_category_normalized", df.event_category.replace(CATEGORY_NORMALISATION))
    df.insert(4, "event_class", df.black_swan_classification.str[0])
    df["overlaps_other_events"] = df.concurrent_events_in_5d_window.fillna("").astype(str).str.len() > 0
    df.to_csv(OUT / "historical_event_responses.csv", index=False)
    prov = {"events_master_sha256": hashlib.sha256((OUT / "events_master.csv").read_bytes()).hexdigest(),
            "event_market_returns_sha256": hashlib.sha256((OUT / "event_market_returns.csv").read_bytes()).hexdigest(),
            "market_features_daily_sha256": hashlib.sha256((OUT / "market_features_daily.csv").read_bytes()).hexdigest(),
            "rows": len(df), "independent_episodes": int(df.episode_id.nunique()),
            "validation_groups": int(df.validation_group.nunique()),
            "events_added": 0, "note": "No events were added: every candidate needs a verified source and price coverage; "
                                       "raw data start 2015-09-01, so pre-2016 episodes (e.g. 2008 GFC) cannot be measured."}
    (OUT / "historical_event_responses_provenance.json").write_text(json.dumps(prov, indent=1), encoding="utf-8")
    return df


if __name__ == "__main__":
    d = main()
    print(d.shape, "episodes", d.episode_id.nunique(), "overlapping", int(d.overlaps_other_events.sum()))
    print(d[["event_id", "event_category", "nifty_5d_return_pct", "brent_5d_change_pct", "pre_nifty_prev_20d_vol_ann_pct",
             "nifty_sessions_to_recover_baseline", "overlaps_other_events"]].head(12).to_string())
