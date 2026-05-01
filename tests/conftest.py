"""Shared pytest fixtures."""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.timefm_trader.models import (
    Forecast, Signal, Position, Order, Insight, BotState, TradeRecord,
    Direction, TradeMode
)
from src.timefm_trader import config


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """100-candle OHLCV dataframe with realistic BTC-like prices."""
    np.random.seed(42)
    n = 100
    timestamps = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(n)]
    close = 60000 + np.cumsum(np.random.randn(n) * 200)
    open_ = close - np.random.randn(n) * 100
    high = np.maximum(open_, close) + abs(np.random.randn(n) * 150)
    low = np.minimum(open_, close) - abs(np.random.randn(n) * 150)
    volume = abs(np.random.randn(n) * 1000 + 5000)
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


@pytest.fixture
def sample_forecast() -> Forecast:
    return Forecast(
        symbol="BTCUSDT",
        timeframe="1h",
        forecast_prices=[61000, 61500, 62000, 62500, 63000],
        lower_bound=[60500, 60800, 61200, 61500, 61800],
        upper_bound=[61500, 62200, 62800, 63500, 64200],
        confidence_score=0.75,
        last_price=60800.0,
        expected_gain_pct=0.033,
    )


@pytest.fixture
def sample_signal(sample_forecast) -> Signal:
    return Signal(
        symbol="BTCUSDT",
        direction=Direction.BUY,
        confidence=0.75,
        expected_gain_pct=0.033,
        timeframe="1h",
        forecast=sample_forecast,
    )


@pytest.fixture
def sample_position() -> Position:
    return Position(
        symbol="BTCUSDT",
        entry_price=60000.0,
        size_usd=1000.0,
        quantity=1000.0 / 60000.0,
        entry_fee=1.0,
        current_price=62000.0,
        stop_loss_pct=-0.04,
    )


@pytest.fixture
def sample_insight() -> Insight:
    return Insight(
        coin="BTCUSDT",
        direction=Direction.BEARISH,
        strength=0.5,
        reason="Test insight",
        ttl_minutes=60,
    )


@pytest.fixture
def empty_bot_state() -> BotState:
    return BotState(
        mode=TradeMode.PAPER,
        running=True,
        paused=False,
        balance_usd=10000.0,
        initial_balance=10000.0,
        positions={},
        trade_history=[],
        active_insights=[],
        total_fees_paid=0.0,
        coins_scanned=0,
        last_scan_time=None,
        signals_found=0,
    )
