from __future__ import annotations

from datetime import datetime

from rich.console import Console

from src.timefm_trader.dashboard import TerminalDashboard
from src.timefm_trader.models import BotState, Direction, Insight, Position, TradeMode


def _render_text(state: BotState) -> str:
    dashboard = TerminalDashboard()
    console = Console(record=True, width=160)
    console.print(dashboard.render(state))
    return console.export_text()


def test_render_populated_state() -> None:
    position = Position(
        symbol="BTCUSDT",
        entry_price=60000.0,
        size_usd=1200.0,
        quantity=0.02,
        entry_fee=1.2,
        current_price=61800.0,
    )
    position.price_history = [59800, 60200, 60500, 60300, 60900, 61100, 61400, 61200, 61600, 61800]
    state = BotState(
        mode=TradeMode.PAPER,
        running=True,
        paused=False,
        balance_usd=8800.0,
        initial_balance=10000.0,
        positions={"BTCUSDT": position},
        trade_history=[],
        active_insights=[
            Insight(
                coin="BTCUSDT",
                direction=Direction.BULLISH,
                strength=0.82,
                reason="Momentum improving",
                ttl_minutes=30,
            )
        ],
        total_fees_paid=2.4,
        coins_scanned=20,
        last_scan_time=datetime.utcnow(),
        signals_found=3,
    )

    assert TerminalDashboard().render(state) is not None


def test_render_empty_positions() -> None:
    state = BotState(
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

    assert TerminalDashboard().render(state) is not None


def test_render_paused_contains_banner() -> None:
    state = BotState(
        mode=TradeMode.PAPER,
        running=True,
        paused=True,
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

    rendered = _render_text(state)
    assert "PAUSED" in rendered
