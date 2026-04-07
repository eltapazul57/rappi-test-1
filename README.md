# Rappi Operations Intelligence System

AI-powered conversational analytics for Rappi operations data — ask questions in natural language, get SQL-backed answers and an automated weekly insights report.

---

## Quick Start (from zero)

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org/) |
| OpenAI API key | — | [platform.openai.com](https://platform.openai.com/) |

### Step 1 — Add the data file

Place the Excel workbook at:

```
data/rappi_data.xlsx
```

The file is not committed to the repo. The backend loads it on startup and creates `data/rappi.db` automatically. If you update the Excel file, delete `data/rappi.db` and restart the backend.

### Step 2 — Configure environment variables

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set your OpenAI API key:

```
OPENAI_API_KEY=sk-...
```

All other values have sensible defaults and do not need to be changed for local development.

### Step 3 — Install and start the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload
```

**Alternative — with Poetry:**

```bash
cd backend
poetry install
poetry run uvicorn app:app --reload
```

The backend runs at **http://localhost:8000**. On first start you will see a log line like:

```
Database ready — 12573 metric rows, 1242 order rows.
```

If you see `Startup data load failed`, check that `data/rappi_data.xlsx` exists.

### Step 4 — Install and start the frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at **http://localhost:5173**.

### Step 5 — Open the app

Go to **http://localhost:5173** in your browser. You will see two tabs:

- **Chat** — ask questions in natural language
- **Insights** — generate the automated weekly report

---

## Environment Variables Reference

All variables live in `backend/.env`. Full list with defaults:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model used for SQL generation and responses |
| `MAX_TOKENS` | `1000` | Max tokens per LLM response |
| `MAX_RETRIES` | `2` | SQL retry attempts before returning an error |
| `MAX_CONVERSATION_HISTORY` | `10` | Turns of conversation context sent to the LLM |
| `ANOMALY_THRESHOLD` | `0.10` | Min week-over-week change to flag as anomaly (10%) |
| `TREND_MIN_WEEKS` | `3` | Min consecutive declining weeks to flag as trend |
| `BENCHMARK_STD_THRESHOLD` | `1.0` | Min z-score deviation to flag in benchmarking |
| `CORRELATION_MIN_ABS` | `0.3` | Min absolute correlation to report |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origins (comma-separated) |

---

## Project Architecture

### Repository Structure

```
/
├── backend/
│   ├── app.py                  # FastAPI entry point — /chat, /insights, /health
│   ├── graph/
│   │   ├── __init__.py         # LangGraph graph assembly and compilation
│   │   ├── state.py            # ChatState TypedDict shared across all nodes
│   │   ├── intent_classifier.py
│   │   ├── sql_generator.py
│   │   ├── sql_executor.py
│   │   ├── error_handler.py
│   │   ├── response_formatter.py
│   │   └── routing.py
│   ├── insights.py             # Automated insights engine (pure pandas, no LLM)
│   ├── db.py                   # Excel → SQLite loader + orders_enriched view
│   ├── prompts.py              # System prompt for SQL generation
│   ├── config.py               # All configuration from .env
│   ├── pyproject.toml          # Poetry dependency declaration
│   ├── requirements.txt        # pip fallback (mirrors pyproject.toml)
│   └── .env.example            # Environment variable template
├── frontend/
│   └── src/
│       ├── App.jsx             # Root component — tab navigation
│       ├── api.js              # Fetch client for /chat and /insights
│       └── components/
│           ├── Chat.jsx        # Conversational chat UI
│           └── Insights.jsx    # Weekly report UI
├── data/                       # ← place rappi_data.xlsx here (not committed)
└── README.md
```

### Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React 19 + Vite | Fast dev server, minimal bundle |
| Backend | FastAPI | Async, auto-docs at `/docs`, low boilerplate |
| LLM orchestration | LangGraph | Explicit graph flow, retry logic without spaghetti |
| LLM | GPT-4o | Best SQL generation accuracy in practice |
| Database | SQLite | Zero infra, loads from Excel on startup |
| Insights engine | pandas | Deterministic, fast, no LLM cost for analytics |
| Dependency mgmt | Poetry | Reproducible lockfile |

---

## Bot — How It Works

### Conversation Flow (LangGraph)

```
User message
      │
      ▼
intent_classifier          ← GPT-4o, temperature=0, max_tokens=5
      │
      ├─ "data_query" ──> sql_generator ──> sql_executor
      │                         ▲               │
      │                         │    error      ▼
      │                    error_handler ◄──────┤  (max 2 retries)
      │                                         │ success
      │                                         ▼
      └─ "general" ──────────────────> response_formatter
                                                │
                                                ▼
                                         answer + data + sql
```

**intent_classifier** — classifies the message as `data_query` (needs SQL) or `general` (conversational). Uses a single-word forced-choice prompt at temperature 0.

**sql_generator** — injects the full database schema + metric definitions + business term mappings into the system prompt, then asks GPT-4o to produce a SQLite query. On retry, the previous SQL error is appended so the model can self-correct.

**sql_executor** — runs the SQL against SQLite, returns JSON-serialised rows or an error string.

**error_handler** — logs the failure and increments `retry_count`. After `MAX_RETRIES`, routing sends the state to the response formatter with a graceful fallback message.

**response_formatter** — receives the results (or fallback) and produces a 3–6 sentence business-language answer. Always ends with a proactive follow-up suggestion. Responds in the same language as the user.

### Conversational Memory

Each session has a `session_id` (generated server-side on first request, persisted client-side). The server stores the last `MAX_CONVERSATION_HISTORY` turns per session in memory and appends them to every LLM call, enabling multi-turn context.

### SQL Generation Rules (key ones)

- Metric values are stored as normalized ratios — `0.85` means 85%. Never multiply by 100 in the query.
- Metric names must match exactly (e.g. `Perfect Orders`, not `Perfect Order`).
- Zone/city names use `LOWER(ZONE) LIKE '%name%'` — never exact match.
- Window functions (`LAG`, `LEAD`, `ROW_NUMBER`, `RANK`) are supported. The `FILTER` clause is not — use `CASE WHEN` instead.
- For trend questions, all 9 week columns (`L8W_ROLL` → `L0W_ROLL`) are returned in a single row per zone.
- For inference questions, `orders_enriched` is joined with `input_metrics` to surface both volume and operational metrics together.

### Business Term Mappings

| User says | SQL interprets as |
|---|---|
| "zonas problemáticas" / "problem zones" | zones where 3+ metrics are below country average in `L0W_ROLL` |
| "zonas críticas" | `ZONE_PRIORITIZATION = 'High Priority'` with deteriorating metrics |
| "zonas de alto rendimiento" | zones where most metrics are above country average |

---

## Insights Engine — How It Works

The insights engine runs entirely in pandas — no LLM, no API cost, deterministic output. It runs 5 analysis functions and assembles a Markdown report.

### Analysis Functions

**`detect_anomalies(df)`**
Week-over-week change between `L1W_ROLL` and `L0W_ROLL`. Flags any zone+metric where `|change| > ANOMALY_THRESHOLD` (default 10%). Uses absolute delta when the denominator is near zero to avoid meaningless large percentages. Handles "lower is better" metrics (e.g. `Restaurants Markdowns / GMV`) by flipping the improvement/deterioration label.

**`detect_concerning_trends(df)`**
Walks backwards through week columns from `L0W_ROLL`. Counts how many consecutive weeks the metric has been declining. Flags if streak ≥ `TREND_MIN_WEEKS` (default 3). These are structural problems, not one-off fluctuations.

**`benchmark_zones(df)`**
Groups zones by `COUNTRY + ZONE_TYPE + METRIC`. Computes z-score of each zone vs its peer group. Flags zones with `|z| > BENCHMARK_STD_THRESHOLD` (default 1.0) as outperforming or underperforming. Peer groups need at least 3 zones to be meaningful.

**`compute_correlations(df)`**
Pivots `input_metrics` to a zone × metric matrix using `L0W_ROLL`. Drops metrics with >50% null zones. Computes pairwise Pearson correlations. Reports pairs with `|r| > CORRELATION_MIN_ABS` (default 0.3).

**`detect_opportunities(df_metrics, df_orders)`**
Joins zones with strong order growth (≥10% over 5 weeks) against zones that are underperforming vs peers on at least one metric. These zones have demand already arriving but operational gaps that risk the growth.

### Report Structure

```
## High Priority Zone Watchlist     ← zones flagged in ZONE_PRIORITIZATION
## Executive Summary                ← 1 finding per analysis type, different countries
## Recommended Actions              ← top 3 scored by urgency × impact
## Opportunities                    ← growth zones with metric gaps
## Anomalies                        ← deteriorations + improvements
## Concerning Trends                ← structural multi-week declines
## Benchmarking                     ← underperformers + outperformers vs peers
## Key Metric Relationships         ← correlated metric pairs
```

Executive summary findings are deliberately drawn from different countries when possible to avoid all 5 bullets pointing at the same zone.

### Metric Formatting

Metrics are stored as normalized ratios. The engine formats them correctly per type:
- **Ratio metrics** (most): displayed as `85.3%`
- **`Gross Profit UE`**: displayed as raw decimal (it's a per-order margin value, not a 0–1 ratio)

---

## API Reference

### `POST /chat`

```json
Request:  { "message": "string", "session_id": "string | null" }
Response: { "answer": "string", "data": [...], "sql": "string | null", "session_id": "string" }
```

`data` contains the raw SQL result rows as a JSON array. `sql` contains the generated query (useful for debugging). If `session_id` is null, a new session is created and returned.

### `POST /insights`

```json
Response: { "report": "string (Markdown)" }
```

Runs all 5 analysis functions and returns the full executive report. No request body needed.

### `GET /health`

```json
Response: { "status": "ok", "database": "loaded | not loaded" }
```

### Debug Endpoints (development only)

| Endpoint | Returns |
|---|---|
| `GET /debug/tables` | All tables and views with row counts |
| `GET /debug/preview/{table}` | First N rows of a table (`input_metrics`, `orders`, `orders_enriched`) |
| `GET /debug/metrics` | All distinct metric names in the database |
| `GET /debug/insights/anomalies` | Raw anomaly detection output |
| `GET /debug/insights/trends` | Raw trend detection output |
| `GET /debug/insights/benchmarks` | Raw benchmarking output |
| `GET /debug/insights/correlations` | Raw correlation output |
| `GET /debug/insights/opportunities` | Raw opportunity detection output |
| `GET /debug/insights/report` | Full Markdown report (same as `/insights`) |

Interactive API docs available at **http://localhost:8000/docs**.

---

## Data Model

### `input_metrics` table (12,573 rows)

One row per `COUNTRY × CITY × ZONE × METRIC`. Week columns go from oldest (`L8W_ROLL`) to most recent (`L0W_ROLL`). Values are normalized ratios — `0.85` means 85%.

| Column | Type | Notes |
|---|---|---|
| COUNTRY | string | AR, BR, CL, CO, CR, EC, MX, PE, UY |
| CITY | string | |
| ZONE | string | Operational zone / neighborhood |
| ZONE_TYPE | string | `Wealthy` or `Non Wealthy` |
| ZONE_PRIORITIZATION | string | `High Priority`, `Prioritized`, `Not Prioritized` |
| METRIC | string | One of 13 metrics — see table below |
| L8W_ROLL … L0W_ROLL | float | Metric value per week. NULLs allowed in older weeks. |

### `orders` table (1,242 rows)

One row per `COUNTRY × CITY × ZONE`. Columns `L8W` → `L0W` hold raw order counts. **Does not have `ZONE_TYPE` or `ZONE_PRIORITIZATION`.**

### `orders_enriched` view

Joins `orders` with `ZONE_TYPE` and `ZONE_PRIORITIZATION` from `input_metrics`. Use this view when you need order volume alongside zone metadata.

### Metric Definitions

| Metric | Description | Direction |
|---|---|---|
| `% PRO Users Who Breakeven` | Pro users whose generated value covers membership cost | Higher is better |
| `% Restaurants Sessions With Optimal Assortment` | Sessions with ≥40 restaurants / total sessions | Higher is better |
| `Gross Profit UE` | Gross margin per order | Higher is better |
| `Lead Penetration` | Enabled stores / (leads + enabled + churned) | Higher is better |
| `MLTV Top Verticals Adoption` | Users ordering across multiple verticals / total users | Higher is better |
| `Non-Pro PTC > OP` | Non-Pro checkout → order placed conversion | Higher is better |
| `Perfect Orders` | Orders without cancellations, defects, or delays / total | Higher is better |
| `Pro Adoption (Last Week Status)` | Pro subscribers / total users | Higher is better |
| `Restaurants Markdowns / GMV` | Restaurant discounts / restaurant GMV | **Lower is better** |
| `Restaurants SS > ATC CVR` | Select Store → Add to Cart conversion | Higher is better |
| `Restaurants SST > SS CVR` | Select restaurant vertical → select store conversion | Higher is better |
| `Retail SST > SS CVR` | Select supermarket vertical → select store conversion | Higher is better |
| `Turbo Adoption` | Turbo buyers / users with Turbo available | Higher is better |
