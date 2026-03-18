import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import "./App.css";

// ── Formatters ────────────────────────────────────────────────────────────────

function fmtPrice(n) {
  return typeof n === "number"
    ? n.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    : "—";
}

function fmtVol(n) {
  if (n == null || n === "") return "—";
  const num = Number(n);
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(2) + "M";
  if (num >= 1_000) return (num / 1_000).toFixed(1) + "K";
  return num.toLocaleString();
}

// ── Stock Chart ───────────────────────────────────────────────────────────────

const PERIODS = [
  { label: "5D", key: "5d" },
  { label: "1M", key: "1mo" },
  { label: "3M", key: "3mo" },
  { label: "6M", key: "6mo" },
  { label: "1Y", key: "1y" },
];

function StockChart({ history, ticker, currentPrice }) {
  const [period, setPeriod] = useState("1mo");

  const allDates = history?.map((h) => h.date) ?? [];
  const allCloses = history?.map((h) => h.close) ?? [];

  // Filter by period client-side using the already-loaded data;
  // if the data doesn't cover the requested range the full set is shown.
  const filterByPeriod = (data, p) => {
    if (!data || data.length === 0) return [];
    const now = new Date(data[data.length - 1].date);
    const cutoff = new Date(now);
    if (p === "5d") cutoff.setDate(now.getDate() - 5);
    else if (p === "1mo") cutoff.setMonth(now.getMonth() - 1);
    else if (p === "3mo") cutoff.setMonth(now.getMonth() - 3);
    else if (p === "6mo") cutoff.setMonth(now.getMonth() - 6);
    else if (p === "1y") cutoff.setFullYear(now.getFullYear() - 1);
    return data.filter((d) => new Date(d.date) >= cutoff);
  };

  const filtered = filterByPeriod(history, period);
  if (!filtered || filtered.length === 0) return null;

  const closes = filtered.map((d) => d.close);
  const minC = Math.min(...closes);
  const maxC = Math.max(...closes);
  const pad = (maxC - minC) * 0.1 || 1;
  const first = filtered[0].close;
  const last = filtered[filtered.length - 1].close;
  const isUp = last >= first;
  const accent = isUp ? "#00d4b4" : "#ff4d6d";

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="chart-tooltip">
        <span className="tooltip-date">{d.date}</span>
        <span className="tooltip-price">${fmtPrice(d.close)}</span>
        <span className="tooltip-ohlcv">
          O ${fmtPrice(d.open)} · H ${fmtPrice(d.high)} · L ${fmtPrice(d.low)}
        </span>
        <span className="tooltip-vol">Vol {fmtVol(d.volume)}</span>
      </div>
    );
  };

  const tickFormatter = (date) => {
    const d = new Date(date);
    if (period === "5d")
      return d.toLocaleDateString(undefined, { weekday: "short" });
    if (period === "1mo")
      return d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
    return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
  };

  return (
    <div className="chart-wrap">
      <div className="chart-header">
        <span className="chart-title">{ticker} — Price Chart</span>
        <div className="period-tabs">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              className={`period-tab${period === p.key ? " active" : ""}`}
              onClick={() => setPeriod(p.key)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart
          data={filtered}
          margin={{ top: 6, right: 8, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={accent} stopOpacity={0.3} />
              <stop offset="95%" stopColor={accent} stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={tickFormatter}
            tick={{ fill: "#8892a4", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            minTickGap={40}
          />
          <YAxis
            domain={[minC - pad, maxC + pad]}
            tick={{ fill: "#8892a4", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
            width={52}
          />
          <Tooltip content={<CustomTooltip />} />
          {currentPrice != null && (
            <ReferenceLine
              y={currentPrice}
              stroke="#f0c040"
              strokeDasharray="4 3"
              strokeWidth={1.2}
              label={{
                value: `$${fmtPrice(currentPrice)}`,
                fill: "#f0c040",
                fontSize: 11,
                position: "right",
              }}
            />
          )}
          <Area
            type="monotone"
            dataKey="close"
            stroke={accent}
            strokeWidth={2}
            fill="url(#chartGrad)"
            dot={false}
            activeDot={{ r: 4, fill: accent, stroke: "none" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Stock Info Card ───────────────────────────────────────────────────────────

function StockCard({ stock, response }) {
  const change =
    stock.close != null && stock.open != null ? stock.close - stock.open : null;
  const changePct =
    change != null && stock.open ? (change / stock.open) * 100 : null;
  const isUp = change != null ? change >= 0 : null;

  return (
    <div className="stock-card">
      <div className="stock-header">
        <div>
          <span className="ticker-symbol">{stock.ticker}</span>
          <span className="stock-label">Today&apos;s Summary</span>
        </div>
        <div className="price-block">
          <span className="current-price">
            ${fmtPrice(stock.current_price)}
          </span>
          {change != null && (
            <span className={`price-change ${isUp ? "up" : "down"}`}>
              {isUp ? "▲" : "▼"} ${Math.abs(change).toFixed(2)}
              &nbsp;({Math.abs(changePct).toFixed(2)}%)
            </span>
          )}
        </div>
      </div>

      {stock.open != null && (
        <>
          <p className="section-label">OHLCV</p>
          <div className="ohlcv-grid">
            <div className="stat-box">
              <span className="stat-label">Open</span>
              <span className="stat-value">${fmtPrice(stock.open)}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">High</span>
              <span className="stat-value up">${fmtPrice(stock.high)}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Low</span>
              <span className="stat-value down">${fmtPrice(stock.low)}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Close</span>
              <span className="stat-value">${fmtPrice(stock.close)}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Volume</span>
              <span className="stat-value">{fmtVol(stock.volume)}</span>
            </div>
          </div>
        </>
      )}

      {stock.history?.length > 0 && (
        <StockChart
          history={stock.history}
          ticker={stock.ticker}
          currentPrice={stock.current_price}
        />
      )}

      {response && <p className="ai-response">{response}</p>}
    </div>
  );
}

// ── Multi-Stock Table ─────────────────────────────────────────────────────────

function MultiStockTable({ stocks }) {
  const [sortKey, setSortKey] = useState("ticker");
  const [sortAsc, setSortAsc] = useState(true);

  const handleSort = (key) => {
    if (key === sortKey) setSortAsc((a) => !a);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const sorted = [...stocks].sort((a, b) => {
    const av = a[sortKey] ?? -Infinity;
    const bv = b[sortKey] ?? -Infinity;
    if (typeof av === "string")
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortAsc ? av - bv : bv - av;
  });

  const ColHead = ({ label, k }) => (
    <th onClick={() => handleSort(k)} className="sortable">
      {label}
      {sortKey === k ? (sortAsc ? " ▲" : " ▼") : ""}
    </th>
  );

  return (
    <div className="stock-card">
      <p className="section-label">
        Today&apos;s Summary — {stocks.length} tickers
      </p>
      <div className="multi-table-wrap">
        <table className="data-table multi-table">
          <thead>
            <tr>
              <ColHead label="Ticker" k="ticker" />
              <ColHead label="Price" k="current_price" />
              <ColHead label="Change" k="change" />
              <ColHead label="Chg %" k="changePct" />
              <ColHead label="Open" k="open" />
              <ColHead label="High" k="high" />
              <ColHead label="Low" k="low" />
              <ColHead label="Close" k="close" />
              <ColHead label="Volume" k="volume" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((s) => {
              const change =
                s.close != null && s.open != null ? s.close - s.open : null;
              const changePct =
                change != null && s.open ? (change / s.open) * 100 : null;
              const isUp = change == null ? null : change >= 0;
              const row = { ...s, change, changePct };
              return (
                <tr key={s.ticker}>
                  <td className="ticker-cell">{s.ticker}</td>
                  <td>${fmtPrice(s.current_price)}</td>
                  <td className={isUp === null ? "" : isUp ? "up" : "down"}>
                    {change === null
                      ? "—"
                      : `${isUp ? "▲" : "▼"} ${isUp ? "+" : ""}${change.toFixed(2)}`}
                  </td>
                  <td className={isUp === null ? "" : isUp ? "up" : "down"}>
                    {changePct === null
                      ? "—"
                      : `${isUp ? "▲" : "▼"} ${isUp ? "+" : ""}${changePct.toFixed(2)}%`}
                  </td>
                  <td>{s.open != null ? `$${fmtPrice(s.open)}` : "—"}</td>
                  <td className="up">
                    {s.high != null ? `$${fmtPrice(s.high)}` : "—"}
                  </td>
                  <td className="down">
                    {s.low != null ? `$${fmtPrice(s.low)}` : "—"}
                  </td>
                  <td>{s.close != null ? `$${fmtPrice(s.close)}` : "—"}</td>
                  <td>{fmtVol(s.volume)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Options Table (puts or calls) ─────────────────────────────────────────────

function OptionsTable({ rows, label, currentPrice }) {
  if (!rows || rows.length === 0) return null;
  const isPuts = label === "PUTS";

  // Find the index AFTER which to insert the current-price marker.
  // For a sorted array of strikes, insert between the last strike ≤ price
  // and the first strike > price.
  let insertAfter = -1;
  if (currentPrice != null) {
    for (let i = 0; i < rows.length; i++) {
      if (rows[i].strike <= currentPrice) insertAfter = i;
      else break;
    }
  }

  return (
    <div className="options-section">
      <span className={`badge ${isPuts ? "badge-puts" : "badge-calls"}`}>
        {label}
      </span>
      <table className="data-table">
        <thead>
          <tr>
            <th>Strike</th>
            <th>Last Price</th>
            <th>Volume</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <>
              <tr
                key={i}
                className={
                  currentPrice != null &&
                  Math.abs(row.strike - currentPrice) ===
                    Math.min(
                      ...rows.map((r) => Math.abs(r.strike - currentPrice)),
                    )
                    ? "row-nearest-strike"
                    : ""
                }
              >
                <td>${fmtPrice(row.strike)}</td>
                <td>${fmtPrice(row.lastPrice)}</td>
                <td>{fmtVol(row.volume)}</td>
              </tr>
              {i === insertAfter && (
                <tr key="price-marker" className="row-current-price-marker">
                  <td colSpan={3}>
                    <span className="price-marker-line" />
                    <span className="price-marker-label">
                      ▶ ${fmtPrice(currentPrice)} current
                    </span>
                    <span className="price-marker-line" />
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Options Chain Card ────────────────────────────────────────────────────────

function OptionsCard({ options }) {
  return (
    <div className="stock-card">
      <div className="stock-header">
        <div>
          <span className="ticker-symbol">{options.ticker}</span>
          <span className="stock-label">Options Chain</span>
        </div>
        <div className="price-block">
          <span className="current-price">
            ${fmtPrice(options.current_price)}
          </span>
          <span className="expiry-label">Expires {options.expiry_date}</span>
        </div>
      </div>

      <div className="range-bar">
        <span className="range-dot" />
        <span className="range-label">Strike range ±10%</span>
        <span className="range-value">${fmtPrice(options.range_low)}</span>
        <span className="range-sep">—</span>
        <span className="range-value">${fmtPrice(options.range_high)}</span>
      </div>

      <div className="options-grid">
        <OptionsTable
          rows={options.puts}
          label="PUTS"
          currentPrice={options.current_price}
        />
        <OptionsTable
          rows={options.calls}
          label="CALLS"
          currentPrice={options.current_price}
        />
      </div>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  const [message, setMessage] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "An error occurred");
      } else {
        setResult(data);
      }
    } catch {
      setError("Error connecting to the server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="app-header">
        <div className="app-logo">📈</div>
        <div className="header-text">
          <h1 className="app-title">Stock Options Tracker</h1>
          <span className="app-subtitle">
            Live market data &amp; options chains
          </span>
        </div>
        <span className="header-badge">Powered by yfinance</span>
      </header>

      <div className="search-wrap">
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="e.g. What is the price of AAPL?  |  PLTR options for 03/20/2026"
          />
          <button type="submit" disabled={loading}>
            {loading ? "Loading…" : "Search"}
          </button>
        </form>
      </div>

      {loading && (
        <div className="loading-bar">
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
          Fetching data…
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {result?.stocks?.length > 0 && <MultiStockTable stocks={result.stocks} />}
      {result?.stock && (
        <StockCard stock={result.stock} response={result.response} />
      )}
      {result?.options && <OptionsCard options={result.options} />}

      {result &&
        !result.stocks?.length &&
        !result.stock &&
        !result.options &&
        result.response && (
          <div className="stock-card">
            <p className="ai-response">{result.response}</p>
          </div>
        )}
    </div>
  );
}

export default App;
