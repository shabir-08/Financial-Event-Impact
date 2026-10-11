# Black Swan Simulator: ML model README

How the Black Swan Simulator's machine-learning model was built: data extraction, events, dataset construction,
the leakage audit, training, evaluation, the model files, how the backend uses them, and the historical-pattern
layer added on top. Every number below comes from files in this repository.

**In one paragraph:**
- The simulator uses one quantitative model, **`scenario_conditional_v1`**. It is a Ridge regression that estimates
  the 5-trading-day return of 18 Indian indices and stocks, *given* hypothetical moves in Brent crude, the S&P 500,
  USD/INR, gold and the US 10-year yield over the **same** 5 sessions.
- On 2023–2026 data it never saw in training, it beats a "predict 0%" guess: MAE 2.24 vs 2.35, with a 95% CI that
  excludes no difference, and 60% directional accuracy.
- It is a **conditional historical association**: not a forecast, not a causal estimate, and not validated for
  unseen crises.
- A second model, **`forecast_trailing_v2`**, tries to forecast the next 5 sessions from information known today. It
  shows **no skill** and is never used for scenarios.

---

## Contents
1. [Pipeline overview](#1-pipeline-overview)
2. [Data extraction](#2-data-extraction)
3. [Historical events dataset](#3-historical-events-dataset)
4. [Event market returns](#4-event-market-returns)
5. [The weekly training table](#5-the-weekly-training-table)
6. [Leakage audit](#6-leakage-audit)
7. [Independent dataset verification](#7-independent-dataset-verification)
8. [Models and evaluation protocol](#8-models-and-evaluation-protocol)
9. [Results](#9-results)
10. [Additional market features (v2) and why they were not adopted](#10-additional-market-features-v2-and-why-they-were-not-adopted)
11. [Model artifacts](#11-model-artifacts)
12. [How the backend uses the model](#12-how-the-backend-uses-the-model)
13. [Historical pattern tracking](#13-historical-pattern-tracking)
14. [Limitations](#14-limitations)
15. [Reproducing everything](#15-reproducing-everything)
16. [File map](#16-file-map)

---

## 1. Pipeline overview

```
 data/raw/*.csv  ──►  events_master.csv  ──►  event_market_returns.csv
 (40 series,          (51 sourced events,     (event × asset × window
  provider data)       A–F classes)            returns, abnormal returns)
        │                                              │
        ▼                                              ▼
 weekly_training_table.csv  ──►  model_training_final.csv  (+ _scenario_inputs.csv)
 (493 weeks, timestamps)         (leakage-audited baseline: 14 features, 18 targets)
        │
        ├──► train_candidates.py / export_models.py ──► data/models/*.json  ──► backend inference
        │
        └──► market_features.py ─► model_training_v2.csv (experiment) ─► run_v2_experiments.py
                    │
                    └──► pattern_library.py ──► data/patterns/pattern_library_v1.json ──► analogue API
```

All scripts are in `research/black_swan/pipeline/`; outputs go to `research/black_swan/output/` and to
`data/models/` and `data/patterns/` for the backend.

---

## 2. Data extraction

**Script:** `pipeline/fetch.py` (asset registry in `pipeline/assets.py`). Downloads are cached as one CSV per series
in `data/raw/`, and `data/raw/manifest.json` records rows, first/last date and retrieval time for each.

- **Period:** 2015-09-01 to 2026-10-09.
  - The research period starts 2016-10-01. The extra year gives ~250 sessions of history for market-model
    estimation and trailing features.
  - October 2026 is incomplete.
- **No filling or interpolation:** rows are exactly what the provider returned, with null closes dropped.

| Group | Series | Source |
|---|---|---|
| Indian indices | NIFTY 50, NIFTY Bank, NIFTY IT, NIFTY Pharma | Yahoo chart (`^NSEI`, `^NSEBANK`, `^CNXIT`, `^CNXPHARMA`); price indices |
| Indian stocks (14) | ONGC, IOC, BPCL, Reliance, IndiGo, Asian Paints, SBI, ICICI Bank, HDFC Bank, TCS, Infosys, L&T, Hindalco, Sun Pharma | Yahoo chart (`*.NS`); adjusted close (splits + dividends) |
| Global equity | S&P 500, Nasdaq, Shanghai Composite, TA-35, Euro Stoxx 50 | Yahoo chart |
| Russian equity | MOEX, RTS | MOEX ISS (official) |
| Commodities | Brent, WTI, Henry Hub | FRED (`DCOILBRENTEU`, `DCOILWTICO`, `DHHNGSP`) |
| | Gold | Yahoo `GC=F` (continuous front-month future) |
| FX | USD/INR, USD/CNY | FRED (`DEXINUS`, `DEXCHUS`, noon New York) |
| | USD/RUB, USD/ILS, Dollar index | Yahoo chart |
| Rates | US 10Y, US 2Y, Fed funds | FRED (`DGS10`, `DGS2`, `DFF`) |
| | India 10Y (monthly) | FRED (`INDIRLTLT01STM`) |
| Volatility | CBOE VIX | FRED (`VIXCLS`) |

That is 38 daily series plus 1 monthly series, from three sources: 27 Yahoo, 9 FRED, 2 MOEX.

- **Provenance:** every dataset sought, including ones that could not be retrieved, is listed with an evidence class
  in `output/data_sources.csv`.
- **Known gaps** (closures, discrepancies, structural breaks) are in `output/data_quality_report.csv`.
- **Licensing:** the Yahoo chart endpoint is unofficial and its data may not be redistributed, so `data/raw/` and
  `output/market_observations.csv` are git-ignored.
- **Not available:** India VIX, any history before 2015 (the 2008 crisis cannot be measured), and sector indices
  other than Bank, IT and Pharma.

---

## 3. Historical events dataset

**Script:** `pipeline/events.py` writes `output/events_master.csv`: **51 events** from 2016-11-08 (demonetisation)
to 2026-10-07 (an RBI repo hike).

- **Each event records:**
  - timing: information time (`info_time_utc`) and its precision (`EXACT` / `APPROX` / `DATE_ONLY`);
  - countries, category and subcategory, economic channels, and relevance to India, oil, FX, equities and bonds;
  - grouping: `episode_id` (related events share an episode) and `validation_group`;
  - **source URLs**.
- **Classification** (each with a written rationale):

| Class | Meaning | Events | Independent episodes |
|---|---|---|---|
| A | Black Swan candidate | 4 | 2 (demonetisation 2016; COVID-19 2020) |
| B | Major geopolitical shock | 18 | 9 |
| C | Macroeconomic / monetary-policy shock | 14 | 10 |
| D | Financial-system crisis | 4 | 4 |
| E | Commodity / supply-chain shock | 4 | 4 |
| F | Other significant market-disrupting event | 7 | 7 |

- **Rejected candidates:** 7, with reasons, in `output/excluded_candidates.csv`.
- **Measured severity:** each event's move as a percentile among all same-length windows in 2016–2026, in
  `output/event_severity_measured.csv`.

---

## 4. Event market returns

**Script:** `pipeline/compute.py` writes `output/event_market_returns.csv`: one row per event × asset × window
(1, 3, 5, 10, 20, 60 trading sessions), 11,322 rows.

- **Baseline:** the last session whose close is at or before the event information time, in that exchange's own
  time zone.
- **Window k** ends at the close of the k-th session after that.
- **Return:** `100 × (end / baseline − 1)`. Yields are reported in basis points instead.
- **Abnormal returns** (Indian assets):
  - market-adjusted return vs NIFTY 50;
  - market-model CAR with t-statistic. The estimation window is 240 sessions ending 21 sessions before the baseline,
    requiring ≥ 150 valid days.
- **Flags:** windows that contain other dataset events carry `concurrent_events_in_window` and a confounding note.
  Windows not yet elapsed are marked `NOT_YET_ELAPSED`.

---

## 5. The weekly training table

**Script:** `pipeline/build_training_table.py` writes `output/weekly_training_table.csv` (the full working table)
and `output/model_training_final.csv` (the training file).

**Row timeline**, on the NSE session calendar:

```
 p = week_start − 5 sessions      week_start (d0)                  week_end (d1 = d0 + 5 sessions)
 |──── feature window ──────────►|──────── target window ─────────►|
                                 ▲ prediction timestamp = NSE close 15:30 IST on d0
```

- **Rows:** 493 consecutive, non-overlapping 5-session weeks, from 2016-10-03 to 2026-10-05.
- **Split** (chronological, never shuffled):
  - `train`: target window ends ≤ 2022, 308 rows.
  - `test`: 2023–2026, 185 rows.
- **18 targets:** `y_<asset>_5d_ret_pct = 100 × (close[d1] / close[d0] − 1)` for NIFTY 50, NIFTY Bank, NIFTY IT,
  NIFTY Pharma and the 14 stocks above.
  - The only missing values are 2 in `y_niftypharma_5d_ret_pct`: Yahoo has no NIFTY Pharma bar for 2026-01-01.
    They are never filled.
- **14 forecasting features (`x_`)**, all known at the prediction timestamp:
  - **5 trailing shocks:** Brent, S&P 500, USD/INR, gold (% change) and US 10Y (bp change) over the 5 sessions before
    d0. Foreign observations are dated before d0, because their d0 prints happen after 15:30 IST.
  - **Market state:** CBOE VIX level, NIFTY 20-session return, NIFTY 20-session annualised volatility.
  - **6 event flags:** `x_is_event` plus one per class B–F, set to 1 if a dataset event *became public* inside the
    feature window.
- **5 scenario shocks (`s_`)** are kept in a separate file, `output/model_training_final_scenario_inputs.csv`. They
  are the same five moves measured over the **target** window. They feed only the scenario-conditional model, never
  a forecast.
- **Evaluation-only metadata (never features):**
  - `regime` (NORMAL 411 / EVENT 75 / BLACK_SWAN 7): a label of the target window, assigned after the fact;
  - `event_ids`;
  - `cv_group` (event validation group, or `NORMAL_<year>`).
- **Documentation:** each column's role, unit, formula and timing is in `output/model_training_final_schema.csv`;
  per-row timestamps and source observation dates are in `output/model_training_final_audit.csv`.

---

## 6. Leakage audit

Recorded in `TRAINING_DATA_AUDIT.md`. The original file is backed up in `output/backups/`.

| Problem in the first version | Fix |
|---|---|
| The 5 market "features" were measured over the **same 5 sessions as the target**, and used foreign closes dated d0, which happen after the prediction time | Redefined as trailing moves before d0; the old values moved to `_scenario_inputs.csv` as `s_` columns |
| Event flags were set when an event *reacted inside the target window*, i.e. before it was public | Set only when the event's information time falls in the feature window. `DATE_ONLY` events count as public at 23:59:59 UTC |
| `x_is_black_swan` labelled the target window with hindsight | Removed from the inputs (kept only as `regime` metadata) |

Targets were unchanged (all 18 identical to the backup). After the fix, the forecasting model no longer beat simple
baselines, which is the honest result.

---

## 7. Independent dataset verification

**Script:** `pipeline/verify_training_dataset.py` writes `output/model_selection/dataset_verification.json`. It
recomputes everything from `data/raw/` with separately written code.

| Check | Result |
|---|---|
| Features and targets recomputed vs the CSV | max difference ≤ 5e-5 (rounding) |
| Feature observations dated on or after `week_start` | 0 |
| Event flags recomputed from `events_master.csv` | 0 mismatches |
| Target windows | always 5 sessions; contiguous, non-overlapping |
| Train/test boundary | touch at one close (2022-12-30); no overlap |
| Duplicates (rows, dates, feature vectors) | 0 |
| Trailing features vs same-week moves | r = 0.78–0.84 with the previous week's move; −0.09 to 0.16 with the target week's |

A later re-check (`pipeline/market_features.py`) recomputed the 8 market features with a third implementation and
matched the baseline to ≤ 5e-4.

---

## 8. Models and evaluation protocol

**Script:** `pipeline/train_candidates.py`, using scikit-learn 1.9.1, XGBoost 3.4.1 and a fixed seed of 20261011.
The protocol was fixed before any test evaluation:

1. **Tuning** uses the **train partition only**, with expanding chronological folds: validate on 2019, 2020, 2021
   and 2022, each fitted on all earlier years.
2. **Selection:** lowest pooled validation MAE, and the model must beat the zero baseline on validation.
3. **Test:** 2023–2026, evaluated **once** per tuned candidate.
4. **Missing targets** are masked per target, never zero-filled. Preprocessing (median imputer, standard scaler) is
   fitted inside each training fold.
5. **Uncertainty:** a 95% CI of the MAE difference vs zero from a **week-block bootstrap** (2,000 draws). Whole
   weeks are resampled, because 18 assets in the same week are not independent.
6. **Crisis holdout:** each of the 26 event groups is left out in turn. The 4 weeks after the held-out block are
   purged, because their trailing features contain the held-out returns.

**Candidates:**
- zero-return baseline and training-mean baseline;
- Ridge (α 0.1–10,000);
- Random Forest (36 settings, shared multi-output vs per-target compared);
- XGBoost (24 settings);
- k-nearest-neighbour analogue average (k 10–80).

**Metrics:** MAE, RMSE and directional accuracy, pooled, per asset, by event/normal week and by market regime, each
reported with its number of observations.

---

## 9. Results

### 9.1 Forecasting model: trailing features, next 5 sessions

| Model | Validation MAE | Test MAE (n=3,328) | Directional acc. | 95% CI vs zero |
|---|---|---|---|---|
| Zero baseline | 3.1866 | 2.3503 | n/a | n/a |
| Training mean | 3.1743 | 2.3394 | 0.552 | |
| **Ridge (selected), α=10,000** | 3.1747 | 2.3399 | 0.551 | −0.036 to +0.016 |
| Random Forest | 3.1849 | 2.3412 | 0.543 | |
| XGBoost | 3.2262 | 2.3790 | 0.522 | |

**Verdict: no demonstrated skill.**
- The strongest penalty was selected, so the predictions vary by only about 0.04 percentage points: in effect each
  asset's historical average return.
- In the crisis holdout, every model did worse than zero on both Black Swan groups.

### 9.2 Scenario-conditional model: same-week shocks, same 5 sessions

**Inputs:** Brent %, S&P 500 %, USD/INR %, gold % and US 10Y bp, all over the target week. **Model:** Ridge, α = 100.

| Evaluation | Model MAE | Zero MAE | Notes |
|---|---|---|---|
| Strict protocol: train ≤ 2022, test 2023–26 | **2.2377** | 2.3503 | 95% CI of difference **−0.170 to −0.058**; directional accuracy 0.604 |
| Walk-forward 2019–2026 (each year fitted on earlier years) | 2.6211 | 2.7828 | directional accuracy 0.612; n = 6,892 |
| Event weeks in test (42) | 2.349 | 2.583 | |
| Normal weeks in test (143) | 2.205 | 2.282 | |
| Held-out event groups beating zero | 22 / 26 | | |
| Black Swan groups held out | VG01: 3.70 vs 4.23; VG07 (COVID): 6.02 vs 6.86 | | only 2 independent episodes |

**Per target, walk-forward out-of-sample** (MAE, then MAE of the zero guess, then R²). All 18 beat zero on MAE.
IndiGo and Sun Pharma have slightly negative R².

| Target | MAE | Zero | R² | Target | MAE | Zero | R² |
|---|---|---|---|---|---|---|---|
| NIFTY 50 | 1.38 | 1.64 | 0.28 | SBI | 2.94 | 3.11 | 0.13 |
| NIFTY Bank | 2.00 | 2.20 | 0.19 | ICICI Bank | 2.41 | 2.63 | 0.19 |
| NIFTY IT | 2.25 | 2.42 | 0.16 | HDFC Bank | 2.29 | 2.44 | 0.14 |
| NIFTY Pharma | 1.91 | 1.97 | 0.03 | TCS | 2.45 | 2.53 | 0.08 |
| ONGC | 3.26 | 3.46 | 0.12 | Infosys | 2.67 | 2.89 | 0.12 |
| IOC | 3.04 | 3.17 | 0.04 | L&T | 2.63 | 2.79 | 0.10 |
| BPCL | 3.36 | 3.47 | 0.08 | Hindalco | 3.42 | 3.83 | 0.18 |
| Reliance | 2.71 | 2.82 | 0.09 | Sun Pharma | 2.38 | 2.42 | −0.02 |
| IndiGo | 3.61 | 3.74 | −0.02 | Asian Paints | 2.47 | 2.55 | 0.04 |

**By market regime** (test, regime known at the start of the week; `output/model_selection_v2/regime_performance.csv`):
the model beats zero in low-volatility, high-volatility (12 weeks only) and no-strong-trend weeks. Other regimes have
too few weeks for a conclusion.

---

## 10. Additional market features (v2) and why they were not adopted

### New features
`pipeline/market_features.py` built **25 trailing features** from the raw data, all as of the prediction timestamp:
- **NIFTY:** 5, 10 and 60-session returns; 5 and 60-session volatility; drawdown from 60-session peak; 60-session max
  drawdown; rebound from trough; distance from the 20 and 50-session moving averages; up/down streak.
- **Sector indices:** NIFTY Bank returns and volatility; NIFTY IT and Pharma 20-session returns.
- **Cross-market:** Brent, USD/INR and S&P 500 20-session return and volatility; gold 20-session return; US 10Y
  20-session change; CBOE VIX 5-session change.

**Safeguards:** a test changes every price after the cutoff and confirms that no feature changes. No feature was
redundant (|r| ≥ 0.95 on training rows).

### Experiment
`output/model_training_v2.csv` is the baseline file, unchanged, plus these 25 columns. `pipeline/run_v2_experiments.py`
evaluated it under the same protocol, with **decision rules written before running**:

| Experiment | Validation MAE | Test MAE | Decision |
|---|---|---|---|
| Forecast, 39 features (Ridge) | 3.1779 (worse than 3.1747) | 2.3414 (paired difference vs baseline +0.0015, CI −0.001 to +0.004) | **No improvement**, forecast model unchanged |
| Forecast, kNN analogue | 3.1816 | 2.3613 | worse than zero |
| Scenario shocks + 5 market conditions (Ridge) | 3.0141 (worse than 2.9911) | 2.2405 | **Keep v1** (pre-conditions add nothing) |

---

## 11. Model artifacts

Both models are plain JSON in `data/models/`, with no pickle. Each file contains:
- `feature_order` and per-feature units;
- targets (symbol, name, asset class, currency, knowledge-graph asset id);
- standardisation means/SDs, intercepts and weights;
- `feature_domain` (min, p01, p99, max of each input in training);
- evaluation metrics, empirical residual quantiles (q05–q95) for intervals, limitations, the dataset SHA-256 and a
  `model_version`.

| File | Status | Used by the simulator? |
|---|---|---|
| `scenario_conditional_v1.json` | conditional association; λ = 100; deployed fit on all 493 rows after evaluation | **Yes** |
| `forecast_trailing_v2.json` | `no_demonstrated_skill`; Ridge α = 10,000 fitted on train rows | No (`supports_hypothetical_shocks: false`) |
| `forecast_trailing_v1.json` | earlier trailing-feature model | No |

**Exporters:** `pipeline/export_models.py` (v1 files) and `pipeline/export_forecast_v2.py` (v2). The backend loader
reproduces the reported test MAE exactly (tested).

---

## 12. How the backend uses the model

**Code:** `app/services/simulation/inference.py`, called from `POST /api/simulations`.

- **Slider mapping:**

| Simulator parameter | Model input |
|---|---|
| `oil_price_change_pct` | Brent |
| `usdinr_change_pct` | USD/INR |
| `sp500_change_pct` | S&P 500 |
| `gold_change_pct` | gold |
| `us10y_change_bp` | US 10Y |

  `inflation_change_pct` and `policy_rate_change_bp` have **no model input**: they shape the knowledge-graph pathways
  only.
- **Validation:** inputs are checked against the scenario catalog's accepted range and are never clamped.
- **Statuses:**
  - `available`: inputs are inside the training range.
  - `available_with_warnings`: an input is in the outer 1% tails.
  - `out_of_domain`: an input is outside the training min/max, e.g. Brent beyond −37% to +34%. Estimates are `null`,
    not 0.
  - `no_supported_inputs`, `model_unavailable`, `unsupported_horizon`: no estimate. Only 5 trading days is
    supported.
- **Defaults and output:** model inputs the user doesn't set are held at 0, and the response says so. Each estimate
  comes with 80% and 90% empirical intervals and out-of-sample reliability (MAE vs zero, R², number of weeks).
- **Separation:** the knowledge graph (pathways, support scores) and the model estimates are separate blocks. Graph
  scores are rankings, not probabilities.

---

## 13. Historical pattern tracking

Built on the same data. The backend reads `data/patterns/pattern_library_v1.json`, exported by
`pipeline/pattern_library.py`.

- **Event-response dataset** (`output/historical_event_responses.csv`):
  - the 51 events with NIFTY 1/5/20/60-session returns and abnormal return, and sector, Brent, USD/INR, US 10Y and
    VIX moves;
  - pre-event conditions and recovery (max drawdown in 20 sessions; sessions to regain the baseline);
  - overlap flags.
- **Regimes:** rule-based, from start-of-week information only.
  - Volatility (NIFTY 20-session): < 12% low, 12–20% elevated, ≥ 20% high.
  - Trend (60-session return): ±8%, plus "recovery after drawdown".
- **Analogue search:**
  - finds the past weeks closest to a scenario's shocks, or to current conditions;
  - uses standardised distance with mean/SD from past weeks only;
  - adjacent weeks count as one episode, and statistics are withheld below 8 weeks / 5 episodes;
  - out-of-range values are flagged.
- **API:** `/api/market-patterns/{conditions/latest, search, regimes, event-responses}`. Every simulation also
  returns a `historical_patterns` block.

Everything here is a historical observation, not a probability or forecast.

---

## 14. Limitations

- **Thin crisis data:** only **two independent Black Swan episodes**, both in the training years. Generalisation to
  an unseen crisis is **not demonstrated**.
- **The scenario model** describes co-movement within the same week. It does not say what *will* happen after a
  shock, and it is not causal.
- **Linear model:** it is fitted mostly on ordinary weeks (411 of 493 are NORMAL). Extreme inputs are refused rather
  than extrapolated.
- **Missing inputs:** no inflation, policy-rate or tariff-size series exist as weekly history, so those sliders
  cannot drive estimates.
- **Weak per-target fit:** out-of-sample R² is modest, between −0.02 and 0.28.
- **Intervals** assume past error behaviour continues.
- **Data sources:** Yahoo data is unofficial and cannot be redistributed. There is no India VIX and no pre-2015
  history.
- **Event timing:** approximate for `APPROX` and `DATE_ONLY` events. Effects of overlapping events cannot be
  separated.

---

## 15. Reproducing everything

```bash
cd research/black_swan
python run_all.py --refresh              # download data/raw, then rebuild every dataset, model file and the pattern library
pip install -r requirements-ml.txt       # scikit-learn, xgboost (research only)
python pipeline/verify_training_dataset.py
python pipeline/train_candidates.py      # ~25 min, output/model_selection/
python pipeline/export_forecast_v2.py
python pipeline/run_v2_experiments.py    # 30-60 min, output/model_selection_v2/
python pipeline/regime_performance.py
cd ../.. && .venv/Scripts/python -m pytest research/black_swan/tests tests
```

Without `--refresh`, `run_all.py` uses the cached `data/raw/` files. Rebuilding the derived datasets is
deterministic: identical inputs give identical file hashes.

---

## 16. File map

| Path | What |
|---|---|
| `pipeline/assets.py`, `fetch.py` | asset registry; data download |
| `pipeline/events.py` | curated events with sources and classes |
| `pipeline/compute.py` | event windows, returns, abnormal returns |
| `pipeline/build_training_table.py` | weekly table and baseline training file (leakage-audited) |
| `pipeline/verify_training_dataset.py` | independent recomputation and timing checks |
| `pipeline/train_candidates.py` | model comparison under the fixed protocol |
| `pipeline/export_models.py`, `export_forecast_v2.py` | JSON model files for the backend |
| `pipeline/market_features.py`, `build_training_v2.py`, `run_v2_experiments.py`, `regime_performance.py` | v2 features and evaluation |
| `pipeline/event_responses.py`, `pattern_library.py`, `data_inventory.py` | event responses, pattern library, data audit |
| `output/model_training_final.csv` | **baseline training file** (SHA-256 `4cc59505…8b7e`, unchanged) |
| `output/model_selection/`, `output/model_selection_v2/` | all evaluation outputs |
| `TRAINING_DATA_AUDIT.md`, `REPORT.md`, `output/pattern_tracking_implementation_report.md` | audit, research report, pattern-tracking report |
| `tests/` | 30 tests: dataset integrity, timing, masking, model files, pipeline |
| `../../data/models/`, `../../data/patterns/` | files served by the backend |
