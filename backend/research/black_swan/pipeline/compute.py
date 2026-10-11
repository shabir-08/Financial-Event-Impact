"""Compute event-window returns, abnormal returns, confounding flags and measured severity.

Timing rule (per asset, in its own exchange time zone):
  baseline session  = last session whose CLOSE is at or before the event's information time
  window k end      = the k-th session whose CLOSE is after the information time
  return_pct        = (ending_price / baseline_price - 1) * 100      (prices / index levels)
  change_bp         = (ending_yield - baseline_yield) * 100            (yields; return_pct = NA)
So news after the close is first reflected in the next session; news before the open is reflected
in that day's session; news during a session makes window 1 include that session (flag
INFO_DURING_SESSION: part of window 1 is pre-news). Nothing is filled or interpolated.

Abnormal returns (Indian stocks and sector indices only), market model vs NIFTY 50:
  estimation window = 240 sessions ending 21 sessions before the baseline (>=150 valid days)
  AR_t = r_asset,t - (alpha + beta * r_nifty,t),   CAR_k = sum of AR_t over window k
  t_stat = CAR_k / (sigma_resid * sqrt(k))   - a statistical association, not causal evidence.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from assets import ASSETS, BY_SYMBOL, MONTHLY  # noqa: E402
from events import EVENTS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "output"
WINDOWS = [1, 3, 5, 10, 20, 60]
RESEARCH_START = date(2016, 10, 1)
DATA_END = date(2026, 10, 9)  # last complete session retrieved (October 2026 is INCOMPLETE)
ABNORMAL_GROUPS = {"india_stock"}
ABNORMAL_INDICES = {"NIFTYBANK", "NIFTYIT", "NIFTYPHARMA"}
EVENT_ASSETS = [a for a in ASSETS if a.symbol != "FEDFUNDS"]
HDFC_MERGER = date(2023, 7, 1)
ORIGIN_INDEX = {"India": "NIFTY50", "United States": "SP500", "China": "SSE", "Russia": "IMOEX", "Israel": "TA35"}


def load_series() -> dict[str, pd.Series]:
    out = {}
    for a in [*ASSETS, *MONTHLY]:
        df = pd.read_csv(RAW / f"{a.symbol}.csv")
        if df.empty:
            out[a.symbol] = pd.Series(dtype=float)
            continue
        df["date"] = pd.to_datetime(df["date"]).dt.date
        out[a.symbol] = df.set_index("date")["value"].astype(float).sort_index()
    return out


def _hm(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


def session_bounds(a, d: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo(a.tz)
    close = datetime.combine(d, _hm(a.close_local), tz)
    open_d = d - timedelta(days=1) if _hm(a.open_local) > _hm(a.close_local) else d  # overnight sessions
    opn = datetime.combine(open_d, _hm(a.open_local), tz)
    return opn.astimezone(timezone.utc), close.astimezone(timezone.utc)


def parse_info(e: dict) -> datetime:
    return datetime.fromisoformat(e["info_time_utc"].replace("Z", "+00:00"))


def event_window(a, s: pd.Series, info: datetime) -> dict:
    """Baseline + post-event sessions for one asset."""
    dates = list(s.index)
    closes = [session_bounds(a, d)[1] for d in dates]
    base_i = None
    for i, c in enumerate(closes):
        if c <= info:
            base_i = i
        else:
            break
    post_start = 0 if base_i is None else base_i + 1
    return {"dates": dates, "base_i": base_i, "post": list(range(post_start, len(dates)))}


def compute_returns(series: dict[str, pd.Series]) -> pd.DataFrame:
    rows = []
    nifty = series["NIFTY50"]
    for e in EVENTS:
        info = parse_info(e)
        info_date = info.date()
        for a in EVENT_ASSETS:
            s = series[a.symbol]
            s = s[s.index <= DATA_END]
            w = event_window(a, s, info)
            base_flags = []
            if a.approx_close:
                base_flags.append("APPROX_SESSION_TIME")
            if e["time_precision"] != "EXACT":
                base_flags.append(f"EVENT_TIME_{e['time_precision']}")
            base_date = w["dates"][w["base_i"]] if w["base_i"] is not None else None
            base_price = float(s.iloc[w["base_i"]]) if w["base_i"] is not None else None
            if base_date and (info_date - base_date).days > 6:
                base_flags.append("STALE_BASELINE_MARKET_CLOSED_OR_GAP")
            first_post = w["dates"][w["post"][0]] if w["post"] else None
            if first_post is not None:
                o, c = session_bounds(a, first_post)
                if o < info < c:
                    base_flags.append("INFO_DURING_SESSION")
            if a.symbol == "HDFCBANK" and base_date and base_date >= HDFC_MERGER - timedelta(days=400):
                base_flags.append("HDFC_MERGER_STRUCTURAL_BREAK_NEARBY")
            for k in WINDOWS:
                flags = list(base_flags)
                row = dict(event_id=e["event_id"], asset_symbol=a.symbol, asset_name=a.name, asset_class=a.asset_class,
                           market=a.market, currency=a.currency, asset_group=a.group, window_trading_days=k,
                           event_reference_time_utc=e["info_time_utc"], event_time_precision=e["time_precision"],
                           baseline_date=base_date, baseline_price=base_price, window_start_date=first_post,
                           window_end_date=None, ending_price=None, absolute_price_change=None,
                           percentage_return=None, change_bp=None, value_kind=a.value_kind,
                           data_frequency="daily", price_adjustment_method=a.adjustment,
                           source=f"{a.source}:{a.source_id}", window_status=None)
                if base_price is None:
                    row["window_status"] = "NO_BASELINE"
                    flags.append("NO_OBSERVATION_BEFORE_EVENT")
                elif len(w["post"]) >= k:
                    end_i = w["post"][k - 1]
                    end_date, end_price = w["dates"][end_i], float(s.iloc[end_i])
                    row.update(window_end_date=end_date, ending_price=end_price,
                               absolute_price_change=end_price - base_price)
                    if a.value_kind == "YIELD_PCT":
                        row["change_bp"] = round((end_price - base_price) * 100, 2)
                    elif base_price <= 0 or end_price <= 0:
                        flags.append("NONPOSITIVE_PRICE_RETURN_UNDEFINED")
                    else:
                        row["percentage_return"] = round((end_price / base_price - 1) * 100, 4)
                    span = (end_date - base_date).days
                    if span > k * 1.6 + 8:
                        flags.append("WINDOW_SPANS_TRADING_GAP")
                    row["window_status"] = "AVAILABLE"
                else:
                    if s.index[-1] < info_date:
                        row["window_status"] = "NOT_YET_PUBLISHED_BY_SOURCE"  # e.g. FRED publication lag
                    else:
                        current = s.index[-1] >= DATA_END - timedelta(days=7)
                        row["window_status"] = "NOT_YET_ELAPSED" if current else "MISSING"
                    flags.append(row["window_status"])
                row["data_quality_flag"] = "|".join(dict.fromkeys(flags)) or "OK"
                rows.append(row)
    df = pd.DataFrame(rows)
    return df


def add_abnormal(df: pd.DataFrame, series: dict[str, pd.Series]) -> pd.DataFrame:
    nifty = series["NIFTY50"]
    rn = nifty.pct_change()
    extra = {c: [] for c in ("benchmark_symbol", "benchmark_return_pct", "market_adjusted_return_pct", "mm_alpha",
                             "mm_beta", "mm_resid_sd", "mm_estimation_days", "car_market_model_pct", "car_t_stat")}
    for _, r in df.iterrows():
        a = BY_SYMBOL[r.asset_symbol]
        eligible = (a.group in ABNORMAL_GROUPS or a.symbol in ABNORMAL_INDICES) and r.window_status == "AVAILABLE" \
            and r.percentage_return is not None and not pd.isna(r.percentage_return)
        vals = dict.fromkeys(extra, None)
        if eligible:
            s = series[a.symbol]
            ra = s.pct_change()
            joined = pd.concat([ra.rename("a"), rn.rename("m")], axis=1).dropna()
            idx = list(joined.index)
            base, end = r.baseline_date, r.window_end_date
            if base in nifty.index and end in nifty.index:
                bench = (nifty[end] / nifty[base] - 1) * 100
                vals.update(benchmark_symbol="NIFTY50", benchmark_return_pct=round(bench, 4),
                            market_adjusted_return_pct=round(r.percentage_return - bench, 4))
            pos = [i for i, d in enumerate(idx) if d <= base]
            if pos:
                b_i = pos[-1]
                est = joined.iloc[max(0, b_i - 260):max(0, b_i - 20)]
                win = joined[(joined.index > base) & (joined.index <= end)]
                if len(est) >= 150 and len(win) > 0:
                    X = np.column_stack([np.ones(len(est)), est["m"].values])
                    coef, *_ = np.linalg.lstsq(X, est["a"].values, rcond=None)
                    resid = est["a"].values - X @ coef
                    sd = float(np.std(resid, ddof=2))
                    ar = win["a"].values - (coef[0] + coef[1] * win["m"].values)
                    car = float(ar.sum())
                    vals.update(mm_alpha=round(float(coef[0]), 6), mm_beta=round(float(coef[1]), 4),
                                mm_resid_sd=round(sd, 6), mm_estimation_days=len(est),
                                car_market_model_pct=round(car * 100, 4),
                                car_t_stat=round(car / (sd * np.sqrt(len(win))), 3) if sd > 0 else None)
        for k_ in extra:
            extra[k_].append(vals[k_])
    for k_, v in extra.items():
        df[k_] = v
    return df


def add_confounders(df: pd.DataFrame) -> pd.DataFrame:
    times = {e["event_id"]: parse_info(e) for e in EVENTS}
    conf = {}
    for e in EVENTS:
        t0 = times[e["event_id"]]
        for k in WINDOWS:
            span = timedelta(days=int(k * 1.5) + 3)
            others = [o for o, t in times.items() if o != e["event_id"] and t0 - timedelta(days=2) <= t <= t0 + span]
            conf[(e["event_id"], k)] = ";".join(others)
    df["concurrent_events_in_window"] = [conf[(r.event_id, r.window_trading_days)] for r in df.itertuples()]
    df["confounding_note"] = np.where(df["concurrent_events_in_window"] != "",
                                      "Other dataset events fall inside this window; returns are not attributable to one event.",
                                      "No other dataset event in window (unlisted macro releases, earnings and policy meetings were NOT screened).")
    return df


def severity(df: pd.DataFrame, series: dict[str, pd.Series]) -> pd.DataFrame:
    """Measured severity: percentile of |event-window move| within all rolling windows of the same length."""
    spec = [("NIFTY50", 1), ("NIFTY50", 5), ("SP500", 5), ("BRENT", 5), ("USDINR", 5), ("UST10Y", 5)]
    dists = {}
    for sym, k in [*spec, *((o, 1) for o in set(ORIGIN_INDEX.values()))]:
        s = series[sym]
        s = s[(s.index >= RESEARCH_START) & (s.index <= DATA_END)]
        if BY_SYMBOL[sym].value_kind == "YIELD_PCT":
            d = (s.shift(-k) - s).abs() * 100
        else:
            d = ((s.shift(-k) / s - 1).abs() * 100).where(s > 0)
        dists[(sym, k)] = np.sort(d.dropna().values)
    out = []
    for e in EVENTS:
        row = {"event_id": e["event_id"]}
        pct_vals = []
        for sym, k in spec:
            m = df[(df.event_id == e["event_id"]) & (df.asset_symbol == sym) & (df.window_trading_days == k)]
            v = None
            if len(m) and m.iloc[0].window_status == "AVAILABLE":
                x = m.iloc[0].change_bp if BY_SYMBOL[sym].value_kind == "YIELD_PCT" else m.iloc[0].percentage_return
                if x is not None and not pd.isna(x):
                    dist = dists[(sym, k)]
                    v = round(100 * np.searchsorted(dist, abs(x), side="right") / len(dist), 1)
                    pct_vals.append(v)
            row[f"{sym.lower()}_abs{k}d_percentile"] = v
        origin = ORIGIN_INDEX.get(e["country"])
        v = None
        if origin:
            m = df[(df.event_id == e["event_id"]) & (df.asset_symbol == origin) & (df.window_trading_days == 1)]
            if len(m) and m.iloc[0].window_status == "AVAILABLE" and not pd.isna(m.iloc[0].percentage_return):
                dist = dists[(origin, 1)]
                v = round(100 * np.searchsorted(dist, abs(m.iloc[0].percentage_return), side="right") / len(dist), 1)
                pct_vals.append(v)
        row["origin_market_index"] = origin
        row["origin_index_abs1d_percentile"] = v
        mx = max(pct_vals) if pct_vals else None
        row["severity_measured_max_percentile"] = mx
        row["severity_tier"] = (None if mx is None else "EXTREME" if mx >= 99 else "HIGH" if mx >= 95
                                else "ELEVATED" if mx >= 80 else "NORMAL")
        core = ["NIFTY50", "SP500", "BRENT", "USDINR", "UST10Y"]
        avail = sum(1 for sym in core if len(df[(df.event_id == e["event_id"]) & (df.asset_symbol == sym)
                                                & (df.window_trading_days == 5) & (df.window_status == "AVAILABLE")]))
        row["data_availability"] = "FULL" if avail == len(core) else "PARTIAL" if avail else "NONE"
        row["core_assets_with_5d_window"] = f"{avail}/{len(core)}"
        out.append(row)
    return pd.DataFrame(out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    series = load_series()
    df = compute_returns(series)
    df = add_abnormal(df, series)
    df = add_confounders(df)
    df.to_csv(OUT / "event_market_returns.csv", index=False)
    sev = severity(df, series)
    sev.to_csv(OUT / "event_severity_measured.csv", index=False)
    print(df.window_status.value_counts().to_string())
    print(sev[["event_id", "severity_tier", "data_availability"]].to_string(index=False))


if __name__ == "__main__":
    main()
