"""Write the remaining deliverables: events_master.csv, market_observations.csv, economic_channels.csv,
data_sources.csv, data_quality_report.csv (run after fetch.py, compute.py, features_model.py)."""

from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from assets import ASSETS, MONTHLY, UNAVAILABLE  # noqa: E402
from compute import DATA_END, RESEARCH_START, load_series  # noqa: E402
from events import EVENTS, EXCLUDED  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT, RAW = ROOT / "output", ROOT / "data" / "raw"
RESEARCH_DATE = "2026-10-11"


def events_master() -> pd.DataFrame:
    sev = pd.read_csv(OUT / "event_severity_measured.csv")
    from features_model import validation_groups

    vg = validation_groups()
    df = pd.DataFrame(EVENTS)
    df["black_swan_classification"] = df["classification"].map({
        "A": "A Black Swan candidate", "B": "B Major geopolitical shock", "C": "C Macroeconomic or monetary-policy shock",
        "D": "D Financial-system crisis", "E": "E Commodity or supply-chain shock", "F": "F Other significant market-disrupting event"})
    df["validation_group"] = df["event_id"].map(vg)
    df = df.merge(sev, on="event_id", how="left")
    df["event_severity"] = df["severity_tier"]
    df["relevance_columns_basis"] = "analyst judgement (subjective) - see measured percentiles for data-based severity"
    df["research_date"] = RESEARCH_DATE
    first = ["event_id", "event_name", "event_start_date", "event_end_date", "info_time_utc", "time_precision", "country",
             "countries_involved", "event_category", "event_subcategory", "event_description", "trigger_type",
             "unexpectedness", "novelty", "event_severity", "economic_channels", "global_relevance", "india_relevance",
             "oil_market_relevance", "currency_market_relevance", "equity_market_relevance", "bond_market_relevance",
             "shipping_market_relevance", "black_swan_classification", "classification_rationale", "data_availability",
             "episode_id", "parent_event_id", "relation_type", "validation_group", "source_urls"]
    rest = [c for c in df.columns if c not in first and c != "classification"]
    return df[first + rest]


def market_observations(series) -> pd.DataFrame:
    rows = []
    for a in [*ASSETS, *MONTHLY]:
        s = series[a.symbol]
        s = s[s.index <= DATA_END]
        rows.append(pd.DataFrame({"date": s.index, "asset_symbol": a.symbol, "value": s.values, "value_kind": a.value_kind,
                                  "currency": a.currency, "frequency": "monthly" if a in MONTHLY else "daily",
                                  "adjustment": a.adjustment, "source": f"{a.source}:{a.source_id}",
                                  "in_research_period": [d >= RESEARCH_START for d in s.index]}))
    return pd.concat(rows, ignore_index=True)


def data_sources() -> pd.DataFrame:
    manifest = json.loads((RAW / "manifest.json").read_text())
    urls = {"yahoo_chart": "https://query1.finance.yahoo.com/v8/finance/chart/{id}",
            "fred": "https://fred.stlouisfed.org/series/{id}",
            "moex_iss": "https://iss.moex.com/iss/history/engines/stock/markets/index/securities/{id}.json"}
    lic = {"yahoo_chart": "Unofficial endpoint; Yahoo terms restrict use - research/demo only, do not redistribute raw data",
           "fred": "FRED public data; check each series' copyright notice (e.g. ICE/CBOE-sourced series carry restrictions)",
           "moex_iss": "MOEX ISS public API; MOEX terms apply; non-commercial use"}
    rows = []
    for a in [*ASSETS, *MONTHLY]:
        m = manifest.get(a.symbol, {})
        rows.append({"dataset": a.name, "internal_symbol": a.symbol, "provider": a.source, "instrument_id": a.source_id,
                     "url": urls[a.source].format(id=a.source_id), "frequency": "monthly" if a in MONTHLY else "daily",
                     "date_coverage": f"{m.get('first')}..{m.get('last')}", "units": a.value_kind,
                     "currency": a.currency, "time_zone": a.tz, "session_close_local": a.close_local,
                     "adjustment_method": a.adjustment, "missing_data_limitations": a.notes or "see data_quality_report.csv",
                     "access_method": "HTTP GET (scripted, pipeline/fetch.py)", "api_requirements": "none (no key)",
                     "licensing": lic[a.source], "retrieval_status": m.get("status"), "retrieved_at_utc": m.get("retrieved_at_utc"),
                     "evidence_class": "A (downloaded and inspected)" if m.get("status") == "RETRIEVED" else "E (unavailable)"})
    for name, why, cls, where in UNAVAILABLE:
        rows.append({"dataset": name, "provider": where, "missing_data_limitations": why, "retrieval_status": "NOT_RETRIEVED",
                     "evidence_class": {"B": "B (available from a source, not downloaded)", "E": "E (unavailable)"}[cls]})
    rows.append({"dataset": "Event dates/times and descriptions", "provider": "news, official and reference sources (see events_master.source_urls)",
                 "access_method": "web search 2026-10-11", "evidence_class": "C (transcribed from published reports)",
                 "missing_data_limitations": "Times of day are often approximate (time_precision column)"})
    return pd.DataFrame(rows)


def quality_report(series) -> pd.DataFrame:
    rows = []
    for a in [*ASSETS, *MONTHLY]:
        s = series[a.symbol]
        s = s[(s.index >= RESEARCH_START) & (s.index <= DATA_END)]
        dates = list(s.index)
        gaps = []
        for d0, d1 in zip(dates, dates[1:]):
            wd = int(np.busday_count(d0 + timedelta(days=1), d1))
            if wd >= 3 and a not in MONTHLY:
                gaps.append(f"{d0}->{d1} ({wd} weekdays)")
        issues = []
        if (s <= 0).any():
            issues.append(f"{int((s <= 0).sum())} non-positive values (returns undefined there)")
        if a.approx_close:
            issues.append("session close time approximated")
        if a.source == "yahoo_chart" and "adjclose" in a.adjustment:
            issues.append("back-adjusted prices change when new corporate actions occur")
        rows.append({"scope": "asset", "item": a.symbol, "rows_in_research_period": len(s),
                     "first": str(dates[0]) if dates else None, "last": str(dates[-1]) if dates else None,
                     "gaps_of_3plus_weekdays": len(gaps), "largest_gaps": "; ".join(sorted(gaps, key=lambda g: -int(g.split("(")[1].split()[0]))[:3]),
                     "issues": "; ".join(issues + ([a.notes] if a.notes else []))})
    ret = pd.read_csv(OUT / "event_market_returns.csv")
    for flag in ["NONPOSITIVE_PRICE_RETURN_UNDEFINED", "WINDOW_SPANS_TRADING_GAP", "STALE_BASELINE_MARKET_CLOSED_OR_GAP",
                 "INFO_DURING_SESSION", "EVENT_TIME_DATE_ONLY", "NOT_YET_ELAPSED", "NOT_YET_PUBLISHED_BY_SOURCE",
                 "HDFC_MERGER_STRUCTURAL_BREAK_NEARBY"]:
        m = ret[ret.data_quality_flag.str.contains(flag, na=False)]
        rows.append({"scope": "event_window_flag", "item": flag, "rows_in_research_period": len(m),
                     "issues": "events: " + ";".join(sorted(m.event_id.unique())[:20])})
    known = [
        ("source_discrepancy", "EV001 demonetisation: a source states indices 'fell over 6%' on 2016-11-09; Yahoo closing data show NIFTY 50 -1.31% (likely an intraday figure in the source)."),
        ("source_discrepancy", "EV022 SWIFT sanctions: sources report the rouble down ~26-40% on 2022-02-28; Yahoo RUB=X shows -1.9% - Western RUB quotes were unreliable under capital controls. Treat USDRUB 2022 windows as unusable."),
        ("source_discrepancy", "EV046: Brent spot (FRED) +6.5% on 2025-10-23 vs Brent futures +5.4% reported - spot vs futures difference."),
        ("market_closure", "MOEX equity trading suspended 2022-02-28..2022-03-23: IMOEX/RTSI windows for EV021/EV022 span the suspension."),
        ("market_closure", "TASE: Sunday sessions until early 2026; Yahoo TA35 history has fewer rows than other indices - check gaps before use."),
        ("survivorship", "Stock basket chosen in 2026 from currently large liquid names; index-membership history not retrieved."),
        ("structural_break", "HDFC Bank merged with HDFC Ltd on 2023-07-01; market-model estimates spanning that date are affected."),
        ("incomplete_period", "October 2026 is incomplete (data to 2026-10-09; FRED FX to 2026-10-02, Brent to 2026-10-06). EV051 windows mostly not elapsed."),
        ("confounding", "Unlisted scheduled events (FOMC/MPC meetings, earnings, macro releases) were NOT screened; only dataset events are flagged in concurrent_events_in_window."),
    ]
    for scope, text in known:
        rows.append({"scope": scope, "item": text.split(":")[0], "issues": text})
    return pd.DataFrame(rows)


CHANNELS = [
    # id, source, target, type, direction, mechanism, events, evidence, url, date, evidence_type, limitations
    ("R01", "Strait of Hormuz closure", "Brent crude", "INCREASES", "POSITIVE",
     "Loss of Gulf seaborne supply raises the crude clearing price", "EV047",
     "EIA: Brent rose from $61 to $118/b in Q1 2026 after Hormuz traffic stopped; measured Brent spot +8.3% (1d) and +70.3% (20d) after EV047",
     "https://www.eia.gov/todayinenergy/detail.php?id=67424", "2026", "Directly reported relationship",
     "Single episode; other supply responses (SPR releases, pipelines) not modelled"),
    ("R02", "Middle East conflict escalation", "Brent crude", "MAY_INCREASE", "POSITIVE",
     "Risk premium on supply/transit disruption", "EV030;EV036;EV043;EV044;EV050",
     "Sources report oil +3-9% after these escalations; measured Brent moves in event_market_returns.csv",
     "https://www.semafor.com/article/06/13/2025/global-oil-prices-soar-after-israel-strikes-iran", "2025-06-13",
     "Directly reported relationship", "Magnitude varies with whether supply is actually hit; premium often fades (EV032)"),
    ("R03", "Brent crude", "India oil import bill", "INCREASES", "POSITIVE",
     "India imports most of its crude; higher prices raise the bill for given volumes", "EV046;EV047",
     "Carnegie: price escalation projected to raise India's annual oil import expenditure by $6-7bn (Rosneft/Lukoil sanctions context)",
     "https://carnegieendowment.org/russia-eurasia/posts/2025/11/the-impact-of-us-sanctions-and-tariffs-on-indias-russian-oil-imports",
     "2025-11", "Economically established mechanism", "Volume and discount effects (Russian crude) modify the bill"),
    ("R04", "Brent crude", "USD/INR", "MAY_INCREASE", "POSITIVE",
     "Higher import bill -> wider current-account deficit -> rupee pressure", "see channel_associations.csv",
     "Measured across 26 events with |Brent 1d|>=2%: USD/INR moved in the same direction as Brent in 46% (1d) / 54% (5d); corr -0.02 / 0.12",
     "output/channel_associations.csv", "2026-10-11", "Plausible but unverified hypothesis",
     "Event-window evidence does NOT confirm the channel at 1-5 day horizons (RBI intervention, risk-off flows dominate); events not independent"),
    ("R05", "Brent crude", "ONGC (upstream)", "MAY_INCREASE", "POSITIVE", "Higher realisations for producers",
     "see channel_associations.csv", "Same sign as Brent in 69% (1d) of 26 oil-shock events; corr 0.51 (1d)",
     "output/channel_associations.csv", "2026-10-11", "Empirically observed association",
     "Windfall taxes and subsidy sharing cap pass-through; 26 events from fewer independent episodes"),
    ("R06", "Brent crude", "Indian OMCs (IOC, BPCL)", "MAY_REDUCE", "NEGATIVE",
     "Administered retail fuel prices squeeze marketing margins when crude rises", "see channel_associations.csv",
     "Opposite sign to Brent in 62% (1d) of 26 oil-shock events but corr ~0 (0.03-0.08)",
     "output/channel_associations.csv", "2026-10-11", "Plausible but unverified hypothesis",
     "Weak and noisy at event horizons; government pricing decisions matter more"),
    ("R07", "Brent crude", "InterGlobe Aviation (IndiGo)", "MAY_REDUCE", "NEGATIVE", "Jet fuel is a major airline cost",
     "EV030;EV043", "Sources report airline shares fell after EV030 and EV043; measured: opposite sign to Brent in 62% (1d), corr -0.21 (1d) but +0.20 (5d)",
     "https://www.nationalheraldindia.com/international/global-airline-shares-fall-as-markets-react-to-attack-on-israel-by-hamas",
     "2023-10-09", "Directly reported relationship", "Indian evidence weak; direction flips by horizon; hedging/fare pass-through"),
    ("R08", "US yields / hawkish Fed surprise", "Emerging-market equities incl. India", "MAY_REDUCE", "NEGATIVE",
     "Higher US yields and USD pull portfolio capital from EMs", "EV002;EV024;EV025",
     "Source (2016): surge in US bond yields after the election weighed on EMs like India",
     "https://www.business-standard.com/amp/article/markets/demonetisation-blues-make-markets-see-red-sensex-nears-6-month-low-116111501924_1.html",
     "2016-11-15", "Directly reported relationship", "Confounded with demonetisation in 2016; magnitude regime-dependent"),
    ("R09", "US equities (S&P 500)", "NIFTY 50", "INFLUENCES", "POSITIVE", "Global risk appetite / co-movement",
     "all", "Weekly walk-forward model: Nifty 5d return +0.92% per 1-sd (2.34%) S&P 500 5d move; strongest of the tested shocks",
     "output/model_feasibility_results.json", "2026-10-11", "Empirically observed association", "Co-movement, not causation"),
    ("R10", "USD/INR depreciation", "NIFTY 50", "INFLUENCES", "NEGATIVE", "Rupee weakness coincides with FPI outflows",
     "all", "Weekly model: Nifty 5d -0.71% per 1-sd (0.67%) rise in USD/INR, controlling for S&P, Brent, US10Y",
     "output/model_feasibility_results.json", "2026-10-11", "Empirically observed association", "Both driven by flows; direction of causality unclear"),
    ("R11", "US tariffs (broad)", "Global equities", "MAY_REDUCE", "NEGATIVE", "Growth/recession risk, supply-chain costs",
     "EV004;EV009;EV038", "Dow -724 pts (EV004); stocks fell ~12% before the April 2025 pause (EV038)",
     "https://www.betashares.com.au/advisers/insights/liberation-day-upended-markets/", "2025", "Directly reported relationship",
     "Policy reversals (EV039) can quickly unwind"),
    ("R12", "US secondary tariff on India", "Indian exporters / INR", "MAY_REDUCE", "NEGATIVE",
     "50% total tariff reduces export competitiveness", "EV045", "EO raising total tariff to 50% from 2025-08-27",
     "https://www.shapiro.com/alerts/us-imposes-additional-25-tariff-on-indian-imports-aug-6-2025/", "2025-08-06",
     "Plausible but unverified hypothesis", "Exporter-level data not collected; measured Nifty move small (see returns)"),
    ("R13", "Sanctions on Rosneft/Lukoil", "Indian imports of Russian crude", "REDUCES", "NEGATIVE",
     "Indian refiners pause purchases from SDN-listed suppliers", "EV046",
     "Major Indian and Chinese buyers paused December purchases; Reliance cut orders from sanctioned firms",
     "https://carnegieendowment.org/russia-eurasia/posts/2025/11/the-impact-of-us-sanctions-and-tariffs-on-indias-russian-oil-imports",
     "2025-11", "Directly reported relationship", "Volumes partly rerouted via non-sanctioned sellers"),
    ("R14", "US sanctions on Rusal", "Aluminium price", "INCREASES", "POSITIVE", "Supply risk from a major producer",
     "EV005", "LME aluminium rose; ~15% gain from start of April 2018 (sources)",
     "https://www.alcircle.com/news/rusal-s-shares-fall-and-lme-surges-on-us-sanctions-of-mr-deripaska-lme-to-continue-with-rusal-listing-30159",
     "2018-04", "Directly reported relationship", "LME aluminium series not retrieved; Hindalco link is a hypothesis (see returns)"),
    ("R15", "India-Pakistan military escalation", "NIFTY 50", "MAY_REDUCE", "NEGATIVE", "Risk premium",
     "EV007;EV008;EV040;EV041;EV042", "Sources: markets reacted mildly and recovered quickly after past conflicts; ceasefire day +3.8% (confounded with US-China truce)",
     "https://www.dtnext.in/news/business/india-pakistan-tensions-history-shows-sensex-bounced-back-stronger-after-every-conflict-831682",
     "2025-05", "Directly reported relationship", "Transient; small sample"),
    ("R16", "Israel war onset", "TA-35 and shekel", "REDUCES", "NEGATIVE", "Domestic risk premium, capital flight",
     "EV030", "TA-35 -6.5% on 2023-10-08, shekel 7-year low (sources); measured TA-35 window returns",
     "https://investmentnews.com/equities/oil-spikes-and-equities-fall-following-hamas-attack-on-israel/244284",
     "2023-10-09", "Directly reported relationship", "Bank of Israel intervention"),
    ("R17", "Red Sea shipping disruption", "Freight costs / Indian trade", "MAY_INCREASE", "POSITIVE",
     "Cape rerouting lengthens voyages", "EV031", "Carriers paused Red Sea transits (sources); freight series NOT retrieved",
     "https://www.argusmedia.com/en/news-and-insights/latest-market-news/2519660-maersk-hapag-lloyd-pause-shipments-through-the-red-sea",
     "2023-12-15", "Plausible but unverified hypothesis", "No freight data in dataset"),
    ("R18", "China stimulus surprise", "Indian equities (via FPI reallocation)", "MAY_REDUCE", "NEGATIVE",
     "Portfolio reallocation from India to China", "EV035", "Chinese stocks rallied most in 7 months (sources); FPI flow data NOT retrieved",
     "https://www.bloomberg.com/news/articles/2024-09-24/chinese-stocks-rally-most-in-seven-months-on-stimulus-blitz",
     "2024-09-24", "Plausible but unverified hypothesis", "Needs NSDL FPI flow data"),
    ("R19", "COVID lockdowns / demand collapse", "Crude oil price", "REDUCES", "NEGATIVE",
     "Demand collapse with storage constraints", "EV012;EV015;EV017;EV018",
     "CRS: WTI turned negative amid oversupply and demand drop", "https://www.everycrsreport.com/reports/IN11354.html",
     "2020-04-22", "Directly reported relationship", "Concurrent supply war (EV013)"),
    ("R20", "Domestic election surprise", "Indian banks / PSU stocks", "MAY_REDUCE", "NEGATIVE",
     "Policy-continuity uncertainty", "EV033", "Bank Nifty -7.95% on 2024-06-04 (sources; measured -7.95%)",
     "https://moneylife.in/article/nifty-sensex-crash-on-election-surprise-tuesday-closing-report/74316.html",
     "2024-06-04", "Directly reported relationship", "Single event"),
]


def channels() -> pd.DataFrame:
    def conf(evidence_type: str) -> str:
        # Defined rule (no invented numbers): reported AND measured-consistent -> HIGH; one of them -> MEDIUM; hypothesis -> LOW
        return {"Directly reported relationship": "MEDIUM", "Empirically observed association": "MEDIUM",
                "Economically established mechanism": "MEDIUM", "Plausible but unverified hypothesis": "LOW"}[evidence_type]

    cols = ["relationship_id", "source_entity", "target_entity", "relationship_type", "direction", "economic_mechanism",
            "event_id", "supporting_evidence", "source_url", "evidence_date", "evidence_type", "limitations"]
    df = pd.DataFrame(CHANNELS, columns=cols)
    # Evidence for oil -> Indian equity channels is filled from the computed associations (never hand-typed numbers).
    assoc = pd.read_csv(OUT / "channel_associations.csv")

    def a(tgt_prefix: str, shock_prefix: str, k: int):
        m = assoc[assoc.target.str.startswith(tgt_prefix) & assoc.shock.str.startswith(shock_prefix) & (assoc.target_window_days == k)]
        return m.iloc[0] if len(m) else None

    def raw_text(tgt):
        r1, r5 = a(tgt, "BRENT 1d", 1), a(tgt, "BRENT 1d", 5)
        return (f"Raw returns, {int(r1.n_events)} events with |Brent 1d|>=2%: same sign as Brent {r1.share_same_sign:.0%} (1d) / "
                f"{r5.share_same_sign:.0%} (5d); corr {r1.pearson_corr:+.2f} / {r5.pearson_corr:+.2f}") if r1 is not None else "NA"

    def car_text(tgt):
        c = a(tgt + " (5d market-model", "BRENT 5d", 5)
        return (f"Market-model CAR (5d) in {int(c.n_events)} large oil shocks (|Brent 5d|>=8%) from only "
                f"{int(c.n_independent_validation_groups)} independent validation groups: same sign as Brent "
                f"{c.share_same_sign:.0%}, corr {c.pearson_corr:+.2f}, |t|>=2 in {int(c.n_abs_t_ge_2)} ({c.event_ids})") if c is not None else "NA"

    upd = {"R04": raw_text("USDINR"),
           "R05": raw_text("ONGC") + ". " + car_text("ONGC"),
           "R06": "IOC: " + raw_text("IOC") + ". " + car_text("IOC") + ". BPCL: " + car_text("BPCL"),
           "R07": raw_text("INDIGO") + ". " + car_text("INDIGO") + ". Also reported: airline shares fell after EV030 (source URL)."}
    for rid, txt in upd.items():
        df.loc[df.relationship_id == rid, "supporting_evidence"] = txt
    df.loc[df.relationship_id.isin(["R06", "R07"]), "evidence_type"] = "Empirically observed association"
    df.loc[df.relationship_id.isin(["R06", "R07"]), "limitations"] = (
        "Holds in market-adjusted (abnormal) returns for LARGE oil shocks; raw returns at 1-5 days are dominated by "
        "broad risk-off. Few independent episodes; government fuel-pricing and hedging modify the effect.")
    df["confidence_level"] = df["evidence_type"].map(conf)
    df.loc[df.relationship_id.isin(["R01", "R05", "R06"]), "confidence_level"] = "HIGH"  # mechanism AND measured CAR-consistent
    df.loc[df.relationship_id == "R07", "confidence_level"] = "MEDIUM"  # reported, but measured CAR correlation is weak
    df["confidence_method"] = ("HIGH = reported or established AND consistent with measured data in this dataset; "
                               "MEDIUM = one source of support; LOW = hypothesis or contradicted by measured data")
    return df


def main() -> None:
    series = load_series()
    events_master().to_csv(OUT / "events_master.csv", index=False)
    market_observations(series).to_csv(OUT / "market_observations.csv", index=False)
    channels().to_csv(OUT / "economic_channels.csv", index=False)
    data_sources().to_csv(OUT / "data_sources.csv", index=False)
    quality_report(series).to_csv(OUT / "data_quality_report.csv", index=False)
    pd.DataFrame(EXCLUDED, columns=["candidate_event", "reason_excluded"]).to_csv(OUT / "excluded_candidates.csv", index=False)
    for f in sorted(OUT.glob("*")):
        print(f"{f.name:40s} {f.stat().st_size/1024:9.1f} KB")


if __name__ == "__main__":
    main()
