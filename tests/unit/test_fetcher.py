from __future__ import annotations

from unittest.mock import AsyncMock

import ccxt.async_support as ccxt
import pandas as pd
import pytest

from src.timefm_trader.fetcher import (
    get_all_usdt_pairs,
    get_current_prices,
    get_ohlcv,
)


@pytest.mark.asyncio
async def test_get_all_usdt_pairs():
    exchange = AsyncMock()
    exchange.load_markets.return_value = {
        "BTC/USDT": {
            "quote": "USDT",
            "spot": True,
            "active": True,
            "quoteVolume": 1000,
        },
        "ETH/USDT": {
            "quote": "USDT",
            "spot": True,
            "active": True,
            "quoteVolume": 2000,
        },
        "BTC/BTC": {
            "quote": "BTC",
            "spot": True,
            "active": True,
            "quoteVolume": 500,
        },
        "XYZ/USDT": {
            "quote": "USDT",
            "spot": False,
            "active": True,
            "quoteVolume": 100,
        },
    }

    result = await get_all_usdt_pairs(exchange)

    assert result == ["ETH/USDT", "BTC/USDT"]


@pytest.mark.asyncio
async def test_get_ohlcv_happy_path():
    exchange = AsyncMock()
    exchange.fetch_ohlcv.return_value = [
        [1609459200000, 29000, 29500, 28800, 29200, 1500.0]
    ]

    result = await get_ohlcv(exchange, "BTC/USDT", "1h", limit=1)

    assert list(result.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(result) == 1
    assert isinstance(result.loc[0, "timestamp"], pd.Timestamp)


@pytest.mark.asyncio
async def test_get_ohlcv_on_ccxt_exception():
    exchange = AsyncMock()
    exchange.fetch_ohlcv.side_effect = ccxt.NetworkError("network issue")

    result = await get_ohlcv(exchange, "BTC/USDT", "1h", limit=1)

    assert result.empty


@pytest.mark.asyncio
async def test_get_current_prices():
    exchange = AsyncMock()
    exchange.fetch_tickers.return_value = {"BTC/USDT": {"last": 30000.0}}

    result = await get_current_prices(exchange, ["BTC/USDT"])

    assert result == {"BTC/USDT": 30000.0}
