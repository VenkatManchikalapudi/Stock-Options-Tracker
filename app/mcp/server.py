from mcp.server.fastmcp import FastMCP
from datetime import date, timedelta
import yfinance as yf
import pandas as pd
import json

mcp = FastMCP("FinanceServer")


def _next_friday() -> str:
    """Return the ISO date of the nearest upcoming Friday (or today if today is Friday)."""
    today = date.today()
    days_ahead = (4 - today.weekday()) % 7  # Friday = weekday 4; 0 if already Friday
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def _nearest_expiry(available: tuple, target: str) -> str:
    """Return the closest available expiry to *target* (YYYY-MM-DD string)."""
    if target in available:
        return target
    try:
        td = date.fromisoformat(target)
        closest = min(available, key=lambda d: abs((date.fromisoformat(d) - td).days))
        return closest
    except Exception:
        return available[0] if available else target


@mcp.tool()
def get_stock_info(ticker: str) -> str:
    """
    Fetch current price and today's OHLCV data for a stock.
    Returns JSON with ticker, current_price, open, high, low, close, volume.
    """
    try:
        stock = yf.Ticker(ticker)
        current_price = stock.fast_info["lastPrice"]
        if current_price is None:
            return json.dumps({"error": f"No price data found for '{ticker.upper()}'. Verify the ticker symbol.", "ticker": ticker.upper()})
        hist = stock.history(period="1d")

        result: dict = {
            "ticker": ticker.upper(),
            "current_price": round(current_price, 2),
        }
        if not hist.empty:
            row = hist.iloc[-1]
            result.update({
                "open":   round(float(row["Open"]),  2),
                "high":   round(float(row["High"]),  2),
                "low":    round(float(row["Low"]),   2),
                "close":  round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker.upper()})


@mcp.tool()
def get_options(ticker: str, expiry_date: str = "") -> str:
    """
    Fetch put AND call options for a stock for a given expiry date.
    If expiry_date is omitted or empty, defaults to the nearest Friday.
    Automatically snaps to the nearest available expiry if the requested
    date is not listed by the exchange.
    Filters strikes to within 10% of the current stock price.
    Returns current_price, range, expiry_date, puts and calls.
    """
    try:
        stock = yf.Ticker(ticker)
        current_price = stock.fast_info["lastPrice"]
        if current_price is None:
            return json.dumps({"error": f"No price data found for '{ticker.upper()}'. Verify the ticker symbol.", "ticker": ticker.upper()})
        lower = current_price * 0.90
        upper = current_price * 1.10

        available = stock.options  # tuple of YYYY-MM-DD strings
        if not available:
            return json.dumps({"error": f"No options data available for '{ticker.upper()}'.", "ticker": ticker.upper()})

        target = expiry_date.strip() if expiry_date and expiry_date.strip() else _next_friday()
        expiry_date = _nearest_expiry(available, target)

        chain = stock.option_chain(expiry_date)

        def _filter(df: pd.DataFrame) -> list:
            filtered = df[(df["strike"] >= lower) & (df["strike"] <= upper)]
            return json.loads(
                filtered[["strike", "lastPrice", "volume"]].to_json(orient="records")
            )

        result = {
            "ticker":        ticker.upper(),
            "current_price": round(current_price, 2),
            "range_low":     round(lower, 2),
            "range_high":    round(upper, 2),
            "expiry_date":   expiry_date,
            "puts":          _filter(chain.puts),
            "calls":         _filter(chain.calls),
        }
        return json.dumps(result)
    except Exception as e:
        return f"Error fetching options for {ticker} on {expiry_date}: {str(e)}"


@mcp.tool()
def get_stock_history(ticker: str, period: str = "1mo") -> str:
    """
    Fetch historical daily OHLCV for a stock.
    period: yfinance period string — '5d', '1mo', '3mo', '6mo', '1y', etc.
    Returns a JSON array of {date, open, high, low, close, volume}.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return json.dumps({"error": f"No history data for '{ticker.upper()}'."})
        records = []
        for dt, row in hist.iterrows():
            records.append({
                "date":   dt.strftime("%Y-%m-%d"),
                "open":   round(float(row["Open"]),  2),
                "high":   round(float(row["High"]),  2),
                "low":    round(float(row["Low"]),   2),
                "close":  round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return json.dumps(records)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
