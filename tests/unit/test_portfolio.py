"""Unit tests for portfolio trade accounting."""
from __future__ import annotations

import pytest

from src.timefm_trader.portfolio import Portfolio


@pytest.fixture
def portfolio() -> Portfolio:
    return Portfolio(10000, 0.001, -0.04, 0.1, 0.3, 10)


def test_open_position_success(portfolio: Portfolio) -> None:
    pos = portfolio.open_position("BTCUSDT", 60000.0, 1000.0)

    assert pos is not None
    assert "BTCUSDT" in portfolio.positions
    assert portfolio.balance_usd < 10000
    assert portfolio.total_fees_paid == pytest.approx(1.0)


def test_open_position_returns_none_when_size_below_minimum(portfolio: Portfolio) -> None:
    pos = portfolio.open_position("BTCUSDT", 60000, 5.0)

    assert pos is None


def test_open_position_returns_none_when_symbol_already_open(portfolio: Portfolio) -> None:
    portfolio.open_position("BTCUSDT", 60000, 100)
    second = portfolio.open_position("BTCUSDT", 60000, 100)

    assert second is None


def test_open_position_returns_none_when_insufficient_capital(portfolio: Portfolio) -> None:
    pos = portfolio.open_position("BTCUSDT", 60000, 9200)

    assert pos is None


def test_close_position_success(portfolio: Portfolio) -> None:
    portfolio.open_position("BTCUSDT", 60000, 1000)
    record = portfolio.close_position("BTCUSDT", 63000.0)

    assert record is not None
    assert "BTCUSDT" not in portfolio.positions
    assert record.net_pnl > 0
    assert portfolio.balance_usd > 9000


def test_close_position_returns_none_for_unknown_symbol(portfolio: Portfolio) -> None:
    record = portfolio.close_position("UNKNOWN", 100.0)

    assert record is None


def test_update_prices_updates_current_price(portfolio: Portfolio) -> None:
    portfolio.open_position("BTCUSDT", 60000, 1000)
    portfolio.update_prices({"BTCUSDT": 62000.0})

    assert portfolio.positions["BTCUSDT"].current_price == 62000.0


def test_update_prices_returns_stop_loss_symbols(portfolio: Portfolio) -> None:
    portfolio.open_position("BTCUSDT", 60000, 1000)
    hits = portfolio.update_prices({"BTCUSDT": 57500.0})

    assert "BTCUSDT" in hits


def test_portfolio_value_equals_balance_plus_market_value(portfolio: Portfolio) -> None:
    portfolio.open_position("BTCUSDT", 60000, 1000)
    portfolio.update_prices({"BTCUSDT": 62000.0})

    expected = portfolio.balance_usd + (portfolio.positions["BTCUSDT"].quantity * 62000)
    assert portfolio.portfolio_value() == pytest.approx(expected)


def test_total_fees_paid_accumulates(portfolio: Portfolio) -> None:
    portfolio.open_position("BTCUSDT", 60000, 1000)
    portfolio.close_position("BTCUSDT", 63000)

    assert portfolio.total_fees_paid > 0
