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
from datetime import date
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


def weekly_table(series) -> pd.DataFrame:
    nifty = series["NIFTY50"]
    all_days = list(nifty.index)
    evd = event_days(all_days)
    days = [d for d in all_days if RESEARCH_START <= d <= DATA_END]
    rows = []
    for i in range(0, len(days) - REACTION_SESSIONS, REACTION_SESSIONS):
        d0, d1 = days[i], days[i + REACTION_SESSIONS]
        r = {"week_start_close": d0.isoformat(), "week_end_close": d1.isoformat(), "year": d1.year}
        # Same-week shocks (scenario inputs: what oil/S&P/rupee/yields did during the week).
        for sym, col in (("BRENT", "brent"), ("SP500", "sp500"), ("USDINR", "usdinr"), ("GOLD", "gold")):
            s = series[sym]
            a, b = _asof(s, d0, False), _asof(s, d1, False)
            r[f"x_{col}_5d_ret_pct"] = round((b / a - 1) * 100, 4) if a > 0 and b > 0 else None
        u = series["UST10Y"]
        r["x_ust10y_5d_chg_bp"] = round((_asof(u, d1, False) - _asof(u, d0, False)) * 100, 2)
        r["x_vix_level_at_start"] = _asof(series["VIX"], d0, True)
        # Pre-week state (known at the start of the week).
        j = all_days.index(d0)
        r["x_nifty_prev_20d_ret_pct"] = round((nifty[d0] / nifty[all_days[j - 20]] - 1) * 100, 4) if j >= 20 else None
        dr = nifty.pct_change().loc[all_days[max(0, j - 19)]:d0]
        r["x_nifty_prev_20d_vol_ann_pct"] = round(float(dr.std() * np.sqrt(252) * 100), 3)
        for t in TARGETS:
            s = series[t]
            r[f"y_{t.lower()}_5d_ret_pct"] = round((s[d1] / s[d0] - 1) * 100, 4) if d0 in s.index and d1 in s.index else None
        evs = [x for d in days[i + 1:i + REACTION_SESSIONS + 1] for x in evd.get(d, [])]
        lab = _label_cols(evs or None)
        lab.pop("days_since_event_start")
        r.update(lab)
        rows.append(r)
    df = pd.DataFrame(rows)
    # CV group: event weeks keep their event validation group; normal weeks are grouped by year.
    df["cv_group"] = np.where(df.is_event == 1, df.event_validation_group, "NORMAL_" + df.year.astype(str))
    return df


TEST_FROM_YEAR = 2023


def final_table(w: pd.DataFrame) -> pd.DataFrame:
    """The single file to train on: numeric inputs (x_), 0/1 event flags, targets (y_), split and cv_group."""
    f = pd.DataFrame({"week_start": w.week_start_close, "week_end": w.week_end_close})
    f["split"] = np.where(w.year >= TEST_FROM_YEAR, "test", "train")  # chronological, never shuffled
    f["cv_group"] = w.cv_group
    for c in [c for c in w.columns if c.startswith("x_")]:
        f[c] = w[c]
    f["x_is_event"] = w.is_event
    f["x_is_black_swan"] = w.is_black_swan
    classes = w.event_classes.fillna("")
    for letter, name in (("B", "geopolitical"), ("C", "macro_policy"), ("D", "financial_crisis"),
                         ("E", "commodity_supply"), ("F", "other_shock")):
        f[f"x_event_{name}"] = classes.str.contains(letter).astype(int)
    for c in [c for c in w.columns if c.startswith("y_")]:
        f[c] = w[c]
    f["regime"] = w.regime
    f["event_ids"] = w.event_ids.fillna("")
    return f


def main() -> None:
    series = load_series()
    d = daily_table(series)
    w = weekly_table(series)
    d.to_csv(OUT / "daily_training_table.csv", index=False)
    w.to_csv(OUT / "weekly_training_table.csv", index=False)
    f = final_table(w)
    f.to_csv(OUT / "model_training_final.csv", index=False)
    print("final ", f.shape, f.split.value_counts().to_dict())
    print("daily ", d.shape, d.regime.value_counts().to_dict())
    print("weekly", w.shape, w.regime.value_counts().to_dict())


if __name__ == "__main__":
    main()
