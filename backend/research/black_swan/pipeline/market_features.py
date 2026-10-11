"""Historical market feature pipeline (Phase B/C). Reads data/raw only; never modifies the baseline.

Every feature describes information available at the PREDICTION TIMESTAMP of an NSE session d0
(NSE close, 15:30 IST), using the same conventions as model_training_final.csv:

* NSE series (NIFTY 50 and sector indices): closes dated <= d0 (the d0 close is the prediction time).
* Foreign / global series (Brent, S&P 500, USD/INR, gold, US 10Y, CBOE VIX): observations dated
  strictly BEFORE d0 (their d0 prints happen after 15:30 IST).
* k-session windows are anchored on the NSE calendar: the window start is the NSE session k sessions
  before d0; for foreign series the start value is the last observation dated before that session.
* Rolling statistics (volatility, moving averages, peaks, drawdowns) are trailing windows over each
  series' own observations (pandas rolling, right-aligned, never centred), then read as of d0.
* Holidays / missing sessions: no filling or interpolation. A series' last observation before the
  cut-off is used (as-of join); if a window lacks the required observations the value is NaN.
* Only price indices and macro series are used (no single stocks), so dividend/split adjustment
  does not mix adjusted and unadjusted prices.

Outputs:
  output/market_features_daily.csv   one row per NSE session (features as of that session's close)
  output/market_features_weekly.csv  rows aligned to the baseline's week_start/week_end, plus o_
                                     outcome descriptors of the target window (NOT features)
  output/market_features_schema.csv  unit, formula, window and timing of every column

    python pipeline/market_features.py
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
RAW = ROOT / "data" / "raw"
BASELINE = OUT / "model_training_final.csv"
ANN = np.sqrt(252) * 100

# Features that already exist in the baseline (recomputed here only to prove identical conventions and to
# provide "latest conditions" for dates after the last baseline row).
BASELINE_EQUIVALENT = ["x_brent_5d_ret_pct", "x_sp500_5d_ret_pct", "x_usdinr_5d_ret_pct", "x_gold_5d_ret_pct",
                       "x_ust10y_5d_chg_bp", "x_vix_level_at_start", "x_nifty_prev_20d_ret_pct", "x_nifty_prev_20d_vol_ann_pct"]

# New features: (column, unit, formula, window, series, timing)
NEW_FEATURES = [
    ("x_nifty_prev_5d_ret_pct", "%", "100*(close[d0]/close[d0-5]-1)", "5 NSE sessions", "NIFTY50", "nse"),
    ("x_nifty_prev_10d_ret_pct", "%", "100*(close[d0]/close[d0-10]-1)", "10 NSE sessions", "NIFTY50", "nse"),
    ("x_nifty_prev_60d_ret_pct", "%", "100*(close[d0]/close[d0-60]-1)", "60 NSE sessions", "NIFTY50", "nse"),
    ("x_nifty_prev_5d_vol_ann_pct", "% p.a.", "SD of last 5 daily returns x sqrt(252) x 100", "5 returns ending d0", "NIFTY50", "nse"),
    ("x_nifty_prev_60d_vol_ann_pct", "% p.a.", "SD of last 60 daily returns x sqrt(252) x 100", "60 returns ending d0", "NIFTY50", "nse"),
    ("x_nifty_drawdown_from_60d_peak_pct", "%", "100*(close[d0]/max(close over last 60 sessions)-1)", "60 NSE sessions", "NIFTY50", "nse"),
    ("x_nifty_max_drawdown_60d_pct", "%", "min over last 60 sessions of 100*(close/running max within window - 1)", "60 NSE sessions", "NIFTY50", "nse"),
    ("x_nifty_rebound_from_60d_trough_pct", "%", "100*(close[d0]/min(close over last 60 sessions)-1)", "60 NSE sessions", "NIFTY50", "nse"),
    ("x_nifty_dist_ma20_pct", "%", "100*(close[d0]/mean(last 20 closes)-1)", "20 NSE sessions", "NIFTY50", "nse"),
    ("x_nifty_dist_ma50_pct", "%", "100*(close[d0]/mean(last 50 closes)-1)", "50 NSE sessions", "NIFTY50", "nse"),
    ("x_nifty_streak_sessions", "sessions", "signed count of consecutive same-sign daily returns ending d0 (+up, -down)", "ending d0", "NIFTY50", "nse"),
    ("x_niftybank_prev_5d_ret_pct", "%", "100*(close[d0]/close[d0-5]-1)", "5 NSE sessions", "NIFTYBANK", "nse"),
    ("x_niftybank_prev_20d_ret_pct", "%", "100*(close[d0]/close[d0-20]-1)", "20 NSE sessions", "NIFTYBANK", "nse"),
    ("x_niftybank_prev_20d_vol_ann_pct", "% p.a.", "SD of last 20 daily returns x sqrt(252) x 100", "20 returns ending d0", "NIFTYBANK", "nse"),
    ("x_niftyit_prev_20d_ret_pct", "%", "100*(close[d0]/close[d0-20]-1)", "20 NSE sessions", "NIFTYIT", "nse"),
    ("x_niftypharma_prev_20d_ret_pct", "%", "100*(close[d0]/close[d0-20]-1)", "20 NSE sessions", "NIFTYPHARMA", "nse"),
    ("x_brent_20d_ret_pct", "%", "100*(v[last obs < p20]/... ) see timing", "20 NSE sessions before d0", "BRENT", "foreign"),
    ("x_brent_20d_vol_ann_pct", "% p.a.", "SD of last 20 daily returns (obs dated < d0) x sqrt(252) x 100", "20 obs before d0", "BRENT", "foreign"),
    ("x_usdinr_20d_ret_pct", "%", "change between last obs < p20 and last obs < d0; + = rupee weaker", "20 NSE sessions before d0", "USDINR", "foreign"),
    ("x_usdinr_20d_vol_ann_pct", "% p.a.", "SD of last 20 daily returns (obs dated < d0) x sqrt(252) x 100", "20 obs before d0", "USDINR", "foreign"),
    ("x_sp500_20d_ret_pct", "%", "change between last obs < p20 and last obs < d0", "20 NSE sessions before d0", "SP500", "foreign"),
    ("x_sp500_20d_vol_ann_pct", "% p.a.", "SD of last 20 daily returns (obs dated < d0) x sqrt(252) x 100", "20 obs before d0", "SP500", "foreign"),
    ("x_gold_20d_ret_pct", "%", "change between last obs < p20 and last obs < d0", "20 NSE sessions before d0", "GOLD", "foreign"),
    ("x_ust10y_20d_chg_bp", "bp", "100*(yield[last obs < d0] - yield[last obs < p20])", "20 NSE sessions before d0", "UST10Y", "foreign"),
    ("x_vix_5d_chg_pts", "index pts", "VIX[last obs < d0] - VIX[last obs < p5]", "5 NSE sessions before d0", "VIX", "foreign"),
]
OUTCOMES = [  # descriptors of the TARGET window (d0 -> d1); evaluation / analogue reporting only, never inputs
    ("o_nifty_window_max_drawdown_pct", "%", "min over closes d0..d1 of 100*(close/running max from d0 - 1)", "target window", "NIFTY50"),
    ("o_nifty_window_realized_vol_ann_pct", "% p.a.", "SD of the 5 daily returns d0->d1 x sqrt(252) x 100", "target window", "NIFTY50"),
]
NSE_SYMS = ["NIFTY50", "NIFTYBANK", "NIFTYIT", "NIFTYPHARMA"]
FOREIGN_SYMS = ["BRENT", "SP500", "USDINR", "GOLD", "UST10Y", "VIX"]


def _asof_idx(index: pd.Index, dates: list, strictly_before: bool) -> np.ndarray:
    """Position of the last observation dated <= date (or < date)."""
    return np.searchsorted(index.values, np.array(dates, dtype=index.values.dtype), side="left" if strictly_before else "right") - 1


def _take(values: np.ndarray, pos: np.ndarray) -> np.ndarray:
    out = np.full(len(pos), np.nan)
    ok = pos >= 0
    out[ok] = values[pos[ok]]
    return out


def _max_drawdown(window: np.ndarray) -> float:
    run_max = np.maximum.accumulate(window)
    return float(np.min(window / run_max - 1) * 100)


def _streak(r: pd.Series) -> pd.Series:
    s = np.sign(r.fillna(0).to_numpy())
    out = np.zeros(len(s))
    for i in range(len(s)):
        out[i] = s[i] if i == 0 or s[i] == 0 or s[i] != np.sign(out[i - 1]) else out[i - 1] + s[i]
    return pd.Series(out, index=r.index)


def compute_features(series: dict[str, pd.Series], sessions: list, d0s: list) -> pd.DataFrame:
    """Features as of each d0 in d0s (NSE sessions). series values are indexed by calendar date."""
    pos = {d: i for i, d in enumerate(sessions)}
    def p_back(k: int) -> list:
        return [sessions[pos[d] - k] if pos[d] >= k else None for d in d0s]
    f = pd.DataFrame({"date": [str(d) for d in d0s]})

    # ---- NSE series: own rolling stats, read as of d0 (<= d0) --------------------------------------
    for sym in NSE_SYMS:
        s = series[sym].dropna()
        idx = _asof_idx(s.index, d0s, strictly_before=False)
        r = s.pct_change()
        lag = lambda k: s.shift(k)  # noqa: E731  (k observations back on the series' own calendar)
        stats = {
            "ret5": (s / lag(5) - 1) * 100, "ret10": (s / lag(10) - 1) * 100, "ret20": (s / lag(20) - 1) * 100,
            "ret60": (s / lag(60) - 1) * 100,
            "vol5": r.rolling(5, min_periods=5).std() * ANN, "vol20": r.rolling(20, min_periods=20).std() * ANN,
            "vol60": r.rolling(60, min_periods=60).std() * ANN,
            "dd60": (s / s.rolling(60, min_periods=60).max() - 1) * 100,
            "mdd60": s.rolling(60, min_periods=60).apply(_max_drawdown, raw=True),
            "reb60": (s / s.rolling(60, min_periods=60).min() - 1) * 100,
            "ma20": (s / s.rolling(20, min_periods=20).mean() - 1) * 100,
            "ma50": (s / s.rolling(50, min_periods=50).mean() - 1) * 100,
            "streak": _streak(r),
        }
        v = {k: _take(x.to_numpy(), idx) for k, x in stats.items()}
        f[f"_src_{sym.lower()}_date"] = [str(s.index[i]) if i >= 0 else None for i in idx]
        if sym == "NIFTY50":
            f["x_nifty_prev_20d_ret_pct"], f["x_nifty_prev_20d_vol_ann_pct"] = v["ret20"], v["vol20"]
            f["x_nifty_prev_5d_ret_pct"], f["x_nifty_prev_10d_ret_pct"], f["x_nifty_prev_60d_ret_pct"] = v["ret5"], v["ret10"], v["ret60"]
            f["x_nifty_prev_5d_vol_ann_pct"], f["x_nifty_prev_60d_vol_ann_pct"] = v["vol5"], v["vol60"]
            f["x_nifty_drawdown_from_60d_peak_pct"], f["x_nifty_max_drawdown_60d_pct"] = v["dd60"], v["mdd60"]
            f["x_nifty_rebound_from_60d_trough_pct"] = v["reb60"]
            f["x_nifty_dist_ma20_pct"], f["x_nifty_dist_ma50_pct"], f["x_nifty_streak_sessions"] = v["ma20"], v["ma50"], v["streak"]
        elif sym == "NIFTYBANK":
            f["x_niftybank_prev_5d_ret_pct"], f["x_niftybank_prev_20d_ret_pct"] = v["ret5"], v["ret20"]
            f["x_niftybank_prev_20d_vol_ann_pct"] = v["vol20"]
        else:
            f[f"x_{sym.lower()}_prev_20d_ret_pct"] = v["ret20"]

    # ---- foreign series: obs dated < d0, windows anchored on NSE sessions ----------------------------
    for sym in FOREIGN_SYMS:
        s = series[sym].dropna()
        end = _asof_idx(s.index, d0s, strictly_before=True)
        b = _take(s.to_numpy(), end)
        f[f"_src_{sym.lower()}_date"] = [str(s.index[i]) if i >= 0 else None for i in end]
        for k in (5, 20):
            starts = p_back(k)
            st = np.array([_asof_idx(s.index, [p], True)[0] if p is not None else -1 for p in starts])
            a = _take(s.to_numpy(), st)
            name = sym.lower()
            if sym == "UST10Y":
                f[f"x_ust10y_{k}d_chg_bp"] = (b - a) * 100
            elif sym == "VIX":
                if k == 5:
                    f["x_vix_5d_chg_pts"] = b - a
            else:
                with np.errstate(invalid="ignore", divide="ignore"):
                    f[f"x_{name}_{k}d_ret_pct"] = np.where((a > 0) & (b > 0), (b / a - 1) * 100, np.nan)
        if sym == "VIX":
            f["x_vix_level_at_start"] = b
        if sym in ("BRENT", "USDINR", "SP500"):
            vol = s.pct_change().rolling(20, min_periods=20).std() * ANN
            f[f"x_{sym.lower()}_20d_vol_ann_pct"] = _take(vol.to_numpy(), end)
    return f


def outcomes(series: dict[str, pd.Series], week_starts: list, week_ends: list) -> pd.DataFrame:
    s = series["NIFTY50"]
    mdd, rv = [], []
    for a, b in zip(week_starts, week_ends):
        w = s.loc[a:b].to_numpy()
        mdd.append(_max_drawdown(w) if len(w) >= 2 else np.nan)
        rv.append(float(np.std(np.diff(w) / w[:-1], ddof=1) * ANN) if len(w) >= 3 else np.nan)
    return pd.DataFrame({"o_nifty_window_max_drawdown_pct": mdd, "o_nifty_window_realized_vol_ann_pct": rv})


def schema() -> pd.DataFrame:
    rows = []
    for c in BASELINE_EQUIVALENT:
        rows.append((c, "baseline_equivalent", "see model_training_final_schema.csv", "", "", "", "identical to baseline column (tested)"))
    for c, unit, formula, window, sym, kind in NEW_FEATURES:
        timing = ("NSE close dated <= d0 (prediction time = NSE close on d0)" if kind == "nse"
                  else "observations dated < d0; window start = last obs dated < the NSE session k sessions before d0")
        rows.append((c, "feature", unit, formula, window, sym, timing))
    for c, unit, formula, window, sym in OUTCOMES:
        rows.append((c, "outcome_descriptor", unit, formula, window, sym, "known only at week_end; NEVER an input"))
    return pd.DataFrame(rows, columns=["column", "role", "unit", "formula", "window", "source_series", "timing"])


def main() -> dict:
    series = load_series()
    sessions = list(series["NIFTY50"].dropna().index)
    first = pd.Timestamp("2016-01-01").date()
    daily = compute_features(series, sessions, [d for d in sessions if d >= first])
    base = pd.read_csv(BASELINE)
    ws = [pd.Timestamp(x).date() for x in base.week_start]
    we = [pd.Timestamp(x).date() for x in base.week_end]
    weekly = compute_features(series, sessions, ws).rename(columns={"date": "week_start"})
    weekly.insert(1, "week_end", base.week_end)
    weekly = pd.concat([weekly, outcomes(series, ws, we)], axis=1)
    feat_cols = BASELINE_EQUIVALENT + [c[0] for c in NEW_FEATURES]
    src_cols = [c for c in daily.columns if c.startswith("_src_")]
    daily = daily[["date", *feat_cols, *src_cols]].rename(columns={c: c[1:] for c in src_cols})
    weekly = weekly[["week_start", "week_end", *feat_cols, *[o[0] for o in OUTCOMES], *src_cols]].rename(
        columns={c: c[1:] for c in src_cols})
    for df in (daily, weekly):
        num = df.select_dtypes("number").columns
        df[num] = df[num].round(6)
    daily.to_csv(OUT / "market_features_daily.csv", index=False)
    weekly.to_csv(OUT / "market_features_weekly.csv", index=False)
    schema().to_csv(OUT / "market_features_schema.csv", index=False)
    prov = {"raw_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.glob("*.csv"))
                           if p.stem in NSE_SYMS + FOREIGN_SYMS},
            "baseline_sha256": hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
            "daily_rows": len(daily), "weekly_rows": len(weekly), "daily_last_date": daily.date.iloc[-1]}
    (OUT / "market_features_provenance.json").write_text(json.dumps(prov, indent=1), encoding="utf-8")
    return prov


if __name__ == "__main__":
    p = main()
    print({k: v for k, v in p.items() if k != "raw_hashes"})
