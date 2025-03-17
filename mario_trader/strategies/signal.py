"""
Trading signal generation
"""
import numpy as np
from mario_trader.indicators.technical import calculate_indicators
from mario_trader.utils.logger import logger
from mario_trader.strategies.sma_crossover_strategy import generate_sma_crossover_signal


def generate_signal(df, currency_pair):
    """
    Generate trading signals based on technical indicators
    
    Args:
        df: DataFrame with price data
        currency_pair: Currency pair symbol
        
    Returns:
        Tuple of (signal, stop_loss, current_market_price)
        signal: 1 for buy, -1 for sell, 0 for no action
    """
    # Use the SMA crossover strategy
    return generate_sma_crossover_signal(df, currency_pair) 