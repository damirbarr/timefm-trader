"""Terminal dashboard for monitoring bot state."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable

from rich.align import Align
from rich.columns import Columns
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import BotState, Direction, Insight, Position, TradeRecord, TradeMode


def _fmt_usd(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def _sparkline(values: list[float] | None, width: int = 10) -> str:
    if not values:
        return "-" * width
    trimmed = values[-width:]
    if len(trimmed) == 1:
        return "▁" * len(trimmed)

    blocks = "▁▂▃▄▅▆▇█"
    low = min(trimmed)
    high = max(trimmed)
    if high == low:
        return blocks[0] * len(trimmed)

    scale = len(blocks) - 1
    return "".join(blocks[round((value - low) / (high - low) * scale)] for value in trimmed)


def _insight_direction(direction: Direction) -> str:
    mapping = {
        Direction.BUY: "bullish",
        Direction.BULLISH: "bullish",
        Direction.SELL: "bearish",
        Direction.BEARISH: "bearish",
        Direction.HOLD: "neutral",
        Direction.NEUTRAL: "neutral",
    }
    return mapping.get(direction, str(direction))


def _insight_expiry(insight: Insight) -> str:
    expires_at = insight.created_at.timestamp() + (insight.ttl_minutes * 60)
    remaining_seconds = max(0, int(expires_at - datetime.utcnow().timestamp()))
    return f"{max(1, remaining_seconds // 60)}m"


def _trade_win_rate(trades: list[TradeRecord]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for trade in trades if trade.net_pnl > 0)
    return wins / len(trades)


class TerminalDashboard:
    """Rich terminal dashboard for live bot visibility."""

    def render(self, state: BotState) -> Any:
        portfolio_value = state.portfolio_value
        invested = sum(position.size_usd for position in state.positions.values())
        return_style = "green" if state.total_return_pct >= 0 else "red"
        mode_label = "PAPER" if state.mode == TradeMode.PAPER else "LIVE"

        header = Text()
        header.append("TIMEFM TRADER", style="bold cyan")
        header.append(" | ")
        header.append(mode_label, style="bold yellow")
        header.append(" | ")
        header.append(_fmt_usd(portfolio_value), style=f"bold {return_style}")
        header.append(f" ({_fmt_pct(state.total_return_pct)})", style=return_style)
        header.append(f" | Invested: {_fmt_usd(invested)}")
        header.append(f" | Free: {_fmt_usd(state.balance_usd)}")
        header.append(f" | Fees: {_fmt_usd(state.total_fees_paid)}")
        header.append(f" | Positions: {len(state.positions)}")

        positions_panel = Panel(
            self._build_positions_table(state),
            title="Open Positions",
            border_style="blue",
        )

        insights_panel = Panel(
            self._build_insights(state.active_insights),
            title="Active Insights",
            border_style="magenta",
        )
        stats_panel = Panel(
            self._build_stats(state),
            title="Stats",
            border_style="cyan",
        )

        footer = Text()
        if state.paused:
            footer.append("PAUSED", style="bold white on red")
            footer.append(" | ")
        last_update = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        footer.append(f"Last update: {last_update}", style="dim")

        return Group(
            Panel(header, border_style=return_style),
            positions_panel,
            Columns([insights_panel, stats_panel], equal=True, expand=True),
            Panel(footer, border_style="white"),
        )

    async def run(self, state_provider: Callable[[], BotState], refresh_seconds: float = 5.0) -> None:
        with Live(self.render(state_provider()), refresh_per_second=4, screen=True) as live:
            while True:
                live.update(self.render(state_provider()))
                await asyncio.sleep(refresh_seconds)

    def _build_positions_table(self, state: BotState) -> Any:
        if not state.positions:
            return Align.center("No open positions", vertical="middle")

        table = Table(expand=True)
        for column in ("COIN", "ENTRY", "NOW", "FORECAST", "CONF", "TIMEFRAME", "P&L%", "SIZE"):
            table.add_column(column, justify="right" if column not in {"COIN", "TIMEFRAME"} else "left")

        for symbol, position in sorted(state.positions.items()):
            forecast = getattr(position, "forecast", None)
            forecast_price = getattr(forecast, "forecast_prices", [position.current_price or position.entry_price])
            forecast_last = forecast_price[-1] if forecast_price else position.current_price
            confidence = getattr(forecast, "confidence_score", 0.0)
            timeframe = getattr(forecast, "timeframe", "-")
            history = getattr(position, "price_history", None)
            pnl_style = "green" if position.unrealized_pnl_pct >= 0 else "red"
            coin_cell = f"{symbol} {_sparkline(history)}"

            table.add_row(
                coin_cell,
                f"{position.entry_price:,.4f}",
                f"{position.current_price:,.4f}",
                f"{forecast_last:,.4f}",
                f"{confidence:.2f}",
                str(timeframe),
                f"[{pnl_style}]{position.unrealized_pnl_pct * 100:+.2f}%[/]",
                _fmt_usd(position.size_usd),
            )

        return table

    def _build_insights(self, insights: list[Insight]) -> Any:
        active = [insight for insight in insights if not insight.is_expired()]
        if not active:
            return Align.center("No active insights", vertical="middle")

        table = Table(show_header=True, expand=True, box=None)
        table.add_column("Coin")
        table.add_column("Direction")
        table.add_column("Strength", justify="right")
        table.add_column("Reason")
        table.add_column("Expires", justify="right")

        for insight in active:
            direction = _insight_direction(insight.direction)
            style = "green" if direction == "bullish" else "red" if direction == "bearish" else "yellow"
            table.add_row(
                insight.coin,
                f"[{style}]{direction}[/{style}]",
                f"{insight.strength:.2f}",
                insight.reason,
                f"expires {_insight_expiry(insight)}",
            )

        return table

    def _build_stats(self, state: BotState) -> Table:
        table = Table(show_header=False, expand=True, box=None)
        table.add_column("Metric")
        table.add_column("Value", justify="right")

        last_scan = state.last_scan_time.strftime("%Y-%m-%d %H:%M:%S UTC") if state.last_scan_time else "Never"
        table.add_row("Last scan", last_scan)
        table.add_row("Coins scanned", str(state.coins_scanned))
        table.add_row("Signals found", str(state.signals_found))
        table.add_row("Total trades", str(len(state.trade_history)))
        table.add_row("Realized PnL", _fmt_usd(state.realized_pnl))
        table.add_row("Win rate", _fmt_pct(_trade_win_rate(state.trade_history)))
        return table
