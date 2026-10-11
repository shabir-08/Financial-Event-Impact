# Training-Data Audit — `output/model_training_final.csv`

**Audit date:** 2026-10-11 · **File updated in place:** `research/black_swan/output/model_training_final.csv`

**Backups** (taken before any change):
- `output/backups/model_training_final.pre_audit_20261011-164027.csv`. SHA-256 of the original: `5743aa458e8d10c810d7ea458c40258837f58a23b3c50d6aa4cab2278d5387f2`.
- `output/backups/build_training_table.pre_audit_20261011-164027.py`, the original generator.

**Regenerate:** `python run_all.py` (or `python pipeline/build_training_table.py` followed by `python pipeline/train_model.py`).
**Tests:** `pytest research/black_swan/tests`.

**Verdict:**
- The file is now free of the two leakage paths found below. Every input is verified by recomputation to use only information available at the prediction timestamp.
- With the leakage removed, **the forecasting model does not beat the zero or mean baselines** on the 2023–2026 test period.
- **Black Swan generalisation cannot be validated:** the test period has no Black Swan rows, and the training period has only 2 independent Black Swan episodes.

---

## 1. Inventory: what existed before the audit

| Item | Found |
|---|---|
| Training CSV | `research/black_swan/output/model_training_final.csv` (493 rows × 39 columns, 2016-10-03 → 2026-10-05) |
| Generator | `research/black_swan/pipeline/build_training_table.py` (`weekly_table()` and `final_table()`) |
| Sources | `data/raw/*.csv` (provider downloads), `events_master.csv`, `event_market_returns.csv`, `market_observations.csv` |
| Training / validation code | **None in the repository**, local or on GitHub (`origin/main` has no newer commits). The only consumer was the usage snippet given in chat. |
| Simulator / inference code | **None.** The backend computes graph paths and market-data views, but loads no model and has no slider inputs. |

**Before the audit:**
- **Columns:** 15 `x_` features and 18 `y_` targets, plus `week_start`, `week_end`, `split`, `cv_group`, `regime` and `event_ids`.
- **Missing values:** 2 in `y_niftypharma_5d_ret_pct`. No duplicates; dates sorted.
- **Split:** train is 308 rows (target-end year ≤ 2022), test is 185 rows.
- **Regimes:** 411 NORMAL, 75 EVENT, 7 BLACK_SWAN. All 7 Black Swan rows are in training.

---

## 2. Feature-timing and leakage audit

**Timeline of each row,** on the NSE session calendar:
- `p` = `week_start` minus 5 sessions; the feature window runs from `p` to `week_start`.
- The **prediction timestamp** is the NSE close at **15:30 IST on `week_start`**.
- The target window runs from `week_start` to `week_end` (5 sessions later).

Every row's timestamps and the exact source observation dates are in `output/model_training_final_audit.csv`.

| Feature | Calculation found in the code (before) | Verdict | After |
|---|---|---|---|
| `x_brent_5d_ret_pct`, `x_sp500_5d_ret_pct`, `x_usdinr_5d_ret_pct`, `x_gold_5d_ret_pct`, `x_ust10y_5d_chg_bp` | Change from the value at `week_start` to the value at `week_end`: **the same 5 sessions as the target**. They also used foreign closes dated `week_start`, which occur after 15:30 IST. | **LEAKAGE.** Same-week correlation with the NIFTY target was +0.51 for the S&P 500 and −0.44 for USD/INR. | **Corrected:** change between the last observation *dated before* `p` and the last *dated before* `week_start`. Same-week correlation is now +0.06 and −0.02. The old values are preserved in the scenario file (see §11). |
| `x_vix_level_at_start` | VIX close of the last US session before `week_start` | Causal | Unchanged (verified identical) |
| `x_nifty_prev_20d_ret_pct` | NIFTY return from 20 sessions before up to the `week_start` close | Causal (known at the close) | Unchanged |
| `x_nifty_prev_20d_vol_ann_pct` | SD of the 20 daily returns ending at the `week_start` close | Causal; no future rows in the rolling window | Unchanged |
| `x_is_event`, `x_event_*` (5) | 1 if an event's reaction days fell **inside the target window** | **LEAKAGE:** the model was told about events before they were public. | **Corrected:** 1 only if the event's `info_time_utc` falls after the prediction timestamp of `p` and at or before the row's prediction timestamp. `DATE_ONLY` events count as public at 23:59:59 UTC of their date (conservative). |
| `x_is_black_swan` | Black Swan label of the target window | **LEAKAGE and hindsight:** the class is judged partly on impact, which is only known afterwards. | **Removed from the inputs.** The label survives only as evaluation metadata (`regime = BLACK_SWAN`). |
| Targets `y_*_5d_ret_pct` | 100 × (close[`week_end`] / close[`week_start`] − 1), with `week_end` exactly 5 NSE sessions later | Correct | Unchanged (all 18 identical to the backup) |

**Other checks:**
- No forward or backward fills anywhere. Foreign series are taken as-of the last *earlier* observation, which is a causal lookup, not a fill.
- No scaler, imputer or feature selector is fitted on the full dataset. `train_model.py` fits standardisation inside each training fold only (unit-tested).
- The `regime` and `event_ids` columns describe the target window. They are now marked `eval_metadata` in the schema and are excluded from the feature list.

**Remaining real-time caveats (data vintage, not look-ahead):**
- FRED publishes the USD/INR H.10 rates weekly.
- EIA Brent spot prices are published with a lag.
- The *market prices* themselves were observable in real time. A live deployment must use a real-time FX and Brent feed, because these datasets would not be available yet at prediction time.

---

## 3. Event labels, windows and episodes

- **Event-to-row mapping is reproducible** and lives in `public_events()` and `weekly_table()`; the timestamps are in the audit CSV.
- **50 of 51 events map to exactly one row** (unit-tested). EV051 (RBI, 7 Oct 2026) became public after the last complete row, so it is correctly absent.
- **Overlapping events:** all associated IDs are kept in `known_event_ids` and `event_ids`, and the class flags are OR-ed together. 2 rows have more than one known event. No observations are duplicated.
- **Black Swan labels are unchanged** (class A: EV001, EV012, EV015, EV017).
- **Validation-group fix.** `validation_groups()` kept episodes together, but failed to merge *different* episodes whose events were within 30 days of each other. As a result, COVID (VG07) and the oil price war plus Yes Bank (VG08) were split, which would leak in grouped validation. The same happened to the PBOC stimulus (VG22) versus the Iran missile attack 7 days later (VG19).
  - **Fixed** with a merge step that keeps the lowest existing ID; all other IDs are preserved.
  - Events changed: EV013 and EV014 → VG07, EV035 → VG19. This changed 6 rows' `cv_group` in the CSV and the group count in `events_master.csv` (29 → 27). `REPORT.md` is updated accordingly.

---

## 4. Missing values (`output/model_training_final_missing_values.csv`)

| Column | Missing | Cause and handling |
|---|---|---|
| `y_niftypharma_5d_ret_pct` | 2 (both in test) | Yahoo `^CNXPHARMA` has no bar for 2026-01-01, although NSE traded that day (NIFTY 50 has one). The weeks starting 2025-12-24 and 2026-01-01 cannot be computed. **Kept NA, never imputed.** These rows are masked for this one target; their other 17 targets are still used. |
| All 14 features | 0 | – |
| `event_ids`, `known_event_ids` | Empty means "no event" | Metadata only |

---

## 5. Event and Black Swan distribution (`output/model_training_final_event_distribution.csv`)

| Split | NORMAL | EVENT (target window) | BLACK_SWAN (target window) | `x_is_event` = 1 |
|---|---|---|---|---|
| Train (308) | 268 | 33 (12 groups) | 7 (**2 independent groups**) | 23 |
| Test (185) | 143 | 42 (13 groups) | **0** | 24 |

**The Black Swan rows come from only two episodes:**
- **VG01:** demonetisation, confounded with the 2016 US election (EV001/EV002).
- **VG07:** the COVID cluster, which also contains the oil price war and Yes Bank.

No other independent Black Swan episodes exist in Oct 2016 – Oct 2026 under the project's criteria. **Nothing was synthesised or duplicated to balance the classes.** A further verified Black Swan would require history from before 2016 (for example 2008), which is outside the research scope.

---

## 6. Validation (`output/model_validation_report.json`, run on 2026-10-11)

**Model:** a masked multi-output ridge regression, giving one shared standardised feature map with per-asset coefficients.
- λ is chosen by an inner chronological split inside training (fit on years ≤ 2020, validate on 2021–22). λ = 100 was chosen.
- Weekly target windows don't overlap, and the split is on target-end year: the last training window ends 2022-12-30, the same close at which the first test window starts. So **no purge gap is needed**, and this is verified in code.

**A. Chronological test (2023-01 → 2026-10)**, MAE in percentage points over all 18 targets:

| Rows | Model | Zero | Training mean |
|---|---|---|---|
| All (185 rows, 3,328 values) | 2.419 (direction 53.4%) | 2.350 | 2.339 (direction 55.2%) |
| NORMAL (143) | 2.303 | 2.282 | – |
| EVENT (42) | 2.815 | 2.583 | – |
| BLACK_SWAN | **0 rows: cannot be evaluated** | | |

The model beats the zero baseline only for IT, IndiGo and Infosys. **Conclusion:** with causal features, next-week returns are not predictable beyond the baselines from these inputs. Any earlier impression of skill came from the leaked same-week features.

**B. Event-episode holdout** (26 event groups held out in turn, ±1-week purge; non-chronological diagnostic): model MAE 3.50 vs zero 3.31. **Reliable event-level performance cannot be established**, and Black Swan behaviour rests on just 2 groups.

**C. Baselines** (zero, and the training-set mean) are included in every comparison above.

---

## 7. Changes made to the CSV

1. **Rebuilt causally:** `x_brent_5d_ret_pct`, `x_sp500_5d_ret_pct`, `x_usdinr_5d_ret_pct`, `x_gold_5d_ret_pct`, `x_ust10y_5d_chg_bp` (same names).
2. **Rebuilt with public-time logic:** `x_is_event`, `x_event_geopolitical`, `x_event_macro_policy`, `x_event_financial_crisis`, `x_event_commodity_supply`, `x_event_other_shock` (same names).
3. **Removed:** `x_is_black_swan`, a hindsight label. **Added:** `known_event_ids` (provenance). The column count stays at 39: 14 features, 18 targets and 7 other columns.
4. **`cv_group`:** 6 rows changed by the validation-group merge fix; feature-window events are now also used for grouping.
5. **Unchanged:** all rows and keys, the split, all 18 targets, the VIX and NIFTY momentum and volatility features, `regime` and `event_ids` (all verified against the backup).

**New companion files** (all in `output/`):
- `model_training_final_schema.csv`: the role of each column. The training code takes its features from here.
- `model_training_final_audit.csv`: per-row timestamps and source observation dates.
- `model_training_final_scenario_inputs.csv`: the old same-week shock values (`s_…_in_target_window`), for what-if analysis only.
- The missing-value and event-distribution reports.
- `model_validation_report.json`, `model_feature_ranges.json` (training-set ranges, for an out-of-range guard) and `model_coefficients.csv`.

**Code changed:**
- `pipeline/build_training_table.py`: the weekly and final builders, and report generation.
- `pipeline/features_model.py`: the `validation_groups` merge fix.
- **New:** `pipeline/train_model.py` and `tests/test_model_training_final.py`.
- `run_all.py`: now runs the training step.

---

## 8. Simulator compatibility

**No simulator or inference code exists in the repository yet.** Constraints for when it is built:
- **The forecasting features describe the past week.** A slider value fed into `x_brent_5d_ret_pct` therefore means *"oil moved this much over the last 5 sessions"*, not *"oil will move this much next week"*.
- **"If oil moves X% *this* week" is a different, conditional question.** It must be answered by a separate scenario model trained on `model_training_final_scenario_inputs.csv` (the B2 sensitivity experiment). It must be labelled as conditional association, not a forecast and not causation.
- **No inflation feature exists,** so an inflation slider is **unsupported** by this dataset.
- **Out-of-range guard:** refuse or flag inputs outside the training range in `model_feature_ranges.json`. Examples: `x_brent_5d_ret_pct` ranges from −40.2% to +35.7%, and `x_usdinr_5d_ret_pct` from −2.4% to +3.0%.
- **Graph support scores are not return probabilities** and must not be fed to this model as such.

---

## 9. Tests actually executed (2026-10-11)

**`pytest research/black_swan/tests`: 14 passed.** The tests cover:
- the schema and feature/target roles, and that no IDs, labels or targets appear in X;
- rows, targets and causal features preserved against the backup;
- no duplicates, sorted dates, adjacent non-overlapping blocks;
- targets equal to exactly the next 5 NSE sessions (recomputed from raw data for all 493 rows);
- missing targets not imputed;
- shock observations dated before the prediction time, with values recomputed from raw data;
- the same-week correlation removed;
- event flags using only public events, and each event mapped once;
- the chronological split;
- the scenario file preserving the old values;
- the scaler fitted on training rows only, and missing targets masked;
- the training pipeline loading the CSV.

**`pytest tests` (backend): 141 passed, 5 skipped** (the skips are the opt-in live-provider tests). This confirms no backend regression.

---

## 10. Unresolved issues and assumptions

1. **Approximate event times.** 36 rows use events whose time of day is `APPROX` and 4 use `DATE_ONLY`. If a real announcement came later than recorded within the same day, the flag could be one row early. Mitigations: `DATE_ONLY` events are treated as public at the end of their day, and every flagged event is checked to be public before the prediction timestamp.
2. **Publication vintage:** FRED FX and EIA Brent data appear later than the market prices themselves (see §2). Production needs real-time feeds.
3. **No skill and no Black Swan test set:** see §6. Don't present numerical Black Swan forecasts from this model.
4. **Hindsight in the categories:** the B–F category flags use class labels that describe the event type, which is known at announcement. The Black Swan class (A) was removed for hindsight. The categories still rest on analyst classification.
5. **Daily table not audited:** `daily_training_table.csv` was not the subject of this audit. Its `regime` and `is_event` columns describe the *target* day, so treat them as evaluation metadata only.
6. **Yahoo data:** the Nifty Pharma gap and back-adjusted stock prices come from Yahoo. Licensing restricts redistribution.
