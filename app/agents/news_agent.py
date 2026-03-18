import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path

import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .base_agent import BaseAgent

SERVER_PATH = str(Path(__file__).parent.parent / "mcp" / "server.py")
NEWS_MODEL = "qwen2.5-coder:7b"

logger = logging.getLogger("app.news")


class NewsAgent(BaseAgent):
    """
    Fetches recent news headlines for a stock from Yahoo Finance and uses
    llama3.2 to perform sentiment analysis across all articles at once.

    Returns a structured result with:
      - response (str):  short prose summary with overall sentiment
      - news     (dict): {ticker, overall, confidence, summary, articles[]}
    """

    name = "news"
    description = (
        "Fetches recent news and performs AI-powered sentiment analysis for a stock. "
        "Use for queries about market news, headlines, buzz, or sentiment."
    )
    model = NEWS_MODEL

    async def run(self, action: str, params: dict) -> dict:
        ticker = params.get("ticker", "").upper()
        limit  = int(params.get("limit", 10))
        if not ticker:
            return self._empty("No ticker provided.", ticker)

        logger.info("Fetching news for %s (limit=%d)", ticker, limit)
        raw = await self._call_tool("get_stock_news", {"ticker": ticker, "limit": limit})

        try:
            articles_raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            articles_raw = []

        if isinstance(articles_raw, dict) and "error" in articles_raw:
            return self._empty(articles_raw["error"], ticker)

        if not articles_raw:
            return self._empty(f"No news found for {ticker}.", ticker)

        sentiment = await self._analyze_sentiment(ticker, articles_raw)

        overall     = sentiment.get("overall", "NEUTRAL")
        confidence  = sentiment.get("confidence", 50)
        summary     = sentiment.get("summary", "")
        art_sents   = sentiment.get("articles", [])

        articles = []
        for i, article in enumerate(articles_raw):
            sent = "NEUTRAL"
            if i < len(art_sents):
                a = art_sents[i]
                # Model may return plain strings ("BULLISH") or dicts ({"sentiment": "BULLISH"})
                if isinstance(a, dict):
                    sent = a.get("sentiment", "NEUTRAL").upper()
                elif isinstance(a, str):
                    sent = a.upper()
                if sent not in ("BULLISH", "BEARISH", "NEUTRAL"):
                    sent = "NEUTRAL"
            articles.append({
                "title":        article.get("title", ""),
                "publisher":    article.get("publisher", ""),
                "link":         article.get("link", ""),
                "published_at": article.get("published_at", ""),
                "sentiment":    sent,
            })

        response_text = (
            f"{ticker} market sentiment: **{overall}** ({confidence}% confidence). {summary}"
        )

        return {
            "response": response_text,
            "stock":    None,
            "stocks":   None,
            "options":  None,
            "news": {
                "ticker":     ticker,
                "overall":    overall,
                "confidence": confidence,
                "summary":    summary,
                "articles":   articles,
            },
        }

    async def _analyze_sentiment(self, ticker: str, articles: list) -> dict:
        headlines = "\n".join(
            f"{i + 1}. {a.get('title', '')}" for i, a in enumerate(articles)
        )
        prompt = (
            f"You are a financial sentiment analyst. Analyze these {len(articles)} "
            f"news headlines about {ticker}.\n"
            "Return ONLY valid JSON, no explanation, no markdown fences:\n"
            "{\n"
            '  "overall": "BULLISH" or "BEARISH" or "NEUTRAL",\n'
            '  "confidence": <integer 0-100>,\n'
            '  "summary": "<1-2 sentence plain-English market summary>",\n'
            '  "articles": [\n'
            '    {"sentiment": "BULLISH" or "BEARISH" or "NEUTRAL"},\n'
            "    ...\n"
            "  ]\n"
            "}\n\n"
            f"Headlines:\n{headlines}"
        )
        logger.info("Running sentiment analysis for %s (%d articles)", ticker, len(articles))
        t0 = time.perf_counter()
        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model=NEWS_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = (response.message.content or "").strip()
            raw = re.sub(r"^```[a-z]*\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
            result = json.loads(raw.strip())
            logger.info("Sentiment analysis completed in %.2fs — %s (%d%%)",
                        time.perf_counter() - t0, result.get("overall"), result.get("confidence", 0))
            return result
        except Exception as exc:
            logger.warning("Sentiment analysis failed: %s", exc)
            return {
                "overall":    "NEUTRAL",
                "confidence": 50,
                "summary":    "Sentiment analysis unavailable.",
                "articles":   [{"sentiment": "NEUTRAL"}] * len(articles),
            }

    async def _call_tool(self, tool_name: str, tool_args: dict) -> str:
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
                logger.info("MCP %s completed in %.2fs", tool_name, time.perf_counter() - t0)
                return result.content[0].text if result.content else ""

    @staticmethod
    def _empty(message: str, ticker: str = "") -> dict:
        return {
            "response": message,
            "stock":    None,
            "stocks":   None,
            "options":  None,
            "news":     None,
        }
