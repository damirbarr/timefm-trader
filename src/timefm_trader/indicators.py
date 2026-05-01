"""Technical indicators implemented with pandas and numpy."""
from __future__ import annotations

import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add common trend, volatility, and momentum indicators in-place."""
    close = df["close"]
    volume = df["volume"]

    df["ma20"] = close.rolling(20).mean()
    df["ma50"] = close.rolling(50).mean()
    df["ma200"] = close.rolling(200).mean()

    rolling_std20 = close.rolling(20).std()
    df["bb_middle"] = df["ma20"]
    df["bb_upper"] = df["ma20"] + 2 * rolling_std20
    df["bb_lower"] = df["ma20"] - 2 * rolling_std20

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - 100 / (1 + rs)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    df["volume_ma20"] = volume.rolling(20).mean()
    return df
