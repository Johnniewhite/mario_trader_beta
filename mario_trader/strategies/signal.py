"""
Trading signal generation
"""
import numpy as np
from mario_trader.indicators.technical import calculate_indicators


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
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    stop_loss = None
    current_market_price = latest['close']
    
    # Add candle direction (1 for bullish, -1 for bearish)
    df['direction'] = np.sign(df['close'] - df['open'])
    
    # Calculate candle size (absolute difference between open and close)
    df['candle_size'] = abs(df['close'] - df['open'])
    
    # Calculate high-low range for each candle
    df['candle_range'] = df['high'] - df['low']
    
    # BUY SIGNAL CONDITIONS
    if latest['close'] > latest['200_SMA'] and abs(latest['21_SMA'] - latest['50_SMA']) > 0.0001:
        # Check for 3 consecutive sell candles
        consecutive_sells = (df['direction'].iloc[-5] == -1) and \
                           (df['direction'].iloc[-4] == -1) and \
                           (df['direction'].iloc[-3] == -1)
        
        # Check for engulfing buy candle
        current_candle = df.iloc[-2]  # The potential engulfing candle
        
        if consecutive_sells and df['direction'].iloc[-2] == 1:  # Current candle is bullish
            # Calculate the total range of the 3 previous candles
            three_candle_range = df['high'].iloc[-5:-2].max() - df['low'].iloc[-5:-2].min()
            
            # Check if current candle engulfs at least 50% of the 3 previous candles
            current_candle_range = current_candle['high'] - current_candle['low']
            engulfing_percentage = current_candle_range / three_candle_range if three_candle_range > 0 else 0
            
            # Check if RSI is above 50
            if engulfing_percentage >= 0.5 and latest['RSI'] > 50:
                # Generate buy signal
                stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
                stop_loss = current_market_price - stop_loss_distance
                
                # Log additional information for debugging
                from mario_trader.utils.logger import logger
                logger.info(f"BUY SIGNAL GENERATED: {currency_pair}")
                logger.info(f"3 consecutive sells: {consecutive_sells}")
                logger.info(f"Engulfing percentage: {engulfing_percentage:.2f}")
                logger.info(f"RSI: {latest['RSI']:.2f}")
                
                return 1, stop_loss, current_market_price
    
    # SELL SIGNAL CONDITIONS
    if latest['close'] < latest['200_SMA'] and abs(latest['21_SMA'] - latest['50_SMA']) > 0.0001:
        # Check for 3 consecutive buy candles
        consecutive_buys = (df['direction'].iloc[-5] == 1) and \
                          (df['direction'].iloc[-4] == 1) and \
                          (df['direction'].iloc[-3] == 1)
        
        # Check for engulfing sell candle
        current_candle = df.iloc[-2]  # The potential engulfing candle
        
        if consecutive_buys and df['direction'].iloc[-2] == -1:  # Current candle is bearish
            # Calculate the total range of the 3 previous candles
            three_candle_range = df['high'].iloc[-5:-2].max() - df['low'].iloc[-5:-2].min()
            
            # Check if current candle engulfs at least 50% of the 3 previous candles
            current_candle_range = current_candle['high'] - current_candle['low']
            engulfing_percentage = current_candle_range / three_candle_range if three_candle_range > 0 else 0
            
            # Check if RSI is below 50
            if engulfing_percentage >= 0.5 and latest['RSI'] < 50:
                # Generate sell signal
                stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
                stop_loss = current_market_price + stop_loss_distance
                
                # Log additional information for debugging
                from mario_trader.utils.logger import logger
                logger.info(f"SELL SIGNAL GENERATED: {currency_pair}")
                logger.info(f"3 consecutive buys: {consecutive_buys}")
                logger.info(f"Engulfing percentage: {engulfing_percentage:.2f}")
                logger.info(f"RSI: {latest['RSI']:.2f}")
                
                return -1, stop_loss, current_market_price
    
    return 0, 0, current_market_price 