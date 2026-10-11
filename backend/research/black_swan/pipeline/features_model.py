"""Model-ready feature table + an executed feasibility experiment (numpy only, reproducible).

Outputs:
  output/model_feature_table.csv     event x Indian-target rows (Task A)
  output/model_feature_schema.csv    feature definitions, availability timestamps, missing policy
  output/channel_associations.csv    measured sign-agreement between shocks and Indian assets
  output/model_feasibility_results.json  metrics of the experiments actually run below

Experiments (all chronological / grouped; no random shuffling):
  A  event-level ridge: Nifty 5d return ~ scenario shocks, leave-one-validation-group-out
  B1 daily predictive ridge: Nifty r_t ~ information known before the Indian open (t-1)
  B2 weekly scenario-sensitivity ridge: Nifty 5d return ~ contemporaneous 5d shocks, walk-forward by year
Baselines: zero return and training-mean return. Metrics: MAE, RMSE, directional accuracy.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from compute import DATA_END, RESEARCH_START, load_series, parse_info  # noqa: E402
from events import EVENTS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
INDIA_TARGETS = ["NIFTY50", "NIFTYBANK", "NIFTYIT", "NIFTYPHARMA", "ONGC", "IOC", "BPCL", "RELIANCE", "INDIGO",
                 "ASIANPAINT", "SBIN", "ICICIBANK", "HDFCBANK", "TCS", "INFY", "LT", "HINDALCO", "SUNPHARMA"]


def _last_on_or_before(s: pd.Series, d: date):
    sub = s[s.index <= d]
    return (sub.index[-1], float(sub.iloc[-1])) if len(sub) else (None, None)


def validation_groups() -> dict[str, str]:
    """Chain events whose information times are within 30 days of each other into one group,
    and always keep an episode together - prevents leakage between overlapping windows."""
    evs = sorted(EVENTS, key=lambda e: e["info_time_utc"])
    group, gid, prev_t, ep_group = {}, 0, None, {}
    for e in evs:
        t = parse_info(e)
        if e["episode_id"] in ep_group:
            group[e["event_id"]] = ep_group[e["episode_id"]]
        else:
            if prev_t is None or (t - prev_t).days > 30:
                gid += 1
            group[e["event_id"]] = f"VG{gid:02d}"
            ep_group[e["episode_id"]] = group[e["event_id"]]
        prev_t = t
    # Audit fix (2026-10-11): an episode joining an earlier group could leave a time-adjacent event of a
    # DIFFERENT episode in a separate group (e.g. COVID EV015 in VG07 vs oil-war EV013 in VG08, 5 days
    # apart). Merge any two groups with events <= 30 days apart; keep the lowest existing id.
    parent = {g: g for g in group.values()}

    def find(g: str) -> str:
        while parent[g] != g:
            g = parent[g]
        return g

    times = [(parse_info(e), group[e["event_id"]]) for e in evs]
    for (t1, g1), (t2, g2) in zip(times, times[1:]):
        if (t2 - t1).days <= 30 and find(g1) != find(g2):
            a, b = sorted((find(g1), find(g2)))
            parent[b] = a
    return {eid: find(g) for eid, g in group.items()}


def build_feature_table(series: dict[str, pd.Series]) -> pd.DataFrame:
    ret = pd.read_csv(OUT / "event_market_returns.csv")
    vg = validation_groups()

    def val(ev, sym, k, field="percentage_return"):
        m = ret[(ret.event_id == ev) & (ret.asset_symbol == sym) & (ret.window_trading_days == k)]
        if not len(m) or m.iloc[0].window_status != "AVAILABLE":
            return None
        v = m.iloc[0][field]
        return None if pd.isna(v) else float(v)

    rows = []
    for e in EVENTS:
        ev = e["event_id"]
        nb = ret[(ret.event_id == ev) & (ret.asset_symbol == "NIFTY50") & (ret.window_trading_days == 1)]
        base = nb.iloc[0].baseline_date if len(nb) else None
        if base is None or pd.isna(base):
            continue
        base = date.fromisoformat(str(base))
        n = series["NIFTY50"]
        nn = n[n.index <= base]
        pre = {}
        pre["nifty_ret_20d_pre_pct"] = round((nn.iloc[-1] / nn.iloc[-21] - 1) * 100, 4) if len(nn) > 21 else None
        dr = nn.pct_change().dropna().iloc[-20:]
        pre["nifty_realized_vol_20d_pre_ann_pct"] = round(float(dr.std(ddof=1) * np.sqrt(252) * 100), 3) if len(dr) == 20 else None
        info = parse_info(e)
        _, vix = _last_on_or_before(series["VIX"], (info - timedelta(days=1)).date())
        pre["vix_level_pre"] = vix
        for sym, key in (("BRENT", "brent_ret_20d_pre_pct"), ("USDINR", "usdinr_ret_20d_pre_pct"), ("SP500", "sp500_ret_20d_pre_pct")):
            s = series[sym]
            sub = s[s.index < info.date()]
            pre[key] = round((sub.iloc[-1] / sub.iloc[-21] - 1) * 100, 4) if len(sub) > 21 and sub.iloc[-21] > 0 and sub.iloc[-1] > 0 else None
        u = series["UST10Y"]
        us = u[u.index < info.date()]
        pre["ust10y_chg_20d_pre_bp"] = round((us.iloc[-1] - us.iloc[-21]) * 100, 2) if len(us) > 21 else None
        shocks = {
            "brent_shock_1d_pct": val(ev, "BRENT", 1), "brent_shock_5d_pct": val(ev, "BRENT", 5),
            "usdinr_shock_5d_pct": val(ev, "USDINR", 5), "ust10y_shock_5d_bp": val(ev, "UST10Y", 5, "change_bp"),
            "sp500_shock_1d_pct": val(ev, "SP500", 1), "vix_shock_1d_pts": val(ev, "VIX", 1, "absolute_price_change"),
            "gold_shock_5d_pct": val(ev, "GOLD", 5),
        }
        for tgt in INDIA_TARGETS:
            r = dict(event_id=ev, event_date=e["event_start_date"], episode_id=e["episode_id"], validation_group=vg[ev],
                     target_asset=tgt, event_category=e["event_category"], classification=e["classification"],
                     origin_country=e["country"], unexpectedness=e["unexpectedness"],
                     event_time_precision=e["time_precision"], prediction_timestamp_baseline_close=base.isoformat(),
                     **pre, **shocks)
            s = series[tgt]
            ss = s[s.index <= base]
            r["target_ret_20d_pre_pct"] = round((ss.iloc[-1] / ss.iloc[-21] - 1) * 100, 4) if len(ss) > 21 else None
            for k in (1, 5, 20):
                r[f"y_target_ret_{k}d_pct"] = val(ev, tgt, k)
            r["y_target_car_5d_pct"] = val(ev, tgt, 5, "car_market_model_pct")
            rows.append(r)
    return pd.DataFrame(rows)


SCHEMA = [
    # name, definition, dtype, unit, source, availability, missing policy, event-specific, available at prediction time, role
    ("event_category", "Research category of the event", "category", "-", "events_master", "event time", "never missing", True, True, "input"),
    ("classification", "A-F label (Black Swan candidate ... other)", "category", "-", "events_master", "event time", "never missing", True, True, "input"),
    ("origin_country", "Country where the event originates", "category", "-", "events_master", "event time", "never missing", True, True, "input"),
    ("unexpectedness", "UNEXPECTED / PARTIALLY_ANTICIPATED / SCHEDULED_SURPRISE_OUTCOME", "category", "-", "events_master", "event time", "never missing", True, True, "input"),
    ("nifty_ret_20d_pre_pct", "NIFTY 50 return over 20 sessions ending at the baseline close", "float", "%", "Yahoo ^NSEI", "baseline close", "drop row if missing", False, True, "input"),
    ("nifty_realized_vol_20d_pre_ann_pct", "Annualised stdev of 20 daily NIFTY returns before baseline", "float", "% p.a.", "Yahoo ^NSEI", "baseline close", "drop row if missing", False, True, "input"),
    ("vix_level_pre", "CBOE VIX close on the last US session before the event day", "float", "index pts", "FRED VIXCLS", "prior US close", "keep NA; model must handle", False, True, "input"),
    ("brent_ret_20d_pre_pct", "Brent spot 20-observation return before the event date", "float", "%", "FRED DCOILBRENTEU", "prior London close", "keep NA", False, True, "input"),
    ("usdinr_ret_20d_pre_pct", "USD/INR 20-observation change before the event date", "float", "%", "FRED DEXINUS", "prior NY noon", "keep NA", False, True, "input"),
    ("sp500_ret_20d_pre_pct", "S&P 500 20-session return before the event date", "float", "%", "Yahoo ^GSPC", "prior US close", "keep NA", False, True, "input"),
    ("ust10y_chg_20d_pre_bp", "US 10Y yield change over 20 observations before event date", "float", "bp", "FRED DGS10", "prior US close", "keep NA", False, True, "input"),
    ("target_ret_20d_pre_pct", "Target asset 20-session return to baseline (momentum)", "float", "%", "Yahoo", "baseline close", "drop row if missing", False, True, "input"),
    ("brent_shock_1d_pct", "Brent spot move over its first post-event observation", "float", "%", "FRED DCOILBRENTEU", "AFTER event (contemporaneous)", "keep NA", True, False, "scenario_input"),
    ("brent_shock_5d_pct", "Brent spot move over 5 post-event observations", "float", "%", "FRED", "AFTER event", "keep NA", True, False, "scenario_input"),
    ("usdinr_shock_5d_pct", "USD/INR move over 5 post-event observations", "float", "%", "FRED DEXINUS", "AFTER event", "keep NA", True, False, "scenario_input"),
    ("ust10y_shock_5d_bp", "US 10Y yield change over 5 post-event observations", "float", "bp", "FRED DGS10", "AFTER event", "keep NA", True, False, "scenario_input"),
    ("sp500_shock_1d_pct", "S&P 500 move on its first post-event session", "float", "%", "Yahoo ^GSPC", "AFTER event", "keep NA", True, False, "scenario_input"),
    ("vix_shock_1d_pts", "VIX change on first post-event session", "float", "pts", "FRED VIXCLS", "AFTER event", "keep NA", True, False, "scenario_input"),
    ("gold_shock_5d_pct", "Gold futures 5-session move (roll artefacts possible)", "float", "%", "Yahoo GC=F", "AFTER event", "keep NA", True, False, "scenario_input"),
    ("y_target_ret_1d_pct", "Target return, baseline close -> 1st post-event session close", "float", "%", "Yahoo", "AFTER event", "row excluded for that horizon", True, False, "target"),
    ("y_target_ret_5d_pct", "Target return, baseline -> 5th post-event session", "float", "%", "Yahoo", "AFTER event", "row excluded for that horizon", True, False, "target"),
    ("y_target_ret_20d_pct", "Target return, baseline -> 20th post-event session", "float", "%", "Yahoo", "AFTER event", "row excluded for that horizon", True, False, "target"),
    ("y_target_car_5d_pct", "Market-model CAR vs NIFTY 50 over 5 sessions (stocks/sector indices)", "float", "%", "computed", "AFTER event", "NA for NIFTY50 itself", True, False, "target"),
    ("episode_id / validation_group", "Episode and leakage-safe CV group", "id", "-", "events_master", "-", "never missing", True, True, "grouping"),
]


def ridge_fit(X, y, lam):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    A = np.column_stack([np.ones(len(Z)), Z])
    P = np.eye(A.shape[1]) * lam
    P[0, 0] = 0
    w = np.linalg.solve(A.T @ A + P, A.T @ y)
    return lambda Xn: np.column_stack([np.ones(len(Xn)), (Xn - mu) / sd]) @ w, w, mu, sd


def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    nz = y != 0
    return {"n": int(len(y)), "MAE": round(float(np.mean(np.abs(y - p))), 4),
            "RMSE": round(float(np.sqrt(np.mean((y - p) ** 2))), 4),
            "directional_accuracy": round(float(np.mean(np.sign(y[nz]) == np.sign(p[nz]))), 4) if nz.any() else None}


def experiment_a(ft: pd.DataFrame) -> dict:
    feats = ["brent_shock_5d_pct", "ust10y_shock_5d_bp", "sp500_shock_1d_pct", "nifty_realized_vol_20d_pre_ann_pct"]
    d = ft[ft.target_asset == "NIFTY50"].dropna(subset=feats + ["y_target_ret_5d_pct"])
    X, y, g = d[feats].values.astype(float), d["y_target_ret_5d_pct"].values.astype(float), d["validation_group"].values
    preds, base_mean = np.zeros(len(y)), np.zeros(len(y))
    for grp in np.unique(g):
        tr, te = g != grp, g == grp
        f, *_ = ridge_fit(X[tr], y[tr], lam=5.0)
        preds[te] = f(X[te])
        base_mean[te] = y[tr].mean()
    _, w, *_ = ridge_fit(X, y, lam=5.0)
    return {"description": "Event-level ridge (lambda=5, standardised), Nifty 5d return on contemporaneous shocks; leave-one-validation-group-out",
            "n_events": int(len(y)), "n_validation_groups": int(len(np.unique(g))), "features": feats,
            "model": metrics(y, preds), "baseline_zero": metrics(y, np.zeros(len(y))),
            "baseline_train_mean": metrics(y, base_mean),
            "full_sample_coefficients_per_1sd": dict(zip(["intercept", *feats], [round(float(v), 4) for v in w])),
            "caveat": "Shocks are contemporaneous (scenario inputs), so this measures conditional association, not forecasting skill."}


def _daily_frame(series):
    n = series["NIFTY50"]
    df = pd.DataFrame({"nifty": n})
    df["r"] = df["nifty"].pct_change() * 100
    # US/London/NY-noon data dated t-1 are known before the Indian open on t.
    for sym, col in (("SP500", "sp"), ("BRENT", "brent"), ("USDINR", "inr"), ("VIX", "vix")):
        s = series[sym]
        ch = s.diff() if sym == "VIX" else s.pct_change() * 100
        ch = ch.where(np.isfinite(ch))
        prev = []
        for d in df.index:
            sub = ch[ch.index < d]
            prev.append(sub.iloc[-1] if len(sub) else np.nan)
        df[f"{col}_prev"] = prev
    df["r_prev"] = df["r"].shift(1)
    return df[(df.index >= RESEARCH_START) & (df.index <= DATA_END)]


def experiment_b1(series) -> dict:
    df = _daily_frame(series).dropna()
    feats = ["sp_prev", "brent_prev", "inr_prev", "vix_prev", "r_prev"]
    years = sorted({d.year for d in df.index})
    out, ys, ps, zs, ms = {}, [], [], [], []
    for yr in years[3:]:
        tr = df[[d.year < yr for d in df.index]]
        te = df[[d.year == yr for d in df.index]]
        if len(te) == 0:
            continue
        f, *_ = ridge_fit(tr[feats].values, tr["r"].values, lam=10.0)
        p = f(te[feats].values)
        ys += list(te["r"].values); ps += list(p); zs += [0.0] * len(te); ms += [tr["r"].mean()] * len(te)
        out[str(yr)] = metrics(te["r"].values, p)
    _, w, *_ = ridge_fit(df[feats].values, df["r"].values, lam=10.0)
    return {"description": "Daily walk-forward ridge: Nifty return on day t using only information available before the Indian open (US/London/NY-noon data dated t-1, Nifty t-1). Train on all prior years, test each year.",
            "features": feats, "test_years": list(out), "per_year": out, "model_all_test": metrics(ys, ps),
            "baseline_zero": metrics(ys, zs), "baseline_train_mean": metrics(ys, ms),
            "full_sample_coefficients_per_1sd": dict(zip(["intercept", *feats], [round(float(v), 4) for v in w])),
            "note": "October 2026 is incomplete (data to 2026-10-09)."}


def experiment_b2(series, event_windows: set[date]) -> dict:
    """Non-overlapping 5-session blocks: Nifty 5d return vs contemporaneous 5d shocks."""
    n = series["NIFTY50"]
    n = n[(n.index >= RESEARCH_START) & (n.index <= DATA_END)]
    idx = list(n.index)
    rows = []
    for i in range(0, len(idx) - 5, 5):
        d0, d1 = idx[i], idx[i + 5]
        rec = {"start": d0, "end": d1, "y": (n[d1] / n[d0] - 1) * 100}
        for sym, key, kind in (("BRENT", "brent", "pct"), ("SP500", "sp", "pct"), ("USDINR", "inr", "pct"), ("UST10Y", "ust", "bp")):
            s = series[sym]
            _, a = _last_on_or_before(s, d0)
            _, b = _last_on_or_before(s, d1)
            rec[key] = None if a is None or b is None or (kind == "pct" and a <= 0) else ((b - a) * 100 if kind == "bp" else (b / a - 1) * 100)
        rec["event_block"] = any(d0 < d <= d1 for d in event_windows)
        rows.append(rec)
    df = pd.DataFrame(rows).dropna()
    feats = ["brent", "sp", "inr", "ust"]
    years = sorted({d.year for d in df.start})
    ys, ps, zs, flags = [], [], [], []
    for yr in years[3:]:
        tr, te = df[[d.year < yr for d in df.start]], df[[d.year == yr for d in df.start]]
        f, *_ = ridge_fit(tr[feats].values, tr["y"].values, lam=5.0)
        ys += list(te["y"]); ps += list(f(te[feats].values)); zs += [0.0] * len(te); flags += list(te["event_block"])
    ys, ps, zs, flags = map(np.asarray, (ys, ps, zs, flags))
    _, w, *_ = ridge_fit(df[feats].values, df["y"].values, lam=5.0)
    ss_res, ss_tot = float(np.sum((ys - ps) ** 2)), float(np.sum((ys - ys.mean()) ** 2))
    return {"description": "Walk-forward ridge on non-overlapping 5-session blocks: Nifty 5d return vs contemporaneous Brent, S&P 500, USD/INR (%) and US10Y (bp) changes. A scenario-sensitivity model, not a forecaster.",
            "n_blocks": int(len(df)), "n_test_blocks": int(len(ys)), "features": feats,
            "model_all_test": metrics(ys, ps), "baseline_zero": metrics(ys, zs),
            "out_of_sample_R2": round(1 - ss_res / ss_tot, 4),
            "model_event_blocks": metrics(ys[flags], ps[flags]) if flags.any() else None,
            "model_non_event_blocks": metrics(ys[~flags], ps[~flags]),
            "full_sample_coefficients_per_1sd": dict(zip(["intercept", *feats], [round(float(v), 4) for v in w])),
            "feature_sd_full_sample": {f_: round(float(df[f_].std()), 4) for f_ in feats}}


def associations(ret: pd.DataFrame) -> pd.DataFrame:
    """Sign agreement of Indian assets with oil shocks across events where |Brent 1d| >= 2%."""
    b = ret[(ret.asset_symbol == "BRENT") & (ret.window_trading_days == 1) & (ret.window_status == "AVAILABLE")]
    shock = b[b.percentage_return.abs() >= 2][["event_id", "percentage_return"]].rename(columns={"percentage_return": "brent_1d"})
    rows = []
    for tgt in ["NIFTY50", "USDINR", "ONGC", "IOC", "BPCL", "INDIGO", "ASIANPAINT", "RELIANCE", "SP500"]:
        for k in (1, 5):
            t = ret[(ret.asset_symbol == tgt) & (ret.window_trading_days == k) & (ret.window_status == "AVAILABLE")]
            m = shock.merge(t[["event_id", "percentage_return"]], on="event_id").dropna()
            if len(m) < 3:
                continue
            same = float(np.mean(np.sign(m.brent_1d) == np.sign(m.percentage_return)))
            corr = float(np.corrcoef(m.brent_1d, m.percentage_return)[0, 1]) if len(m) > 2 else None
            rows.append({"shock": "BRENT 1d move, |move|>=2%", "target": tgt, "target_window_days": k, "n_events": len(m),
                         "share_same_sign": round(same, 3), "pearson_corr": round(corr, 3) if corr is not None else None,
                         "event_ids": ";".join(m.event_id)})
    # Market-model CAR (stock vs NIFTY 50) for large oil shocks: |Brent 5d| >= 8%
    b5 = ret[(ret.asset_symbol == "BRENT") & (ret.window_trading_days == 5) & (ret.window_status == "AVAILABLE")]
    big = b5[b5.percentage_return.abs() >= 8][["event_id", "percentage_return"]].rename(columns={"percentage_return": "brent_5d"})
    for tgt in ["ONGC", "IOC", "BPCL", "INDIGO", "ASIANPAINT", "RELIANCE", "HINDALCO"]:
        t = ret[(ret.asset_symbol == tgt) & (ret.window_trading_days == 5)][["event_id", "car_market_model_pct", "car_t_stat"]]
        m = big.merge(t, on="event_id").dropna()
        if len(m) < 3:
            continue
        same = float(np.mean(np.sign(m.brent_5d) == np.sign(m.car_market_model_pct)))
        sig = int(np.sum(m.car_t_stat.abs() >= 2))
        rows.append({"shock": "BRENT 5d move, |move|>=8%", "target": f"{tgt} (5d market-model CAR vs NIFTY 50)",
                     "target_window_days": 5, "n_events": len(m), "share_same_sign": round(same, 3),
                     "pearson_corr": round(float(np.corrcoef(m.brent_5d, m.car_market_model_pct)[0, 1]), 3),
                     "n_abs_t_ge_2": sig, "event_ids": ";".join(m.event_id)})
    return pd.DataFrame(rows)


def _add_group_counts(df: pd.DataFrame) -> pd.DataFrame:
    vg = validation_groups()
    df["n_independent_validation_groups"] = [len({vg[e] for e in ids.split(";")}) for ids in df.event_ids]
    return df


def main() -> None:
    series = load_series()
    ft = build_feature_table(series)
    ft.to_csv(OUT / "model_feature_table.csv", index=False)
    pd.DataFrame(SCHEMA, columns=["feature_name", "definition", "data_type", "unit", "source", "availability_timestamp",
                                  "missing_data_policy", "event_specific", "available_at_prediction_time", "role"]
                 ).to_csv(OUT / "model_feature_schema.csv", index=False)
    ret = pd.read_csv(OUT / "event_market_returns.csv")
    _add_group_counts(associations(ret)).to_csv(OUT / "channel_associations.csv", index=False)
    ev_dates = {date.fromisoformat(str(d)) for d in ret[(ret.asset_symbol == "NIFTY50") & (ret.window_trading_days == 1)
                                                        & ret.window_end_date.notna()].window_end_date}
    results = {"experiment_A_event_level": experiment_a(ft), "experiment_B1_daily_predictive": experiment_b1(series),
               "experiment_B2_weekly_scenario_sensitivity": experiment_b2(series, ev_dates),
               "data_end": DATA_END.isoformat()}
    (OUT / "model_feasibility_results.json").write_text(json.dumps(results, indent=2))
    for k, v in results.items():
        if isinstance(v, dict):
            print(k, {kk: v[kk] for kk in v if kk.startswith(("model", "baseline", "out_of", "n_"))})


if __name__ == "__main__":
    main()
