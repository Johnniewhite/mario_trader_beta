"""
SMA Crossover Strategy with RSI Confirmation

This strategy generates trading signals based on the following conditions:

For a BUY signal:
- The closing price must be above the 200-day SMA
- There must be sufficient separation between the 21-day and 50-day SMAs (except if price recently crossed the 200 SMA)
- There must be 3 or more consecutive sell candles and then a buy candle
- RSI must be above 50

For a SELL signal:
- The closing price must be below the 200-day SMA
- There must be sufficient separation between the 21-day and 50-day SMAs (except if price recently crossed the 200 SMA)
- There must be 3 or more consecutive buy candles and a sell candle
- RSI must be below 50
"""
import numpy as np
from mario_trader.indicators.technical import calculate_indicators
from mario_trader.utils.logger import logger


def check_price_crossed_200sma_recently(df, lookback=10):
    """
    Check if price crossed the 200 SMA recently
    
    Args:
        df: DataFrame with price data
        lookback: Number of candles to look back
        
    Returns:
        True if price crossed 200 SMA recently, False otherwise
    """
    for i in range(1, min(lookback, len(df))):
        prev_candle = df.iloc[-i-1]
        curr_candle = df.iloc[-i]
        
        # Check if price crossed above 200 SMA
        if (prev_candle['close'] < prev_candle['200_SMA'] and 
            curr_candle['close'] > curr_candle['200_SMA']):
            return True
            
        # Check if price crossed below 200 SMA
        if (prev_candle['close'] > prev_candle['200_SMA'] and 
            curr_candle['close'] < curr_candle['200_SMA']):
            return True
            
    return False


def check_consecutive_candles(df, direction, count=3):
    """
    Check for consecutive candles in the specified direction
    
    Args:
        df: DataFrame with price data
        direction: 1 for buy candles, -1 for sell candles
        count: Number of consecutive candles to check for
        
    Returns:
        True if there are count consecutive candles in the specified direction, False otherwise
    """
    # Add candle direction (1 for bullish, -1 for bearish)
    if 'direction' not in df.columns:
        df['direction'] = np.sign(df['close'] - df['open'])
    
    # Check the last 'count' candles (excluding the most recent one)
    for i in range(2, 2 + count):
        if i >= len(df) or df['direction'].iloc[-i] != direction:
            return False
    
    return True


def generate_sma_crossover_signal(df, currency_pair):
    """
    Generate trading signals based on SMA crossover strategy with RSI confirmation
    
    Args:
        df: DataFrame with price data
        currency_pair: Currency pair symbol
        
    Returns:
        Tuple of (signal, stop_loss, current_market_price)
        signal: 1 for buy, -1 for sell, 0 for no action
    """
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    current_market_price = latest['close']
    
    # Add candle direction (1 for bullish, -1 for bearish)
    df['direction'] = np.sign(df['close'] - df['open'])
    
    # Check if price recently crossed 200 SMA
    recently_crossed_200sma = check_price_crossed_200sma_recently(df)
    
    # Check for sufficient separation between 21 and 50 SMAs
    sma_separation = abs(latest['21_SMA'] - latest['50_SMA'])
    sufficient_separation = sma_separation > 0.0001 or recently_crossed_200sma
    
    # Log market conditions
    logger.debug(f"{currency_pair} - Price: {latest['close']:.5f}, 200 SMA: {latest['200_SMA']:.5f}")
    logger.debug(f"{currency_pair} - 21 SMA: {latest['21_SMA']:.5f}, 50 SMA: {latest['50_SMA']:.5f}")
    logger.debug(f"{currency_pair} - RSI: {latest['RSI']:.2f}")
    logger.debug(f"{currency_pair} - SMA Separation: {sma_separation:.5f}")
    logger.debug(f"{currency_pair} - Recently crossed 200 SMA: {recently_crossed_200sma}")
    
    # BUY SIGNAL CONDITIONS
    if latest['close'] > latest['200_SMA'] and sufficient_separation:
        # Check for 3 consecutive sell candles followed by a buy candle
        consecutive_sells = check_consecutive_candles(df, -1, 3)
        current_candle_is_buy = df['direction'].iloc[-1] == 1
        
        if consecutive_sells and current_candle_is_buy and latest['RSI'] > 50:
            # Calculate stop loss based on recent swing low or a percentage of price
            stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
            stop_loss = current_market_price - stop_loss_distance
            
            # Log signal information
            logger.info(f"BUY SIGNAL GENERATED: {currency_pair}")
            logger.info(f"3+ consecutive sell candles: {consecutive_sells}")
            logger.info(f"Current candle is buy: {current_candle_is_buy}")
            logger.info(f"RSI > 50: {latest['RSI']:.2f}")
            logger.info(f"Price > 200 SMA: {latest['close']:.5f} > {latest['200_SMA']:.5f}")
            
            return 1, stop_loss, current_market_price
    
    # SELL SIGNAL CONDITIONS
    if latest['close'] < latest['200_SMA'] and sufficient_separation:
        # Check for 3 consecutive buy candles followed by a sell candle
        consecutive_buys = check_consecutive_candles(df, 1, 3)
        current_candle_is_sell = df['direction'].iloc[-1] == -1
        
        if consecutive_buys and current_candle_is_sell and latest['RSI'] < 50:
            # Calculate stop loss based on recent swing high or a percentage of price
            stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
            stop_loss = current_market_price + stop_loss_distance
            
            # Log signal information
            logger.info(f"SELL SIGNAL GENERATED: {currency_pair}")
            logger.info(f"3+ consecutive buy candles: {consecutive_buys}")
            logger.info(f"Current candle is sell: {current_candle_is_sell}")
            logger.info(f"RSI < 50: {latest['RSI']:.2f}")
            logger.info(f"Price < 200 SMA: {latest['close']:.5f} < {latest['200_SMA']:.5f}")
            
            return -1, stop_loss, current_market_price
    
    return 0, 0, current_market_price 