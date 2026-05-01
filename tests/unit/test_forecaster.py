import importlib
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from src.timefm_trader.models import Forecast


def _make_ohlcv(rows: int, last_price: float = 60000.0) -> pd.DataFrame:
    close = np.linspace(last_price - (rows - 1), last_price, rows)
    return pd.DataFrame({"close": close})


def _import_forecaster_class():
    sys.modules.pop("src.timefm_trader.forecaster", None)
    with patch.dict("sys.modules", {"timesfm": MagicMock()}):
        module = importlib.import_module("src.timefm_trader.forecaster")
    return module.TimeFMForecaster


def test_forecast_timeframe_returns_correct_forecast():
    TimeFMForecaster = _import_forecaster_class()
    forecaster = TimeFMForecaster()
    forecaster._model = MagicMock()

    point_forecasts = np.array([[62000.0] * 64])
    quantile_forecasts = np.zeros((1, 64, 9))
    quantile_forecasts[0, :, 0] = 59000.0
    quantile_forecasts[0, :, -1] = 63000.0
    forecaster._model.forecast.return_value = (point_forecasts, quantile_forecasts)

    df = _make_ohlcv(100, last_price=60000.0)
    result = forecaster.forecast_timeframe(df, "1h", "BTCUSDT")

    assert result is not None
    assert result.symbol == "BTCUSDT"
    assert result.timeframe == "1h"
    assert len(result.forecast_prices) == 64
    assert result.last_price == 60000.0


def test_forecast_timeframe_returns_none_when_df_too_short():
    TimeFMForecaster = _import_forecaster_class()
    forecaster = TimeFMForecaster()

    result = forecaster.forecast_timeframe(_make_ohlcv(31), "1h", "BTCUSDT")

    assert result is None


def test_forecast_timeframe_returns_none_when_penalized_confidence_non_positive():
    TimeFMForecaster = _import_forecaster_class()
    forecaster = TimeFMForecaster()
    forecaster._model = MagicMock()

    point_forecasts = np.array([[60000.0] * 64])
    quantile_forecasts = np.zeros((1, 64, 9))
    quantile_forecasts[0, :, 0] = 59000.0
    quantile_forecasts[0, :, -1] = 63000.0
    forecaster._model.forecast.return_value = (point_forecasts, quantile_forecasts)

    result = forecaster.forecast_timeframe(_make_ohlcv(100), "1h", "BTCUSDT")

    assert result is None


def test_select_best_timeframe_returns_highest_absolute_confidence():
    TimeFMForecaster = _import_forecaster_class()
    forecaster = TimeFMForecaster()

    forecast_a = Forecast("BTCUSDT", "1h", [1.0], [0.9], [1.1], 0.3, 1.0, 0.01)
    forecast_b = Forecast("BTCUSDT", "4h", [1.0], [0.9], [1.1], 0.7, 1.0, 0.02)
    forecast_c = Forecast("BTCUSDT", "1d", [1.0], [0.9], [1.1], 0.5, 1.0, 0.03)

    result = forecaster.select_best_timeframe(
        {"1h": forecast_a, "4h": forecast_b, "1d": forecast_c}
    )

    assert result is not None
    assert result.confidence_score == 0.7


def test_select_best_timeframe_returns_none_when_all_inputs_are_none():
    TimeFMForecaster = _import_forecaster_class()
    forecaster = TimeFMForecaster()

    result = forecaster.select_best_timeframe({"1h": None, "4h": None})

    assert result is None
