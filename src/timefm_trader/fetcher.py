"""Market data fetching helpers."""
from __future__ import annotations

import logging

import ccxt.async_support as ccxt
import pandas as pd


logger = logging.getLogger(__name__)


async def get_all_usdt_pairs(exchange) -> list[str]:
    """Return active USDT spot pairs sorted by 24h quote volume."""
    markets = await exchange.load_markets()
    filtered_markets = [
        (symbol, market)
        for symbol, market in markets.items()
        if market.get("quote") == "USDT"
        and market.get("spot") is True
        and market.get("active") is True
    ]
    filtered_markets.sort(
        key=lambda item: item[1].get("quoteVolume") or 0,
        reverse=True,
    )
    return [symbol for symbol, _ in filtered_markets]


async def get_ohlcv(exchange, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Fetch OHLCV candles and normalize them into a dataframe."""
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    except ccxt.BaseError:
        logger.exception("Failed to fetch OHLCV for %s on timeframe %s", symbol, timeframe)
        return pd.DataFrame()

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


async def get_current_prices(exchange, symbols: list[str]) -> dict[str, float]:
    """Fetch current last-traded prices for the provided symbols."""
    try:
        tickers = await exchange.fetch_tickers(symbols)
    except ccxt.BaseError:
        logger.exception("Failed to fetch current prices for %s symbols", len(symbols))
        return {}

    return {
        symbol: ticker["last"]
        for symbol, ticker in tickers.items()
        if ticker.get("last") is not None
    }
