"""Shared data models for all modules."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import pandas as pd


class Direction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    BEARISH = "bearish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"


class TradeMode(str, Enum):
    PAPER = "paper"
    REAL = "real"


@dataclass
class Forecast:
    symbol: str
    timeframe: str                          # best timeframe selected
    forecast_prices: list[float]            # predicted prices, N steps ahead
    lower_bound: list[float]                # confidence interval lower
    upper_bound: list[float]                # confidence interval upper
    confidence_score: float                 # magnitude / uncertainty, fee-penalized
    last_price: float
    expected_gain_pct: float                # (forecast[-1] - last_price) / last_price


@dataclass
class Insight:
    coin: str                               # symbol or "ALL"
    direction: Direction
    strength: float                         # 0.0 - 1.0
    reason: str
    ttl_minutes: int
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_expired(self) -> bool:
        from datetime import timedelta
        return datetime.utcnow() > self.created_at + timedelta(minutes=self.ttl_minutes)


@dataclass
class Signal:
    symbol: str
    direction: Direction
    confidence: float
    expected_gain_pct: float
    timeframe: str
    forecast: Forecast
    insight_adjusted: bool = False


@dataclass
class Position:
    symbol: str
    entry_price: float
    size_usd: float
    quantity: float                         # coins held
    entry_fee: float
    entry_time: datetime = field(default_factory=datetime.utcnow)
    current_price: float = 0.0
    stop_loss_pct: float = -0.04

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity - self.entry_fee

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price

    @property
    def hit_stop_loss(self) -> bool:
        return self.unrealized_pnl_pct <= self.stop_loss_pct


@dataclass
class Order:
    symbol: str
    side: Direction                         # BUY or SELL
    size_usd: float
    price: float
    fee_pct: float


@dataclass
class TradeRecord:
    symbol: str
    entry_price: float
    exit_price: float
    size_usd: float
    quantity: float
    entry_fee: float
    exit_fee: float
    entry_time: datetime
    exit_time: datetime

    @property
    def net_pnl(self) -> float:
        return (self.exit_price - self.entry_price) * self.quantity - self.entry_fee - self.exit_fee

    @property
    def net_pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return self.net_pnl / self.size_usd


@dataclass
class BotState:
    mode: TradeMode
    running: bool
    paused: bool
    balance_usd: float
    initial_balance: float
    positions: dict[str, Position]          # symbol → Position
    trade_history: list[TradeRecord]
    active_insights: list[Insight]
    total_fees_paid: float
    coins_scanned: int
    last_scan_time: Optional[datetime]
    signals_found: int

    @property
    def portfolio_value(self) -> float:
        invested = sum(p.size_usd + p.unrealized_pnl for p in self.positions.values())
        return self.balance_usd + invested

    @property
    def total_return_pct(self) -> float:
        if self.initial_balance == 0:
            return 0.0
        return (self.portfolio_value - self.initial_balance) / self.initial_balance

    @property
    def realized_pnl(self) -> float:
        return sum(t.net_pnl for t in self.trade_history)
