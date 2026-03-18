# Stock & Options Researcher

A full-stack AI-powered stock and options research tool. Ask natural language questions — by ticker symbol or company name — about stock prices, options chains, and price history. A local AI orchestrator routes your query to the right agent, fetches live data via Yahoo Finance, and returns a formatted response with charts.

---

## Preview

![AAPL stock data with price chart, news sentiment side-by-side](docs/aapl-screenshot.png)

---

## Architecture Flow

See [`architecture.mmd`](architecture.mmd) for the full Mermaid source.

---

## Tech Stack

| Layer          | Technology                                           |
| -------------- | ---------------------------------------------------- |
| Frontend       | React 19 + Vite + Recharts                           |
| Backend API    | FastAPI + Uvicorn                                    |
| Orchestration  | `OrchestratorAgent` — `phi4-mini` (Ollama)           |
| Finance Agent  | `FinanceAgent` — `llama3.2` (Ollama)                 |
| News Agent     | `NewsAgent` — `qwen2.5-coder:7b` (Ollama)            |
| Data Tools     | MCP server via `FastMCP` (stdio transport)           |
| Market Data    | `yfinance`, `pandas`                                 |
| AI Runtime     | Ollama (local, no API key required)                  |
| Logging        | Python `logging` — `app.*` hierarchy, INFO level     |
| Stock Mappings | `app/data/stock_mappings.py` — 100+ company → ticker |

---

## Project Structure

```
.
├── app/
│   ├── main.py                   # FastAPI app, CORS, logging config (INFO)
│   ├── routers/
│   │   └── chat.py               # POST /chat endpoint — logs request, timing, errors
│   ├── agents/
│   │   ├── base_agent.py         # Abstract BaseAgent interface
│   │   ├── orchestrator_agent.py # Routing + intent detection — logs routing path
│   │   ├── finance_agent.py      # Data fetching + formatting — logs MCP calls + timing
│   │   └── news_agent.py         # News fetch + sentiment — logs fetch, analysis, timing
│   ├── data/
│   │   ├── __init__.py
│   │   └── stock_mappings.py     # COMPANY_NAME_MAP, TICKER_GROUPS (Mag7, FAANG, etc.)
│   └── mcp/
│       └── server.py             # MCP tools: get_stock_info, get_options, get_stock_history
└── client/
    └── src/
        ├── App.jsx               # React UI — charts, options chain, multi-stock table, news feed
        ├── App.css               # Dark Bloomberg-style theme
        └── index.css             # Global dark background
```

---

## Agent Pattern

The system uses an **Orchestrator → Specialist Agent** pattern:

1. **OrchestratorAgent** receives the raw user message and determines intent:
   - **Name resolution** — company names (e.g. `"Apple"`, `"Palantir"`, `"AppLovin"`) are resolved to tickers before any routing using `COMPANY_NAME_MAP` (100+ entries) from `app/data/stock_mappings.py`.
   - **Fast path** — regex instantly detects ticker + options/price keywords (no LLM call). Handles both `"AAPL options"` and `"options for AAPL"` word orders.
   - **Slow path** — `phi4-mini` classifies ambiguous queries and returns structured `{agent, action, params}` JSON.
2. **FinanceAgent** is dispatched with `(action, params)`:
   - Calls the MCP stdio server as a subprocess.
   - For **price queries**: concurrently fetches `get_stock_info` + `get_stock_history` (1 month by default), attaches history to the stock dict, and uses `llama3.2` to compose a natural-language summary.
   - For **options queries**: fetches `get_options`, defaults to the next Friday expiry and snaps to the nearest available date. Formats a strike/price/volume table. Filters strikes within ±10% of current price.
   - For **multi-stock queries**: fetches all tickers concurrently.
   - Returns `{"response": str, "stock": dict|None, "stocks": list|None, "options": dict|None}`.
3. **OrchestratorAgent** forwards the full result dict to the API router.

### Logging

All components emit structured log lines via Python's `logging` module at `INFO` level (configurable in `main.py`). Loggers follow the `app.*` hierarchy so each module can be tuned independently:

| Logger | What it records |
|---|---|
| `app.chat` | Incoming message text, total round-trip time, errors with traceback |
| `app.orchestrator` | Company-name resolutions, routing path taken (group / regex / LLM / fallback), dispatched agent + action |
| `app.finance` | Action + params received, each MCP tool called with elapsed time |
| `app.news` | News fetch per ticker, sentiment analysis start, overall result + confidence, elapsed time, failures |

### MCP Tools

| Tool                | Params                               | Returns                                                    |
| ------------------- | ------------------------------------ | ---------------------------------------------------------- |
| `get_stock_info`    | `ticker`                             | current price + today's OHLCV as JSON                      |
| `get_options`       | `ticker`, `expiry_date` (YYYY-MM-DD) | puts + calls within ±10% of current price; auto-snaps date |
| `get_stock_history` | `ticker`, `period` (default `1mo`)   | array of `{date, open, high, low, close, volume}` records  |
| `get_stock_news`    | `ticker`, `limit` (default `10`)     | array of `{title, publisher, link, published_at}` articles |

> **Optional caching**: `get_stock_info` results are cached for 5 minutes if a Redis server is reachable on `localhost:6379`. When Redis is unavailable (not installed or not running), caching is silently skipped and every request fetches live data.

### Frontend Features

- **Dark terminal-inspired UI** — Bloomberg-style theme with glassmorphism and gradient accents. Cards are sized to fit the viewport without page scrolling.
- **Price chart** — interactive `AreaChart` (recharts) with period tabs (5D / 1M / 3M / 6M / 1Y), custom OHLCV tooltip showing **% change for the selected period**, dashed reference line at current price, teal/red coloring based on direction.
- **Side-by-side layout** — stock chart card and news/sentiment card rendered side-by-side; the news panel is independently scrollable when articles overflow.
- **OHLCV stat grid** — Open, High, Low, Close, Volume tiles.
- **Options chain** — side-by-side PUTS/CALLS tables with current-price marker row and nearest-strike highlight.
- **Multi-stock table** — sortable table for basket/group queries (Mag 7, FAANG, etc.).
- **News + sentiment feed** — latest headlines with per-article BULLISH/BEARISH/NEUTRAL badges, overall sentiment summary, and confidence score.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) running locally with the following models pulled:
  ```bash
  ollama pull phi4-mini
  ollama pull llama3.2
  ollama pull qwen2.5-coder:7b
  ```

### Backend

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

> **Optional — Redis caching**: install `redis` and start a local Redis server on port `6379` to enable 5-minute caching of `get_stock_info` results.
>
> ```bash
> pip install redis
> redis-server   # or: brew services start redis
> ```

### Frontend

```bash
cd client
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Example Queries

**Stock prices**

- `What is the price of AAPL?`
- `How is Palantir trading today?`
- `NVDA stock price`

**Options chains**

- `Show me PLTR options for 03/20/2026`
- `TSLA options expiring 2026-03-21`
- `APP options chain` _(AppLovin — not Apple)_
- `Palo Alto Networks options`

**Multi-stock baskets**

- `Show me Mag 7 stocks`
- `FAANG prices`
- `Compare AAPL MSFT GOOGL`

**News & sentiment**

- `NVDA news and sentiment`
- `What are the latest headlines for TSLA?`
- `AAPL market buzz`
- `PLTR sentiment`
