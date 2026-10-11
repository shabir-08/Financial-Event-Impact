# Historical Market-Shock Dataset (Oct 2016 – Oct 2026)

A dataset that links documented events in **Russia, India, China, the United States and Israel**
to price moves measured from data. It covers 51 events in 33 historical episodes, 39 market series and
18 Indian target assets. Every price in it was downloaded by script, and every event carries its
source URLs. Nothing is interpolated, synthetic or estimated from charts.

* **Research date:** 2026-10-11. **Data end:** 2026-10-09. **October 2026 is incomplete**: FRED FX runs
  to 2026-10-02 and Brent to 2026-10-06.
* **Findings and recommendations:** [`REPORT.md`](REPORT.md).
* **ML model, end to end** (data extraction → dataset → leakage audit → training → evaluation → backend use): [`ML_MODEL_README.md`](ML_MODEL_README.md).
* **Reproduce:** `python run_all.py` uses the cached downloads in `data/raw/`; `python run_all.py --refresh`
  downloads everything again. It needs `pandas`, `numpy` and `httpx` (the backend's `.venv` has them).
* **Backend model artifacts:** `pipeline/export_models.py`, which `run_all.py` also runs, writes
  `../../data/models/scenario_conditional_v1.json` (used by the simulator) and `forecast_trailing_v1.json`
  (recorded only; it cannot take hypothetical shocks). Each artifact holds the coefficients,
  standardisation, feature domain, walk-forward metrics, residual-quantile intervals and the SHA-256 of
  the training CSV.
* **Model comparison (zero baseline, Ridge, Random Forest, XGBoost):** this step needs
  `pip install -r requirements-ml.txt`. It is not part of `run_all.py` because it takes about 25 minutes.
  1. `python pipeline/verify_training_dataset.py` recomputes every feature, target and event flag from
     `data/raw/` and checks timing.
  2. `python pipeline/train_candidates.py` tunes on train-only folds (2019–2022), scores each tuned
     model once on the test split, and holds out each event group in turn.
  3. `python pipeline/export_forecast_v2.py` writes `../../data/models/forecast_trailing_v2.json`.

  Results go to `output/model_selection/`. Ridge was selected, but it is effectively a per-asset
  training-mean predictor. Its test MAE (2.3399 vs 2.3503 for the zero baseline) has a 95% CI that
  includes no difference. The test years contain no Black Swan weeks.
* **Historical pattern tracking:** details and results are in
  [`output/pattern_tracking_implementation_report.md`](output/pattern_tracking_implementation_report.md).
  * `pipeline/data_inventory.py` writes `output/data_inventory.json/.md`, recording file hashes and the baseline hash
    before any change.
  * `pipeline/market_features.py` writes `output/market_features_{daily,weekly,schema}.csv`: 25 new trailing
    features, all as of the prediction timestamp.
  * `pipeline/event_responses.py` writes `output/historical_event_responses.csv`: the 51 events with their market
    responses, pre-event conditions and recovery.
  * `pipeline/build_training_v2.py` writes `output/model_training_v2.csv`: the baseline plus the 25 new features.
    It is experimental; the baseline file is unchanged.
  * `pipeline/pattern_library.py` writes `../../data/patterns/pattern_library_v1.json`, which the backend's
    `/api/market-patterns/*` endpoints and the simulator use.

  `run_all.py` runs the steps above. The slow experiments are run by hand:
  `python pipeline/run_v2_experiments.py`, which takes 30–60 minutes and writes to `output/model_selection_v2/`,
  then `python pipeline/regime_performance.py`.

## Files (`output/`)

| File | Rows | What it is |
|---|---|---|
| `events_master.csv` | 51 | Event metadata, A–F classification, timing, channels, relevance, measured severity, episode and validation group, sources |
| `market_observations.csv` | 105,974 | Every downloaded observation in long format: date, asset, value, source, adjustment |
| `event_market_returns.csv` | 11,322 | One row per event × asset × window (1/3/5/10/20/60 sessions): baseline, end, return, abnormal return, flags |
| `event_severity_measured.csv` | 51 | Measured severity: percentile of each event's move among all same-length windows, 2016–2026 |
| `economic_channels.csv` | 20 | Knowledge-graph relationships, each with evidence type, evidence, URL, defined confidence level and limitations |
| `channel_associations.csv` | 25 | Measured agreement in direction (raw returns and market-adjusted abnormal returns) between oil shocks and Indian assets |
| `weekly_training_table.csv` | 493 | Full working table behind model_training_final.csv: causal features (`x_`), in-window shocks (`s_`), targets, timestamps, event labels. Use model_training_final.csv for training. |
| `daily_training_table.csv` | 2,470 | The same labels per trading day; inputs are only data known before the Indian market opens |
| `model_training_final.csv` | 493 | **The file to train on** (leakage-audited 2026-10-11, see [TRAINING_DATA_AUDIT.md](TRAINING_DATA_AUDIT.md)): 14 causal features, 18 targets, chronological `split`, `cv_group` |
| `model_training_final_schema.csv` | 39 | Role of every column (feature / target / row_id / split / metadata); training code reads features from here |
| `model_training_final_audit.csv` | 493 | Per-row prediction timestamp, source observation dates, event public times |
| `model_training_final_scenario_inputs.csv` | 493 | Same-week (in-target-window) shocks, for what-if analysis only, never as forecasting inputs |
| `model_training_final_missing_values.csv`, `model_training_final_event_distribution.csv` | – | Missing-value and event/Black Swan distribution reports |
| `model_validation_report.json`, `model_feature_ranges.json`, `model_coefficients.csv` | – | Output of `pipeline/train_model.py` |
| `model_feature_table.csv` | 918 | Model-ready rows (event × 18 Indian targets), with inputs, scenario inputs, targets and CV groups |
| `model_feature_schema.csv` | 24 | Each feature's definition, unit, source, when it becomes available, missing-data policy and role |
| `model_feasibility_results.json` | – | Metrics from the experiments actually run (A, B1, B2) |
| `data_sources.csv` | 48 | Provenance for every dataset, including those sought but not retrieved, with evidence class A–E |
| `data_quality_report.csv` | 56 | Gaps, closures, discrepancies with the sources, survivorship and structural breaks |
| `excluded_candidates.csv` | 7 | Candidate events considered and rejected, with the reason |
| `key_event_summary.md`, `oil_event_india_car.md` | – | Tables quoted in REPORT.md |

## Definitions

**Event information time** (`info_time_utc`) is when the news first became public. `time_precision` is:
- `EXACT`: a published time.
- `APPROX`: a time of day inferred from the sources.
- `DATE_ONLY`: only the date is known. It is set to 00:00 UTC, so window 1 may include trading before the news.

**Baseline and windows** are set per asset, in that exchange's own time zone:
- The baseline is the last session whose **close** is at or before the information time.
- Window *k* ends at the close of the *k*-th session whose close is after the information time.

So news after the close is first reflected in the next session. News during a session gets the flag
`INFO_DURING_SESSION`, because part of window 1 then happened before the news. The baseline is never
included in both the start and the end of a window.

**Returns**
- `percentage_return = (ending_price / baseline_price − 1) × 100`.
- Yields (`value_kind=YIELD_PCT`) report `change_bp`, and `percentage_return` is NA.
- Where a price is zero or negative (WTI on 2020-04-20), the return is NA with a flag.

**Abnormal returns** are computed for Indian stocks and the Bank/IT/Pharma sector indices only. The
benchmark is the **NIFTY 50**, never the S&P 500.
- `market_adjusted_return_pct` is the asset's return minus the NIFTY 50's return over the same window.
- The market model estimates `r_asset = α + β·r_NIFTY` over the 240 sessions ending 21 sessions before
  the baseline, and requires at least 150 observations.
- `car_market_model_pct` is the sum of daily abnormal returns over the window. `car_t_stat` is CAR divided
  by (residual SD × √k).
- These are statistical associations, not evidence that the event caused the move.

**Measured severity** is the percentile of |move| for the NIFTY 50 (1d and 5d), the S&P 500 (5d), Brent (5d),
USD/INR (5d), the US 10-year yield (5d) and the event's home-market index (1d). Each move is ranked
against all rolling windows of the same length, 2016-10 to 2026-10. The highest percentile sets the tier:
EXTREME ≥ 99, HIGH ≥ 95, ELEVATED ≥ 80, otherwise NORMAL. It describes the market's reaction, which
includes moves from concurrent events. The `*_relevance` columns are **analyst judgements**, labelled as such.

**Classification:** A Black Swan candidate · B Major geopolitical shock · C Macroeconomic or monetary-policy shock ·
D Financial-system crisis · E Commodity or supply-chain shock · F Other significant market-disrupting event.

**Episodes and validation groups:** related events share an `episode_id`, with relationships recorded in
`parent_event_id` and `relation_type` (escalation, policy response, secondary economic shock and so on).
`validation_group` links episodes whose events fall within 30 days of each other. Cross-validation
must keep each group together.

## Window status and data-quality flags

**Window status:**
- `AVAILABLE`: the window was computed.
- `NOT_YET_ELAPSED`: the *k*-th session hasn't happened yet.
- `NOT_YET_PUBLISHED_BY_SOURCE`: the source lags. For example, FRED FX data ends 2026-10-02.
- `MISSING`: data that should exist is absent.

**Data-quality flags:**
- `APPROX_SESSION_TIME`: the close time is approximated (futures, spot assessments, FX).
- `EVENT_TIME_APPROX` or `EVENT_TIME_DATE_ONLY`: the event time is imprecise.
- `INFO_DURING_SESSION`: the news arrived during the session (see above).
- `WINDOW_SPANS_TRADING_GAP`: the window spans a trading gap, for example the MOEX suspension in 2022.
- `STALE_BASELINE_MARKET_CLOSED_OR_GAP`: the market was closed before the event or the data has a gap.
- `NONPOSITIVE_PRICE_RETURN_UNDEFINED`: a zero or negative price makes the return undefined.
- `HDFC_MERGER_STRUCTURAL_BREAK_NEARBY`: HDFC Bank's 2023 merger affects the estimate.

## Missing values and units

* Missing values are left empty (NA), **never 0**.
* Prices are in the asset's quote currency, with no FX conversion.
* FX is quoted as local currency per USD, so a rise means the local currency weakened.
* Yields are in percent, and their changes are in basis points.
* Indian stock prices are Yahoo's split- and dividend-adjusted closes, back-adjusted as of the retrieval date.
* Indices are price indices, without dividends.
* Brent, WTI and Henry Hub are EIA spot prices via FRED, so there are no futures rolls. Gold is the
  Yahoo front-month future, which does include roll jumps.

## Licensing

* **FRED and MOEX ISS:** public, but the providers' terms apply.
* **Yahoo chart endpoint:** unofficial. Use it for research only, and don't redistribute its raw data.

`data_sources.csv` lists each dataset's licence, and which sought datasets could not be retrieved (for
example NIFTY Financial Services, daily Indian 10-year bond yields and freight indices).
