import numpy as np
import pandas as pd
import timesfm

from src.timefm_trader import config
from src.timefm_trader.models import Forecast


class TimeFMForecaster:
    def __init__(self):
        self._model = None

    def _load_model(self):
        if self._model is None:
            self._model = timesfm.TimesFm(
                hparams=timesfm.TimesFmHparams(
                    backend="cpu",
                    per_core_batch_size=32,
                    horizon_len=config.FORECAST_HORIZON,
                ),
                checkpoint=timesfm.TimesFmCheckpoint(
                    huggingface_repo_id="google/timesfm-1.0-200m-pytorch"
                ),
            )

    def forecast_timeframe(
        self, df: pd.DataFrame, timeframe: str, symbol: str
    ) -> Forecast | None:
        if len(df) < 32:
            return None

        self._load_model()
        close = df["close"].values.astype(float)
        last_price = float(close[-1])

        point_forecasts, quantile_forecasts = self._model.forecast([close], freq=[0])
        forecast_prices = point_forecasts[0].tolist()
        lower_bound = quantile_forecasts[0, :, 0].tolist()
        upper_bound = quantile_forecasts[0, :, -1].tolist()

        expected_gain_pct = (forecast_prices[-1] - last_price) / last_price
        mean_uncertainty = (
            float(np.mean(np.array(upper_bound) - np.array(lower_bound))) / last_price
        )
        if mean_uncertainty == 0:
            return None

        raw_confidence = abs(expected_gain_pct) / mean_uncertainty
        penalized_confidence = raw_confidence - config.round_trip_fee()
        if penalized_confidence <= 0:
            return None

        return Forecast(
            symbol=symbol,
            timeframe=timeframe,
            forecast_prices=forecast_prices,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            confidence_score=penalized_confidence,
            last_price=last_price,
            expected_gain_pct=expected_gain_pct,
        )

    def select_best_timeframe(
        self, forecasts: dict[str, Forecast | None]
    ) -> Forecast | None:
        valid = {tf: forecast for tf, forecast in forecasts.items() if forecast is not None}
        if not valid:
            return None
        return max(valid.values(), key=lambda forecast: abs(forecast.confidence_score))
