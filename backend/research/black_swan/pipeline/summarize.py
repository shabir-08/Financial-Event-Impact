"""Generate output/key_event_summary.md (tables embedded in REPORT.md) from the computed CSVs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"


def fmt(v, kind="pct"):
    if v is None or pd.isna(v):
        return "NA"
    return f"{v:+.2f}%" if kind == "pct" else f"{v:+.0f}bp"


def main() -> None:
    ret = pd.read_csv(OUT / "event_market_returns.csv")
    em = pd.read_csv(OUT / "events_master.csv")
    sev = pd.read_csv(OUT / "event_severity_measured.csv")

    def get(ev, sym, k, field="percentage_return"):
        m = ret[(ret.event_id == ev) & (ret.asset_symbol == sym) & (ret.window_trading_days == k)]
        if not len(m) or m.iloc[0].window_status != "AVAILABLE":
            return None
        return m.iloc[0][field]

    lines = ["| Event | Class | First India session | NIFTY 1d | NIFTY 5d | NIFTY 20d | Brent 5d | USD/INR 5d | US10Y 5d | S&P 1d | Severity | Concurrent events (5d) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in em.itertuples():
        n1 = ret[(ret.event_id == e.event_id) & (ret.asset_symbol == "NIFTY50") & (ret.window_trading_days == 1)].iloc[0]
        conf = ret[(ret.event_id == e.event_id) & (ret.asset_symbol == "NIFTY50") & (ret.window_trading_days == 5)].iloc[0].concurrent_events_in_window
        lines.append(f"| {e.event_id} {e.event_name[:48]} | {e.black_swan_classification[0]} | {n1.window_start_date if isinstance(n1.window_start_date, str) else 'NA'} | "
                     f"{fmt(get(e.event_id,'NIFTY50',1))} | {fmt(get(e.event_id,'NIFTY50',5))} | {fmt(get(e.event_id,'NIFTY50',20))} | "
                     f"{fmt(get(e.event_id,'BRENT',5))} | {fmt(get(e.event_id,'USDINR',5))} | {fmt(get(e.event_id,'UST10Y',5,'change_bp'),'bp')} | "
                     f"{fmt(get(e.event_id,'SP500',1))} | {e.event_severity if isinstance(e.event_severity, str) else 'NA'} | {conf if isinstance(conf, str) else ''} |")
    (OUT / "key_event_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # India stock reactions for oil-related events (market-model CAR, 5d)
    oil_events = ["EV013", "EV021", "EV043", "EV046", "EV047", "EV048", "EV049", "EV050"]
    stocks = ["ONGC", "IOC", "BPCL", "RELIANCE", "INDIGO", "ASIANPAINT", "HINDALCO"]
    l2 = ["| Event | Brent 5d | " + " | ".join(stocks) + " |", "|---|---|" + "---|" * len(stocks)]
    for ev in oil_events:
        cells = []
        for s in stocks:
            m = ret[(ret.event_id == ev) & (ret.asset_symbol == s) & (ret.window_trading_days == 5)].iloc[0]
            cells.append("NA" if pd.isna(m.car_market_model_pct) else f"{m.car_market_model_pct:+.1f} (t={m.car_t_stat:+.1f})")
        l2.append(f"| {ev} | {fmt(get(ev,'BRENT',5))} | " + " | ".join(cells) + " |")
    (OUT / "oil_event_india_car.md").write_text("\n".join(l2) + "\n", encoding="utf-8")
    print("\n".join(lines[:6])); print("\n".join(l2))
    print(sev.severity_tier.value_counts().to_string())


if __name__ == "__main__":
    main()
