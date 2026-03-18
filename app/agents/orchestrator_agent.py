import asyncio
import json
import re
from datetime import datetime

import ollama

from .base_agent import BaseAgent
from .finance_agent import FinanceAgent
from .news_agent import NewsAgent
from ..data.stock_mappings import COMPANY_NAME_MAP, TICKER_GROUPS

# Lightweight model — fast JSON classification, no heavy reasoning needed
ORCHESTRATOR_MODEL = "phi4-mini:latest"

# Pre-sort company name keys longest-first so multi-word names match before
# their shorter prefixes (e.g. "palo alto networks" before "palo alto").
_COMPANY_KEYS_SORTED = sorted(COMPANY_NAME_MAP.keys(), key=len, reverse=True)


def _resolve_company_names(text: str) -> str:
    """
    Replace any company name in *text* with its ticker symbol.
    Operates on a lowercased copy for matching but preserves original case
    of surrounding text by splicing.  Returns the modified string.
    """
    lower = text.lower()
    result = text
    offset = 0  # tracks drift between original and modified string indices

    for name in _COMPANY_KEYS_SORTED:
        ticker = COMPANY_NAME_MAP[name]
        # Only match whole-word boundaries
        pattern = r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])"
        for m in re.finditer(pattern, lower):
            start = m.start() + offset
            end   = m.end()   + offset
            result = result[:start] + ticker + result[end:]
            # Recompute lower from result for subsequent iterations
            offset += len(ticker) - (m.end() - m.start())
            lower = result.lower()
            break  # re.finditer iterator invalidated; outer loop will re-search

    return result


# Words that are never valid ticker symbols
_STOPWORDS = {
    "FOR", "THE", "AND", "ARE", "GET", "PUT", "CALL", "WHAT", "SHOW",
    "HOW", "CAN", "YOU", "ON", "AT", "IN", "OF", "TO", "A", "AN", "IS",
    "ME", "MY", "DO", "IT", "ITS", "WITH", "OR", "NOT", "NO", "THAT",
    "TODAY", "NOW", "GIVE", "TELL", "ABOUT", "STOCK",
    # Options-related words that must never be matched as tickers
    "OPTIONS", "OPTION", "CHAIN", "CALLS", "PUTS", "EXPIRY", "STRIKE",
    "PRICE", "PRICES", "TRADING", "QUOTE", "WORTH", "VALUE",
    # News-related words
    "NEWS", "HEADLINES", "HEADLINE", "SENTIMENT", "BUZZ", "MARKET",
}

# Describe available agents for the LLM routing prompt
_AGENT_REGISTRY_DESCRIPTION = (
    "Available agents and their actions:\n"
    '- agent: "finance", action: "get_stock_info",      params: {"ticker": "<SYMBOL>"}\n'
    '- agent: "finance", action: "get_multiple_stocks", params: {"tickers": ["<SYMBOL>", "<SYMBOL>"]}\n'
    '- agent: "finance", action: "get_options",         params: {"ticker": "<SYMBOL>", "expiry_date": "<YYYY-MM-DD>"}\n'
    '- agent: "news",    action: "get_news",            params: {"ticker": "<SYMBOL>"}\n'
    "Use get_multiple_stocks when the user asks about several tickers at once.\n"
    "Use get_news when the user asks about news, headlines, sentiment, or buzz around a stock.\n"
)

# Fast-path regex patterns — avoids LLM for common queries
# Handles both word orders:
#   ticker-first: "APP options chain", "PLTR calls for 03/20/2026"
#   keyword-first: "options for AAPL", "show me TSLA puts 2026-03-20"
# Date is optional — if omitted the server defaults to the nearest Friday.
_OPTIONS_RE = re.compile(
    r"(?:"
    r"\b([A-Z]{1,5})\b\s+(?:options?|puts?|calls?|chain)"   # ticker-first
    r"|\b(?:options?|puts?|calls?|chain)\b.*?\b([A-Z]{1,5})\b"  # keyword-first
    r")"
    r"(?:.*?(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}))?",
    re.IGNORECASE,
)

# Matches: "price of AAPL" or "what is TSLA trading at"
_PRICE_RE = re.compile(
    r"\b(?:price|trading|quote|worth|value)\b.*?\b([A-Z]{1,5})\b"
    r"|\b([A-Z]{1,5})\b.*?\b(?:price|trading|quote|worth|value)\b",
    re.IGNORECASE,
)

# News / sentiment query
_NEWS_RE = re.compile(
    r"\b(?:news|headlines?|sentiment|buzz)\b.*?\b([A-Z]{2,5})\b"
    r"|\b([A-Z]{2,5})\b.*?\b(?:news|headlines?|sentiment|buzz)\b",
    re.IGNORECASE,
)

# Standalone ticker detection
_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")



def _parse_date(raw: str) -> str:
    """Normalise MM/DD/YYYY or YYYY-MM-DD to YYYY-MM-DD."""
    raw = raw.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    try:
        return datetime.strptime(raw, "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return raw


def _detect_group(text: str):
    """Fast-path: match known ticker group names (case-insensitive)."""
    lower = text.lower()
    for group_name, tickers in TICKER_GROUPS.items():
        if group_name in lower:
            return "finance", "get_multiple_stocks", {"tickers": tickers}
    return None


def _detect_intent(text: str):
    """
    Fast-path intent detection using regex.
    Returns (agent_name, action, params) or None.
    """
    upper = text.upper()

    # News / sentiment query
    m = _NEWS_RE.search(text)
    if m:
        ticker = (m.group(1) or m.group(2) or "").upper()
        if ticker and ticker not in _STOPWORDS:
            return "news", "get_news", {"ticker": ticker}

    # Options query
    m = _OPTIONS_RE.search(text)
    if m:
        # group(1) = ticker-first match, group(2) = keyword-first match
        raw_ticker = (m.group(1) or m.group(2) or "").upper()
        if raw_ticker and raw_ticker not in _STOPWORDS:
            params: dict = {"ticker": raw_ticker}
            if m.group(3):
                params["expiry_date"] = _parse_date(m.group(3))
            return "finance", "get_options", params

    # Price query
    m = _PRICE_RE.search(text)
    if m:
        ticker = (m.group(1) or m.group(2)).upper()
        if ticker not in _STOPWORDS:
            return "finance", "get_stock_info", {"ticker": ticker}

    # Standalone all-caps ticker
    tokens = _TICKER_RE.findall(upper)
    candidates = [t for t in tokens if t not in _STOPWORDS and len(t) >= 2]
    if len(candidates) == 1:
        return "finance", "get_stock_info", {"ticker": candidates[0]}

    return None


def _strip_code_fences(text: str) -> str:
    text = re.sub(r"^```[a-z]*\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def _llm_route(user_message: str):
    """
    Use phi4-mini to classify the user's intent.
    Returns a dict {agent, action, params} or None on failure.
    """
    system_prompt = (
        "You are a routing assistant. Given a user message, determine which agent "
        "and action should handle it. Respond ONLY with valid JSON — no explanation.\n\n"
        + _AGENT_REGISTRY_DESCRIPTION
        + "IMPORTANT: Use the EXACT ticker symbol as written by the user. "
        "Do NOT expand abbreviations or guess alternative symbols "
        "(e.g. APP means APP, not AAPL; HOOD means HOOD, not something else).\n"
        'If the message is unrelated to stocks or finance, return: '
        '{"agent": null, "action": null, "params": {}}'
    )
    try:
        response = await asyncio.to_thread(
            ollama.chat,
            model=ORCHESTRATOR_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        raw = _strip_code_fences((response.message.content or "").strip())
        return json.loads(raw)
    except Exception:
        return None


# Map agent name strings to agent instances (lazy-initialised)
_AGENT_INSTANCES: dict[str, BaseAgent] = {}


def _get_agents() -> dict[str, BaseAgent]:
    global _AGENT_INSTANCES
    if not _AGENT_INSTANCES:
        _AGENT_INSTANCES = {
            "finance": FinanceAgent(),
            "news":    NewsAgent(),
        }
    return _AGENT_INSTANCES


class OrchestratorAgent(BaseAgent):
    def __init__(self, system_prompt: str = ""):
        super().__init__()
        self.system_prompt = system_prompt

    async def run(self, action: str, params: dict) -> dict:
        """Delegate to route() — satisfies BaseAgent abstract method."""
        return await self.route(f"{action} {params}")

    async def route(self, user_message: str) -> dict:
        """
        Classify user intent and dispatch to the appropriate agent.
        Returns the agent result dict with keys: response, stock, stocks, options, news.
        """
        # Step 1: resolve company names → tickers
        resolved = _resolve_company_names(user_message)

        # Step 2: fast-path — known ticker groups (Mag7, FAANG, …)
        group_result = _detect_group(resolved)
        if group_result:
            agent_name, action, params = group_result
            return await _get_agents()[agent_name].run(action, params)

        # Step 3: fast-path regex intent detection
        intent = _detect_intent(resolved)
        if intent:
            agent_name, action, params = intent
            return await _get_agents()[agent_name].run(action, params)

        # Step 4: slow-path LLM routing via phi4-mini
        route_info = await _llm_route(resolved)
        if route_info and route_info.get("agent"):
            agent_name = route_info["agent"]
            action = route_info.get("action", "")
            params = route_info.get("params", {})
            agents = _get_agents()
            if agent_name in agents:
                return await agents[agent_name].run(action, params)

        # Step 5: fallback — unrecognised intent
        return {
            "response": (
                "I'm not sure how to help with that. "
                "Try asking about a stock price, options chain, or news for a specific ticker."
            ),
            "stock": None,
            "stocks": None,
            "options": None,
            "news": None,
        }
