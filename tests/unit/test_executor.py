"""Unit tests for order execution orchestration."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.timefm_trader.executor import Executor
from src.timefm_trader.models import Position, TradeRecord


@pytest.mark.asyncio
async def test_execute_buy_paper_mode() -> None:
    portfolio = MagicMock()
    position = MagicMock(spec=Position)
    portfolio.open_position.return_value = position
    executor = Executor(portfolio=portfolio, paper_mode=True)

    result = await executor.execute_buy("BTCUSDT", 60000, 1000)

    assert result is position
    portfolio.open_position.assert_called_once_with("BTCUSDT", 60000, 1000)


@pytest.mark.asyncio
async def test_execute_sell_paper_mode() -> None:
    portfolio = MagicMock()
    portfolio.positions = {"BTCUSDT": MagicMock()}
    record = MagicMock(spec=TradeRecord)
    portfolio.close_position.return_value = record
    executor = Executor(portfolio=portfolio, paper_mode=True)

    result = await executor.execute_sell("BTCUSDT", 62000)

    assert result is record
    portfolio.close_position.assert_called_once_with("BTCUSDT", 62000)


@pytest.mark.asyncio
async def test_execute_sell_returns_none_when_symbol_not_open() -> None:
    portfolio = MagicMock()
    portfolio.positions = {}
    executor = Executor(portfolio=portfolio, paper_mode=True)

    result = await executor.execute_sell("BTCUSDT", 62000)

    assert result is None


@pytest.mark.asyncio
async def test_process_stop_losses_sells_stop_loss_symbols() -> None:
    portfolio = MagicMock()
    portfolio.update_prices.return_value = ["SOLUSDT"]
    portfolio.positions = {"SOLUSDT": MagicMock(current_price=90.0)}
    executor = Executor(portfolio=portfolio, paper_mode=True)
    executor.execute_sell = AsyncMock(return_value=MagicMock(spec=TradeRecord))

    records = await executor.process_stop_losses({"SOLUSDT": 90.0})

    executor.execute_sell.assert_awaited_once_with("SOLUSDT", 90.0)
    assert len(records) == 1
