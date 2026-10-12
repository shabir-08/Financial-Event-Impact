# XYZ Financial Intelligence — Financial Event Market Impact Graph

**Hackwave 3.0 · PS 5 · AI + Finance + Knowledge Graphs**

> **One line:** We turn live financial news into a map of *how* an event can ripple through the economy to
> specific sectors, stocks and currencies — with the evidence for every step, the real market reaction,
> and a "what-if" simulator for shocks that haven't happened yet.

---

## Contents

1. [The 30-second pitch](#1-the-30-second-pitch)
2. [The problem and our answer](#2-the-problem-and-our-answer)
3. [The user workflow](#3-the-user-workflow-what-a-user-actually-does)
4. [Every feature, front to back](#4-every-feature-front-to-back)
5. [The engine: what happens to one news article](#5-the-engine-what-happens-to-one-news-article)
6. [How we stay honest (our differentiator)](#6-how-we-stay-honest-our-differentiator)
7. [Technology](#7-technology)
8. [Demo script for the judges (5 minutes)](#8-demo-script-for-the-judges-5-minutes)
9. [Questions judges may ask](#9-questions-judges-may-ask)
10. [Known limitations](#10-known-limitations)
11. [How to run it](#11-how-to-run-it)
12. [Glossary](#12-glossary)

---

## 1. The 30-second pitch

> "When OPEC cuts oil output, the headline says *oil rises*. But what does that mean for an Indian airline,
> an oil marketing company, or the rupee? Today an analyst has to work that chain out in their head.
>
> Our platform reads live news from publishers like the Economic Times, Mint, Hindustan Times, BBC and
> Bloomberg, detects the financial event, and builds a **knowledge graph** of how it can travel:
> *oil supply → crude price → India's import bill → rupee → OMC margins → HPCL shares*.
> Every link shows **why** it exists — a quote from the article or a rule from our economic knowledge
> base — and we check it against **real market data**.
>
> It also links today's news to **earlier related events**, and a **Black Swan simulator** lets you ask
> *'what if oil jumps 30%?'* using a model trained on about 9.5 years of Indian market data.
> And it never pretends: scores are rankings, not probabilities, and links are possible mechanisms, not proof."

---

## 2. The problem and our answer

| The problem | Our answer |
|---|---|
| News is read as **isolated stories**. | We show a **connected chain of impact** from the event to assets. |
| It's hard to see *which* stocks or sectors an event touches, and *how*. | A graph with **ranked pathways** from the event to each affected asset. |
| AI summaries can invent facts. | Every link carries **evidence**: an exact quote checked word-for-word against the article, or a written economic rule. Unverifiable claims are labelled. |
| "Will this move the market?" is usually guesswork. | We show the **observed** market reaction after the event and how **similar past events** behaved. |
| Events are analysed one at a time. | **Event Lineage** connects today's event to related earlier ones. |
| Nobody can test a crisis before it happens. | The **Black Swan simulator** runs "what-if" shocks through the graph and an ML model. |

**What it is not:** it is not a stock-tip tool and not a price predictor. It explains *possible* mechanisms
and shows the evidence. We say this clearly in the app and the reports.

---

## 3. The user workflow (what a user actually does)

```
 ┌──────────────┐   ┌──────────────┐   ┌───────────────────┐   ┌──────────────────────┐
 │ 1. Front page │──►│ 2. Log in    │──►│ 3. Overview       │──►│ 4. Analysis Workspace │
 │ live headlines│   │ (demo login) │   │ list of events,   │   │ knowledge graph of    │
 │ from RSS      │   │              │   │ add new events    │   │ the selected event    │
 └──────┬───────┘   └──────────────┘   └───────────────────┘   └──────────┬───────────┘
        │ "Analyse" on a headline                                           │
        └──────────────► runs the full analysis ─────────────────────────────┤
                                                                            ▼
   ┌───────────────────┬────────────────────┬──────────────────┬──────────────────────┐
   │ 5. Propagation    │ 6. Event Lineage   │ 7. Market        │ 8. Evidence &         │
   │ Path: ranked      │ related earlier /  │ Analysis: real   │ Sources: the quotes   │
   │ chains to assets  │ later events       │ price reaction   │ behind every link     │
   └───────────────────┴────────────────────┴──────────────────┴──────────────────────┘
                                         │
                ┌────────────────────────┴─────────────────────────┐
                ▼                                                  ▼
   ┌──────────────────────────┐                     ┌──────────────────────────────┐
   │ 9. Black Swan Simulator  │                     │ 10. Reports: 12-section       │
   │ "what if" shocks + ML    │                     │ report, export to PDF         │
   └──────────────────────────┘                     └──────────────────────────────┘
```

**Step by step:**

1. **Open the front page** (`/`): "The global briefing" shows today's real headlines and images from
   publisher RSS feeds. Already-analysed events are shown first; fresh headlines say *"not analysed yet"*.
2. **Click "Analyse"** on a headline (or log in first): the system reads the article, decides whether it is
   a financial event, and builds its impact graph (takes up to a few minutes because an AI model is used).
3. **Overview** lists all events. From here you can also **fetch more live news** (choose publishers) or
   **paste any article** to analyse.
4. **Analysis Workspace** shows the event's knowledge graph. Click any node (e.g. *Crude oil price*) or edge to
   see what it is and why it is there.
5. **Propagation Path** lists the strongest chains from the event to each asset, step by step.
6. **Event Lineage** shows earlier/later events that share the same economic drivers.
7. **Market Analysis** shows how the affected assets actually moved after the event.
8. **Evidence & Sources** shows the exact article passages and knowledge-base rules behind every link.
9. **Black Swan Simulator** lets you pick a crisis (oil shock, rate shock, trade war…) and set its size.
10. **Reports** turns an event or a simulation into a 12-section report you can download as PDF.

---

## 4. Every feature, front to back

Each feature below has two parts: **what you see** and **what happens behind it**.

### 4.1 Live front page ("The global briefing")

**What you see:** a newspaper-style page with real headlines, publisher images and times — e.g. *"FII Selloff
in Indian Equities Intensifies (Economic Times)"*. Analysed events have **Learn more**; new headlines have
**Analyse** and **Read at {publisher}**. A *Demo edition* (clearly labelled fictional stories) exists for offline demos.

**Behind it:**
- The backend reads **RSS feeds** — the free, official machine-readable feeds that publishers provide
  (Hindustan Times, Economic Times, Mint, BBC, Bloomberg). No API key is needed.
- Feeds are parsed **safely** (protected against malicious XML), duplicates are removed, and each article keeps
  its publisher name and link for attribution. Images come from the publisher's own feed; if a feed has no
  image (Bloomberg), we show the publisher name instead of a stock photo.
- Only headline + short summary are stored (full articles are the publisher's content).

### 4.2 Login

**What you see:** a login / create-account dialog.

**Behind it:** this is a **demo login stored in the browser** (any email and password work). It controls
navigation only; there is no server-side user account system yet. *Say this honestly if asked.*

### 4.3 Overview and "Add events"

**What you see:** all events with their type, date, source and a **SIMULATED** badge on test data.
The **Add events** panel has two tabs:
- **Fetch live news** — pick a source (RSS publishers, GDELT, Finnhub), optional keyword, number of articles.
- **Analyse an article** — paste a headline and text of any article.

**Behind it:** fetched articles are stored, deduplicated, quickly **pre-filtered** for financial relevance
(cheap keyword check, so we don't spend AI calls on cricket scores), then analysed in the background.
The page refreshes itself as new events appear. Pasted text is labelled *user-supplied*.

### 4.4 Analysis Workspace — the knowledge graph

**What you see:** an interactive graph. The event sits in the middle; around it are entities such as
*Crude oil price*, *India's oil import bill*, *Value of the rupee*, *HPCL shares*. Arrows show possible effects.
Click a node or edge for details, a mini price chart, and the evidence.

**Behind it (the core of the project):**
1. **Entities** (companies, commodities, currencies, indicators…) are extracted from the article by an AI model
   and **matched to a fixed catalogue** of 103 economic entities and 41 tradable assets, so "USD/INR",
   "rupee-dollar rate" and "USDINR" all become the same node.
2. **Article links (REPORTED):** relationships the article itself states, e.g. *"OPEC cut raises crude prices"*.
   The supporting sentence must appear **word-for-word** in the article, otherwise the link is marked **UNVERIFIED**.
3. **Knowledge-base links (INFERRED):** our hand-written economic rules add well-known mechanisms the article
   doesn't spell out, e.g. *higher crude → higher import bill for India → pressure on the rupee*. A rule is only
   used if its conditions fit the event.
4. **Scoring:** every link gets a support score (0–1) from confidence, evidence quality, economic relevance,
   historical support and applicability. It is a **ranking, not a probability**.

### 4.5 Propagation Path

**What you see:** "Path #1 to HPCL: Event → Crude oil price → India's oil import bill → OMC margins → HPCL",
each step labelled *reported* or *inferred*, the direction (*potential upward/downward pressure*), and any
uncertainties ("this link depends on context").

**Behind it:** the graph is searched for all chains from the event to every asset (up to a maximum length).
Each chain is scored: *average strength of its links × a small penalty for each extra step*. Longer chains
rank lower because every extra step adds uncertainty. If links point in opposite directions we say
*mixed signals* instead of guessing.

### 4.6 Event Lineage (newest feature)

**What you see:** for the selected event, the **earlier (and later) events that share its economic drivers**:
a merged graph of all of them, a timeline (each event marked *live* or *expired*), and for every link a card
explaining **which shared entities caused it** and how much each counted.

Example: *OPEC cut → India oil import bill rises → rupee under pressure*. Open the rupee event and you see the two
earlier events behind it.

**Behind it:**
1. After each analysis, the system lists the event's important entities (from its ranked paths) and their roles:
   *trigger*, *intermediate* or *asset*.
2. It compares the event with every earlier event using **TF-IDF similarity** — entities that appear in almost
   every event (USD/INR, crude oil, RBI) count for very little, so they can't link events on their own.
3. A link needs ≥ 2 shared entities, at least one of them specific (not a common hub, not just the final stock),
   and a similarity of at least 0.25. Each event keeps at most 3 "parents"; the strongest is the *primary* one.
4. **News fades:** each event's relevance halves over a set time — about 7 days for a company story, 14 for a
   central-bank decision, 21 for a commodity shock, 30 for a war — so old events stop being linked as parents.
   A very similar but faded event is shown as a **historical analogue**; a near-identical report from the same
   days is flagged as a **duplicate**.
5. A chain's strength is the **product** of its link strengths, so A→B→C is weaker than B→C alone.
6. All of this is stored per analysis and re-computed safely when an event is re-analysed or arrives late.

> Current status: built, tested and running. With today's small set of real events no links have formed yet;
> they appear automatically as more news is analysed.

### 4.7 Market Analysis

**What you see:** for each affected asset, how its price **actually moved** in the days after the event,
with the instrument and data provider named. If data is missing you see *why* (e.g. market closed, symbol not
available) — never a made-up number.

**Behind it:** daily prices come from a market-data provider (Yahoo Finance chart data). We measure returns over
fixed windows after the time the news was **first reported**, and compare with how the same asset reacted to
**similar historical events**. That historical agreement feeds back into the link scores (*historical support*).
Price moves are shown as **co-movement, not proof of cause**.

### 4.8 Evidence & Sources

**What you see:** for every link, the exact article passage (marked *verified* if found word-for-word), the
publisher, and for inferred links the knowledge-base rule and its written rationale.

**Behind it:** this is the **evidence package** — the same package is given to the AI to write the explanation,
and the AI is **only allowed to use facts from it**. Its answer is then checked: any number or reference not in
the evidence is rejected or removed.

### 4.9 Black Swan Simulator

**What you see:** pick a crisis — **global oil supply shock, Middle East geopolitical crisis, US interest-rate
shock, US–China trade war, pandemic supply-chain shock** — set its size, and watch a **3D graph** light up as the
shock spreads. You get a timeline, a summary, ML estimates for Indian stocks/indices, historical look-alike
periods, and live price charts for nodes.

**Behind it:**
1. **Graph propagation:** the shock is pushed through the same knowledge graph (marked *ASSUMED*, because it is a
   hypothetical input, not news).
2. **ML model (`scenario_conditional_v1`):** a Ridge regression trained on **about 9.5 years of weekly market data
   (493 weeks, including 51 sourced historical events)** that estimates the 5-day return of **18 Indian indices and stocks** *given* moves in Brent crude,
   the S&P 500, USD/INR, gold and the US 10-year yield.
   - On data it never saw (2023–2026) it beats the "predict 0%" baseline (average error 2.24 vs 2.35) and gets the
     direction right about **60%** of the time.
   - It answers *"historically, when these inputs moved like this, what did Indian stocks do?"* — a
     **conditional association, not a forecast**.
   - The training data went through a **leakage audit** (no future information used) and an independent check.
     A second, true-forecasting model showed **no skill**, so we do **not** use it — and we say so.
3. **Historical patterns:** the system finds past weeks whose market conditions looked most similar and shows
   what happened next (shown as history, not as a forecast).

### 4.10 Reports

**What you see:** one click turns an event or a simulation into a professional report with **12 sections**:
Executive Summary · Event and Scenario Details · Evidence and Sources · Knowledge Graph · Impact Pathways ·
Sector Impact · Company and Asset Analysis · Historical Market Behaviour · Quantitative ML Predictions ·
Timeline · Uncertainty and Alternatives · Sources and Methodology. Download as **PDF**.

**Behind it:** the report is assembled from the stored analysis (not re-invented by AI). Each section has
citations; a section with no data says **"unavailable"** and why. Identical reports are not duplicated.

### 4.11 Stored Analyses, Settings and Demo mode

- **Stored Analyses:** every analysis run is saved with its steps, versions and warnings, so results are reproducible.
- **Settings:** switch **Demo mode** on/off. Demo mode shows clearly labelled fictional data for offline
  presentations; live mode never silently falls back to demo data — if the backend is down you see an error.

---

## 5. The engine: what happens to one news article

```
 Publisher RSS ─► 1 Ingest & dedupe ─► 2 Pre-filter ─► 3 AI: is it a financial event? what type?
      │
      ▼
 4 AI: extract entities ─► 5 Match to catalogue ─► 6 AI: extract stated relationships (quotes verified)
      │
      ▼
 7 Build event graph (article links + knowledge-base rules) ─► 8 Find & rank paths to assets
      │
      ▼
 9 Market data: real reaction + similar past events ─► 10 Re-score links ─► 11 Save everything
      │
      ▼
 12 Evidence package ─► 13 AI explanation (checked against evidence) ─► 14 Event Lineage links
      │
      ▼
 REST API ─► React frontend
```

| Step | In simple words |
|---|---|
| 1 Ingest | Download headlines from RSS (or GDELT/Finnhub), skip ones we already have. |
| 2 Pre-filter | Cheap keyword check — drop sport, entertainment, etc. before using AI. |
| 3 Classify | AI decides if it is a financial event and which of 22 types (rate change, energy supply, war…). Similar articles about the same event are merged. |
| 4–5 Entities | AI lists companies, commodities, currencies…; we map each to one catalogue ID (no duplicates). |
| 6 Relationships | AI lists cause-effect statements with the exact sentence; we check the sentence really is in the article. |
| 7 Graph | Event + article links + matching economic rules from the knowledge base. Dead ends are removed. |
| 8 Paths | All chains from the event to assets, ranked by strength. |
| 9–10 Market | Real price moves after the event + comparison with similar past events; agreement raises link scores. |
| 11 Save | Graph, paths, scores and evidence are saved in PostgreSQL with version numbers. |
| 12–13 Explain | AI writes a plain-English explanation using **only** the evidence package; we validate it. |
| 14 Lineage | Link the event to related earlier events (Section 4.6). |

**AI models used:** Google **Gemini 2.5 Flash**, with automatic fallback to **Groq (gpt-oss-120b)** if Gemini is
busy or rate-limited. If an optional step fails (e.g. market data or the explanation), the analysis is marked
*partial* and still saved — it never silently fills the gap with fake data.

---

## 6. How we stay honest (our differentiator)

Say this to the judges — it is what separates us from "an AI that summarises news":

1. **Every link has a source label:** *REPORTED* (quoted from the article and verified), *INFERRED* (economic rule),
   *OBSERVED* (market data), *UNVERIFIED* (claimed but quote not found), *ASSUMED* (simulator input).
2. **Scores are rankings, not probabilities.** We never say "70% chance HPCL falls".
3. **Graph links are possible mechanisms, not proven causes.** Price moves are co-movement.
4. **No fake data:** missing market data shows the reason; the live app never swaps in demo data.
5. **AI is fenced in:** the explanation can only use the evidence package and is checked for invented numbers.
6. **Our ML model reports its weakness:** we published that the forecasting model has no skill and only use the
   scenario model, with its real accuracy.
7. **Everything is versioned and reproducible:** model, knowledge-base and configuration versions are stored with results.

---

## 7. Technology

| Layer | Tools |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Cytoscape.js (2D graphs), Three.js (3D simulator graph), Recharts (charts), jsPDF (PDF reports) |
| Backend API | Python, FastAPI, Pydantic |
| Database | PostgreSQL 16 (Docker), SQLAlchemy, Alembic migrations |
| Graph analysis | NetworkX |
| AI | Gemini 2.5 Flash → Groq gpt-oss-120b fallback (mock mode for tests) |
| News | Publisher RSS (HT, ET, Mint, BBC, Bloomberg), GDELT, Finnhub |
| Market data | Yahoo Finance chart data |
| ML | scikit-learn (Ridge regression), pandas, NumPy |
| Testing | pytest (~290 backend tests), Vitest (31 frontend tests), Playwright (end-to-end in a real browser) |

---

## 8. Demo script for the judges (5 minutes)

| Time | Do this | Say this |
|---|---|---|
| 0:00 | Open the front page | "These are today's real headlines from ET, Mint, HT, BBC and Bloomberg — read live from their RSS feeds." |
| 0:30 | Click **Learn more** on an analysed event → Workspace | "The AI read the article and built this graph. The event is in the centre; arrows are possible effects." |
| 1:15 | Click an edge, show its evidence | "REPORTED means the article said it — and we verified the exact sentence. INFERRED is an economic rule from our knowledge base." |
| 2:00 | **Propagation Path** | "Here are the ranked chains from the event to specific stocks, with the direction and the uncertainties." |
| 2:40 | **Market Analysis** | "And this is what the market actually did afterwards — observed data, not a prediction." |
| 3:10 | **Event Lineage** | "We also connect events over time: which earlier news shares the same drivers, and why." |
| 3:40 | **Black Swan Simulator** → oil supply shock | "What if oil spikes? The shock spreads through the graph, and our model trained on about 9.5 years of Indian market data estimates the reaction of 18 stocks and indices." |
| 4:30 | **Reports** → Download PDF | "One click gives a 12-section report with sources for every claim." |
| 4:50 | Close | "Not a black box, not a stock tip: a transparent map of how news moves markets." |

**Tip:** if the internet or AI quota fails during the demo, switch on **Demo mode** in Settings — it is clearly
labelled as fictional data.

---

## 9. Questions judges may ask

**How is this different from ChatGPT summarising news?**
The AI only extracts facts; the reasoning chain comes from a structured graph, a curated economic knowledge base,
verified quotes and real market data. Every step is shown and labelled.

**Can it predict stock prices?**
No, and we don't claim to. It shows possible mechanisms and the observed reaction. Our simulator model estimates
historical associations and we publish its accuracy (≈60% direction on unseen data).

**What if the AI makes something up?**
Quotes are checked word-for-word against the article; unverified ones are labelled. The explanation is checked
against the evidence package and invented numbers are rejected.

**Where does the knowledge base come from?**
Hand-written economic rules (energy, macro & rates, geopolitics & trade), each with a written rationale and
conditions for when it applies, plus a catalogue of 103 entities and 41 tradable assets.

**Why India-focused?**
The asset catalogue and ML model focus on Indian markets (NIFTY, SENSEX, Indian stocks, USD/INR), with global
drivers (oil, US rates, gold) as inputs.

**Does it scale?**
The pipeline runs as a background worker, everything is stored in PostgreSQL with indexes, and AI providers
fall back automatically when rate-limited.

**Is login secure?**
Login is a demo-only browser login for now; a real user system is future work.

---

## 10. Known limitations

- **AI rate limits:** free-tier AI keys allow limited requests; analysis can take minutes or wait for quota.
- **RSS gives headlines and short summaries only**, not full articles; Bloomberg's feed has no images.
- **Knowledge base coverage** is strongest for energy, rates, currencies and trade; other areas are thinner.
- **Event Lineage** needs more analysed events before links appear; its timing parameters are starting values.
- **ML model** is a historical association with modest accuracy and not validated for unseen crises.
- **Login** is a local demo, not real authentication.

---

## 11. How to run it

**Needs:** Python 3.11+, Node.js 18+, Docker.

```bash
# Backend (folder: backend/ in the repo, financial-impact-graph/ locally)
python -m venv .venv
.venv\Scripts\activate                # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d                  # PostgreSQL on port 5433
copy .env.example .env                # add GEMINI_API_KEY / GROQ_API_KEY; NEWS_PROVIDER=rss
alembic upgrade head                  # create the database tables
uvicorn app.main:app --port 8000      # API + docs at http://localhost:8000/docs

# Frontend (folder: frontend/)
npm install
npm run dev -- --port 5175            # open http://localhost:5175
```

Without API keys the backend can run in **mock mode** (`LLM_PROVIDER=mock`); results are then labelled SIMULATED.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **Event** | A financial happening detected in news (e.g. "RBI raises repo rate"). |
| **Entity / node** | A thing in the graph: company, commodity, currency, indicator, sector, asset. |
| **Edge / link** | A possible effect from one node to another, with direction and evidence. |
| **Knowledge graph** | The network of nodes and edges built for one event. |
| **Knowledge base** | Our curated economic rules and entity catalogue. |
| **Propagation path** | A chain of links from the event to an asset. |
| **Support score** | 0–1 ranking of how well-supported a link or path is. Not a probability. |
| **REPORTED / INFERRED / OBSERVED / UNVERIFIED / ASSUMED** | Where a link comes from (article / rule / market data / unverified claim / simulator input). |
| **RSS feed** | A free, official feed of headlines that publishers provide for apps to read. |
| **Event Lineage** | Links between events that share the same economic drivers over time. |
| **Half-life** | Time for an event's relevance to halve. |
| **Black Swan** | A rare, extreme shock (war, pandemic, oil crisis). |
| **Ridge regression** | A simple, robust ML model that learns weighted relationships from data. |
| **Leakage** | Accidentally training a model on information from the future; we audited for it. |
