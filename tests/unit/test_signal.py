from datetime import datetime, timedelta

import pytest

from src.timefm_trader.models import Direction, Forecast, Insight, Signal
from src.timefm_trader.signal import apply_insights, generate_signals, rank_and_allocate


def test_generate_signals_returns_buy_when_expected_gain_above_fee_threshold(
    sample_forecast,
):
    result = generate_signals([sample_forecast], [], 0.001)

    assert len(result) == 1
    assert result[0].direction == Direction.BUY


def test_generate_signals_filters_hold_when_gain_below_fee_threshold(sample_forecast):
    low_gain_forecast = Forecast(
        symbol=sample_forecast.symbol,
        timeframe=sample_forecast.timeframe,
        forecast_prices=sample_forecast.forecast_prices,
        lower_bound=sample_forecast.lower_bound,
        upper_bound=sample_forecast.upper_bound,
        confidence_score=sample_forecast.confidence_score,
        last_price=sample_forecast.last_price,
        expected_gain_pct=0.0005,
    )

    assert generate_signals([low_gain_forecast], [], 0.001) == []


def test_apply_insights_reduces_confidence_for_bearish_insight(
    sample_forecast, sample_insight
):
    adjusted, was_adjusted = apply_insights(sample_forecast, [sample_insight])

    assert adjusted == pytest.approx(0.375)
    assert was_adjusted is True


def test_apply_insights_increases_confidence_for_bullish_insight_but_caps_at_one():
    forecast = Forecast(
        symbol="BTCUSDT",
        timeframe="1h",
        forecast_prices=[1.0],
        lower_bound=[0.9],
        upper_bound=[1.1],
        confidence_score=0.9,
        last_price=1.0,
        expected_gain_pct=0.02,
    )
    bullish_insight = Insight(
        coin="BTCUSDT",
        direction=Direction.BULLISH,
        strength=1.0,
        reason="Momentum",
        ttl_minutes=60,
    )

    adjusted, _ = apply_insights(forecast, [bullish_insight])

    assert adjusted <= 1.0


def test_expired_insights_are_ignored_by_apply_insights(sample_forecast):
    expired_insight = Insight(
        coin="BTCUSDT",
        direction=Direction.BEARISH,
        strength=0.5,
        reason="Expired",
        ttl_minutes=0,
        created_at=datetime.utcnow() - timedelta(minutes=1),
    )

    adjusted, was_adjusted = apply_insights(sample_forecast, [expired_insight])

    assert was_adjusted is False
    assert adjusted == sample_forecast.confidence_score


def test_rank_and_allocate_uses_proportional_allocation(sample_forecast):
    signal_a = Signal("BTCUSDT", Direction.BUY, 0.8, 0.03, "1h", sample_forecast)
    signal_b = Signal("ETHUSDT", Direction.BUY, 0.6, 0.03, "1h", sample_forecast)
    signal_c = Signal("SOLUSDT", Direction.BUY, 0.4, 0.03, "1h", sample_forecast)

    allocations = rank_and_allocate(
        [signal_a, signal_b, signal_c], 10000, 0.1, 0.3, 10
    )

    assert sum(allocations.values()) <= 10000 * 0.9
    assert allocations["BTCUSDT"] > allocations["ETHUSDT"] > allocations["SOLUSDT"]


def test_rank_and_allocate_respects_max_position_pct_cap(sample_forecast):
    signal = Signal("BTCUSDT", Direction.BUY, 1.0, 0.03, "1h", sample_forecast)

    allocations = rank_and_allocate([signal], 10000, 0.1, 0.3, 10)

    assert allocations["BTCUSDT"] <= 3000
