import asyncio
import logging
import sys
import json
import time
from pathlib import Path

import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .base_agent import BaseAgent

# Resolved at import time: <project_root>/app/mcp/server.py
SERVER_PATH = str(Path(__file__).parent.parent / "mcp" / "server.py")

# General-purpose model for composing natural language answers from tool data
FINANCE_MODEL = "llama3.2:latest"

logger = logging.getLogger("app.finance")


class FinanceAgent(BaseAgent):
    """
    Agent responsible for all financial data queries.
    Delegates tool execution to the MCP server (server.py) which uses yfinance,
    then uses llama3.2 to compose a natural language response.

    Supported actions:
      - get_price:   {"ticker": str}
      - get_options: {"ticker": str, "expiry_date": str}  # YYYY-MM-DD
    """

    name = "finance"
    description = (
        "Retrieves live stock prices and options chains from Yahoo Finance. "
        "Use for queries about stock prices, put/call options, or expiry chains."
    )
    model = FINANCE_MODEL

    async def run(self, action: str, params: dict) -> dict:
        """
        Call the MCP tool, format the result, and return a structured dict
        to the orchestrator:
          - response (str):         formatted natural language / table answer
          - stock    (dict | None): OHLCV data (get_stock_info only)
          - stocks   (list | None): list of OHLCV dicts (get_multiple_stocks only)
          - options  (dict | None): parsed options data (get_options only)
        """
        logger.info("Action: %s  params: %s", action, params)
        if action == "get_multiple_stocks":
            return await self._run_multiple(params.get("tickers", []))

        if action == "get_stock_info":
            # Lazily import to avoid circular dependency
            from .news_agent import NewsAgent  # noqa: PLC0415
            hist_params = {**params, "period": "1y"}
            raw_info, raw_hist, news_result = await asyncio.gather(
                self._call_tool("get_stock_info", params),
                self._call_tool("get_stock_history", hist_params),
                NewsAgent().run("get_news", {**params, "limit": 5}),
            )
            result = await _build_result("get_stock_info", raw_info)
            try:
                history = json.loads(raw_hist)
                if isinstance(history, list) and result.get("stock"):
                    result["stock"]["history"] = history
            except (json.JSONDecodeError, TypeError):
                pass
            # Attach compact news blob (only if we got articles back)
            if isinstance(news_result, dict) and news_result.get("news"):
                result["news"] = news_result["news"]
            return result

        raw_output = await self._call_tool(action, params)
        return await _build_result(action, raw_output)

    async def _run_multiple(self, tickers: list[str]) -> dict:
        """Fetch all tickers concurrently via the MCP server."""
        tasks = [
            self._call_tool("get_stock_info", {"ticker": t})
            for t in tickers
        ]
        raw_outputs = await asyncio.gather(*tasks, return_exceptions=True)

        stocks = []
        for raw in raw_outputs:
            if isinstance(raw, Exception):
                continue
            try:
                data = json.loads(raw)
                if "ticker" in data:
                    stocks.append(data)
            except (json.JSONDecodeError, TypeError):
                continue

        return {
            "response": f"Fetched data for {len(stocks)} ticker(s).",
            "stock": None,
            "stocks": stocks,
            "options": None,
        }

    async def _call_tool(self, tool_name: str, tool_args: dict) -> str:
        """Open a stdio connection to the MCP server and call the given tool."""
        logger.debug("MCP call: %s(%s)", tool_name, tool_args)
        t0 = time.perf_counter()
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[SERVER_PATH],
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, tool_args)
                elapsed = time.perf_counter() - t0
                logger.info("MCP %s completed in %.2fs", tool_name, elapsed)
                return result.content[0].text if result.content else ""


# ---------------------------------------------------------------------------
# Result builder — called by FinanceAgent.run(), hands structured dict to orchestrator
# ---------------------------------------------------------------------------

async def _build_result(action: str, raw_output: str) -> dict:
    """
    Parse MCP tool output and build the structured result dict handed back to
    the orchestrator:
      - get_stock_info → LLM composes a natural-language sentence; stock dict attached
      - get_options    → deterministic table (data is too large for the LLM); options dict attached
    """
    if action == "get_options":
        try:
            data = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            data = {}
        return {
            "response": _format_options(raw_output),
            "stock": None,
            "stocks": None,
            "options": data,
        }

    # get_stock_info
    try:
        stock_data = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError):
        stock_data = {}

    response = await asyncio.to_thread(
        ollama.chat,
        model=FINANCE_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a concise financial assistant. "
                    "Given raw JSON data from a financial tool, respond in 1-2 clear sentences. "
                    "Do not repeat the raw data verbatim — summarize naturally."
                ),
            },
            {"role": "user", "content": raw_output},
        ],
    )
    return {
        "response": (response.message.content or raw_output).strip(),
        "stock": stock_data,
        "stocks": None,
        "options": None,
    }


def _format_options(output: str) -> str:
    """Render an options JSON payload as a readable table (puts and calls)."""
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return output

    if "error" in data:
        return data["error"]

    ticker = data.get("ticker", "")
    current_price = data.get("current_price", 0.0)
    low = data.get("range_low", 0.0)
    high = data.get("range_high", 0.0)
    expiry = data.get("expiry_date", "")
    puts = data.get("puts", [])
    calls = data.get("calls", [])

    if not puts and not calls:
        return (
            f"No options found for {ticker} within 10% of "
            f"${current_price:.2f} expiring {expiry}."
        )

    lines = [
        f"{ticker} options expiring {expiry}",
        f"Current price: ${current_price:.2f}  |  10% range: ${low:.2f} – ${high:.2f}",
    ]

    def _render_rows(rows: list, label: str) -> None:
        if not rows:
            return
        lines.append("")
        lines.append(label)
        lines.append(f"{'Strike':<12}{'Last Price':<14}{'Volume'}")
        lines.append(f"{'------':<12}{'----------':<14}{'------'}")
        for row in rows:
            strike = row.get("strike", 0)
            last = row.get("lastPrice", 0)
            vol = int(row.get("volume", 0) or 0)
            lines.append(f"${strike:<11.2f}${last:<13.2f}{vol}")

    _render_rows(puts, "PUTS")
    _render_rows(calls, "CALLS")

    return "\n".join(lines)
