"""
Configuration settings for the trading bot
"""

import logging
import os
import sys
import MetaTrader5 as mt5
from pathlib import Path

# Define base directories
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = BASE_DIR / "logs"

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

def get_default_pair():
    """Get the default currency pair"""
    try:
        # Try to read from currency_pair_list.txt
        pairs_file = BASE_DIR / "currency_pair_list.txt"
        if pairs_file.exists():
            with open(pairs_file, "r") as f:
                pairs = [line.strip() for line in f.readlines() if line.strip()]
                if pairs:
                    return pairs[0]
    except Exception as e:
        print(f"Error reading default pair: {e}")
    
    # Default to EURUSD if no pairs found
    return "EURUSD"

# MT5 Connection Settings
MT5_SETTINGS = {
    "login": 81338593,
    "password": "Mario123$$",
    "server": "Exness-MT5Trial10",
}

# Gemini AI Integration Settings
GEMINI_SETTINGS = {
    "enabled": True,  # Set to True to enable Gemini verification
    "api_key": os.environ.get("GEMINI_API_KEY", ""),  # Get API key from environment variable
    "api_endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
    "min_confidence": 0.7,  # Minimum confidence score (0.0-1.0) to approve trades
    "verification": {
        "enabled": True,  # Enable pre-trade verification
        "required": False  # If True, trades won't be placed without Gemini approval
    },
    "monitoring": {
        "enabled": True,  # Enable trade monitoring
        "interval": 15,  # Check interval in minutes
        "required": False  # If True, trades won't be exited without Gemini recommendation
    }
}

# Trading settings
TRADING_SETTINGS = {
    "default_currency_pair": get_default_pair(),
    "risk_percentage": 0.02,  # 2% risk per trade
    "timeframe": mt5.TIMEFRAME_M5,  # 1-hour timeframe
    "candles_count": 200,  # Number of candles to fetch
    "rsi_period": 14,  # RSI indicator period
    "rsi_overbought": 70,  # RSI overbought level
    "rsi_oversold": 30,  # RSI oversold level
    "sma_period_fast": 21,  # Fast SMA period
    "sma_period_slow": 50,  # Slow SMA period
    "sma_period_trend": 200,  # Trend SMA period
    "min_sma_separation": 0.0005,  # Minimum separation between SMAs
    "debug_mode": False,  # Debug mode (enables more detailed logging and relaxes some conditions)
    "force_buy": False,  # Force a buy signal (for testing)
    "force_sell": False,  # Force a sell signal (for testing)
    "multi_pair_interval": 60,  # Seconds between trading cycles in multi-pair mode
    "profit_taking": {
        "enable_rsi_divergence": True,  # Enable RSI divergence detection for profit taking
        "enable_profit_target": True,  # Enable profit target based on entry to 21 SMA distance
        "profit_factor": 2.0,  # Profit target multiplier (2x the distance to 21 SMA)
    },
    "contingency_plan": {
        "enabled": True,  # Enable contingency plan for trades
        "stop_multiplier": 2.0,  # Lot size multiplier for stop orders (2x initial lot size)
        "limit_multiplier": 3.0,  # Lot size multiplier for limit orders (3x initial lot size)
        "cascade_multiplier": 1.0,  # Additional multiplier for each cascade level
        "stop_loss_multiplier": 3.0,  # Stop loss multiplier (3x the distance to 21 SMA)
        "take_profit_multiplier": 2.0,  # Take profit multiplier (2x the distance to 21 SMA)
        "max_cascade_levels": 5  # Maximum number of cascade levels
    }
}

# Technical Indicator Settings
INDICATOR_SETTINGS = {
    "rsi_period": 14,
    "sma_periods": [21, 50, 200],
}

# Contingency Trade Settings
CONTINGENCY_TRADE_SETTINGS = {
    "lot_size_multipliers": {
        "v1": 1,
        "v2": 1.33,
        "v3": 1,
        "v4": 1.33,
        "v5": 2.44,
        "v6": 3.99,
        "v7": 4.5,
        "v8": 6.7,
        "v9": 9.5,
        "v10": 11.33,
        "v11": 14.5,
        "v12": 17.53,
        "v13": 19.65,
    }
}

# Order Settings
ORDER_SETTINGS = {
    "magic_number": 234000,
    "deviation": 10,
    "comment": "Mario Trader Bot",
}

# Logging Settings
LOGGING_SETTINGS = {
    "enabled": True,
    "level": "DEBUG",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "log_to_file": True,
    "log_file": "mario_trader.log",
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'mario_trader.log')),
        logging.StreamHandler(sys.stdout)
    ]
)

# Export logger instance
logger = logging.getLogger('mario_trader')

# Set MetaTrader5 logging level
mt5_logger = logging.getLogger('MetaTrader5')
mt5_logger.setLevel(logging.ERROR)  # Only log errors from MetaTrader5 