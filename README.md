# TimeFM Trader

Multi-coin crypto trading bot powered by [Google TimeFM](https://github.com/google-research/timesfm) — a zero-shot time series foundation model. Scans all Binance USDT pairs, forecasts prices across multiple timeframes, and trades with full fee accounting.

**Default mode is paper trading (fake money).** Real trading requires explicit opt-in.

## Features

- **TimeFM forecasting** — multi-timeframe per coin (1m/5m/15m/1h/4h/1d), auto-selects best timeframe
- **Full market scan** — all active Binance USDT spot pairs, ranked by expected return
- **Confidence-weighted sizing** — allocates more capital to higher-confidence signals
- **Fee-aware** — 0.1% Binance fee baked into every signal filter and P&L calculation
- **Hard stop-loss** — configurable floor (default -4%), checked every 30s
- **External control API** — REST endpoints for agents/scripts to adjust risk, force trades, inject insights
- **Terminal dashboard** — live `rich` table with positions, P&L, sparklines
- **Web dashboard** — browser UI with candlestick charts, MA overlays, TimeFM forecast projection, RSI/MACD panels
- **52 tests** — unit + integration coverage

## Quick Start

```bash
git clone https://github.com/damirbarr/timefm-trader
cd timefm-trader

make install       # create venv + install deps
make env           # create .env from template

# edit .env if needed, then:
make run           # terminal dashboard (paper mode)
make web           # browser dashboard at localhost:8080
make both          # terminal + web simultaneously
```

## Makefile Commands

```
make install          Create venv and install all dependencies
make install-dev      Install with linting/type-checking extras
make run              Terminal dashboard, paper mode
make web              Web dashboard at localhost:8080, paper mode
make both             Terminal + web simultaneously
make run-live         Terminal dashboard, LIVE trading (real money)
make web-live         Web dashboard, LIVE trading
make test             Full test suite with coverage report
make test-unit        Unit tests only
make test-integration Integration tests only
make lint             Ruff linter
make format           Auto-format with ruff
make typecheck        mypy type check
make clean            Remove caches and build artifacts
make clean-venv       Full reset including venv
```

## Configuration

All config lives in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `PAPER_MODE` | `true` | Fake money mode |
| `INITIAL_BALANCE` | `10000` | Starting USD balance |
| `BINANCE_API_KEY` | — | Required for live trading only |
| `BINANCE_SECRET` | — | Required for live trading only |
| `STOP_LOSS_PCT` | `-0.04` | Hard stop-loss (-4%) |
| `MIN_CONFIDENCE` | `0.3` | Minimum signal confidence |
| `RESERVE_PCT` | `0.10` | % always kept as free USDT |
| `MAX_POSITION_PCT` | `0.30` | Max position size per coin |
| `SCAN_INTERVAL_S` | `60` | Full market scan interval |
| `CONTROL_API_TOKEN` | `change-me` | Auth token for control API |
| `WEB_PORT` | `8080` | Web dashboard port |

## Control API

The web server exposes REST endpoints for external agents (scripts, another Claude instance, etc.) to adjust the bot while it runs. All endpoints require `Authorization: Bearer <token>`.

```bash
# Pause trading
curl -X POST localhost:8080/control/trading \
  -H "Authorization: Bearer change-me" \
  -d '{"action": "pause"}'

# Inject a market insight
curl -X POST localhost:8080/control/insight \
  -H "Authorization: Bearer change-me" \
  -d '{"coin":"ALL","direction":"bearish","strength":0.7,"reason":"Fed announcement","ttl_minutes":120}'

# Adjust risk parameters on the fly
curl -X POST localhost:8080/control/risk \
  -H "Authorization: Bearer change-me" \
  -d '{"stop_loss_pct": -0.06, "min_confidence": 0.5}'

# Force sell a position
curl -X POST localhost:8080/control/position \
  -H "Authorization: Bearer change-me" \
  -d '{"action": "force_sell", "coin": "SOLUSDT"}'

# Get full bot state snapshot
curl localhost:8080/control/state \
  -H "Authorization: Bearer change-me"
```

### Insight API

Insights blend with TimeFM forecasts — they nudge confidence scores without overriding the model. Bearish insights dampen buy signals; bullish insights amplify them. Insights expire automatically after `ttl_minutes`.

```json
{
  "coin": "BTCUSDT",     // or "ALL" for market-wide
  "direction": "bearish",
  "strength": 0.8,       // 0.0 - 1.0
  "reason": "CPI data dropping in 2h",
  "ttl_minutes": 120
}
```

## Architecture

```
fetcher → forecaster → signal → portfolio → executor
                                    ↑
                              stop-loss monitor (30s)
                                    ↓
                         dashboard (terminal) + web (browser)
```

| File | Responsibility |
|------|---------------|
| `fetcher.py` | Binance OHLCV + pair discovery |
| `indicators.py` | MA/RSI/MACD/Bollinger in pure numpy |
| `forecaster.py` | TimeFM multi-timeframe, best-timeframe selection |
| `signal.py` | Confidence scoring, insight blending, capital allocation |
| `portfolio.py` | Positions, fees, P&L, stop-loss tracking |
| `executor.py` | Paper/live order execution (same interface) |
| `web.py` | FastAPI + WebSocket + control API |
| `dashboard.py` | Rich terminal live dashboard |
| `bot.py` | Async scan loop orchestrator |
| `main.py` | CLI entry point |

## Live Trading

Set `PAPER_MODE=false` in `.env` and add your Binance API keys. The executor switches from simulated fills to real market orders — all other logic (fees, signals, portfolio tracking) is identical to paper mode.

**Only use API keys with Spot trading permissions. Never enable withdrawals.**

## Testing

```bash
make test           # full suite + coverage
make test-unit      # faster, no integration
```

Tests mock all external dependencies (Binance API, TimeFM model) so they run offline without any API keys or GPU.
