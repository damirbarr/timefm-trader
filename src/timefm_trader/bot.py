"""Main trading bot orchestration loop."""
from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime
from typing import Any

from . import config
from .models import BotState, Direction, Insight, TradeMode

logger = logging.getLogger(__name__)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


try:
    from .forecaster import TimeFMForecaster  # type: ignore
except ImportError:
    class TimeFMForecaster:  # type: ignore[override]
        async def forecast_timeframe(self, symbol: str, timeframe: str, ohlcv: Any) -> Any:
            return None

        def select_best_timeframe(self, forecasts: list[Any]) -> Any:
            return next((forecast for forecast in forecasts if forecast is not None), None)


try:
    from .portfolio import Portfolio  # type: ignore
except ImportError:
    class Portfolio:  # type: ignore[override]
        def __init__(
            self,
            initial_balance: float,
            fee_pct: float,
            stop_loss_pct: float,
            reserve_pct: float,
            max_position_pct: float,
            min_trade_usd: float,
        ) -> None:
            self.initial_balance = initial_balance
            self.balance_usd = initial_balance
            self.positions: dict[str, Any] = {}
            self.trade_history: list[Any] = []
            self.total_fees_paid = 0.0
            self.stop_loss_pct = stop_loss_pct
            self.reserve_pct = reserve_pct
            self.fee_pct = fee_pct
            self.max_position_pct = max_position_pct
            self.min_trade_usd = min_trade_usd


try:
    from .executor import Executor  # type: ignore
except ImportError:
    class Executor:  # type: ignore[override]
        def __init__(
            self,
            portfolio: Portfolio,
            paper_mode: bool,
            api_key: str = "",
            secret: str = "",
        ) -> None:
            self.portfolio = portfolio

        async def execute_buy(
            self,
            coin: str,
            current_price: float,
            size_usd: float | None = None,
        ) -> bool:
            return False

        async def execute_sell(self, coin: str, current_price: float) -> bool:
            return False

        async def process_stop_losses(self, prices: dict[str, float]) -> None:
            return None


try:
    from . import fetcher  # type: ignore
except ImportError:
    class _FetcherFallback:
        async def get_all_usdt_pairs(self) -> list[str]:
            return []

        async def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> Any:
            return None

        async def get_current_prices(self, coins: list[str]) -> dict[str, float]:
            return {coin: 0.0 for coin in coins}

    fetcher = _FetcherFallback()


try:
    from . import signal  # type: ignore
except ImportError:
    class _SignalFallback:
        async def generate_signals(
            self,
            forecasts: list[Any],
            insights: list[Insight],
            fee_pct: float,
        ) -> list[Any]:
            return []

        async def rank_and_allocate(
            self,
            signals: list[Any],
            available_capital: float,
            reserve_pct: float,
            max_position_pct: float,
            min_trade_usd: float,
        ) -> dict[str, float]:
            return {}

    signal = _SignalFallback()


try:
    import ccxt.async_support as ccxt  # type: ignore
except ImportError:
    ccxt = None


class TradingBot:
    def __init__(self) -> None:
        self.forecaster = TimeFMForecaster()
        self.portfolio = Portfolio(
            initial_balance=config.INITIAL_BALANCE,
            fee_pct=config.effective_fee(),
            stop_loss_pct=config.STOP_LOSS_PCT,
            reserve_pct=config.RESERVE_PCT,
            max_position_pct=config.MAX_POSITION_PCT,
            min_trade_usd=config.MIN_TRADE_USD,
        )
        self.executor = Executor(
            self.portfolio,
            paper_mode=config.PAPER_MODE,
            api_key=config.BINANCE_API_KEY,
            secret=config.BINANCE_SECRET,
        )
        self.exchange = None
        if ccxt is not None:
            self.exchange = ccxt.binance({"enableRateLimit": True})
        self.active_insights: list[Insight] = []
        self.paused: bool = False
        self.watchlist_override: set[str] | None = None
        self._state = BotState(
            mode=TradeMode.PAPER if config.PAPER_MODE else TradeMode.REAL,
            running=True,
            paused=False,
            balance_usd=getattr(self.portfolio, "balance_usd", config.INITIAL_BALANCE),
            initial_balance=getattr(
                self.portfolio,
                "initial_balance",
                getattr(self.portfolio, "_initial_balance", config.INITIAL_BALANCE),
            ),
            positions=getattr(self.portfolio, "positions", {}),
            trade_history=getattr(self.portfolio, "trade_history", []),
            active_insights=[],
            total_fees_paid=getattr(self.portfolio, "total_fees_paid", 0.0),
            coins_scanned=0,
            last_scan_time=None,
            signals_found=0,
        )

    async def run(self) -> None:
        try:
            await asyncio.gather(self._scan_loop(), self._stop_loss_loop())
        finally:
            await self._close_exchange()

    async def _scan_loop(self) -> None:
        semaphore = asyncio.Semaphore(20)

        while True:
            try:
                if self.paused:
                    await asyncio.sleep(config.SCAN_INTERVAL_S)
                    continue

                if self.watchlist_override:
                    pairs = sorted(self.watchlist_override)
                elif self.exchange is not None:
                    pairs = await _maybe_await(fetcher.get_all_usdt_pairs(self.exchange))
                else:
                    pairs = []
                active_insights = self._purge_expired_insights()

                analyses = await asyncio.gather(
                    *(self._analyze_symbol(symbol, active_insights, semaphore) for symbol in pairs),
                    return_exceptions=True,
                )
                signals = [item for item in analyses if item is not None and not isinstance(item, Exception)]
                allocations = await _maybe_await(
                    signal.rank_and_allocate(
                        signals,
                        getattr(self.portfolio, "balance_usd", 0.0),
                        getattr(self.portfolio, "reserve_pct", config.RESERVE_PCT),
                        getattr(self.portfolio, "max_position_pct", config.MAX_POSITION_PCT),
                        getattr(self.portfolio, "min_trade_usd", config.MIN_TRADE_USD),
                    )
                )

                for symbol, size_usd in (allocations or {}).items():
                    if symbol not in self.portfolio.positions:
                        matching_signal = next((item for item in signals if item.symbol == symbol), None)
                        current_price = (
                            getattr(getattr(matching_signal, "forecast", None), "last_price", 0.0)
                            if matching_signal is not None
                            else 0.0
                        )
                        await self.executor.execute_buy(symbol, current_price, size_usd)

                open_symbols = list(self.portfolio.positions.keys())
                bearish_checks = await asyncio.gather(
                    *(self._analyze_symbol(symbol, active_insights, semaphore) for symbol in open_symbols),
                    return_exceptions=True,
                )
                for symbol, result in zip(open_symbols, bearish_checks):
                    if isinstance(result, Exception) or result is None:
                        continue
                    direction = getattr(result, "direction", None)
                    if direction == Direction.SELL:
                        position = self.portfolio.positions.get(symbol)
                        current_price = getattr(getattr(result, "forecast", None), "last_price", None)
                        if current_price is None and position is not None:
                            current_price = getattr(position, "current_price", position.entry_price)
                        await self.executor.execute_sell(symbol, current_price or 0.0)

                self._state.coins_scanned = len(pairs)
                self._state.signals_found = len(signals)
                self._state.last_scan_time = datetime.utcnow()
                self._sync_state()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("scan loop iteration failed")
            await asyncio.sleep(config.SCAN_INTERVAL_S)

    async def _stop_loss_loop(self) -> None:
        while True:
            try:
                open_symbols = list(self.portfolio.positions.keys())
                if open_symbols and self.exchange is not None:
                    prices = await _maybe_await(fetcher.get_current_prices(self.exchange, open_symbols))
                    for symbol, price in prices.items():
                        if symbol in self.portfolio.positions:
                            self.portfolio.positions[symbol].current_price = price
                    await self.executor.process_stop_losses(prices)
                    self._sync_state()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("stop loss loop iteration failed")
            await asyncio.sleep(config.STOP_LOSS_CHECK_S)

    def get_state(self) -> BotState:
        self._sync_state()
        return self._state

    async def handle_command(self, command: dict) -> dict:
        timestamp = datetime.utcnow().isoformat()
        logger.info("command_received ts=%s payload=%s", timestamp, command)

        try:
            command_type = command["type"]
            if command_type == "risk":
                for field in ("stop_loss_pct", "min_confidence", "reserve_pct"):
                    if field in command:
                        setattr(self.portfolio, field, command[field])
                self._sync_state()
                return {"ok": True}

            if command_type == "position":
                action = command.get("action")
                coin = command["coin"]
                current_price = command["current_price"]
                if action == "force_sell":
                    await self.executor.execute_sell(coin, current_price)
                    self._sync_state()
                    return {"ok": True}
                if action == "force_buy":
                    await self.executor.execute_buy(coin, current_price, command["size_usd"])
                    self._sync_state()
                    return {"ok": True}
                return {"ok": False, "error": f"unknown position action: {action}"}

            if command_type == "trading":
                action = command.get("action")
                if action == "pause":
                    self.paused = True
                elif action == "resume":
                    self.paused = False
                else:
                    return {"ok": False, "error": f"unknown trading action: {action}"}
                self._sync_state()
                return {"ok": True}

            if command_type == "watchlist":
                action = command.get("action")
                coin = command["coin"]
                if self.watchlist_override is None:
                    self.watchlist_override = set()
                if action == "add":
                    self.watchlist_override.add(coin)
                elif action == "remove":
                    self.watchlist_override.discard(coin)
                    if not self.watchlist_override:
                        self.watchlist_override = None
                else:
                    return {"ok": False, "error": f"unknown watchlist action: {action}"}
                return {"ok": True}

            if command_type == "insight":
                insight = Insight(
                    coin=command["coin"],
                    direction=Direction(command["direction"]),
                    strength=float(command["strength"]),
                    reason=command["reason"],
                    ttl_minutes=int(command["ttl_minutes"]),
                )
                self.active_insights.append(insight)
                self._purge_expired_insights()
                self._sync_state()
                return {"ok": True}

            if command_type == "config":
                key = command["key"]
                value = command["value"]
                setattr(config, key, value)
                self._sync_state()
                return {"ok": True}

            return {"ok": False, "error": f"unknown command type: {command_type}"}
        except KeyError as exc:
            return {"ok": False, "error": f"missing key: {exc.args[0]}"}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("command handling failed")
            return {"ok": False, "error": str(exc)}

    async def _analyze_symbol(
        self,
        symbol: str,
        active_insights: list[Insight],
        semaphore: asyncio.Semaphore,
    ) -> Any:
        async def _fetch_timeframe(timeframe: str) -> Any:
            async with semaphore:
                if self.exchange is None:
                    return None
                ohlcv = await _maybe_await(fetcher.get_ohlcv(self.exchange, symbol, timeframe, config.OHLCV_LIMIT))
                return await _maybe_await(self.forecaster.forecast_timeframe(ohlcv, timeframe, symbol))

        forecasts = await asyncio.gather(*(_fetch_timeframe(timeframe) for timeframe in config.TIMEFRAMES))
        forecast_map = {
            timeframe: forecast
            for timeframe, forecast in zip(config.TIMEFRAMES, forecasts)
            if forecast is not None
        }
        best = await _maybe_await(self.forecaster.select_best_timeframe(forecast_map))
        if best is None:
            return None
        generated = await _maybe_await(signal.generate_signals([best], active_insights, config.effective_fee()))
        if not generated:
            return None
        return generated[0]

    def _purge_expired_insights(self) -> list[Insight]:
        self.active_insights = [insight for insight in self.active_insights if not insight.is_expired()]
        return self.active_insights

    def _sync_state(self) -> None:
        self._state.mode = TradeMode.PAPER if config.PAPER_MODE else TradeMode.REAL
        self._state.paused = self.paused
        self._state.balance_usd = getattr(self.portfolio, "balance_usd", self._state.balance_usd)
        self._state.initial_balance = getattr(
            self.portfolio,
            "initial_balance",
            getattr(self.portfolio, "_initial_balance", self._state.initial_balance),
        )
        self._state.positions = getattr(self.portfolio, "positions", self._state.positions)
        self._state.trade_history = getattr(self.portfolio, "trade_history", self._state.trade_history)
        self._state.active_insights = list(self.active_insights)
        self._state.total_fees_paid = getattr(self.portfolio, "total_fees_paid", self._state.total_fees_paid)

    async def _close_exchange(self) -> None:
        if self.exchange is not None and hasattr(self.exchange, "close"):
            await _maybe_await(self.exchange.close())
