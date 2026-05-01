"""Portfolio state and trade accounting."""
from __future__ import annotations

from datetime import datetime

from src.timefm_trader.models import Position, TradeRecord


class Portfolio:
    def __init__(
        self,
        initial_balance: float,
        fee_pct: float,
        stop_loss_pct: float,
        reserve_pct: float,
        max_position_pct: float,
        min_trade_usd: float,
    ):
        self.balance_usd = initial_balance
        self.fee_pct = fee_pct
        self.stop_loss_pct = stop_loss_pct
        self.reserve_pct = reserve_pct
        self.max_position_pct = max_position_pct
        self.min_trade_usd = min_trade_usd
        self.positions: dict[str, Position] = {}
        self.trade_history: list[TradeRecord] = []
        self.total_fees_paid: float = 0.0
        self._initial_balance = initial_balance

    def available_capital(self) -> float:
        return self.balance_usd * (1.0 - self.reserve_pct)

    def portfolio_value(self) -> float:
        invested = sum((p.current_price * p.quantity) for p in self.positions.values())
        return self.balance_usd + invested

    def open_position(self, symbol: str, price: float, size_usd: float) -> Position | None:
        if size_usd < self.min_trade_usd:
            return None
        if symbol in self.positions:
            return None
        if size_usd > self.available_capital():
            return None

        fee = size_usd * self.fee_pct
        total_cost = size_usd + fee
        self.balance_usd -= total_cost
        self.total_fees_paid += fee
        quantity = size_usd / price

        pos = Position(
            symbol=symbol,
            entry_price=price,
            size_usd=size_usd,
            quantity=quantity,
            entry_fee=fee,
            current_price=price,
            stop_loss_pct=self.stop_loss_pct,
        )
        self.positions[symbol] = pos
        return pos

    def close_position(self, symbol: str, exit_price: float) -> TradeRecord | None:
        if symbol not in self.positions:
            return None

        pos = self.positions.pop(symbol)
        proceeds = pos.quantity * exit_price
        exit_fee = proceeds * self.fee_pct
        net_proceeds = proceeds - exit_fee
        self.balance_usd += net_proceeds
        self.total_fees_paid += exit_fee

        record = TradeRecord(
            symbol=symbol,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            size_usd=pos.size_usd,
            quantity=pos.quantity,
            entry_fee=pos.entry_fee,
            exit_fee=exit_fee,
            entry_time=pos.entry_time,
            exit_time=datetime.utcnow(),
        )
        self.trade_history.append(record)
        return record

    def update_prices(self, prices: dict[str, float]) -> list[str]:
        stop_loss_hits = []
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price
                if self.positions[symbol].hit_stop_loss:
                    stop_loss_hits.append(symbol)
        return stop_loss_hits

    def get_state_snapshot(self) -> dict:
        return {
            "balance_usd": self.balance_usd,
            "portfolio_value": self.portfolio_value(),
            "total_fees_paid": self.total_fees_paid,
            "positions": {
                sym: {
                    "symbol": p.symbol,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "size_usd": p.size_usd,
                    "quantity": p.quantity,
                    "unrealized_pnl": p.unrealized_pnl,
                    "unrealized_pnl_pct": p.unrealized_pnl_pct,
                    "entry_time": p.entry_time.isoformat(),
                }
                for sym, p in self.positions.items()
            },
            "trade_count": len(self.trade_history),
            "realized_pnl": sum(t.net_pnl for t in self.trade_history),
        }
