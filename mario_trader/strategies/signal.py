"""
Trading signal generation
"""
import numpy as np
from mario_trader.indicators.technical import calculate_indicators
from mario_trader.utils.logger import logger


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
    
    # Debug information
    logger.debug(f"{currency_pair} - Price: {latest['close']}, 200 SMA: {latest['200_SMA']}")
    logger.debug(f"{currency_pair} - 21 SMA: {latest['21_SMA']}, 50 SMA: {latest['50_SMA']}")
    logger.debug(f"{currency_pair} - RSI: {latest['RSI']}")
    
    # BUY SIGNAL CONDITIONS
    if latest['close'] > latest['200_SMA'] and abs(latest['21_SMA'] - latest['50_SMA']) > 0.0001:
        # Check for 3 consecutive sell candles followed by a buy candle
        consecutive_sells = (df['direction'].iloc[-4] == -1) and \
                           (df['direction'].iloc[-3] == -1) and \
                           (df['direction'].iloc[-2] == -1)
        
        # Check if the last candle is a buy candle
        current_candle_is_buy = df['direction'].iloc[-1] == 1
        
        # Check if the last sell candle touched the 21 SMA
        last_sell_candle = df.iloc[-2]
        touched_21_sma = (last_sell_candle['low'] <= last_sell_candle['21_SMA'] <= last_sell_candle['high'])
        
        if consecutive_sells and current_candle_is_buy and touched_21_sma:
            # Check if RSI is above 50
            if latest['RSI'] > 50:
                # Generate buy signal
                stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
                stop_loss = current_market_price - stop_loss_distance
                
                # Log additional information for debugging
                logger.info(f"BUY SIGNAL GENERATED: {currency_pair}")
                logger.info(f"3 consecutive sells: {consecutive_sells}")
                logger.info(f"Current candle is buy: {current_candle_is_buy}")
                logger.info(f"Last sell candle touched 21 SMA: {touched_21_sma}")
                logger.info(f"RSI: {latest['RSI']:.2f}")
                
                return 1, stop_loss, current_market_price
        
        # Log if we found 3 consecutive sell candles but no signal was generated
        if consecutive_sells:
            logger.debug(f"{currency_pair} - Found 3 consecutive sell candles")
    
    # SELL SIGNAL CONDITIONS
    if latest['close'] < latest['200_SMA'] and abs(latest['21_SMA'] - latest['50_SMA']) > 0.0001:
        # Check for 3 consecutive buy candles followed by a sell candle
        consecutive_buys = (df['direction'].iloc[-4] == 1) and \
                          (df['direction'].iloc[-3] == 1) and \
                          (df['direction'].iloc[-2] == 1)
        
        # Check if the last candle is a sell candle
        current_candle_is_sell = df['direction'].iloc[-1] == -1
        
        # Check if the last buy candle touched the 21 SMA
        last_buy_candle = df.iloc[-2]
        touched_21_sma = (last_buy_candle['low'] <= last_buy_candle['21_SMA'] <= last_buy_candle['high'])
        
        if consecutive_buys and current_candle_is_sell and touched_21_sma:
            # Check if RSI is below 50
            if latest['RSI'] < 50:
                # Generate sell signal
                stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
                stop_loss = current_market_price + stop_loss_distance
                
                # Log additional information for debugging
                logger.info(f"SELL SIGNAL GENERATED: {currency_pair}")
                logger.info(f"3 consecutive buys: {consecutive_buys}")
                logger.info(f"Current candle is sell: {current_candle_is_sell}")
                logger.info(f"Last buy candle touched 21 SMA: {touched_21_sma}")
                logger.info(f"RSI: {latest['RSI']:.2f}")
                
                return -1, stop_loss, current_market_price
        
        # Log if we found 3 consecutive buy candles but no signal was generated
        if consecutive_buys:
            logger.debug(f"{currency_pair} - Found 3 consecutive buy candles")
    
    return 0, 0, current_market_price 