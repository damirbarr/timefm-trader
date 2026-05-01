from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.timefm_trader.bot import TradingBot
from src.timefm_trader.models import Direction


@pytest.fixture
def bot() -> TradingBot:
    with (
        patch("src.timefm_trader.bot.TimeFMForecaster", return_value=MagicMock()),
        patch("src.timefm_trader.bot.Portfolio") as portfolio_cls,
        patch("src.timefm_trader.bot.Executor") as executor_cls,
    ):
        portfolio = MagicMock()
        portfolio.balance_usd = 10000.0
        portfolio.initial_balance = 10000.0
        portfolio.positions = {}
        portfolio.trade_history = []
        portfolio.total_fees_paid = 0.0
        portfolio.stop_loss_pct = -0.04
        portfolio.min_confidence = 0.3
        portfolio.reserve_pct = 0.1
        portfolio_cls.return_value = portfolio

        executor = AsyncMock()
        executor_cls.return_value = executor

        yield TradingBot()


@pytest.mark.asyncio
async def test_handle_command_pause(bot: TradingBot) -> None:
    result = await bot.handle_command({"type": "trading", "action": "pause"})
    assert result == {"ok": True}
    assert bot.paused is True


@pytest.mark.asyncio
async def test_handle_command_resume(bot: TradingBot) -> None:
    bot.paused = True
    result = await bot.handle_command({"type": "trading", "action": "resume"})
    assert result == {"ok": True}
    assert bot.paused is False


@pytest.mark.asyncio
async def test_handle_command_insight_appends(bot: TradingBot) -> None:
    result = await bot.handle_command(
        {
            "type": "insight",
            "coin": "BTCUSDT",
            "direction": "bearish",
            "strength": 0.8,
            "reason": "test",
            "ttl_minutes": 60,
        }
    )

    assert result == {"ok": True}
    assert len(bot.active_insights) == 1
    assert bot.active_insights[0].direction == Direction.BEARISH


@pytest.mark.asyncio
async def test_handle_command_risk_updates_portfolio(bot: TradingBot) -> None:
    result = await bot.handle_command({"type": "risk", "stop_loss_pct": -0.06})
    assert result == {"ok": True}
    assert bot.portfolio.stop_loss_pct == -0.06


@pytest.mark.asyncio
async def test_handle_command_unknown_type(bot: TradingBot) -> None:
    result = await bot.handle_command({"type": "unknown"})
    assert result["ok"] is False
    assert "unknown command type" in result["error"]
