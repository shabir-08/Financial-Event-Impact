# Historical Market-Shock Research — Russia, India, China, US, Israel (Oct 2016 – Oct 2026)

**Research performed:** 2026-10-11 · **Market data through:** 2026-10-09 (October 2026 incomplete) ·
**Primary market:** India · Reproducible with `python run_all.py` (see [README](README.md) for schemas and definitions).

How each kind of number in this report was obtained:

- **Prices and returns** were calculated from series downloaded by script: Yahoo chart, FRED, and MOEX's official data service.
- **Event dates and descriptions** were transcribed from the sources linked in `output/events_master.csv`.
- **Model metrics** come from the experiments actually run in `pipeline/features_model.py`.
- **Relevance labels and classifications** are analyst judgements, and are labelled as such.

---

## Deliverable 1 — Executive summary

**Coverage**
- **Events:** 51 verified events in **33 distinct episodes**. They collapse into **27 leakage-safe validation groups**, because episodes with events within 30 days of each other (for example the COVID crash, the 2020 oil price war and Yes Bank) are merged. This count was corrected in the training-data audit on 2026-10-11; see [TRAINING_DATA_AUDIT.md](TRAINING_DATA_AUDIT.md).
- **By origin country:**

  | Country | Events |
  |---|---|
  | United States | 19 |
  | India | 15 |
  | Russia | 6 |
  | Israel | 6 |
  | China | 5 |

- **By classification:** 4 Black Swan candidates (A), 18 geopolitical shocks (B), 14 macro or policy shocks (C), 4 financial-system crises (D), 4 commodity or supply shocks (E), 7 other (F).
- Only the **COVID-19 onset** (3 events in one episode) and **India's 2016 demonetisation** are labelled Black Swan candidates. Most "shocks" were partly anticipated or scheduled.
- **Market data:** 39 series downloaded with no gaps beyond exchange holidays, except the MOEX suspension in 2022 and holiday gaps in the TA-35 and Shanghai series.
- **Not retrievable for free:** NIFTY Financial Services, Energy and Metal indices; the daily Indian 10-year bond yield (only an OECD monthly average was found); and all freight and shipping indices.

**Main findings**
1. **The largest Indian market moves in the dataset came from domestic and global macro shocks, not foreign geopolitics:**

   | Event | NIFTY move |
   |---|---|
   | COVID crash, 12 Mar 2020 | −8.30% (1d), −19.02% (5d) |
   | 2024 election result | −5.93% (1d) |
   | 2019 corporate tax cut | +5.32% (1d) |
   | Russia's invasion of Ukraine | −4.78% (1d) |
   | 2026 Iran ceasefire | +3.78% (1d) |

   India–Pakistan military escalations moved the NIFTY by less than 1% on the first day (Pulwama −0.20%, Balakot −0.41%, Operation Sindoor +0.14%).

2. **Oil is the main transmission channel from foreign conflicts to India, but it shows up in sector *relative* returns, not in the index or the rupee at 1–5 days:**
   - Across 26 events with |Brent 1d| ≥ 2%, USD/INR moved in the same direction as oil only 46–54% of the time.
   - Oil-marketing companies (IOC, BPCL) showed little raw-return reaction.
   - After removing the market factor (market-model abnormal returns against the NIFTY 50), the 18 large oil shocks (|Brent 5d| ≥ 8%, from only 8 independent validation groups) show clear effects:
     - BPCL: correlation −0.73 with Brent
     - Asian Paints: −0.73
     - IOC: −0.60
     - Hindalco: +0.54
     - ONGC: +0.29; its abnormal return moved in the same direction as oil in 83% of these shocks
3. **2026 Iran war and Hormuz closure (EV047):** Brent spot rose +34.2% over 5 sessions and +70.3% over 20. Over the same windows the NIFTY fell −4.57% and −9.93%. IOC and BPCL had 5-day abnormal returns of −11.2% and −10.7% (t ≈ −4.0 and −3.4); IndiGo had −7.7% (t −2.2).
4. **One shared event-level model is not supportable.** In the experiment, an event-level ridge regression did **worse than predicting zero** (MAE 4.06 vs 3.58 percentage points).
5. **A weekly shock-sensitivity model is defensible as a scenario tool.** It achieved an out-of-sample R² of 0.31 and was right on direction 68% of the time. Its error rises from 1.29 to 2.09 percentage points in event weeks.

**Recommendation (short):** the dataset is ready for a **scenario-sensitivity model with event conditioning** and for knowledge-graph evidence. It is **not** ready, and with only 27 independent groups will never on its own be ready, for training a model that predicts the market impact of Black Swan events.

---

## Deliverable 2 — Historical event master table

The full table is `output/events_master.csv`, with all requested columns plus timing precision, episode and parent links, validation group, measured severity and sources. The episodes are:

| Episode | Events | Type |
|---|---|---|
| EP01/EP02 | Demonetisation + US election (same Indian session, confounded) | A / F |
| EP03 | Volmageddon 2018 | F |
| EP04 | US–China trade war 2018–19 (3 events) | C |
| EP05 | Rusal sanctions 2018 | E |
| EP06 | IL&FS / NBFC crisis 2018 | D |
| EP07 | Pulwama–Balakot 2019 | B |
| EP08 | Corporate tax cut 2019 | C |
| EP09 | COVID-19 2020 (Wuhan → WHO → Fed → India lockdown → WTI negative) | A |
| EP10 / EP11 | Oil price war 2020 / Yes Bank (concurrent with EP09; same validation group) | E / D |
| EP12 | Galwan 2020 | B |
| EP13 | Evergrande 2021 | D |
| EP14 | Russia–Ukraine war 2022 (invasion, SWIFT) | B |
| EP15 | RBI off-cycle hike 2022 | C |
| EP16 | US inflation and Fed 2022 (CPI, Jackson Hole) | C |
| EP17 | US chip export controls 2022 | C |
| EP18 | Hindenburg–Adani 2023 | F |
| EP19 | SVB 2023 | D |
| EP20 | Wagner mutiny 2023 | B |
| EP21 | Israel–Hamas war 2023 (+ Red Sea shipping) | B / E |
| EP22 | Iran–Israel strikes 2024 | B |
| EP23 | India election 2024 | F |
| EP24 | Aug-2024 global deleveraging | F |
| EP25 | PBOC stimulus 2024 | C |
| EP26 | DeepSeek 2025 | F |
| EP27 | Liberation Day tariffs + pause 2025 | C |
| EP28 | Pahalgam → Sindoor → ceasefire 2025 | B |
| EP29 | Israel–Iran 12-day war 2025 | B |
| EP30 | US secondary tariff on India 2025 | C |
| EP31 | Rosneft/Lukoil sanctions 2025 | E |
| EP32 | Iran war and Hormuz 2026 (strikes → ceasefire → interim deal → renewed strikes) | B |
| EP33 | RBI hike Oct 2026 (windows mostly not yet elapsed) | C |

**Classification method.** "Black Swan candidate" (A) requires all three of:
- a highly unexpected event,
- an extreme impact,
- no plausible way for markets to have priced it beforehand.

Under that test, the 2022 invasion (B) was excluded because Western intelligence warned of it publicly beforehand. The 2026 Hormuz closure (B) was excluded because the risk was discussed for decades. The labels are judgements; `classification_rationale` gives the reasoning for each event.

**Excluded candidates** are listed with reasons in `output/excluded_candidates.csv` (for example Abqaiq 2019, which originated outside the five countries, and Nord Stream, which is not separately sourced and overlaps EP14).

---

## Deliverable 3 — Event-to-market impact table

The full table is `output/event_market_returns.csv`: 11,322 rows, covering 51 events × 37 assets × 6 windows. Each row has its baseline and end dates and prices, the return, a data-quality flag, concurrent events, and abnormal returns for Indian assets.

The summary below shows raw returns. **They are not attributable to a single event when concurrent events are listed.**

| Event | Class | First India session | NIFTY 1d | NIFTY 5d | NIFTY 20d | Brent 5d | USD/INR 5d | US10Y 5d | S&P 1d | Severity | Concurrent events (5d) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EV001 India demonetisation | A | 2016-11-09 | -1.31% | -5.06% | -5.17% | -2.33% | +1.60% | +40bp | +0.38% | EXTREME | EV002 |
| EV002 US election result 2016 | F | 2016-11-09 | -1.31% | -5.06% | -5.17% | +1.56% | +2.53% | +34bp | +1.11% | EXTREME | EV001 |
| EV003 Volmageddon | F | 2018-02-06 | -1.58% | -1.19% | -4.80% | -6.54% | +0.41% | -1bp | -4.10% | EXTREME | |
| EV004 Section 301 tariffs | C | 2018-03-23 | -1.15% | +0.96% | +4.65% | +0.06% | +0.03% | -12bp | -2.52% | HIGH | |
| EV005 Rusal / oligarch sanctions | E | 2018-04-09 | +0.46% | +1.44% | +3.72% | +7.36% | +0.55% | +0bp | -2.19% | ELEVATED | |
| EV006 IL&FS / DHFL crash | D | 2018-09-21 | -0.81% | -2.29% | -8.80% | +3.18% | +0.75% | -1bp | -0.04% | NORMAL | |
| EV007 Pulwama | B | 2019-02-15 | -0.20% | +0.41% | +6.34% | +5.61% | +0.30% | -2bp | -0.27% | NORMAL | |
| EV008 Balakot | B | 2019-02-26 | -0.41% | +0.99% | +5.19% | +0.66% | +0.13% | +5bp | -0.08% | NORMAL | |
| EV009 Tariff tweet May 2019 | C | 2019-05-06 | -0.97% | -3.70% | +1.80% | -0.44% | +1.36% | -7bp | -0.45% | ELEVATED | |
| EV010 Yuan breaks 7 | C | 2019-08-05 | -1.23% | +1.02% | -1.39% | -6.14% | +1.81% | -12bp | -2.98% | HIGH | |
| EV011 India corporate tax cut | C | 2019-09-20 | +5.32% | +8.09% | +8.25% | -3.38% | -0.53% | -9bp | -0.49% | EXTREME | |
| EV012 Wuhan lockdown | A | 2020-01-23 | +0.61% | +0.19% | +0.16% | -4.27% | +0.39% | -13bp | +0.03% | HIGH | |
| EV013 OPEC+ collapse / price war | E | 2020-03-09 | -4.90% | -16.31% | -20.39% | -39.52% | +1.02% | -4bp | -1.71% | EXTREME | EV014;EV015;EV016 |
| EV014 Yes Bank moratorium | D | 2020-03-06 | -2.48% | -11.66% | -21.98% | -33.57% | +0.26% | -20bp | -3.39% | EXTREME | EV013;EV015 |
| EV015 WHO pandemic declaration | A | 2020-03-12 | -8.30% | -19.02% | -14.00% | -33.85% | +1.18% | +26bp | -4.89% | EXTREME | EV016 |
| EV016 Fed emergency cut | C | 2020-03-16 | -7.61% | -12.15% | -9.67% | -20.78% | +1.96% | -2bp | -11.98% | EXTREME | EV017 |
| EV017 India lockdown | A | 2020-03-25 | +6.62% | +10.21% | +18.99% | -19.20% | -1.26% | -6bp | +9.38% | EXTREME | |
| EV018 WTI negative | F | 2020-04-21 | -3.03% | +0.22% | -4.13% | -12.62% | -0.43% | -5bp | -1.79% | HIGH | |
| EV019 Galwan clash | B | 2020-06-16 | +1.02% | +5.07% | +10.08% | +9.53% | -0.28% | +0bp | +1.90% | HIGH | |
| EV020 Evergrande | D | 2021-09-20 | -1.07% | +1.52% | +5.07% | +3.72% | +0.23% | +10bp | -1.70% | ELEVATED | |
| EV021 Russia invades Ukraine | B | 2022-02-24 | -4.78% | -3.31% | +0.53% | +19.79% | +1.35% | -13bp | +1.50% | EXTREME | EV022 |
| EV022 SWIFT sanctions | B | 2022-02-28 | +0.81% | -4.77% | +4.00% | +25.67% | +1.77% | -23bp | -0.24% | EXTREME | |
| EV023 RBI off-cycle hike | C | 2022-05-04 | -2.29% | -4.86% | -2.84% | -2.22% | +1.07% | +2bp | +2.99% | HIGH | |
| EV024 US CPI surprise | C | 2022-06-13 | -2.64% | -5.61% | +0.12% | -2.09% | +0.21% | +24bp | -2.91% | EXTREME | |
| EV025 Jackson Hole | C | 2022-08-29 | -1.40% | +0.61% | -3.09% | -5.79% | -0.31% | +23bp | -3.37% | HIGH | |
| EV026 US chip controls | C | 2022-10-10 | -0.43% | -0.74% | +5.13% | -6.74% | -0.19% | +17bp | -2.80% | HIGH | |
| EV027 Hindenburg–Adani | F | 2023-01-25 | -1.25% | -2.77% | -3.11% | -3.02% | +0.07% | +3bp | -0.07% | ELEVATED | |
| EV028 SVB | D | 2023-03-09 | -0.93% | -4.41% | -0.73% | -9.50% | +1.20% | -47bp | -1.85% | EXTREME | |
| EV029 Wagner mutiny | B | 2023-06-26 | +0.14% | +3.52% | +5.39% | +1.29% | +0.06% | +5bp | -0.77% | ELEVATED | |
| EV030 Hamas attack | B | 2023-10-09 | -0.72% | +0.50% | -1.23% | +7.36% | +0.04% | -7bp | +0.63% | EXTREME | |
| EV031 Red Sea shipping | E | 2023-12-18 | -0.18% | -0.50% | +2.99% | +4.78% | -0.01% | -3bp | -0.01% | NORMAL | |
| EV032 Iran attack on Israel (Apr 2024) | B | 2024-04-15 | -1.10% | -0.81% | -1.34% | -5.54% | -0.16% | +12bp | -1.20% | ELEVATED | |
| EV033 India election 2024 | F | 2024-06-04 | -5.93% | -0.02% | +3.70% | +4.11% | +0.43% | +6bp | +0.15% | EXTREME | |
| EV034 Aug 2024 deleveraging | F | 2024-08-05 | -2.68% | -1.42% | +2.27% | -0.75% | +0.30% | +0bp | -1.84% | HIGH | |
| EV035 PBOC stimulus | C | 2024-09-24 | +0.01% | -0.49% | -5.66% | -3.47% | +0.28% | +6bp | +0.25% | EXTREME | EV036 |
| EV036 Iran missiles (Oct 2024) | B | 2024-10-03 | -2.12% | -3.16% | -5.64% | +12.98% | +0.24% | +22bp | -0.93% | HIGH | |
| EV037 DeepSeek | F | 2025-01-27 | -1.14% | +1.80% | -1.28% | -2.03% | +0.39% | -5bp | -1.46% | ELEVATED | |
| EV038 Liberation Day tariffs | C | 2025-04-03 | -0.35% | -4.00% | +4.49% | -12.90% | +1.31% | +14bp | -4.84% | EXTREME | EV039 |
| EV039 Tariff pause | C | 2025-04-11 | +1.92% | +7.71% | +9.73% | +0.95% | -1.12% | +9bp | +9.52% | EXTREME | |
| EV040 Pahalgam | B | 2025-04-23 | +0.67% | +0.70% | +2.67% | -4.62% | -0.19% | -19bp | +2.51% | HIGH | |
| EV041 Operation Sindoor | B | 2025-05-07 | +0.14% | +0.82% | +0.67% | +7.31% | +1.07% | +19bp | +0.43% | HIGH | EV042 |
| EV042 India–Pakistan ceasefire | B | 2025-05-12 | +3.82% | +4.21% | +4.14% | +1.46% | +0.13% | +6bp | +3.26% | EXTREME | |
| EV043 Israel strikes Iran | B | 2025-06-13 | -0.68% | -0.38% | +1.88% | +13.45% | +1.20% | +2bp | -1.13% | HIGH | EV044 |
| EV044 US strikes Fordow | B | 2025-06-23 | -0.56% | +2.09% | -0.57% | -11.89% | -1.31% | -9bp | +0.96% | ELEVATED | |
| EV045 US 50% tariff on India | C | 2025-08-07 | +0.09% | +0.18% | +0.68% | -2.53% | -0.26% | +7bp | +0.73% | NORMAL | |
| EV046 Rosneft/Lukoil sanctions | E | 2025-10-23 | +0.09% | +0.72% | +1.25% | +4.38% | +0.32% | +11bp | +0.58% | HIGH | |
| EV047 Iran war / Hormuz halt | B | 2026-03-02 | -1.24% | -4.57% | -9.93% | +34.24% | +0.77% | +18bp | +0.04% | EXTREME | |
| EV048 US–Iran ceasefire | B | 2026-04-08 | +3.78% | +4.79% | +5.20% | -14.12% | +0.44% | -7bp | +2.51% | EXTREME | |
| EV049 Interim Hormuz deal | B | 2026-06-15 | +0.98% | +1.65% | +2.49% | -9.23% | -0.45% | +3bp | +1.65% | ELEVATED | |
| EV050 Renewed US strikes | B | 2026-07-08 | -2.12% | -1.42% | +0.89% | +16.59% | +1.30% | +3bp | -0.28% | HIGH | |
| EV051 RBI hike Oct 2026 | C | 2026-10-07 | -0.76% | NA | NA | NA | NA | NA | -0.22% | NORMAL | |

**How to read this table:**
- "First India session" is the first NSE session that could reflect the news under the timing rule.
- The S&P 1d column uses the S&P 500's own first post-event session.
- Severity reflects the **market reaction**, which includes everything else that happened in the window.
- Some rows clearly show raw returns misattributing cause. EV017 (India's lockdown) shows NIFTY +6.62% the next day: global markets rallied on stimulus news that day, and the S&P 1d is +9.38%.

**Indian stock abnormal returns in the oil shocks** (5-day market-model CAR against the NIFTY 50, in %, with t-statistic):

| Event | Brent 5d | ONGC | IOC | BPCL | RELIANCE | INDIGO | ASIANPAINT | HINDALCO |
|---|---|---|---|---|---|---|---|---|
| EV013 price war | -39.52% | -15.8 (t=-4.2) | +12.9 (t=+3.3) | +14.8 (t=+3.1) | -4.2 (t=-1.3) | -6.1 (t=-1.2) | +3.7 (t=+1.3) | -3.1 (t=-0.9) |
| EV021 invasion | +19.79% | +8.1 (t=+1.8) | +0.4 (t=+0.1) | -0.1 (t=-0.0) | +3.9 (t=+1.5) | -12.1 (t=-2.8) | -10.1 (t=-2.9) | +20.0 (t=+4.2) |
| EV043 Israel–Iran | +13.45% | +2.4 (t=+0.6) | -2.2 (t=-0.6) | -1.1 (t=-0.3) | +0.1 (t=+0.0) | -3.7 (t=-1.0) | +2.9 (t=+1.0) | -0.8 (t=-0.2) |
| EV046 Rosneft/Lukoil | +4.38% | +2.5 (t=+0.8) | +5.3 (t=+1.7) | +2.0 (t=+0.6) | +1.8 (t=+0.9) | -2.8 (t=-0.8) | +1.3 (t=+0.5) | +7.8 (t=+2.4) |
| EV047 Hormuz | +34.24% | +1.5 (t=+0.5) | -11.2 (t=-4.0) | -10.7 (t=-3.4) | +7.7 (t=+3.8) | -7.7 (t=-2.2) | -4.0 (t=-1.4) | +7.1 (t=+2.4) |
| EV048 ceasefire | -14.12% | -4.4 (t=-1.5) | +3.4 (t=+1.2) | +6.4 (t=+2.0) | -2.5 (t=-1.3) | +3.2 (t=+1.0) | +7.7 (t=+2.8) | -0.7 (t=-0.2) |
| EV049 interim deal | -9.23% | -0.8 (t=-0.3) | -0.2 (t=-0.1) | -0.9 (t=-0.3) | -0.2 (t=-0.1) | +4.0 (t=+1.2) | -2.6 (t=-0.9) | -3.7 (t=-1.1) |
| EV050 renewed strikes | +16.59% | +1.9 (t=+0.6) | -2.4 (t=-0.8) | -1.1 (t=-0.3) | +0.2 (t=+0.1) | -2.8 (t=-0.9) | -2.5 (t=-0.9) | +1.0 (t=+0.3) |

---

## Deliverable 4 — Event-specific reports

**EV047–EV050: 2026 Iran war and the Strait of Hormuz** (episode EP32; sources: Wikipedia "2026 Iran war", the UK House of Commons Library, S&P Global/Platts, the EIA, Al Jazeera)
- **What happened:**
  - US and Israeli strikes on Iran began on Saturday 28 Feb 2026, and Iran closed the strait.
  - Tanker traffic halted on 1 March, according to Platts tracking.
  - A two-week ceasefire came on 7 April. An interim deal was agreed on 14 June, then collapsed and expired in August.
  - The US struck Iran again on 8 July. Attacks on shipping continued into September.
- **Measured market reaction:**
  - **Brent spot:** +8.3% on the first session (2 March), +34.2% over 5 sessions and +70.3% over 20.
  - **NIFTY:** −1.24% (1d), −4.57% (5d), −9.93% (20d).
  - **USD/INR:** +0.77% over 5 days.
  - **US 10-year yield:** +18bp over 5 days.
  - **Indian sectors, abnormal returns over 5 days:** oil-marketing companies around −11% (t ≈ −4), IndiGo −7.7% (t −2.2). Reliance (+7.7%, t 3.8) and Hindalco (+7.1%) rose.
  - **Ceasefire (EV048):** NIFTY +3.78% (1d) and Brent −14.1% (5d).
- **Supported by evidence:** the oil price channel (EIA) and the oil → oil-marketing-company and aviation margin channel, seen in abnormal returns.
- **Uncertain:**
  - The start date is only known to the day, so the 1-day window may include pre-news trading.
  - The later sub-events overlap each other.
  - Freight and LNG prices were not retrieved.
  - The 7 Oct 2026 RBI hike (EV051) is linked as a policy response, but its windows have not elapsed.

**EV021–EV022: Russia's invasion of Ukraine and the SWIFT sanctions** (EP14)
- **Measured market reaction:**
  - **Invasion day:** NIFTY −4.78% on 24 Feb 2022, consistent with the "nearly 5%" in the sources.
  - **Brent:** +19.8% (5d) after the invasion and +25.7% (5d) after the SWIFT sanctions.
  - **Indian stocks, abnormal returns over 5 days:** IndiGo −12.1% (t −2.8), Asian Paints −10.1% (t −2.9), Hindalco +20.0% (t 4.2), the last consistent with the commodity-supply channel.
- **Data distortions:**
  - MOEX was suspended from 28 Feb to 23 Mar 2022, so IMOEX and RTSI windows span the gap and are flagged.
  - Sources report the rouble falling 26–40% on 28 Feb, but Yahoo's USD/RUB shows only −1.9%. The USD/RUB series is unreliable under capital controls and should not be used for 2022.

**EV012–EV018: COVID-19 cluster** (EP09, merged with EP10 and EP11 into one validation group)
- **Measured market reaction:**
  - **Wuhan lockdown:** India barely reacted at first (NIFTY +0.61% on day 1; Shanghai −2.75%, matching the source).
  - **March 2020:** the NIFTY fell −8.30% (1d) and −19.02% (5d) after the WHO declaration, and −7.61% (1d) after the Fed's emergency cut.
  - **Brent:** fell about 34–40% over 5 days.
- **Why these events can't be separated:** they overlap each other (concurrent-event flags) and coincide with the oil price war (EV013) and Yes Bank (EV014). They must be treated as **one** observation for validation.
- **Data distortions:** WTI's negative settlement (EV018) makes percentage returns undefined; these are flagged rather than filled.

**EV033: India election result, 2024**
- **Measured market reaction:** NIFTY −5.93% and Bank NIFTY −7.95% on 4 June 2024, matching the sources exactly. Most of the fall was regained within 20 sessions (+3.70% over 20d).
- **Why it matters:** a scheduled event whose outcome surprised. It is a domestic political shock with no oil channel.

**EV038–EV039: Liberation Day tariffs and the pause, 2025**
- **Measured market reaction:**
  - **After the tariffs:** NIFTY −0.35% (1d) and −4.00% (5d); S&P 500 −4.84% (1d); Brent −12.9% (5d), reflecting a demand-shock channel.
  - **After the pause:** S&P +9.52% (1d) and NIFTY +7.71% (5d).
- **Why it matters:** a policy reversal 7 days later turns the first event's windows into overlapping, confounded observations.

**EV030: Hamas attack on Israel, October 2023**
- **Measured market reaction:** TA-35 −5.58% from the last pre-attack close to 9 October (sources: −6.5% on Sunday). Brent +7.4% over 5 days. NIFTY −0.72% (1d) and +0.50% (5d).
- **Why it matters:** the evidence points to **limited direct transmission to India** unless oil supply is threatened.

**EV001: Demonetisation, 2016**
- **Measured market reaction:** NIFTY −1.31% (1d) and −5.06% (5d).
- **Source discrepancy:** a source claims indices "fell over 6%" on 9 Nov. The closing data contradict this; the figure was most likely intraday.
- **Confounding:** the same session priced the US election (EV002). Both share one window and cannot be separated with daily data.

---

## Deliverable 5 — Datasets

The files are in `output/`; schemas, units and flags are described in the [README](README.md). All numerical values were downloaded and calculated by script (evidence class A). Event metadata was transcribed from cited sources (class C). Datasets that were sought but not retrieved are listed in `data_sources.csv` (class B or E). **No synthetic data is included.**

---

## Deliverable 6 — Model-ready feature table

`output/model_feature_table.csv` has 918 rows (51 events × 18 Indian targets) in 27 validation groups. `output/model_feature_schema.csv` defines each feature. The features fall into four roles:

- **Inputs, available at the baseline close:**
  - Event category, classification, country and how unexpected it was.
  - NIFTY return and realised volatility over the previous 20 sessions.
  - VIX at the prior US close.
  - Brent, USD/INR and S&P 500 returns, and the change in the US 10-year yield, over the previous 20 observations.
  - The target asset's own 20-session momentum.
- **Scenario inputs, not available ex ante:** the shock in Brent (1d, 5d), USD/INR (5d), the US 10-year yield (5d, bp), the S&P 500 (1d), VIX (1d) and gold (5d). These measure what happened **after** the event. In a simulator the user must *supply* them as the hypothetical shock. Using them in a forecaster would be look-ahead leakage.
- **Targets:** returns over 1, 5 and 20 sessions, plus the 5-day market-model abnormal return (CAR) for stocks and sector indices.
- **Grouping:** `episode_id` and `validation_group`.

**Missing data:**
- NA means unavailable. The 18 NA 5d/20d targets all belong to the 7 Oct 2026 RBI hike, which has not elapsed.
- Never replace NA with zero.
- Encode categories one-hot.
- Standardise numeric features within each training fold only.
- Keep units as named (percent or basis points); every series is already in its own quote currency.

---

## Deliverable 7 — Model feasibility report (experiments actually run)

| Experiment | Setup | Model | Zero baseline | Mean baseline |
|---|---|---|---|---|
| **A** Event-level | NIFTY 5d return ~ shocks; ridge; leave-one-validation-group-out; n = 50 events, 26 groups | MAE 4.06, RMSE 5.82, direction 52% | MAE 3.58, RMSE 5.44 | MAE 3.78, direction 52% |
| **B1** Daily predictive | NIFTY on day *t* using only data known before the Indian open (S&P, Brent, USD/INR, VIX on *t*−1, NIFTY on *t*−1); walk-forward by year, 2019–2026; n = 1,916 | MAE 0.714, RMSE 1.077, direction 57.0% | MAE 0.726, RMSE 1.092 | MAE 0.724, direction 53.7% |
| **B2** Weekly scenario sensitivity | NIFTY 5d ~ same-week Brent, S&P 500, USD/INR, US 10Y; non-overlapping blocks; walk-forward; n = 382 test blocks | MAE 1.38, RMSE 1.87, **OOS R² 0.31**, direction 67.8%; event weeks MAE 2.09 (n = 42) vs other weeks 1.29 | MAE 1.65, RMSE 2.26 | – |

In experiment B2, the full-sample sensitivities of the NIFTY's 5-day return, per one standard deviation of each shock, were:

| Shock (size of 1 SD) | Effect on NIFTY 5d return |
|---|---|
| S&P 500 (2.34%) | +0.92% |
| USD/INR (0.67%) | −0.71% |
| Brent (6.19%) | −0.01% |
| US 10-year yield (11.9bp) | 0.00% |

Brent has almost no effect on the index once global equities and the rupee are included in the model.

**Conclusions**
- **Data volume.** There are 11,322 return rows but only **27 independent historical groups**. Duplicating events across assets and windows does not add independent observations. That is far too few to learn event-type effects, and experiment A confirms it: it does worse than predicting zero.
- **One shared model is defensible only in this form:** a **shared asset-response model** trained on the full daily or weekly history (about 490 non-overlapping weeks), with:
  - shock variables as inputs,
  - an asset identifier or per-asset coefficients,
  - event features as conditioning or interaction terms,
  - prediction intervals widened in event regimes (event-week error is about 1.6× normal).
- **Recommended initial model:** ridge regression or multi-output ridge, per horizon (1d, 5d, 20d), for the NIFTY 50, Bank NIFTY, IT, Pharma and the stock basket. Gradient-boosted trees are only worth trying once B2 is beaten out of sample. Neural networks are not justified at this sample size.
- **Validation:**
  - Use chronological walk-forward validation. Event analyses must hold out whole validation groups.
  - Report MAE, RMSE and direction accuracy against zero and mean baselines.
  - Add empirical prediction intervals from out-of-sample residuals, computed separately for event and normal regimes.
- **Out-of-range scenarios.** The simulator should check every scenario input against that feature's empirical distribution in the training data. If an input is outside the observed range, or in a tail supported by only one or two episodes, it must answer **"Insufficient historical evidence for a reliable numerical estimate"**. It should then fall back to the knowledge-graph explanation alone. Example: in the downloaded Brent spot series, 20-observation rises above +35% occur only in three episodes:
  - the April–May 2020 rebound from about $9 a barrel (EV018's 20-day window is +90%; the series maximum is +281%, from a near-zero base),
  - the February 2022 invasion, and
  - the 2026 Iran war (EV047: +70%).

  Estimates in that tail rest on three episodes.
- **Data that would materially help:**
  - NSE FPI flow data (daily)
  - Daily Indian 10-year G-Sec yields (FBIL/CCIL)
  - NIFTY sector indices from niftyindices.com
  - Freight indices (licensed)
  - Intraday data to sharpen event timing
  - Index-membership history (to address survivorship)
  - A screened calendar of scheduled macro releases, to flag confounders

---

## Deliverable 8 — Knowledge-graph relationships

`output/economic_channels.csv` lists 20 relationships, each with its evidence type, evidence text, URL, date, limitations and a confidence level assigned by a defined rule:

- **HIGH:** reported or established, and consistent with the measured data
- **MEDIUM:** one source of support
- **LOW:** a hypothesis, or contradicted by the measured data

The most important relationships:

| ID | Relationship | Evidence type | Confidence |
|---|---|---|---|
| R01 | Hormuz closure → Brent ↑ | Directly reported (EIA) + measured | HIGH |
| R05 | Brent ↑ → ONGC ↑ | Empirical (raw and CAR) | HIGH |
| R06 | Brent ↑ → IOC/BPCL ↓ (relative to market) | Empirical (CAR correlation −0.60 / −0.73, in 8 independent groups) | HIGH |
| R07 | Brent ↑ → IndiGo ↓ | Reported + weak empirical (CAR correlation −0.18) | MEDIUM |
| R04 | Brent ↑ → USD/INR ↑ (1–5d) | Hypothesis; **not confirmed** at event horizons | LOW |
| R09 / R10 | S&P 500 → NIFTY (+); USD/INR ↑ → NIFTY (−) | Empirical (weekly model) | MEDIUM |
| R13 | Rosneft/Lukoil sanctions → Indian Russian-crude imports ↓ | Directly reported | MEDIUM |
| R17 / R18 | Red Sea → freight; China stimulus → India FPI outflows | Hypotheses (data not retrieved) | LOW |

These fit the backend's knowledge base:
- R06 and R07 support existing rules: `kb.energy.oil_to_india_omc_margins` and the airline-margin chain.
- **R04 should lower the reliability of `kb.energy.cad_to_inr` at short horizons.**
- R09 and R10 suggest adding an S&P 500 → NIFTY co-movement edge.

---

## Deliverable 9 — Unresolved questions and gaps

1. **Event timing.** Times are approximate for 39 events, exact for 8, and only date-level for 4 (EV037 DeepSeek, EV047 the 2026 strikes, EV049 the interim deal, EV050 the renewed strikes). Intraday data would be needed to separate pre-news and post-news trading.
2. **Discrepancies with sources:**
   - Demonetisation: the source's "6%" vs −1.31% at the close.
   - USD/RUB 2022: Yahoo's −1.9% vs the sources' −26% to −40%.
   - Brent spot vs futures for EV046.
3. **Unavailable data:**
   - Daily Indian 10-year yields, so the bond-market channel for India is untested.
   - Freight and tanker rates, so the shipping channel is untested.
   - NIFTY Financial Services, Energy and Metal indices.
   - FPI flows.
   - LME aluminium.
4. **Confounders not screened:** scheduled FOMC/MPC meetings, earnings and macro releases. Only events in the dataset are flagged as concurrent.
5. **Survivorship and structural breaks:**
   - The stock basket was chosen with 2026 hindsight.
   - HDFC Bank merged with HDFC Ltd in July 2023.
   - Yahoo's back-adjusted prices change as new corporate actions occur.
6. **Market closures:** the MOEX suspension in 2022, TASE's move from Sunday to Monday–Friday trading in 2026, and Chinese and Israeli holiday gaps.
7. **Incomplete period:** October 2026. EV051's windows have mostly not elapsed (132 rows `NOT_YET_ELAPSED`, 30 `NOT_YET_PUBLISHED_BY_SOURCE`).
8. **Subjective inputs:** the A–F classifications and relevance labels are analyst judgements. Measured severity is provided alongside them for that reason.
9. **Curated dates in the backend:** the backend's `historical_events.json` dates should be cross-checked against this dataset. This dataset's sources are newer.
10. **Licensing:** Yahoo data cannot be redistributed. For any public release, switch the equity data to a licensed provider (NSE, or a paid vendor).

---

## Final recommendation

**The dataset is ready for:**
- (a) an event study and evidence for the knowledge graph, and
- (b) training a **weekly or daily shock-sensitivity model** (Task B) that uses events as conditioning information.

The model should report uncertainty explicitly and refuse out-of-range scenarios.

**It is not ready for, and with 27 independent groups cannot support,** an event-level model that predicts the market impact of Black Swan events (Task A).

Before training, collect the data listed in Deliverable 7, above all FPI flows and daily G-Sec yields.
