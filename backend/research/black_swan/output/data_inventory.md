# Data inventory

Generated 2026-10-11T15:41:58+00:00 by `pipeline/data_inventory.py`. Machine-readable version: `data_inventory.json`.

## Baseline (unchanged)

- `research/black_swan/output/model_training_final.csv`: 493 rows x 39 columns; 14 features, 18 targets; split {'train': 308, 'test': 185}
- SHA-256 `4cc595053b894f8d655ad224978310c06069d53cb527bb32a58bc06642208b7e`
- Test MAE (2023-2026): zero_baseline 2.3503, train_mean_baseline 2.3394, ridge 2.3399, random_forest 2.3412, xgboost 2.379

## Not available

- **India VIX**: not in data/raw; not downloaded by fetch.py. no India-specific implied volatility; CBOE VIX and realised NIFTY volatility used instead.
- **Pre-2015 market history (e.g. 2008 global financial crisis)**: raw series start 2015-09-01. GFC and earlier episodes cannot be measured from existing data.
- **Sector indices beyond Bank/IT/Pharma (e.g. NIFTY Energy, Auto, FMCG)**: not downloaded. sector analysis limited to NIFTY Bank, IT, Pharma and single stocks.

## Files

| File | Kind | Rows | Cols | Dates | Missing | Dup keys | Training | Purpose |
|---|---|---|---|---|---|---|---|---|
| `data/raw/ASIANPAINT.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series ASIANPAINT - Asian Paints |
| `data/raw/BPCL.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series BPCL - Bharat Petroleum |
| `data/raw/BRENT.csv` | raw | 2818 | 3 | 2015-09-01..2026-10-06 | 0 | 0 | input to feature pipelines only | Daily series BRENT - Brent crude spot (Europe, FOB) |
| `data/raw/DXY.csv` | raw | 2794 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series DXY - US Dollar Index |
| `data/raw/FEDFUNDS.csv` | raw | 4056 | 3 | 2015-09-01..2026-10-08 | 0 | 0 | input to feature pipelines only | Daily series FEDFUNDS - Effective federal funds rate |
| `data/raw/GOLD.csv` | raw | 2793 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series GOLD - Gold futures (COMEX front month) |
| `data/raw/HDFCBANK.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series HDFCBANK - HDFC Bank |
| `data/raw/HENRYHUB.csv` | raw | 2797 | 3 | 2015-09-01..2026-10-06 | 0 | 0 | input to feature pipelines only | Daily series HENRYHUB - Henry Hub natural gas spot |
| `data/raw/HINDALCO.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series HINDALCO - Hindalco Industries |
| `data/raw/ICICIBANK.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series ICICIBANK - ICICI Bank |
| `data/raw/IMOEX.csv` | raw | 2796 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series IMOEX - MOEX Russia Index |
| `data/raw/IN10Y_M.csv` | raw | 131 | 3 | 2015-09-01..2026-07-01 | 0 | 0 | input to feature pipelines only | Daily series IN10Y_M - India 10-year government bond yield (monthly, OECD MEI) |
| `data/raw/INDIGO.csv` | raw | 2692 | 3 | 2015-11-10..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series INDIGO - InterGlobe Aviation (IndiGo) |
| `data/raw/INFY.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series INFY - Infosys |
| `data/raw/IOC.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series IOC - Indian Oil Corporation |
| `data/raw/LT.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series LT - Larsen & Toubro |
| `data/raw/NASDAQ.csv` | raw | 2793 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series NASDAQ - Nasdaq Composite |
| `data/raw/NIFTY50.csv` | raw | 2733 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series NIFTY50 - NIFTY 50 |
| `data/raw/NIFTYBANK.csv` | raw | 2737 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series NIFTYBANK - NIFTY Bank |
| `data/raw/NIFTYIT.csv` | raw | 2737 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series NIFTYIT - NIFTY IT |
| `data/raw/NIFTYPHARMA.csv` | raw | 2736 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series NIFTYPHARMA - NIFTY Pharma |
| `data/raw/ONGC.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series ONGC - Oil and Natural Gas Corporation |
| `data/raw/RELIANCE.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series RELIANCE - Reliance Industries |
| `data/raw/RTSI.csv` | raw | 2795 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series RTSI - RTS Index (USD) |
| `data/raw/SBIN.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series SBIN - State Bank of India |
| `data/raw/SP500.csv` | raw | 2793 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series SP500 - S&P 500 |
| `data/raw/SSE.csv` | raw | 2692 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series SSE - SSE Composite (Shanghai) |
| `data/raw/STOXX50.csv` | raw | 2793 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series STOXX50 - EURO STOXX 50 |
| `data/raw/SUNPHARMA.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series SUNPHARMA - Sun Pharmaceutical |
| `data/raw/TA35.csv` | raw | 2219 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series TA35 - TA-35 (Tel Aviv) |
| `data/raw/TCS.csv` | raw | 2738 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series TCS - Tata Consultancy Services |
| `data/raw/USDCNY.csv` | raw | 2770 | 3 | 2015-09-01..2026-10-02 | 0 | 0 | input to feature pipelines only | Daily series USDCNY - USD/CNY (Fed H.10 noon buying rate) |
| `data/raw/USDILS.csv` | raw | 2890 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series USDILS - USD/ILS (Yahoo) |
| `data/raw/USDINR.csv` | raw | 2770 | 3 | 2015-09-01..2026-10-02 | 0 | 0 | input to feature pipelines only | Daily series USDINR - USD/INR (Fed H.10 noon buying rate) |
| `data/raw/USDRUB.csv` | raw | 2891 | 3 | 2015-09-01..2026-10-09 | 0 | 0 | input to feature pipelines only | Daily series USDRUB - USD/RUB (Yahoo) |
| `data/raw/UST10Y.csv` | raw | 2776 | 3 | 2015-09-01..2026-10-08 | 0 | 0 | input to feature pipelines only | Daily series UST10Y - US 10-year Treasury yield (constant maturity) |
| `data/raw/UST2Y.csv` | raw | 2776 | 3 | 2015-09-01..2026-10-08 | 0 | 0 | input to feature pipelines only | Daily series UST2Y - US 2-year Treasury yield (constant maturity) |
| `data/raw/VIX.csv` | raw | 2825 | 3 | 2015-09-01..2026-10-08 | 0 | 0 | input to feature pipelines only | Daily series VIX - CBOE VIX |
| `data/raw/WTI.csv` | raw | 2777 | 3 | 2015-09-01..2026-10-06 | 0 | 0 | input to feature pipelines only | Daily series WTI - WTI crude spot (Cushing) |
| `output/channel_associations.csv` | derived | 25 | 9 | - | 18 | - | False | Measured direction agreement between oil shocks and Indian assets |
| `output/daily_training_table.csv` | derived | 2470 | 37 | 2016-10-03..2026-10-09 | 15661 | 0 | False | Daily labels and pre-open inputs (pre-audit daily table) |
| `output/data_quality_report.csv` | report | 56 | 8 | - | 119 | - | False | Known gaps, closures, discrepancies, structural breaks |
| `output/data_sources.csv` | metadata | 48 | 19 | - | 126 | - | False | Provenance of every dataset sought, with evidence class |
| `output/economic_channels.csv` | curated | 20 | 14 | - | 0 | 3 | False | Knowledge-graph channels with evidence and confidence |
| `output/event_market_returns.csv` | derived | 11322 | 35 | 2016-11-07..2026-10-06 | 75468 | 0 | False | Event x asset x window (1/3/5/10/20/60 sessions) returns and abnormal returns |
| `output/event_severity_measured.csv` | derived | 51 | 13 | - | 5 | 0 | False | Per-event percentile of moves among same-length windows |
| `output/events_master.csv` | curated | 51 | 44 | 2016-11-08..2026-10-07 | 129 | 0 | False | Curated event metadata with sources, timing, episode and validation groups |
| `output/excluded_candidates.csv` | curated | 7 | 2 | - | 0 | - | False | Candidate events rejected, with reasons |
| `output/market_observations.csv` | derived (raw copy) | 105974 | 9 | 2015-09-01..2026-10-09 | 0 | 0 | False | All raw observations in long format (git-ignored: Yahoo licensing) |
| `output/model_coefficients.csv` | report | 15 | 19 | - | 0 | - | False | Coefficients from train_model.py |
| `output/model_feature_schema.csv` | metadata | 24 | 10 | - | 0 | - | False | Schema of model_feature_table.csv |
| `output/model_feature_table.csv` | derived (superseded) | 918 | 30 | - | 194 | 0 | False | Pre-audit event x target table (superseded) |
| `output/model_training_final.csv` | derived (verified) | 493 | 39 | 2016-10-03..2026-09-25 | 859 | 0 | True | BASELINE training set: 14 causal features, 18 five-session targets, chronological split |
| `output/model_training_final_audit.csv` | metadata | 493 | 23 | 2016-10-03..2026-09-25 | 2571 | - | False | Per-row prediction timestamps and source observation dates |
| `output/model_training_final_event_distribution.csv` | report | 7 | 5 | - | 4 | - | False | Event/regime distribution report |
| `output/model_training_final_missing_values.csv` | report | 39 | 6 | - | 36 | - | False | Missing-value report |
| `output/model_training_final_scenario_inputs.csv` | derived | 493 | 9 | 2016-10-03..2026-09-25 | 411 | 0 | True | Same-week shocks (s_) for what-if/conditional analysis only |
| `output/model_training_final_schema.csv` | metadata | 39 | 9 | - | 0 | - | False | Column roles, units, timing for the baseline |
| `output/weekly_training_table.csv` | derived | 493 | 68 | 2016-10-03..2026-09-25 | 4252 | - | False | Working superset behind model_training_final.csv (timestamps, s_ shocks, labels) |
| `output/backups/model_training_final.pre_audit_20261011-164027.csv` | backup | 493 | 39 | 2016-10-03..2026-09-25 | 413 | 0 | False | Pre-audit copy kept for traceability (contains leakage; never train on it) |
