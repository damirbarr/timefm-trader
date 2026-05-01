"""Trade execution wrapper for paper and live modes."""
from __future__ import annotations

import logging

from src.timefm_trader.models import Direction, Position, TradeRecord
from src.timefm_trader.portfolio import Portfolio

logger = logging.getLogger(__name__)


class Executor:
    def __init__(self, portfolio: Portfolio, paper_mode: bool, api_key: str = "", secret: str = ""):
        self.portfolio = portfolio
        self.paper_mode = paper_mode
        self._exchange = None
        if not paper_mode and api_key:
            import ccxt

            self._exchange = ccxt.binance({"apiKey": api_key, "secret": secret})

    async def execute_buy(self, symbol: str, price: float, size_usd: float) -> Position | None:
        if self.paper_mode:
            return self.portfolio.open_position(symbol, price, size_usd)
        try:
            order = self._exchange.create_market_buy_order(symbol, size_usd / price)
            fill_price = order.get("average") or order.get("price") or price
            return self.portfolio.open_position(symbol, fill_price, size_usd)
        except Exception as e:
            logger.error("Buy order failed for %s: %s", symbol, e)
            return None

    async def execute_sell(self, symbol: str, price: float) -> TradeRecord | None:
        if symbol not in self.portfolio.positions:
            return None
        if self.paper_mode:
            return self.portfolio.close_position(symbol, price)
        try:
            pos = self.portfolio.positions[symbol]
            order = self._exchange.create_market_sell_order(symbol, pos.quantity)
            fill_price = order.get("average") or order.get("price") or price
            return self.portfolio.close_position(symbol, fill_price)
        except Exception as e:
            logger.error("Sell order failed for %s: %s", symbol, e)
            return None

    async def process_stop_losses(self, current_prices: dict[str, float]) -> list[TradeRecord]:
        hit_symbols = self.portfolio.update_prices(current_prices)
        results = []
        for symbol in hit_symbols:
            price = current_prices.get(symbol, self.portfolio.positions[symbol].current_price)
            record = await self.execute_sell(symbol, price)
            if record:
                results.append(record)
                logger.info(
                    "Stop-loss triggered for %s at %.4f, PnL: %.2f",
                    symbol,
                    price,
                    record.net_pnl,
                )
        return results
