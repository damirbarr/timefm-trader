"""CLI entrypoint for running the trading bot."""
from __future__ import annotations

import asyncio
from contextlib import suppress

import click
import uvicorn
from fastapi import FastAPI

from src.timefm_trader import config
from src.timefm_trader.bot import TradingBot
from src.timefm_trader.dashboard import TerminalDashboard

try:
    from src.timefm_trader.web import app as web_app
except ImportError:
    web_app = FastAPI(title="TimeFM Trader")


def _apply_mode_override(paper: bool | None, live: bool | None) -> None:
    if paper and live:
        raise click.UsageError("Choose only one of --paper or --live.")
    if paper:
        config.PAPER_MODE = True
    if live:
        config.PAPER_MODE = False


async def _run_terminal(bot: TradingBot) -> None:
    dashboard = TerminalDashboard()
    await asyncio.gather(
        bot.run(),
        dashboard.run(bot.get_state, refresh_seconds=config.DASHBOARD_REFRESH_S),
    )


async def _run_web(bot: TradingBot) -> None:
    web_app.state.state_provider = bot.get_state
    web_app.state.command_handler = bot.handle_command

    server = uvicorn.Server(
        uvicorn.Config(
            web_app,
            host=config.WEB_HOST,
            port=config.WEB_PORT,
            log_level="info",
        )
    )
    bot_task = asyncio.create_task(bot.run())
    try:
        await server.serve()
    finally:
        bot_task.cancel()
        with suppress(asyncio.CancelledError):
            await bot_task


async def _run_both(bot: TradingBot) -> None:
    dashboard = TerminalDashboard()
    web_app.state.state_provider = bot.get_state
    web_app.state.command_handler = bot.handle_command
    server = uvicorn.Server(
        uvicorn.Config(
            web_app,
            host=config.WEB_HOST,
            port=config.WEB_PORT,
            log_level="info",
        )
    )

    tasks = [
        asyncio.create_task(bot.run()),
        asyncio.create_task(dashboard.run(bot.get_state, refresh_seconds=config.DASHBOARD_REFRESH_S)),
        asyncio.create_task(server.serve()),
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


@click.group()
@click.option("--paper", is_flag=True, default=False, help="Run in paper mode.")
@click.option("--live", is_flag=True, default=False, help="Run in live mode.")
@click.pass_context
def cli(ctx: click.Context, paper: bool, live: bool) -> None:
    _apply_mode_override(paper, live)
    ctx.ensure_object(dict)


@cli.command()
def run() -> None:
    bot = TradingBot()
    try:
        asyncio.run(_run_terminal(bot))
    except KeyboardInterrupt:
        pass


@cli.command()
def web() -> None:
    bot = TradingBot()
    try:
        asyncio.run(_run_web(bot))
    except KeyboardInterrupt:
        pass


@cli.command()
def both() -> None:
    bot = TradingBot()
    try:
        asyncio.run(_run_both(bot))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
