"""
SMA Crossover Strategy with RSI Confirmation

This strategy generates trading signals based on the following conditions:

For a BUY signal:
- The closing price must be above the 200-day SMA
- There must be sufficient separation between the 21-day and 50-day SMAs (except if price recently crossed the 200 SMA)
- There must be 3 or more consecutive sell candles and then a buy candle
- RSI must be above 50

For a SELL signal:
- The closing price must be above the 200-day SMA (same as buy)
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
    Check for consecutive candles in the specified direction followed by opposite direction
    
    Args:
        df: DataFrame with price data
        direction: 1 for checking buy candles followed by sell, -1 for checking sell candles followed by buy
        count: Number of consecutive candles required for a signal
        
    Returns:
        True if the pattern is detected, False otherwise
    """
    # Add candle direction (1 for bullish, -1 for bearish) if not already present
    if 'direction' not in df.columns:
        df['direction'] = np.sign(df['close'] - df['open'])
    
    if len(df) < count + 1:
        # Not enough data
        return False
    
    # Get the current candle direction (most recent)
    current_direction = df['direction'].iloc[-1]
    
    # For a buy signal (direction=-1), we need:
    # 1. Current candle is bullish (direction=1)
    # 2. Previous 'count' candles are all bearish (direction=-1)
    if direction == -1 and current_direction == 1:
        # Check if previous 'count' candles are all bearish
        for i in range(2, count+2):  # Starting from 2nd most recent candle
            if i > len(df) or df['direction'].iloc[-i] != -1:
                return False
        return True
    
    # For a sell signal (direction=1), we need:
    # 1. Current candle is bearish (direction=-1)
    # 2. Previous 'count' candles are all bullish (direction=1)
    elif direction == 1 and current_direction == -1:
        # Check if previous 'count' candles are all bullish
        for i in range(2, count+2):  # Starting from 2nd most recent candle
            if i > len(df) or df['direction'].iloc[-i] != 1:
                return False
        return True
    
    return False


def log_candle_pattern(df, currency_pair):
    """
    Log the recent candle pattern for debugging
    
    Args:
        df: DataFrame with price data
        currency_pair: Currency pair symbol
    """
    if 'direction' not in df.columns:
        df['direction'] = np.sign(df['close'] - df['open'])
    
    # Create a visual representation of recent candles
    # + for bullish (buy) candles, - for bearish (sell) candles
    pattern = ""
    for i in range(10, 0, -1):
        if i >= len(df):
            continue
        
        if df['direction'].iloc[-i] == 1:
            pattern += "+"
        else:
            pattern += "-"
    
    # The rightmost character represents the most recent candle
    logger.debug(f"{currency_pair} - Recent candle pattern (right=newest): {pattern}")
    
    # Check and log specific patterns
    # Modified to match our actual requirements better
    if pattern.endswith("---+"):
        logger.debug(f"{currency_pair} - Detected 3 sell candles followed by a buy candle")
    if pattern.endswith("+++-"):
        logger.debug(f"{currency_pair} - Detected 3 buy candles followed by a sell candle")


def generate_sma_crossover_signal(df, currency_pair, debug_mode=False):
    """
    Generate trading signals based on SMA crossover strategy with RSI confirmation
    
    Args:
        df: DataFrame with price data
        currency_pair: Currency pair symbol
        debug_mode: If True, relaxes some conditions for testing purposes
        
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
    
    # Log candle pattern
    log_candle_pattern(df, currency_pair)
    
    # Check for consecutive candles pattern
    # For a buy signal: 3+ consecutive SELL candles followed by a BUY candle
    buy_pattern = check_consecutive_candles(df, -1, 3)
    
    # For a sell signal: 3+ consecutive BUY candles followed by a SELL candle
    sell_pattern = check_consecutive_candles(df, 1, 3)
    
    # Current candle direction
    current_candle_is_buy = df['direction'].iloc[-1] == 1
    current_candle_is_sell = df['direction'].iloc[-1] == -1
    
    # Log consecutive candle checks
    logger.debug(f"{currency_pair} - Buy pattern (3+ sell candles followed by buy): {buy_pattern}")
    logger.debug(f"{currency_pair} - Sell pattern (3+ buy candles followed by sell): {sell_pattern}")
    logger.debug(f"{currency_pair} - Current candle is buy: {current_candle_is_buy}")
    logger.debug(f"{currency_pair} - Current candle is sell: {current_candle_is_sell}")
    
    # BUY SIGNAL CONDITIONS
    # The closing price must be above the 200-day SMA
    price_above_200sma = latest['close'] > latest['200_SMA']
    # RSI must be above 50
    rsi_above_50 = latest['RSI'] > 50
    
    # Log individual conditions for BUY signal
    logger.debug(f"{currency_pair} - Price > 200 SMA: {price_above_200sma}")
    logger.debug(f"{currency_pair} - Sufficient SMA separation: {sufficient_separation}")
    logger.debug(f"{currency_pair} - RSI > 50: {rsi_above_50}")
    
    # In debug mode, we'll relax some conditions to force signals for testing
    if debug_mode:
        # If price and RSI conditions are met but other conditions aren't,
        # still generate a buy signal for testing
        if price_above_200sma and rsi_above_50:
            logger.info(f"DEBUG MODE: Forcing BUY signal for {currency_pair} for testing")
            stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
            stop_loss = current_market_price - stop_loss_distance
            return 1, stop_loss, current_market_price
    
    # Check for BUY signal with all conditions
    if price_above_200sma and sufficient_separation and buy_pattern and rsi_above_50:
        # Calculate stop loss based on recent swing low or a percentage of price
        stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
        stop_loss = current_market_price - stop_loss_distance
        
        # Log signal information
        logger.info(f"BUY SIGNAL GENERATED: {currency_pair}")
        logger.info(f"Buy pattern found: {buy_pattern}")
        logger.info(f"Current candle is buy: {current_candle_is_buy}")
        logger.info(f"RSI > 50: {latest['RSI']:.2f}")
        logger.info(f"Price > 200 SMA: {latest['close']:.5f} > {latest['200_SMA']:.5f}")
        
        return 1, stop_loss, current_market_price
    
    # SELL SIGNAL CONDITIONS
    # The closing price must be above the 200-day SMA (same as buy)
    price_above_200sma = latest['close'] > latest['200_SMA']
    # RSI must be below 50
    rsi_below_50 = latest['RSI'] < 50
    
    # Log individual conditions for SELL signal
    logger.debug(f"{currency_pair} - Price > 200 SMA: {price_above_200sma}")
    logger.debug(f"{currency_pair} - Sufficient SMA separation: {sufficient_separation}")
    logger.debug(f"{currency_pair} - RSI < 50: {rsi_below_50}")
    
    # In debug mode, we'll relax some conditions to force signals for testing
    if debug_mode:
        # If price and RSI conditions are met but other conditions aren't,
        # still generate a sell signal for testing
        if price_above_200sma and rsi_below_50:
            logger.info(f"DEBUG MODE: Forcing SELL signal for {currency_pair} for testing")
            stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
            stop_loss = current_market_price + stop_loss_distance
            return -1, stop_loss, current_market_price
    
    # Check for SELL signal with all conditions
    if price_above_200sma and sufficient_separation and sell_pattern and rsi_below_50:
        # Calculate stop loss based on recent swing high or a percentage of price
        stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
        stop_loss = current_market_price + stop_loss_distance
        
        # Log signal information
        logger.info(f"SELL SIGNAL GENERATED: {currency_pair}")
        logger.info(f"Sell pattern found: {sell_pattern}")
        logger.info(f"Current candle is sell: {current_candle_is_sell}")
        logger.info(f"RSI < 50: {latest['RSI']:.2f}")
        logger.info(f"Price > 200 SMA: {latest['close']:.5f} > {latest['200_SMA']:.5f}")
        
        return -1, stop_loss, current_market_price
    
    # If any conditions were close but not met, log them for debugging
    if price_above_200sma and sufficient_separation and current_candle_is_buy and not rsi_above_50:
        logger.debug(f"{currency_pair} - Almost BUY signal but RSI not > 50: {latest['RSI']:.2f}")
    
    if price_above_200sma and sufficient_separation and rsi_above_50 and not buy_pattern:
        logger.debug(f"{currency_pair} - Almost BUY signal but missing correct candle pattern")
    
    if price_above_200sma and sufficient_separation and current_candle_is_sell and not rsi_below_50:
        logger.debug(f"{currency_pair} - Almost SELL signal but RSI not < 50: {latest['RSI']:.2f}")
    
    if price_above_200sma and sufficient_separation and rsi_below_50 and not sell_pattern:
        logger.debug(f"{currency_pair} - Almost SELL signal but missing correct candle pattern")
    
    return 0, 0, current_market_price 