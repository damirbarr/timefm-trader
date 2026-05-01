"""All configuration in one place. Override via environment variables or .env file."""
import os
from dotenv import load_dotenv

load_dotenv()

# Trading mode
PAPER_MODE: bool = os.getenv("PAPER_MODE", "true").lower() == "true"
INITIAL_BALANCE: float = float(os.getenv("INITIAL_BALANCE", "10000"))

# Binance fees
BINANCE_FEE_PCT: float = float(os.getenv("BINANCE_FEE_PCT", "0.001"))   # 0.1% per side
BNB_DISCOUNT: bool = os.getenv("BNB_DISCOUNT", "false").lower() == "true"
BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET: str = os.getenv("BINANCE_SECRET", "")

# Risk management
STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "-0.04"))        # -4%
MIN_CONFIDENCE: float = float(os.getenv("MIN_CONFIDENCE", "0.3"))
RESERVE_PCT: float = float(os.getenv("RESERVE_PCT", "0.10"))             # 10% always free
MAX_POSITION_PCT: float = float(os.getenv("MAX_POSITION_PCT", "0.30"))   # 30% max per coin
MIN_TRADE_USD: float = float(os.getenv("MIN_TRADE_USD", "10"))

# Forecasting
TIMEFRAMES: list[str] = ["1m", "5m", "15m", "1h", "4h", "1d"]
OHLCV_LIMIT: int = int(os.getenv("OHLCV_LIMIT", "512"))                  # candles per timeframe
FORECAST_HORIZON: int = int(os.getenv("FORECAST_HORIZON", "64"))         # steps ahead

# Bot loop
SCAN_INTERVAL_S: int = int(os.getenv("SCAN_INTERVAL_S", "60"))
STOP_LOSS_CHECK_S: int = int(os.getenv("STOP_LOSS_CHECK_S", "30"))
DASHBOARD_REFRESH_S: float = float(os.getenv("DASHBOARD_REFRESH_S", "5"))

# Web server
WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT: int = int(os.getenv("WEB_PORT", "8080"))
CONTROL_API_TOKEN: str = os.getenv("CONTROL_API_TOKEN", "change-me-in-production")

# Effective fee after BNB discount
def effective_fee() -> float:
    if BNB_DISCOUNT:
        return BINANCE_FEE_PCT * 0.75
    return BINANCE_FEE_PCT

def round_trip_fee() -> float:
    return effective_fee() * 2
