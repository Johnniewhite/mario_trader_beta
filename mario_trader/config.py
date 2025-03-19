"""
Configuration settings for the trading bot
"""

# MT5 Connection Settings
MT5_SETTINGS = {
    "login": 81338593,
    "password": "Mario123$$",
    "server": "Exness-MT5Trial10",
}

# Trading Settings
TRADING_SETTINGS = {
    "default_currency_pair": "EURUSD",
    "risk_percentage": 0.02,  # 2% of account balance
    "timeframe": "M5",  # 5-minute candles
    "candles_count": 200,  # Number of candles to fetch
    "multi_pair_interval": 60,  # Seconds between trading cycles in multi-pair mode
    "max_open_positions": 5,  # Maximum number of open positions at once
    "max_daily_trades": 20,  # Maximum number of trades per day
    "debug_mode": False,  # Set to True to relax strategy conditions for testing
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