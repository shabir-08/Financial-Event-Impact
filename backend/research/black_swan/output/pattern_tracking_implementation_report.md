# Historical market pattern tracking and ML pipeline review

Date: 2026-10-11. Scope: data audit, historical market features, event-response dataset, rule-based regimes,
historical analogue search, event-conditioned analysis, training dataset v2 with model evaluation, backend API,
and frontend integration into the Black Swan Simulator.

## 1. Summary

- **Forecasting did not improve.** The 25 new trailing market features were evaluated under the baseline protocol
  with decision rules fixed before running. They did not improve the next-5-session forecasts (rule R1 failed on
  validation; test MAE 2.3414 vs 2.3399 for the baseline Ridge). `forecast_trailing_v2.json` is unchanged and remains
  labelled `no_demonstrated_skill`.
- **The scenario-conditional model was re-evaluated before relying on it.** Under the strict chronological protocol,
  its feature set (same-week Brent, S&P 500, USD/INR, gold and US 10Y moves; Ridge, α = 100) was trained on weeks
  ending ≤ 2022 and tested on 2023–2026:
  - Test MAE 2.2377 vs 2.3503 for a zero-return guess.
  - Week-block bootstrap 95% CI of the difference: −0.170 to −0.058.
  - Directional accuracy 0.604.
  - Adding pre-conditions did not help (rule R2 failed), so `scenario_conditional_v1.json` is unchanged.
  - This is a **same-week association**, not a forecast or a causal effect.
- **Pattern tracking is implemented and tested end to end:**
  - an analogue search, regimes and event-conditioned analysis;
  - API endpoints and a `historical_patterns` block in each simulation;
  - frontend panels for analogues, regime, outcome distribution and model estimates.
- **Black Swan generalisation is still not demonstrated.** The data contain two independent Black Swan episodes
  (demonetisation 2016, COVID-19 2020), both before the test period. In leave-one-event-group-out evaluation the
  scenario-conditional Ridge has a lower MAE than zero on both (pooled 5.56 vs 6.34 over 10 weeks). Two episodes
  cannot establish reliability.

## 2. Data audit (Phase A)

Machine-readable: `output/data_inventory.json`; readable table: `output/data_inventory.md`. It covers 60 CSV
files, recorded **before** any change.

- **Baseline:** `output/model_training_final.csv`, SHA-256 `4cc595053b894f8d655ad224978310c06069d53cb527bb32a58bc06642208b7e`.
  493 × 39; 14 features, 18 targets; split train 308 / test 185.
  - The hash is unchanged after all work; a test checks it.
  - Baseline test MAE: zero 2.3503, training mean 2.3394, Ridge 2.3399, RF 2.3412, XGBoost 2.3790.
- **Raw daily series:** 40 CSVs from Yahoo chart, FRED and MOEX ISS, starting 2015-09-01 and ending 2026-10-09
  (FRED series end slightly earlier).
- **Not available:**
  - India VIX: CBOE VIX and realised NIFTY volatility are used instead.
  - Pre-2015 history: the 2008 financial crisis cannot be measured.
  - Sector indices other than NIFTY Bank, IT and Pharma.
- **Data quality:**
  - The inventory found no duplicate keys in any table after composite keys were used.
  - `events_master.csv` uses two spellings for two categories. The source was not edited; a normalised category
    column was added in the derived event dataset.

## 3. Historical market features (Phase B/C)

`pipeline/market_features.py` produces `output/market_features_daily.csv` (2,653 sessions) and
`output/market_features_weekly.csv` (the 493 baseline rows). Each feature's unit, formula, window and timing is in
`output/market_features_schema.csv`.

**Timing:** the prediction timestamp is the NSE close on `week_start`.
- NSE series use closes dated ≤ d0.
- Foreign series use observations dated < d0.
- k-session windows are anchored on the NSE calendar; rolling windows look backwards only (never centred).
- There is no filling or interpolation: missing history gives NaN.
- Only price indices and macro series are used, so adjusted and unadjusted prices never mix.

**Proof of identical conventions:** the 8 baseline-equivalent features recomputed by this pipeline match the
baseline to within 5e-4.

**New features (25):**

| Series | Features |
|---|---|
| NIFTY 50 | 5, 10 and 60-session returns; 5 and 60-session realised volatility; drawdown from 60-session peak; 60-session max drawdown; rebound from 60-session trough; distance from 20 and 50-session moving averages; up/down streak |
| NIFTY Bank | 5 and 20-session returns; 20-session volatility |
| NIFTY IT, NIFTY Pharma | 20-session returns |
| Brent, USD/INR, S&P 500 | 20-session return and volatility |
| Gold | 20-session return |
| US 10Y | 20-session change (bp) |
| CBOE VIX | 5-session change |

**Redundancy rule** (training rows only): drop a feature with |r| ≥ 0.95 against an earlier one. None qualified;
the highest was 0.944 (NIFTY vs NIFTY Bank volatility).

**Outcome descriptors** (`o_` columns: NIFTY max drawdown and realised volatility inside the target window) are
reporting values only. They never enter a model.

## 4. Event-response dataset (Phase 3)

`output/historical_event_responses.csv` has one row per event in `events_master.csv` (51 events, 33 independent
episodes).

- **Responses** come from `event_market_returns.csv`, which uses the documented baseline/window convention:
  - NIFTY 1/5/20/60-session returns and the 5-session market-model abnormal return;
  - NIFTY Bank, IT and Pharma 5-session returns;
  - Brent, USD/INR, US 10Y, CBOE VIX and S&P 500 5-session moves.
  - Windows that have not elapsed stay NA, with their status.
- **Pre-event conditions** are read as of the NIFTY baseline close.
- **Recovery:** max NIFTY drawdown in the 20 sessions after the event, and sessions until NIFTY first closes back at
  or above its baseline.
- **Overlap:** 11 events have other dataset events inside their 5-session window, and are flagged.
- **No events were added.** Every candidate would need a verified source and price coverage. The listed episodes
  (COVID-19, demonetisation, Russia–Ukraine, the oil price war, IL&FS, RBI and Fed actions, tariff shocks) were
  already present. The 2008 crisis predates the raw data.

## 5. Regimes (Phase 5)

`app/services/patterns/regimes.py` uses fixed rules on start-of-week information only:
- **Volatility** (NIFTY 20-session realised volatility): < 12% low, 12–20% elevated, ≥ 20% high.
- **Trend** (60-session return): ≥ +8% strong uptrend, ≤ −8% strong downtrend, otherwise no strong trend.
- **Recovery after drawdown:** a ≥ 10% drawdown followed by a ≥ 5% rebound.

A test confirms that the labels depend only on condition features.

Historical sample, 2016–2026 (descriptive; next-5-session NIFTY return):

| Regime | Weeks | Spells | Median next-5-session % | Share of down weeks |
|---|---|---|---|---|
| low volatility | 257 | 33 | 0.30 | 0.41 |
| elevated volatility | 179 | 43 | 0.26 | 0.46 |
| high volatility | 57 | 12 | 0.70 | 0.40 |
| no strong trend | 322 | 43 | 0.36 | 0.42 |
| strong uptrend | 107 | 28 | 0.03 | 0.47 |
| strong downtrend | 19 | 11 | 1.44 | 0.26 |
| recovery after drawdown | 45 | 13 | 0.01 | 0.49 |

High-volatility and downtrend weeks come from few spells (12 and 11). Clustering was not attempted; the rule-based
labels are the only regime method.

## 6. Analogue search and event-conditioned analysis (Phases 4 and 6)

### Analogue search (`app/services/patterns/analogues.py`)
- **Method:**
  - Distance is the standardised root-mean-square difference.
  - Mean and SD come from the candidate pool: weeks whose outcome window ended on or before the as-of date.
  - Rows lacking a matched feature are excluded and counted.
- **Independence:** weeks within 21 days of each other, or in the same event group, form one cluster.
  - Sample statistics are withheld below 8 weeks or 5 clusters.
  - Values outside every historical observation, and nearest matches ≥ 1 SD away, are flagged.
- **Modes:**
  - *scenario*: shock assumptions vs historical same-week moves, optionally with the latest observed conditions.
    Outcomes are the same 5 sessions.
  - *conditions*: start-of-week conditions. Outcomes are the next 5 sessions.
- **As a predictor:** used as a kNN predictor, the analogue method did not beat zero on the test years.
  - Trailing features: MAE 2.3613 (baseline features) and 2.3560 (v2 features).
  - Same-week shocks: 2.3137, vs Ridge 2.2377.
  - It is therefore offered as historical context, not as a forecast.

### Event-conditioned analysis (`app/services/patterns/events.py`)
- **One event per episode:** statistics use the earliest event of each episode, and need ≥ 3 episodes.
- **Sufficient groups** (classes B, C, D, E, F): 9, 10, 4, 4 and 7 episodes.
- **Insufficient group:** class A (Black Swan candidates) has 2 episodes, so its statistics are withheld.

## 7. Training dataset v2 and model evaluation (Phases E/F)

`output/model_training_v2.csv` (493 × 64) is every baseline column, unchanged, plus the 25 new features. A test
checks for no `o_`/`s_` columns, no `x_is_black_swan`, and missing targets kept as missing.

**Protocol:** identical to the baseline.
- Tuning on the train partition with expanding folds (2019–2022).
- Selection by validation MAE; one test evaluation; week-block bootstrap CIs.
- Leave-one-event-group-out with a 4-week purge.

The decision rules were written into `pipeline/run_v2_experiments.py` before it ran. Outputs are in
`output/model_selection_v2/`.

| Experiment | Selected (validation) | Validation MAE | Test MAE | Zero test MAE | 95% CI vs zero (test) | Groups beating zero (holdout) |
|---|---|---|---|---|---|---|
| Baseline forecast (14 features) | Ridge | 3.1747 | 2.3399 | 2.3503 | −0.036 to +0.016 | 15/26 |
| forecast_v2 (39 features) | Ridge | 3.1779 | 2.3414 | 2.3503 | −0.034 to +0.016 | 14/26 |
| forecast_v1_knn (14 features) | kNN | 3.1816 | 2.3613 | 2.3503 | — | — |
| scenario_s5 (5 same-week shocks) | Ridge α=100 | 2.9911 | 2.2377 | 2.3503 | −0.170 to −0.058 | 22/26 |
| scenario_s5_cond (+5 conditions) | Ridge α=100 | 3.0141 | 2.2405 | 2.3503 | −0.168 to −0.054 | 22/26 |

**Other forecast_v2 candidates** (validation MAE vs zero 3.1866): RF 3.1896, XGBoost 3.2372, kNN 3.1940. None
was selected.

**Decisions:**
- R1: v2 vs the baseline Ridge paired test difference is +0.0015 (95% CI −0.001 to +0.004). **No improvement.**
- R2: s5_cond minus s5 paired difference is +0.0028 (−0.007 to +0.012). **Keep `scenario_conditional_v1`.**

**By input-time regime** (`regime_performance.csv`, test 2023–2026): the scenario-conditional Ridge has a lower MAE
than zero in low volatility (CI −0.175 to −0.027), high volatility (12 weeks, 3 spells) and no-strong-trend
weeks. The forecast models are indistinguishable from zero in every regime with adequate size.

**Event vs normal test weeks:**
- Scenario Ridge: 2.349 vs 2.583 (zero) in 42 event weeks; 2.205 vs 2.282 in 143 normal weeks.
- forecast_v2 Ridge: 2.561 vs 2.583 and 2.277 vs 2.282.

## 8. Backend and frontend integration (Phase G)

### Backend
- **New endpoints:** `GET /api/market-patterns/conditions/latest`, `POST /api/market-patterns/search`,
  `GET /api/market-patterns/regimes`, `GET /api/market-patterns/event-responses[/{event_id}]`.
- **Simulator:** `POST /api/simulations` now includes `historical_patterns` and records `pattern_library_version`.
- **CORS:** configurable through `CORS_ALLOWED_ORIGINS` (default: the Vite dev server).
- **Database:** no migration. The library is a versioned JSON file
  (`data/patterns/pattern_library_v1.json`, `pattern_library_v1+c239704dfd88`).

### Frontend (`frontend/`, copied from the supplied ZIP)
- **Simulator wiring:**
  - Uses `GET /api/scenarios` and the real `POST /api/simulations` contract through an adapter.
  - 3D positions are computed from the layer.
  - Failures are shown as errors. Demo data appears only on request, with a DEMO DATA banner.
- **New panels:** historical analogues, regime, outcome distribution and model estimates. Null estimates show as
  "unavailable", never 0. Support scores are labelled "not a probability".
- **Other demo-only pages** (Overview, Propagation Path, Saved Analyses, Workspace fallback) now carry a DEMO DATA
  banner. The false "Persistence confirmed" text and the fake password check were removed. The PDF export header
  says DEMO DATA.

## 9. Tests executed (2026-10-11)

| Suite | Command | Result |
|---|---|---|
| Research | `.venv/Scripts/python -m pytest research/black_swan/tests` | 30 passed |
| Backend (test database `financial_impact_graph_test`) | `.venv/Scripts/python -m pytest tests` | 217 passed, 5 skipped (real-provider tests need keys) |
| Frontend type-check | `node node_modules/typescript/bin/tsc --noEmit` | passed |
| Frontend unit tests | `npm test` (Vitest + jsdom) | 15 passed |
| Frontend production build | `npm run build` | passed (existing >500 kB chunk warning) |
| Live HTTP check | uvicorn on :8000: CORS preflight, `POST /api/simulations`, pattern search | 200 with allow-origin; `historical_patterns` present |

**Determinism:** re-running the four new pipeline steps reproduced identical file hashes and library version.

**Not done:** the UI was not checked in a real browser; rendering is verified with jsdom tests only.

## 10. Limitations

- **Thin crisis data:** two independent Black Swan episodes, both in the training years. Generalisation to an
  unseen crisis is not demonstrated.
- **The scenario model** is a same-week linear association: not causal, horizon 5 trading days only, and inputs
  outside the training range (e.g. Brent > +33.8%) are declined.
- **Analogue statistics** describe small, overlapping historical samples. They are not probabilities.
- **Missing inputs:** no India VIX, no pre-2015 history, and few sector indices. Inflation, policy-rate and tariff
  magnitudes have no historical weekly series, so they cannot be matched or modelled.
- **Event timing:** where only the date is known (`DATE_ONLY`), the event counts as public at the end of that date.
  Overlapping events cannot be separated.
- **Frontend gaps:** Overview, Propagation Path, Evidence, Market Analysis and Saved Analyses are still demo-only,
  now labelled. Wiring them to `/api/events/*` is outstanding.

## 11. Reproduce

```bash
cd research/black_swan
python pipeline/data_inventory.py          # audit (records hashes)
python run_all.py                          # full pipeline incl. market_features, event_responses,
                                           # build_training_v2, pattern_library
pip install -r requirements-ml.txt
python pipeline/run_v2_experiments.py      # 30-60 min, output/model_selection_v2/
python pipeline/regime_performance.py
cd ../.. && .venv/Scripts/python -m pytest tests research/black_swan/tests
cd frontend && npm ci && npm test && npm run build
```

## 12. Files

- **Created (research):**
  - `pipeline/`: `data_inventory.py`, `market_features.py`, `event_responses.py`, `build_training_v2.py`,
    `pattern_library.py`, `run_v2_experiments.py`, `regime_performance.py`
  - `tests/test_pattern_pipeline.py`
  - `output/`: `data_inventory.{json,md}`, `market_features_{daily,weekly,schema}.csv`,
    `market_features_provenance.json`, `historical_event_responses.csv` (+ provenance),
    `model_training_v2.csv` (+ schema, provenance), `model_selection_v2/`, this report
- **Created (backend):**
  - `app/services/patterns/` (`analogues`, `regimes`, `events`, `library`, `service`)
  - `app/api/market_patterns.py`, `app/schemas/patterns.py`
  - `data/patterns/pattern_library_v1.json`
  - `tests/unit/test_patterns.py`, `tests/api/test_patterns_api.py`
- **Created (frontend):**
  - `frontend/`, copied from the ZIP
  - `HistoricalPatternsPanel`, `ModelEstimatesPanel`, `DemoDataBanner`
  - `types/patterns.ts`, `vitest.config.ts`, `src/test/`, `.env.example`, `.gitignore`
- **Modified (backend):** `app/main.py` (router, CORS), `app/core/config.py`, `app/api/deps.py`,
  `app/api/simulations.py`, `app/services/simulation/orchestrator.py`, `.env.example`, `README.md`,
  `tests/api/test_simulation_api.py`
- **Modified (research):** `pipeline/train_candidates.py` (parametrised; default run unchanged apart from an extra
  `test_predictions.csv`), `run_all.py`, `README.md`
- **Modified (frontend):** `BlackSwanSimulatorPage`, `ScenarioControlPanel`, `ImpactGraph3D`, `NodeDetailsPanel`,
  `blackSwanApi`, `apiClient`, `pdfService`, `types/blackSwan.ts`, the Overview, Propagation Path, Saved Analyses
  and Workspace pages, `package.json` (test script, dev dependencies)
- **Unchanged:** `model_training_final.csv`, `events_master.csv`, all files in `data/models/`.
