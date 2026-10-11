"""Download every series in assets.py and cache it under data/raw/ (one CSV per asset).

Sources: Yahoo chart endpoint (unofficial; research use), FRED CSV (official), MOEX ISS (official).
Nothing is interpolated or filled: rows are exactly what each provider returned (null closes dropped).
Run: python pipeline/fetch.py   (add --refresh to re-download)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from assets import ASSETS, MONTHLY, AssetDef  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
START = "2015-09-01"  # ~250 sessions before the research period for market-model estimation
UA = {"User-Agent": "Mozilla/5.0 (financial-impact-graph research)"}


def _get(client: httpx.Client, url: str, **kw) -> httpx.Response:
    for attempt in range(4):
        r = client.get(url, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        return r
    return r


def fetch_yahoo(client: httpx.Client, a: AssetDef) -> pd.DataFrame:
    p1 = int(datetime.fromisoformat(START).replace(tzinfo=timezone.utc).timestamp())
    p2 = int(time.time())
    r = _get(client, f"https://query1.finance.yahoo.com/v8/finance/chart/{a.source_id}",
             params={"period1": p1, "period2": p2, "interval": "1d", "events": "div,splits"}, headers=UA, timeout=60)
    res = (r.json().get("chart") or {}).get("result")
    if not res:
        return pd.DataFrame()
    res = res[0]
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    tz = res["meta"].get("exchangeTimezoneName") or a.tz
    dates = [pd.Timestamp(t, unit="s", tz="UTC").tz_convert(tz).date() for t in ts]
    df = pd.DataFrame({"date": dates, "close": q.get("close"), "adjclose": adj if adj else q.get("close")})
    df = df.dropna(subset=["close"]).drop_duplicates("date", keep="last")
    # Weekend-dated bars are provider artefacts for markets that do not trade at weekends.
    if a.tz not in ("Asia/Jerusalem",):
        df = df[[d.weekday() < 5 for d in df["date"]]]
    df["value"] = df["adjclose"] if "adjclose" in a.adjustment else df["close"]
    return df[["date", "value", "close"]]


def fetch_fred(client: httpx.Client, a: AssetDef) -> pd.DataFrame:
    r = _get(client, "https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": a.source_id, "cosd": START},
             timeout=120, follow_redirects=True)
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")  # FRED uses '.' for missing
    df = df.dropna(subset=["value"])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["close"] = df["value"]
    return df


def fetch_moex(client: httpx.Client, a: AssetDef) -> pd.DataFrame:
    rows, start = [], 0
    while True:
        r = _get(client, f"https://iss.moex.com/iss/history/engines/stock/markets/index/securities/{a.source_id}.json",
                 params={"from": START, "start": start, "iss.meta": "off"}, timeout=60)
        h = r.json()["history"]
        if not h["data"]:
            break
        cols = h["columns"]
        rows += [dict(zip(cols, x)) for x in h["data"]]
        start += len(h["data"])
    df = pd.DataFrame(rows)
    df = df[["TRADEDATE", "CLOSE"]].rename(columns={"TRADEDATE": "date", "CLOSE": "value"}).dropna()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["close"] = df["value"]
    return df.drop_duplicates("date", keep="last")


FETCHERS = {"yahoo_chart": fetch_yahoo, "fred": fetch_fred, "moex_iss": fetch_moex}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with httpx.Client() as client:
        for a in [*ASSETS, *MONTHLY]:
            path = RAW / f"{a.symbol}.csv"
            if path.exists() and not args.refresh:
                manifest[a.symbol] = json.loads((RAW / "manifest.json").read_text()).get(a.symbol, {}) \
                    if (RAW / "manifest.json").exists() else {}
                print(f"cached  {a.symbol}")
                continue
            try:
                df = FETCHERS[a.source](client, a)
                status = "RETRIEVED" if not df.empty else "EMPTY"
            except Exception as exc:  # noqa: BLE001 - record and continue
                df, status = pd.DataFrame(columns=["date", "value", "close"]), f"ERROR: {type(exc).__name__}: {exc}"[:300]
            df.to_csv(path, index=False)
            manifest[a.symbol] = {"status": status, "rows": int(len(df)),
                                  "first": str(df["date"].min()) if len(df) else None,
                                  "last": str(df["date"].max()) if len(df) else None,
                                  "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            print(f"{status:9s} {a.symbol:12s} rows={len(df)} {manifest[a.symbol]['first']}..{manifest[a.symbol]['last']}")
            time.sleep(0.3)
    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
