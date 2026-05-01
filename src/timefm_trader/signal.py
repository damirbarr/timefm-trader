from src.timefm_trader import config
from src.timefm_trader.models import Direction, Forecast, Insight, Signal


def _get_active_insights_for(symbol: str, insights: list[Insight]) -> list[Insight]:
    return [
        insight
        for insight in insights
        if not insight.is_expired() and (insight.coin == symbol or insight.coin == "ALL")
    ]


def apply_insights(forecast: Forecast, insights: list[Insight]) -> tuple[float, bool]:
    confidence = forecast.confidence_score
    adjusted = False

    for insight in _get_active_insights_for(forecast.symbol, insights):
        adjusted = True
        if insight.direction in (Direction.BEARISH,):
            confidence *= 1.0 - insight.strength
        elif insight.direction in (Direction.BULLISH,):
            confidence = min(1.0, confidence * (1.0 + insight.strength * 0.5))

    return confidence, adjusted


def generate_signals(
    forecasts: list[Forecast], insights: list[Insight], fee_pct: float
) -> list[Signal]:
    signals = []
    min_gain = fee_pct * 2

    for forecast in forecasts:
        if forecast.expected_gain_pct > min_gain:
            direction = Direction.BUY
        elif forecast.expected_gain_pct < -min_gain:
            direction = Direction.SELL
        else:
            continue

        confidence, was_adjusted = apply_insights(forecast, insights)
        if confidence < config.MIN_CONFIDENCE:
            continue

        signals.append(
            Signal(
                symbol=forecast.symbol,
                direction=direction,
                confidence=confidence,
                expected_gain_pct=forecast.expected_gain_pct,
                timeframe=forecast.timeframe,
                forecast=forecast,
                insight_adjusted=was_adjusted,
            )
        )

    return sorted(signals, key=lambda signal: signal.confidence, reverse=True)


def rank_and_allocate(
    signals: list[Signal],
    available_capital: float,
    reserve_pct: float,
    max_position_pct: float,
    min_trade_usd: float,
) -> dict[str, float]:
    if not signals:
        return {}

    deployable = available_capital * (1.0 - reserve_pct)
    total_confidence = sum(signal.confidence for signal in signals)
    allocations = {}

    for signal in signals:
        raw = deployable * (signal.confidence / total_confidence)
        capped = min(raw, available_capital * max_position_pct)
        if capped >= min_trade_usd:
            allocations[signal.symbol] = capped

    return allocations
