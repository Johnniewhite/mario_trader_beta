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

    if latest['close'] > latest['200_SMA'] and abs(latest['21_SMA'] - latest['50_SMA']) > 0.0001:
        df['direction'] = np.sign(df['close'] - df['open'])
        consecutive_sells = (df['direction'].shift(2) == -1) & (df['direction'].shift(3) == -1) & (df['direction'].shift(4) == -1)

        if consecutive_sells.iloc[-8]:
            last_candle = df.iloc[-4]
            previous_candle = df.iloc[-3]

            if last_candle['open'] < last_candle['close'] and \
                    last_candle['open'] < previous_candle['close'] < previous_candle['open'] < last_candle['close'] and \
                    df['RSI'].iloc[-4] > 50:
                current_market_price = latest['close']
                stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
                stop_loss = current_market_price - stop_loss_distance
                last_candle_type = "buy"

                if last_candle['open'] > last_candle['close']:
                    last_candle_type = "sell"

                return 1, stop_loss, current_market_price

    if latest['close'] < latest['200_SMA'] and abs(latest['21_SMA'] - latest['50_SMA']) > 0.0001:        
        df['direction'] = np.sign(df['close'] - df['open'])
        consecutive_buys = (df['direction'].shift(2) == 1) & (df['direction'].shift(3) == 1) & (
                df['direction'].shift(4) == 1)

        if consecutive_buys.iloc[-8] and df['RSI'].iloc[-4] < 50:
            last_candle = df.iloc[-3]
            previous_candle = df.iloc[-4]

            if last_candle['open'] > last_candle['close'] and \
                    last_candle['open'] > previous_candle['close'] and \
                    previous_candle['close'] > previous_candle['open'] and \
                    previous_candle['open'] > last_candle['close']:

                current_market_price = latest['close']
                stop_loss_distance = abs(latest['21_SMA'] - current_market_price)
                stop_loss = current_market_price + stop_loss_distance
                last_candle_type = "sell"

                if last_candle['open'] < last_candle['close']:
                    last_candle_type = "buy"
                return -1, stop_loss, current_market_price

    return 0, 0, current_market_price 