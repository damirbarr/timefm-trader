from __future__ import annotations

import pandas as pd

from src.timefm_trader.indicators import add_indicators


def test_add_indicators_adds_required_columns(sample_ohlcv):
    df = add_indicators(sample_ohlcv.copy())

    expected_columns = {
        "ma20",
        "ma50",
        "ma200",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "rsi",
        "macd",
        "macd_signal",
        "macd_hist",
        "volume_ma20",
    }

    assert expected_columns.issubset(df.columns)


def test_ma20_last_value_matches_rolling_mean(sample_ohlcv):
    df = add_indicators(sample_ohlcv.copy())

    expected = df["close"].rolling(20).mean().iloc[-1]

    assert df["ma20"].iloc[-1] == expected


def test_rsi_values_are_in_range(sample_ohlcv):
    df = add_indicators(sample_ohlcv.copy())

    rsi = df["rsi"].dropna()

    assert not rsi.empty
    assert ((rsi >= 0) & (rsi <= 100)).all()


def test_bollinger_band_ordering(sample_ohlcv):
    df = add_indicators(sample_ohlcv.copy())

    valid_rows = df.dropna(subset=["bb_upper", "bb_middle", "bb_lower"])

    assert not valid_rows.empty
    assert (valid_rows["bb_upper"] > valid_rows["bb_middle"]).all()
    assert (valid_rows["bb_middle"] > valid_rows["bb_lower"]).all()


def test_macd_hist_equals_macd_minus_signal(sample_ohlcv):
    df = add_indicators(sample_ohlcv.copy())

    valid_rows = df.dropna(subset=["macd", "macd_signal", "macd_hist"])

    pd.testing.assert_series_equal(
        valid_rows["macd_hist"],
        valid_rows["macd"] - valid_rows["macd_signal"],
        check_names=False,
    )


def test_short_dataframe_add_indicators_without_crash(sample_ohlcv):
    df = add_indicators(sample_ohlcv.head(10).copy())

    assert pd.isna(df["ma200"].iloc[-1])
