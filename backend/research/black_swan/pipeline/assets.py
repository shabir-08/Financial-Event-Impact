"""Asset registry: every series the research pipeline downloads, with provenance metadata.

close_local / open_local are the times (exchange-local) used to decide whether an event's
information time falls before, during or after a session. Times marked approx_close=True are
approximations (futures settlement, FX fixing conventions) and produce a data-quality flag.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetDef:
    symbol: str  # internal symbol used in all outputs
    name: str
    asset_class: str  # EQUITY_INDEX | EQUITY | COMMODITY | FX | RATE | VOLATILITY
    market: str
    currency: str
    source: str  # yahoo_chart | fred | moex_iss
    source_id: str
    tz: str
    open_local: str
    close_local: str
    value_kind: str = "PRICE"  # PRICE | YIELD_PCT | INDEX_LEVEL
    adjustment: str = "none (price index)"
    approx_close: bool = False
    group: str = "global"
    notes: str = ""


A = AssetDef
ASSETS: list[AssetDef] = [
    # ---- Indian equity indices (Yahoo; price indices, no dividends)
    A("NIFTY50", "NIFTY 50", "EQUITY_INDEX", "NSE", "INR", "yahoo_chart", "^NSEI", "Asia/Kolkata", "09:15", "15:30", group="india"),
    A("NIFTYBANK", "NIFTY Bank", "EQUITY_INDEX", "NSE", "INR", "yahoo_chart", "^NSEBANK", "Asia/Kolkata", "09:15", "15:30", group="india"),
    A("NIFTYIT", "NIFTY IT", "EQUITY_INDEX", "NSE", "INR", "yahoo_chart", "^CNXIT", "Asia/Kolkata", "09:15", "15:30", group="india"),
    A("NIFTYPHARMA", "NIFTY Pharma", "EQUITY_INDEX", "NSE", "INR", "yahoo_chart", "^CNXPHARMA", "Asia/Kolkata", "09:15", "15:30", group="india"),
    # ---- Indian stocks (Yahoo adjusted close: split + dividend back-adjusted as of retrieval date)
    *[A(sym.replace(".NS", ""), name, "EQUITY", "NSE", "INR", "yahoo_chart", sym, "Asia/Kolkata", "09:15", "15:30",
        adjustment="Yahoo adjclose (splits+dividends, back-adjusted at retrieval)", group="india_stock", notes=note)
      for sym, name, note in [
          ("ONGC.NS", "Oil and Natural Gas Corporation", "upstream oil"),
          ("IOC.NS", "Indian Oil Corporation", "oil marketing / refining"),
          ("BPCL.NS", "Bharat Petroleum", "oil marketing / refining"),
          ("RELIANCE.NS", "Reliance Industries", "refining + diversified; 1:1 bonus 2024 (adjusted)"),
          ("INDIGO.NS", "InterGlobe Aviation (IndiGo)", "aviation; fuel-cost exposure"),
          ("ASIANPAINT.NS", "Asian Paints", "crude-derived input costs"),
          ("SBIN.NS", "State Bank of India", "banking"),
          ("ICICIBANK.NS", "ICICI Bank", "banking"),
          ("HDFCBANK.NS", "HDFC Bank", "banking; merged with HDFC Ltd on 2023-07-01 (structural break)"),
          ("TCS.NS", "Tata Consultancy Services", "IT services exporter (USD revenue)"),
          ("INFY.NS", "Infosys", "IT services exporter (USD revenue)"),
          ("LT.NS", "Larsen & Toubro", "capital goods / infrastructure"),
          ("HINDALCO.NS", "Hindalco Industries", "aluminium (LME-linked)"),
          ("SUNPHARMA.NS", "Sun Pharmaceutical", "pharma exporter"),
      ]],
    # ---- Global equity indices
    A("SP500", "S&P 500", "EQUITY_INDEX", "NYSE/Nasdaq", "USD", "yahoo_chart", "^GSPC", "America/New_York", "09:30", "16:00"),
    A("NASDAQ", "Nasdaq Composite", "EQUITY_INDEX", "Nasdaq", "USD", "yahoo_chart", "^IXIC", "America/New_York", "09:30", "16:00"),
    A("SSE", "SSE Composite (Shanghai)", "EQUITY_INDEX", "SSE", "CNY", "yahoo_chart", "000001.SS", "Asia/Shanghai", "09:30", "15:00"),
    A("TA35", "TA-35 (Tel Aviv)", "EQUITY_INDEX", "TASE", "ILS", "yahoo_chart", "TA35.TA", "Asia/Jerusalem", "09:59", "17:25",
      approx_close=True, notes="TASE traded Sun-Thu until early 2026 then moved to Mon-Fri; session dates taken from the data"),
    A("STOXX50", "EURO STOXX 50", "EQUITY_INDEX", "Eurex/STOXX", "EUR", "yahoo_chart", "^STOXX50E", "Europe/Zurich", "09:00", "17:30"),
    A("IMOEX", "MOEX Russia Index", "EQUITY_INDEX", "MOEX", "RUB", "moex_iss", "IMOEX", "Europe/Moscow", "10:00", "18:50",
      approx_close=True, notes="Main-session close; trading suspended 2022-02-28 to 2022-03-23; foreign access restricted since 2022"),
    A("RTSI", "RTS Index (USD)", "EQUITY_INDEX", "MOEX", "USD", "moex_iss", "RTSI", "Europe/Moscow", "10:00", "18:50",
      approx_close=True, notes="USD-denominated; same suspension as IMOEX"),
    # ---- Commodities
    A("BRENT", "Brent crude spot (Europe, FOB)", "COMMODITY", "Spot (EIA via FRED)", "USD", "fred", "DCOILBRENTEU",
      "Europe/London", "08:00", "16:30", approx_close=True, notes="Spot assessment; FRED/EIA daily; no futures roll artefacts"),
    A("WTI", "WTI crude spot (Cushing)", "COMMODITY", "Spot (EIA via FRED)", "USD", "fred", "DCOILWTICO",
      "America/New_York", "09:00", "14:30", approx_close=True, notes="Went negative on 2020-04-20: percentage returns undefined"),
    A("HENRYHUB", "Henry Hub natural gas spot", "COMMODITY", "Spot (EIA via FRED)", "USD", "fred", "DHHNGSP",
      "America/New_York", "08:00", "12:00", approx_close=True),
    A("GOLD", "Gold futures (COMEX front month)", "COMMODITY", "COMEX", "USD", "yahoo_chart", "GC=F",
      "America/New_York", "18:00", "17:00", approx_close=True, adjustment="continuous front-month; roll jumps not removed"),
    # ---- FX (USD per ... quoted as local currency per USD)
    A("USDINR", "USD/INR (Fed H.10 noon buying rate)", "FX", "FRED H.10", "INR", "fred", "DEXINUS",
      "America/New_York", "12:00", "12:00", approx_close=True, notes="Official noon NY rate; not an onshore Indian close"),
    A("USDCNY", "USD/CNY (Fed H.10 noon buying rate)", "FX", "FRED H.10", "CNY", "fred", "DEXCHUS",
      "America/New_York", "12:00", "12:00", approx_close=True, notes="Managed currency; onshore band"),
    A("USDRUB", "USD/RUB (Yahoo)", "FX", "Yahoo FX", "RUB", "yahoo_chart", "RUB=X", "Europe/London", "00:00", "23:59",
      approx_close=True, notes="Capital controls and sanctions from 2022 distort quotes; Western quotes thin/unreliable"),
    A("USDILS", "USD/ILS (Yahoo)", "FX", "Yahoo FX", "ILS", "yahoo_chart", "ILS=X", "Europe/London", "00:00", "23:59",
      approx_close=True),
    A("DXY", "US Dollar Index", "FX", "ICE", "USD", "yahoo_chart", "DX-Y.NYB", "America/New_York", "18:00", "17:00",
      approx_close=True),
    # ---- Rates / volatility
    A("UST10Y", "US 10-year Treasury yield (constant maturity)", "RATE", "US Treasury via FRED", "USD", "fred", "DGS10",
      "America/New_York", "08:00", "16:00", value_kind="YIELD_PCT", approx_close=True),
    A("UST2Y", "US 2-year Treasury yield (constant maturity)", "RATE", "US Treasury via FRED", "USD", "fred", "DGS2",
      "America/New_York", "08:00", "16:00", value_kind="YIELD_PCT", approx_close=True),
    A("FEDFUNDS", "Effective federal funds rate", "RATE", "FRB NY via FRED", "USD", "fred", "DFF",
      "America/New_York", "00:00", "23:59", value_kind="YIELD_PCT", approx_close=True),
    A("VIX", "CBOE VIX", "VOLATILITY", "CBOE via FRED", "USD", "fred", "VIXCLS", "America/New_York", "09:30", "16:15",
      value_kind="INDEX_LEVEL"),
]

#: Monthly series kept separately (cannot be used for daily event windows).
MONTHLY = [
    A("IN10Y_M", "India 10-year government bond yield (monthly, OECD MEI)", "RATE", "OECD via FRED", "INR", "fred",
      "INDIRLTLT01STM", "Asia/Kolkata", "00:00", "23:59", value_kind="YIELD_PCT",
      notes="MONTHLY average only - no daily free source retrieved"),
]

BY_SYMBOL = {a.symbol: a for a in [*ASSETS, *MONTHLY]}

#: Series sought but not retrieved (documented in data_sources.csv).
UNAVAILABLE = [
    ("NIFTY Financial Services", "Yahoo NIFTY_FIN_SERVICE.NS returned only the latest bar", "B",
     "NSE India historical index data (download from niftyindices.com; terms apply)"),
    ("NIFTY Energy / NIFTY Metal", "Yahoo ^CNXENERGY / ^CNXMETAL returned only the latest bar", "B",
     "niftyindices.com historical data"),
    ("India 10Y G-Sec daily yield", "No free daily API retrieved; only OECD monthly average via FRED", "B",
     "RBI DBIE / CCIL / FBIL benchmark yields (manual download)"),
    ("RBI repo rate history", "Not downloaded; policy dates taken from news/RBI statements", "B", "RBI press releases / DBIE"),
    ("Baltic Dry Index / container freight (Drewry WCI, SCFI, Freightos FBX)", "Proprietary or no free API; not retrieved",
     "E", "Baltic Exchange, Drewry, SSE (licensed)"),
    ("Tanker freight rates (TD3C etc.)", "Proprietary; not retrieved", "E", "Baltic Exchange / Argus / Platts"),
    ("NY Fed Global Supply Chain Pressure Index", "Monthly, Excel download; not retrieved", "B",
     "https://www.newyorkfed.org/research/policy/gscpi"),
    ("Nifty 50 constituent history", "Index membership changes not retrieved; stock basket may have survivorship bias", "B",
     "NSE index reconstitution circulars"),
]
