# Autonomous Financial Event Market Impact Graph

> Trace how financial events propagate across sectors and assets.

**Hackwave 3.0 · PS 5 · AI • Finance • Knowledge Graphs**

> ⚠️ **Status: early draft.** This README describes the intended vision and architecture. Details will change as the project is built.

---

## 1. Overview

Financial events rarely affect a single company. A geopolitical conflict, a commodity shock, an interest-rate decision, or a regulatory change can ripple through economic variables, sectors, and financial instruments. Most tools present news as **isolated stories**. This project presents it as a **connected chain of impact**.

Given an unstructured financial news item, the system:

1. Detects the financial event
2. Extracts the relevant entities (companies, commodities, sectors, indicators, instruments)
3. Builds and updates a knowledge graph of relationships between them
4. Traces plausible propagation paths from the event to affected assets
5. Scores each relationship and path
6. Explains every connection with supporting evidence
7. Clearly communicates **uncertainty**, separating observed facts from inferred relationships

### Illustrative impact chain

```
Crude oil rises 12%
   → Inflation expectations increase
      → Interest-rate expectations shift
         → Banks and real estate may be affected
            → Relevant indices and assets respond
```

Real events branch, so the system traces **multiple** paths (e.g., the same oil spike may also pressure airlines and benefit oil producers).

---

## 2. The Problem

- News is consumed as disconnected headlines, so the second- and third-order effects of an event are easy to miss.
- Analysts manually connect events to sectors and assets, which is slow, subjective, and hard to audit.
- Predictions are often presented with false certainty, with no visible evidence trail.

## 3. Our Approach

We combine NLP, event extraction, knowledge graphs, time-series data, graph algorithms, and LLM-based reasoning into a single pipeline, with a frontend built to make the reasoning **visible and inspectable**.

**Core principles**

- **Explainability first:** every edge in the graph must answer "why does this connection exist?"
- **Fact vs. inference:** observed facts (stated in the source, visible in market data) are visually and structurally distinct from inferred relationships.
- **Honest uncertainty:** we use confidence scores and plausibility language ("may be affected"), never guarantees.
- **Dynamic by design:** the graph updates as new events arrive rather than being rebuilt from scratch.

---

## 4. Key Features

| # | Capability | Description |
|---|-----------|-------------|
| 1 | Event detection | Classify unstructured text into event types (commodity shock, rate decision, geopolitical, regulatory, etc.) with magnitude, direction, and time |
| 2 | Entity extraction | Pull out companies, commodities, sectors, indicators, and instruments |
| 3 | Relationship scoring | Identify links between entities and score strength and confidence |
| 4 | Knowledge graph | Construct and incrementally update a dependency graph |
| 5 | Propagation paths | Estimate plausible multi-hop paths and rank affected assets |
| 6 | Time-series integration | Cross-check inferred links against market data where available |
| 7 | Explanations and evidence | Show reasoning and source snippets for every chain |

---

## 5. System Architecture (planned)

```
┌────────────────────┐
│  News / Text Input │  (articles, headlines, reports)
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Event Detection    │  LLM / NLP classification
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Entity Extraction  │  NER + LLM structured output
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Relation Extraction│  identify + score relationships
│ & Scoring          │
└─────────┬──────────┘
          ▼
┌────────────────────┐        ┌─────────────────────┐
│ Knowledge Graph    │◄──────►│ Time-Series Data    │
│ (nodes + edges)    │        │ (prices, yields)    │
└─────────┬──────────┘        └─────────────────────┘
          ▼
┌────────────────────┐
│ Graph Algorithms   │  path finding, weighted ranking,
│                    │  per-hop impact decay
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ LLM Reasoning &    │  explanations, evidence, uncertainty
│ Explanation Layer  │
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Frontend           │  interactive graph + evidence panels
└────────────────────┘
```

### Graph model

**Node types:** Event · Economic Variable/Indicator · Sector · Company · Commodity · Instrument/Index

**Edge attributes (draft):**

- `relation`: e.g., raises, lowers, pressures, benefits
- `score`: strength of the relationship (0–1)
- `confidence`: certainty in the link (0–1)
- `type`: `observed` or `inferred`
- `evidence`: source snippet, data reference, or reasoning note
- `timestamp`: when the link was created or last updated

---

## 6. Frontend Experience

The frontend is a core part of the product, since the value is in *seeing* the chain of impact.

Planned views:

1. **Input panel:** paste or select a news event
2. **Extraction view:** source text with colour-coded highlighted entities
3. **Graph canvas:** animated, interactive dependency graph
4. **Path explorer:** switch between propagation paths, highlight one and dim the rest
5. **Affected assets:** ranked list with confidence indicators
6. **Evidence panel:** click any edge to see the explanation, source, and fact/inferred tag
7. **Time-series panel:** price reaction around the event for affected assets
8. **Legend:** line styles and opacity conventions for observed vs. inferred and confidence levels

**Design conventions (draft)**

- Solid edges = observed · Dashed edges = inferred
- Edge thickness = strength · Opacity = confidence
- Language like "may be affected" rather than definitive claims

---

## 7. Demo Flow

1. Introduce a financial news event
2. Watch entities get extracted and highlighted
3. See the connected graph build
4. Explore multiple propagation paths
5. Review the ranked, potentially affected assets
6. Click any connection to understand why it exists

---

## 8. Tech Stack (tentative)

> To be finalized.

- **Frontend:** React, a graph visualization library (Cytoscape.js / React Flow / Sigma.js), a charting library for time series
- **Backend:** Python, FastAPI
- **NLP / LLM:** LLM-based extraction and reasoning, optional FinBERT for finance-specific sentiment
- **Graph storage:** Neo4j or NetworkX
- **Market data:** public APIs and datasets (TBD)

---

## 9. Future Scope

### 9.1 Country-based editions

Region-specific versions tuned to local markets, regulations, and data sources:

- 🇮🇳 **India edition:** Nifty, Sensex, RBI policy, INR, SEBI regulation
- 🇬🇧 **UK edition:** FTSE indices, Bank of England policy, GBP, FCA regulation
- 🇺🇸 **USA edition:** S&P 500, Nasdaq, Dow, Federal Reserve policy, USD, SEC regulation

Each edition would carry its own entity vocabulary, sector mappings, relationship priors, and data feeds.

### 9.2 Subscription system

Tiered access to the platform, for example:

- **Free:** limited events per day, basic graph view
- **Pro:** unlimited events, deeper propagation paths, historical analysis, exports
- **Enterprise:** see below

(Tier structure and pricing to be decided.)

### 9.3 Enterprise portfolio and exposure tracking

For larger companies and institutions:

- Upload or connect **asset holdings and exposures**
- Track **gains and losses** against events
- **Automatically flag** when a new event affects the company's assets, with the impact chain that explains why
- Alerts and notifications for high-confidence, high-exposure events
- Audit trail of events, flagged exposures, and the reasoning behind each flag

### 9.4 Other ideas

- Streaming ingestion from live news sources
- Backtesting inferred relationships against historical events
- Collaborative workspaces and shared graphs
- Public API for third-party integration

---

## 10. Limitations and Disclaimer

- Relationships are **plausible inferences**, not guarantees.
- Outputs are for informational and research purposes only and are **not financial advice**.
- Quality depends on source data and model reasoning; confidence scores are indicative, not absolute.

---

## 11. Getting Started

> Setup instructions will be added as the project develops.

```bash
# clone the repository
git clone <repo-url>
cd <repo-name>

# frontend
cd frontend
npm install
npm run dev

# backend
cd ../backend
pip install -r requirements.txt
uvicorn main:app --reload
```

---

## 12. Team

> Add team members and roles here.

## 13. Roadmap

- [ ] Finalize problem scope and API contract (JSON schema)
- [ ] Frontend mock-data prototype
- [ ] Event and entity extraction pipeline
- [ ] Knowledge graph construction
- [ ] Propagation path algorithm
- [ ] Time-series integration
- [ ] Explanation and evidence layer
- [ ] End-to-end demo
- [ ] Future scope: country editions, subscriptions, enterprise tracking

---

*Built for Hackwave 3.0.*
