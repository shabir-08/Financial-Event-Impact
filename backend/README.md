# Financial Event Market Impact Graph — Backend

Backend for **Hackwave 3.0: tracing how financial events propagate across sectors and assets.**
It turns unstructured financial news into structured events, builds an **event-specific knowledge
graph**, traces **ranked propagation paths** to potentially affected assets, adds **historical market
context** where data exists, and produces an **evidence-grounded explanation**. Everything is
persisted in PostgreSQL and exposed through a FastAPI REST API for a separately built frontend.

It is not a news summariser and it is not a price predictor. Scores are heuristic rankings,
**not probabilities**, and graph edges are **potential mechanisms, not causal claims**.

```
news provider ─► ingest/dedupe ─► pre-filter ─► LLM classify ─► LLM entities ─► normalise
     ─► LLM relationships (passages verified verbatim) ─► associate with existing event or create
     ─► graph: event + REPORTED edges + event triggers + knowledge-base expansion (INFERRED)
     ─► bounded path search & ranking (NetworkX) ─► market data: observed reaction + historical
        comparisons ─► re-score with historical support ─► persist ─► evidence package
     ─► LLM explanation ─► reference/number validation ─► REST API
```

---

## Contents
1. [Quick start (mock mode, no credentials)](#1-quick-start-mock-mode-no-credentials)
2. [Configuration and credentials](#2-configuration-and-credentials)
3. [Running the API, worker and demo](#3-running-the-api-worker-and-demo)
4. [Tests](#4-tests)
5. [How the analysis works](#5-how-the-analysis-works)
6. [API reference](#6-api-reference)
7. [Project layout and extending](#7-project-layout-and-extending)
8. [Troubleshooting](#8-troubleshooting)
9. [Known limitations](#9-known-limitations)

---

## 1. Quick start (mock mode, no credentials)

**Prerequisites:** Python 3.11+ (developed on 3.14), Docker (for PostgreSQL), git.

```bash
cd financial-impact-graph
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d                 # PostgreSQL 16 on localhost:5433 (+ a separate test DB)
cp .env.example .env                 # defaults: LLM_PROVIDER=mock, NEWS_PROVIDER=gdelt, MARKET_DATA_PROVIDER=none
alembic upgrade head                 # create the schema
uvicorn app.main:app --reload        # http://127.0.0.1:8000/docs
```

The knowledge-base catalog (entities, assets, provider symbols, reference events) is seeded into
the database automatically at startup. The operation is idempotent.

Run the end-to-end demonstration (SIMULATED fixture articles, mock LLM, no network):

```bash
python scripts/demo.py
```

---

## 2. Configuration and credentials

All settings are environment variables; see [`.env.example`](.env.example) for the full list.
Secrets are held as `SecretStr`, are never returned by the API (`/api/health/integrations` reports
only whether a credential is *present*), and are redacted from logs.

| Integration | Setting | Credential | Notes |
|---|---|---|---|
| LLM (mock) | `LLM_PROVIDER=mock` | none | Deterministic keyword/catalog rules over the actual article text. Every output is labelled **SIMULATED** and runs are recorded with `mode=SIMULATED`. |
| LLM (Claude) | `LLM_PROVIDER=anthropic`, `LLM_MODEL` (default `claude-opus-5-5`), `LLM_EFFORT` | `ANTHROPIC_API_KEY` | Official `anthropic` SDK, structured outputs (`output_config.format`), server-side refusal fallback (`LLM_USE_SERVER_FALLBACKS`). **Billed API usage; a Claude.ai / Claude Max subscription does not provide API credits.** |
| LLM (Gemini) | `LLM_PROVIDER=gemini`, `GEMINI_MODEL` (default `gemini-2.5-flash`) | `GEMINI_API_KEY` | Free tier key from Google AI Studio (low per-minute/day limits; Google may use free-tier data to improve its products). Uses Gemini's OpenAI-compatible endpoint. |
| LLM (Groq) | `LLM_PROVIDER=groq`, `GROQ_MODEL` (default `llama-3.3-70b-versatile`) | `GROQ_API_KEY` | Free tier, no card, open models; small tokens-per-minute limits on free tier. |
| LLM (xAI Grok) | `LLM_PROVIDER=xai`, `XAI_MODEL` (no default) | `XAI_API_KEY` | Set the Grok model your account can use. |
| LLM (Ollama) | `LLM_PROVIDER=ollama`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL` | none | Runs locally; free; quality depends on the model and your hardware. |
| **LLM fallback chain** | `LLM_PROVIDER=fallback`, `LLM_FALLBACK_CHAIN=gemini,groq`, `LLM_FALLBACK_COOLDOWN_SECONDS` | keys of the members | Tries providers in order per call (see §5.9). Members without a key are skipped; mock is never allowed. |
| News (GDELT) | `NEWS_PROVIDER=gdelt` | none | GDELT DOC 2.0 API. Headlines + metadata only (no article bodies). Rate-limited (~1 request / 5 s). |
| News (Finnhub) | `NEWS_PROVIDER=finnhub` | `FINNHUB_API_KEY` | `/news` endpoint, headline + summary. Key sent as a header, never in URLs. |
| News (fixture) | `NEWS_PROVIDER=fixture` | none | SIMULATED demo articles in `data/fixtures/articles.json` (example.com URLs). |
| Market data (none) | `MARKET_DATA_PROVIDER=none` | none | Historical analysis reports `UNAVAILABLE`. |
| Market data (Yahoo) | `MARKET_DATA_PROVIDER=yahoo_chart` | none | **Unofficial, undocumented endpoint, for research/demo use only. Verify Yahoo's terms before any other use.** Broad coverage (NSE/BSE, US, FX, futures); Russian data may be missing. |
| Market data (Alpha Vantage) | `MARKET_DATA_PROVIDER=alphavantage` | `MARKET_DATA_API_KEY` | Official API. US equities/ETFs and FX only in this adapter; the free tier returns ~100 recent sessions, so older historical windows are `UNAVAILABLE`. |

A missing optional integration never disables unrelated features. Without an LLM key, LLM-dependent
endpoints return `503 configuration_error` while every read endpoint keeps working. A misconfigured
real provider is **never silently replaced by the mock**.

---

## 3. Running the API, worker and demo

```bash
uvicorn app.main:app --reload                       # API + Swagger UI at /docs, ReDoc at /redoc
python -m app.workers.pipeline_worker --once        # one ingest → detect → analyse cycle
python -m app.workers.pipeline_worker --interval 900
```

**Demonstration** (`scripts/demo.py`, drives everything through the REST API and writes every
response to `demo_output/<timestamp>/`):

```bash
python scripts/demo.py                                      # SIMULATED articles, mock LLM
python scripts/demo.py --news gdelt --market yahoo_chart    # REAL GDELT headlines + REAL Yahoo prices
python scripts/demo.py --llm anthropic --news gdelt --market yahoo_chart   # real Claude (billed)
python scripts/demo.py --base-url http://127.0.0.1:8000     # against a running server
```

The demo prints, for the best-covered event: sources, reported primary effects, entity
normalisation counts, graph size by edge status, pipeline steps, top ranked paths with edge
statuses, potentially affected assets with market-data status and observed returns, and the
validated explanation.

---

## 4. Tests

```bash
pytest                    # 141 tests run by default (+5 opt-in live tests skipped); no paid or external calls
RUN_REAL_PROVIDER_TESTS=1 pytest tests/integration/test_real_providers.py   # opt-in live smoke tests
```

* Tests use `TEST_DATABASE_URL` (default: the compose test DB `financial_impact_graph_test`). If
  PostgreSQL is unreachable the suite falls back to SQLite and the PostgreSQL-only migration test skips.
* `tests/unit`: knowledge base, normalisation, LLM schemas, mock provider, Anthropic adapter (against a
  fake SDK client: request shape, retries, refusal, truncation, rate limits), scoring, applicability,
  graph construction, path ranking, cycle avoidance, event windows, provider parsing and HTTP failure
  modes (respx), explanation validation, log redaction.
* `tests/integration`: ingestion and deduplication, the full mock pipeline on PostgreSQL, event merging,
  failure handling (no mock substitution, ungrounded explanations rejected), market analysis with a
  test-only provider (its data is labelled simulated), provider outages producing `PARTIAL` runs,
  and an Alembic upgrade/downgrade check.
* `tests/api`: every endpoint, validation errors, 404s, pagination, background vs. synchronous
  analysis, user-supplied input labelling, and no credential leakage.

---

## 5. How the analysis works

### 5.1 Evidence statuses
| Status | Meaning |
|---|---|
| `REPORTED` | Stated in a source article; the supporting passage was verified **verbatim** against the article text. |
| `UNVERIFIED` | Claimed by extraction, but the passage could not be found in the article (low evidence score). |
| `INFERRED` | From the economic knowledge base or an event-trigger rule. **Never attributed to the article.** |
| `OBSERVED` | Measured in market data (event → asset co-movement). Displayed only and **never used for path search**. |

Entities are stored with `origin=ARTICLE` (explicitly mentioned) or `origin=INFERRED` (introduced by a
knowledge-base expansion in a given analysis run).

### 5.2 Entity normalisation (`app/services/entities/normalization.py`)
* Mentions resolve only by **exact canonical id or exact alias** (case/whitespace-insensitive).
* Multiple candidates or a type mismatch produce `AMBIGUOUS`; no match produces `UNRESOLVED`. Fuzzy matches are kept as
  suggestions only. **Tickers are never guessed.** Assets resolve only through the catalog, and
  provider symbols live in `asset_symbols`.

### 5.3 Knowledge base (`data/knowledge_base/`)
JSON files validated with Pydantic at startup; a broken reference fails fast.
* `relationships/*.json`: 57 economic rules (`source → target`, relationship type, effect sign,
  mechanism, applicability conditions, time horizon, rationale, reliability, relevance, evidence basis).
* `assets.json`: 41 assets with provider symbols and **exposure edges**. These are converted into rules
  so assets are reached the same way as any other node.
* `event_triggers.json`: connects an event type plus involved entities to a variable even when the article
  does not name it (e.g. a US–China tariff event connects to `variable:us_tariffs_on_china`).
* `entities.json`, `event_categories.json`, `source_quality.json`, `historical_events.json`.

Rule conditions: `event_types` and `requires_entities_any/all` are **hard**; if unmet, the rule is not
applied and the exclusion is recorded in `graph_stats.excluded`. `context_entities_any` is **soft**:
if none are present, applicability is multiplied by 0.7.

### 5.4 Relationship scoring (`app/services/relationships/scoring.py`)

```
base  = (w_c·C + w_e·E + w_r·R + w_h·H) / Σ w(available components)
score = A · base
```

| Component | Article edge (REPORTED/UNVERIFIED) | Knowledge-base edge (INFERRED) |
|---|---|---|
| C confidence | max extraction confidence, ×0.5 if passage unverified | rule `reliability` |
| E evidence | source-count factor (1 source 0.6, 2 → 0.8, ≥3 → 0.9) × (0.5 + 0.5·mean source quality); 0.2 if unverified | by evidence basis: instrument definition 0.9, established mechanism 0.6, empirical association 0.5, contested 0.3 |
| R relevance | 1.0 primary effect, 0.8 other stated relationship | rule `economic_relevance` |
| H historical | not applicable | directional consistency vs. comparable past events (final edge into an asset), else missing |
| A applicability | 1.0 | 1.0, or 0.7 when soft context is absent |

* Default weights 0.30 / 0.30 / 0.25 / 0.15 (`SCORE_WEIGHT_*`) are **heuristic and uncalibrated**.
* **Missing H is not scored as zero.** H and its weight are dropped and the other weights are
  renormalised; `historical_support_status` records why (`UNAVAILABLE`, `INSUFFICIENT_DATA`,
  `NO_COMPARABLE_EVENTS`, …).
* Unknown news domains get a neutral 0.6 source quality, flagged as unassessed (not zero).
* All components and the final score are stored on every `relationships` row.

### 5.5 Graph construction and path ranking
* `GraphBuilder` (NetworkX `DiGraph`) runs these steps:
  1. Add the event node and the article-mentioned entities.
  2. Add REPORTED/UNVERIFIED claim edges. If articles disagree on direction, the edge becomes
     context-dependent and the conflict is recorded.
  3. Add matching event triggers.
  4. Run a bounded BFS over applicable rules (`GRAPH_KB_EXPANSION_DEPTH`, `GRAPH_MAX_NODES`).
  5. Prune inferred dead ends that reach no asset.
* "Mentioned in the article" creates a non-traversable *involvement* edge for display. A mention alone
  never implies an impact path.
* `PathAnalyzer` enumerates **simple paths** (cycle-free) from the event to each reachable asset up to
  `PATH_MAX_DEPTH`. It keeps the best `PATH_MAX_PER_ASSET` per asset and `PATH_MAX_TOTAL` overall:

  ```
  path_score = geometric_mean(edge scores) × 0.9^(edges−1) × (0.85 if any context-dependent edge)
  ```
  Net direction is the product of edge signs. Any context-dependent edge makes the direction
  `DIRECTION_UNCERTAIN`; opposite signs across an asset's paths give `MIXED_SIGNALS`. Each path stores
  its weakest link, edge-status counts and uncertainties. Betweenness centrality is stored per node.

### 5.6 Market data and historical analysis (`app/services/market_data/`)
* **Anchor date:** the event's information time (earliest article timestamp) converted to the asset's
  exchange time zone.
* **Reference close:** the last close on a trading day **strictly before** the anchor date. Because
  intraday timing is unknown, the window may include same-day pre-announcement moves.
* **Window k:** the close of the k-th trading session on or after the anchor date (default k = 1, 3, 5, 20).
  Trading days are the dates present in the provider series, so each market's holidays are respected.
  Weekend-dated bars (provider artifacts) are dropped for markets that do not trade at weekends.
* Returns are in the quote currency. Yield instruments (`^TNX`) rise when bond prices fall; see
  `quote_semantics`.
* Statuses: `AVAILABLE`, `PARTIALLY_AVAILABLE`, `UNAVAILABLE`. Windows that have not elapsed are marked
  `NOT_YET_ELAPSED`. Nothing is interpolated or fabricated.
* **Observed reaction** (`observation_kind=CURRENT_EVENT`) is context only.
* **Historical support** (`HISTORICAL_EVENT`) uses only reference events whose reported direction on
  the path's *seed variable* is known. For example, an OPEC+ cut (oil UP) and the 2020 price war (oil DOWN)
  imply opposite predicted signs for the same path. Each comparison is scored on the 5-day return:
  consistent = 1, inconsistent = 0, and |r| < 0.25% = 0.5. The mean is used only when at least
  `HISTORICAL_MIN_COMPARISONS` events have data.
* Reference events: 13 hand-curated, well-known events (`CURATED_REFERENCE`, dates to be verified), plus
  real events this system has analysed (`SYSTEM_DETECTED`). Simulated events are never added.
* Bars are cached in `market_data`. If no provider is configured now but an earlier run cached data, the
  market endpoints serve the cache only and never fetch.
* **Why data is missing** is reported as a limitation `{code, source, message, detail}`. When several
  apply, the most fundamental one is shown:

  | Code | Source | Meaning |
  |---|---|---|
  | `NOT_CONFIGURED` | integration | `MARKET_DATA_PROVIDER=none` |
  | `NO_PROVIDER_COVERAGE` | provider_coverage | No symbol mapping, or the provider has no data for the symbol |
  | `PROVIDER_ERROR` | provider_outage | The provider failed or rate-limited the request |
  | `MISSING_OBSERVATIONS` | missing_observations | Data exists, but bars needed for the calculation are missing |
  | `NOT_YET_ELAPSED` | timing | The event is too recent for the window |
  | `FUTURE_RANGE` | timing | The requested range is in the future |
  | `NOT_REQUESTED` | analysis_scope | The asset was outside the top `MARKET_MAX_ASSETS` analysed in that run |
* **Gaps:** weekdays with no bar are reported. A single missing weekday is flagged `likely_holiday`, and
  leading/trailing gaps are reported against the requested range. A daily return that spans a gap is
  flagged `return_spans_gap`.
* **Freshness:** the latest observation date, `retrieved_at`, and `sessions_since_latest`. A series is
  `is_stale` when more than 2 expected sessions have passed since its latest bar, and a bar dated today is
  flagged `latest_may_be_incomplete`. `usable_as_current_price` is true only when the series is neither
  stale nor incomplete.

### 5.7 Evidence-grounded explanation (`app/services/explanations/`)
The evidence package is built from persisted rows only. It contains the event, articles (`A*`), verified
passages (`P*`), relationships (`R*`) with score components, candidate paths (`PATH*`), candidate
assets, market observations (`M*`), conflicting evidence, missing data and limitations.

The response is then validated:
* every cited reference id must exist in the package;
* every asset must be a candidate;
* **every percentage in the text must appear in the package**;
* over-confident or probabilistic language is rejected.

One corrective retry is allowed. If it still fails, invalid references are removed (`SANITIZED`) or the
explanation is rejected (`FAILED_VALIDATION`) and the run becomes `PARTIAL`.

Article text is treated as untrusted in all prompts; it is wrapped in tags and explicitly marked as
data, not instructions.

### 5.8 Event detection and association
* **Stage 1:** a keyword/source/language pre-filter with no LLM call.
* **Stage 2:** LLM classification against the `EventType` enum (22 categories, metadata in
  `event_categories.json`).
* Articles merge into an existing event only if all of these hold: same event type, within 48 h, and
  primary-effect overlap ≥ 0.5 with entity overlap ≥ 0.2 (or near-identical titles).
  **Shared entities alone never merge events.**
* Verification status:
  * `SINGLE_SOURCE` or `CORROBORATED`, the latter requiring ≥ 2 distinct domains;
  * `USER_SUPPLIED` for `POST /api/events/analyze`;
  * `SIMULATED` for fixture articles.
* Each event keeps `processing_history` and `extraction_version`; each run keeps
  `analysis_version`, the knowledge-base hash and a config snapshot.

### 5.9 LLM providers and the fallback chain
* Gemini, Groq, xAI Grok and Ollama share one adapter (`services/llm/openai_compatible.py`) that calls
  their OpenAI-compatible `/chat/completions` endpoint with plain `httpx`; keys go in the
  `Authorization` header only.
* Structured output: `response_format=json_schema` (best-effort) plus the JSON schema in the system
  prompt. If a provider/model rejects `json_schema` (HTTP 400), the adapter switches to `json_object`.
  Every response is validated with Pydantic, with one corrective retry; truncation (`finish_reason=length`)
  and content-filter refusals are structured errors.
* `LLM_PROVIDER=fallback` (`services/llm/fallback.py`) tries `LLM_FALLBACK_CHAIN` in order **per call**:
  * **Fail over** on outages, timeouts, rate limits, bad keys or unknown models, and on invalid or refused output.
  * **Cooldown:** a rate-limited or failing provider is skipped for `LLM_FALLBACK_COOLDOWN_SECONDS`;
    a bad key is skipped for 10 minutes.
  * **All fail:** the call fails with a structured error listing every attempt.
* Traceability: each event stores the provider that actually served it (`events.llm_provider`) and
  `processing_history[].llm_served_by` with the failover trail; the run's explanation stores its
  provider and trail. `/api/health/integrations` lists every chain member and what is missing.
* Note: free tiers have small limits (Groq free tier: a few thousand tokens per minute on 70B models), so
  the explanation call, which sends the whole evidence package, is the most likely call to fail over.

### 5.10 Run statuses
`COMPLETED`, `PARTIAL` (an optional step failed: market-data provider error or explanation
validation), `FAILED` (with a structured error). `mode` is `LIVE` (real LLM) or `SIMULATED` (mock LLM
and/or simulated articles).

---

## 6. API reference

Interactive documentation: `/docs` (Swagger) and `/redoc`. Errors always have the shape
`{"error": {"code", "message", "details"}}`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + database check |
| GET | `/api/health/integrations` | Provider configuration/availability (no secrets) |
| GET | `/api/articles` | Paginated articles; filters `status`, `provider`, `simulated`, `q` |
| GET | `/api/articles/{id}` | One article |
| POST | `/api/articles/ingest` | Fetch from news provider (`provider`, `query`, `limit`, optional background `process`) |
| POST | `/api/articles/{id}/process` | Detect event + analyse one article (synchronous) |
| GET | `/api/events` | Paginated events; filters `event_type`, `verification_status`, `simulated`, `country` |
| GET | `/api/events/{id}` | Event detail, source articles, passages, processing history |
| POST | `/api/events/analyze` | **Controlled input:** analyse supplied text (labelled `USER_SUPPLIED`/`SIMULATED`) |
| POST | `/api/events/{id}/analyze` | New analysis run (202 + background, or `{"wait": true}`) |
| GET | `/api/events/{id}/entities` | Article entities with normalisation status + inferred entities |
| GET | `/api/events/{id}/graph` | Cytoscape.js `elements` (nodes/edges with scores, evidence, statuses) |
| GET | `/api/events/{id}/paths` | Ranked paths, affected assets, observations, explanation |
| GET | `/api/events/{id}/evidence` | Source articles, claims (verified or not), relationship evidence |
| GET | `/api/events/{id}/market` | **Market-analysis page data**: per asset summary, chart bars with event/window markers and gaps, freshness, backend-computed window returns + definitions, historical comparisons, availability with limitation code |
| GET | `/api/assets` | Asset catalog with provider symbols |
| GET | `/api/assets/{asset_id}/history` | Daily bars + returns, gaps, freshness, availability status + limitation code |
| GET | `/api/analysis/{id}` | Run status, steps, warnings, errors, explanation (`include_evidence_package=true` for the full package) |

Graph, path and evidence endpoints accept `analysis_id` to read a specific run; by default they use the
event's latest run.

---

## 7. Project layout and extending

```
app/
  main.py                 FastAPI app, lifespan (logging, KB validation, catalog seeding)
  api/                    routers: health, articles, events, graphs (entities/graph/paths/evidence), assets, analysis
  core/                   config (pydantic-settings), logging (redaction), errors (structured)
  database/               SQLAlchemy base + session
  models/                 18 tables (articles, events, event_articles, entities, event_entities, extracted_claims,
                          relationships, relationship_evidence, graph_nodes, impact_paths, asset_impacts,
                          market_data, market_observations, historical_events, analysis_runs, assets, asset_symbols,
                          ingestion_runs)
  schemas/                llm.py (structured-output schemas), api.py (request/response models)
  repositories/           shared queries (pagination, latest run)
  services/
    news/                 provider adapters (gdelt, finnhub, fixture) + ingestion/dedup
    llm/                  provider protocol, anthropic adapter, mock, prompts, factory
    events/               pre-filter, event processor (classification, extraction, association)
    entities/             extraction + normalisation
    relationships/        knowledge base, applicability, claims, scoring
    graph/                builder, paths, persistence, Cytoscape serialisation
    market_data/          provider protocol, yahoo_chart, alphavantage, event windows, service
    explanations/         evidence package, validation, explainer
    pipeline.py           orchestration + persisted step log
  workers/pipeline_worker.py
data/knowledge_base/      the economic knowledge base (JSON)
data/fixtures/            SIMULATED demo articles
alembic/                  migrations
scripts/demo.py           end-to-end demonstration
tests/                    unit / integration / api
```

* **Add an event category:** add an `EventType` value in `app/domain.py` and an entry in
  `event_categories.json` (plus triggers or rules if needed). No pipeline changes are required.
* **Add an economic relationship:** add a rule to any `data/knowledge_base/relationships/*.json`.
* **Add an asset:** add it to `assets.json` with provider symbols and exposures, then restart; the
  catalog re-seeds.
* **Add a provider:** implement the `NewsProvider` / `MarketDataProvider` / `LLMProvider` protocol and
  register it in the corresponding factory.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `database: unavailable` on `/api/health` | `docker compose up -d`; check `DATABASE_URL` (port **5433**). |
| `relation "..." does not exist` | `alembic upgrade head`. |
| `503 configuration_error` on analyse endpoints | `LLM_PROVIDER=anthropic` without `ANTHROPIC_API_KEY`; set the key or use `LLM_PROVIDER=mock`. |
| `429 rate_limited` from ingest (GDELT) | GDELT allows about one request every 5 s; wait and retry. |
| GDELT returns no/odd results | GDELT rejects very short keywords; quoted phrases work. Add `sourcelang:english`: non-English articles are dropped by the pre-filter. |
| Assets show `market_data_status: NOT_REQUESTED` | `MARKET_DATA_PROVIDER=none`, or the asset is outside the top `MARKET_MAX_ASSETS`. |
| History `UNAVAILABLE` with "no … symbol mapping" | The asset has no symbol for that provider (e.g. India 10Y G-Sec); add one to `assets.json` if a licensed source exists. |
| Windows `NOT_YET_ELAPSED` | The event is too recent; re-run analysis after more sessions. |
| Tests run on SQLite | PostgreSQL wasn't reachable at `TEST_DATABASE_URL`; start compose to run the full suite. |
| `docker compose up` doesn't create the test DB | The init script only runs on a fresh volume: `docker compose down -v && docker compose up -d`. |

---

## 9. Known limitations

* **No real LLM has been exercised against a live API in development**, because no Anthropic, Gemini,
  Groq or xAI key was available. The adapters are tested against a fake SDK client (Claude) and mocked
  HTTP (OpenAI-compatible providers): request shape, retries, json_schema fallback, refusal,
  truncation and error mapping. Run `RUN_REAL_PROVIDER_TESTS=1` with keys to smoke-test them. The
  default model names (`gemini-2.5-flash`, `llama-3.3-70b-versatile`) should be checked against each
  provider's current model list.
* The **mock LLM** is keyword-based. It cannot tell a forecast ("hikes expected") from a decision,
  misses implicit effects, and works on headlines only for GDELT/Finnhub items. Its output is always
  labelled SIMULATED.
* GDELT and Finnhub provide **no article bodies**, so extraction relies on headlines and summaries.
* The knowledge base is a hand-built starter set (57 rules, 41 assets) focused on oil, rates, FX,
  trade and geopolitics for India, the US, China, Russia and Israel. Rule reliabilities and scoring
  weights are **editorial heuristics, not calibrated**.
* Historical comparison uses a small curated list of reference events (dates to be verified) and
  5-day windows. It does not control for market conditions or confounding events, and **co-movement is
  not causation**.
* The Yahoo chart endpoint is unofficial (licensing restrictions). Alpha Vantage's free tier lacks long
  history. There is no licensed source for Indian G-Sec yields or Russian equities.
* Event windows use daily closes. Intraday timing and differences between exchange calendars and
  publication times are approximated, as documented in §5.6.
* Background jobs use FastAPI `BackgroundTasks` (in-process, not durable across restarts). Job status
  is persisted in `analysis_runs`, but a crashed process leaves runs in `RUNNING`.
