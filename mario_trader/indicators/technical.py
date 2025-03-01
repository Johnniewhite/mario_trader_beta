"""
Technical indicators for trading analysis
"""
import pandas as pd
import numpy as np


def calculate_rsi(df, period=14):
    """
    Calculate the Relative Strength Index (RSI)
    
    Args:
        df: DataFrame with price data
        period: RSI period
        
    Returns:
        Series with RSI values
    """
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_indicators(df):
    """
    Calculate multiple technical indicators
    
    Args:
        df: DataFrame with price data
        
    Returns:
        DataFrame with added indicators
    """
    df['200_SMA'] = df['close'].rolling(window=200).mean()
    df['21_SMA'] = df['close'].rolling(window=21).mean()
    df['50_SMA'] = df['close'].rolling(window=50).mean()
    df['RSI'] = calculate_rsi(df, 14)
    return df


def detect_rsi_divergence(df, period=14):
    """
    Detect RSI divergence
    
    Args:
        df: DataFrame with price data
        period: Period for divergence detection
        
    Returns:
        1 for bullish divergence, -1 for bearish divergence, 0 for no divergence
    """
    df = calculate_indicators(df)
    rsi = df['RSI']

    if (df['close'].iloc[-2] > df['close'].iloc[-period] and
            rsi.iloc[-3] < rsi.iloc[-period]):
        return 1

    if (df['close'].iloc[-2] < df['close'].iloc[-period] and
            rsi.iloc[-3] > rsi.iloc[-period]):
        return -1

    return 0 