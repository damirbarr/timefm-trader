# TimeFM Crypto Trader — Design Spec
**Date:** 2026-05-01
**Status:** Approved

## Overview

A multi-coin crypto trading bot powered by Google's TimeFM forecasting model. Trades all Binance USDT spot pairs, operates in paper money mode by default, exposes a control API for external agents, and provides both a terminal dashboard and a browser-based charting dashboard.

---

## Architecture

### Module Layout

```
timefm-trader/
├── main.py          # CLI entry: `python main.py run` | `python main.py web`
├── config.py        # all tunable parameters
├── fetcher.py       # Binance USDT pair discovery + OHLCV fetching
├── forecaster.py    # TimeFM wrapper, multi-timeframe per coin
├── signal.py        # forecasts → ranked buy/sell signals with confidence scores
├── portfolio.py     # positions, capital, P&L, fee tracking
├── executor.py      # paper trades OR real Binance orders (same interface)
├── indicators.py    # MA, Bollinger Bands, RSI, MACD, Volume
├── dashboard.py     # rich terminal live dashboard
└── web.py           # FastAPI + WebSocket browser dashboard + control API
```

### Data Flow

```
fetcher → forecaster → signal → portfolio → executor
                                    ↑
                              stop-loss monitor (every 30s)
                                    ↓
                         dashboard.py + web.py (read-only views)
```

`executor` presents an identical interface for paper and real mode. Switching is a single config flag (`PAPER_MODE=true`).

---

## Forecasting & Signal Generation

### Multi-Timeframe Strategy

For every coin, OHLCV data is fetched across **6 timeframes**: `1m, 5m, 15m, 1h, 4h, 1d`.

TimeFM runs forecasts on each timeframe. The **best timeframe per coin** is selected as whichever produces the highest forecast magnitude relative to its uncertainty interval. That timeframe also sets the coin's re-check frequency (e.g. a coin assigned to `1h` is re-evaluated every hour).

### Confidence Scoring

```
confidence = expected_gain / uncertainty_width
```

Penalized by round-trip fee (0.2%). Signals where `expected_gain ≤ fees` are discarded before reaching the portfolio layer.

### Signal Ranking

Surviving signals are ranked by confidence. Capital is allocated proportionally:

```
coin_A  confidence=0.8  →  44% of available capital
coin_B  confidence=0.6  →  33%
coin_C  confidence=0.4  →  22%
```

### Exit Logic

- **TimeFM re-forecast** on every assigned interval → sell when net forecast turns negative after fees
- **Hard stop-loss floor** (default `-4%`, adjustable via Control API at runtime)

### External Insights

Insights from external agents blend with TimeFM forecasts — they nudge the confidence score up or down without overriding it:

```json
POST /control/insight
{
  "coin": "BTCUSDT",
  "direction": "bearish",
  "strength": 0.8,
  "reason": "Fed rate decision in 2h, expect volatility",
  "ttl_minutes": 120
}
```

`coin` can be `"ALL"` for market-wide signals. Insights expire automatically after `ttl_minutes`.

---

## Portfolio & Fees

### Paper Mode (Default)

- Starting balance: `$10,000 USDT` (configurable)
- All orders simulated at real Binance prices
- Fees deducted exactly as in real trading

### Fee Model

| Mode         | Fee per side | Round trip |
|--------------|-------------|------------|
| Standard     | 0.10%       | 0.20%      |
| BNB discount | 0.075%      | 0.15%      |

Fee tier stored in config and updated manually when volume tier changes.

Every trade records:
```
entry_price, entry_fee, entry_time
exit_price,  exit_fee,  exit_time
net_pnl = (exit_price - entry_price) - entry_fee - exit_fee
```

### Position Limits

| Parameter              | Default | Configurable |
|------------------------|---------|--------------|
| Max single position    | 30% of portfolio | yes |
| Max concurrent positions | unlimited (confidence-weighted) | — |
| Minimum trade size     | $10 USDT | yes |
| Reserve (always free)  | 10% of portfolio | yes |

---

## Control API

Runs on the same FastAPI server as the web dashboard. Any caller (Claude agent, script, curl) POSTs JSON commands. Changes take effect on the **next cycle** — no mid-trade mutations. All commands are logged with timestamp and caller for auditability.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/control/risk` | Adjust `stop_loss_pct`, `min_confidence`, `reserve_pct` |
| `POST` | `/control/position` | `force_sell` or `force_buy` a specific coin |
| `POST` | `/control/trading` | `pause` or `resume` all trading |
| `POST` | `/control/watchlist` | Add or remove specific coins |
| `POST` | `/control/config` | Update any config value at runtime |
| `POST` | `/control/insight` | Inject a directional insight with TTL |
| `GET`  | `/control/state` | Full bot state snapshot for agent polling |

**Auth:** single bearer token in config.

### Example Commands

```json
POST /control/risk
{ "stop_loss_pct": -6, "min_confidence": 0.5 }

POST /control/position
{ "action": "force_sell", "coin": "SOLUSDT" }

POST /control/trading
{ "action": "pause" }

POST /control/insight
{ "coin": "ALL", "direction": "bearish", "strength": 0.6, "reason": "market uncertainty", "ttl_minutes": 60 }
```

---

## Dashboards

### Terminal (`python main.py run`)

Live-updating `rich` dashboard, refreshes every 5s:

```
╔══ TIMEFM TRADER ══ PAPER MODE ══ $10,847.23 (+8.47%) ══════════════════╗
║ Invested: $8,234  Free: $2,613  Fees paid: $18.42  Positions: 7        ║
╠════════════╦═══════════╦═══════════╦══════════╦══════════╦═════════════╣
║ COIN       ║ ENTRY     ║ NOW       ║ FORECAST ║ CONF     ║ P&L         ║
╠════════════╬═══════════╬═══════════╬══════════╬══════════╬═════════════╣
║ BTCUSDT    ║ $61,200   ║ $63,450   ║ ↑ $65k   ║ 0.82     ║ +3.67% ▲   ║
║ ETHUSDT    ║ $3,100    ║ $3,050    ║ ↑ $3,200 ║ 0.71     ║ -1.61% ▼   ║
╚════════════╩═══════════╩═══════════╩══════════╩══════════╩═════════════╝
║ Last scan: 14s ago  |  Coins scanned: 312  |  Signals found: 7         ║
║ Active insights: BTC bearish (expires 1h 43m)                          ║
╚════════════════════════════════════════════════════════════════════════╝
```

Sparkline per row shows recent price trend. No full charts in terminal.

### Web (`python main.py web` → `localhost:8080`)

**Main page:**
- Live positions table (same data as terminal)
- Portfolio equity curve chart (balance over time, realized P&L, fees drag, drawdown indicator)
- Active insights panel
- Control panel: pause/resume, force-sell buttons per position

**Per-coin chart** (click any position):
- Candlestick OHLCV (TradingView `lightweight-charts`)
- Price overlays: MA20, MA50, MA200, Bollinger Bands
- TimeFM forecast: dotted continuation line from last candle, shaded confidence band
- Sub-panels: RSI, MACD, Volume bars

**Charting library:** TradingView `lightweight-charts` (OSS). Handles candlesticks natively, live WebSocket updates, no heavy framework.

All control panel actions call the `/control/` API endpoints — same interface available to external agents.

---

## Configuration (`config.py`)

```python
PAPER_MODE          = True
INITIAL_BALANCE     = 10_000        # USD
BINANCE_FEE_PCT     = 0.001         # 0.1% per side
BNB_DISCOUNT        = False
STOP_LOSS_PCT       = -0.04         # -4%
MIN_CONFIDENCE      = 0.3
RESERVE_PCT         = 0.10          # 10% always free
MAX_POSITION_PCT    = 0.30          # 30% max per coin
MIN_TRADE_USD       = 10
TIMEFRAMES          = ["1m","5m","15m","1h","4h","1d"]
SCAN_INTERVAL_S     = 60            # full market scan every 60s
STOP_LOSS_CHECK_S   = 30
WEB_PORT            = 8080
CONTROL_API_TOKEN   = "change-me"
BINANCE_API_KEY     = ""            # required for real mode only
BINANCE_SECRET      = ""
```

---

## Real Money Mode

Set `PAPER_MODE = False` and provide `BINANCE_API_KEY` + `BINANCE_SECRET`. The executor switches from simulated fills to real Binance spot market orders. All other logic (fees, signals, portfolio tracking) is identical.
