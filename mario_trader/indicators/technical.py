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


def detect_support_resistance(df, window=20, tolerance=0.0002):
    """
    Detect support and resistance levels from price data
    
    Args:
        df: DataFrame with price data
        window: Window size for detecting local extrema
        tolerance: Tolerance for grouping similar levels
        
    Returns:
        Dictionary with support and resistance levels
    """
    # Make a copy to avoid modifying the original
    df_copy = df.copy()
    
    # Get the highs and lows
    highs = df_copy['high'].values
    lows = df_copy['low'].values
    
    # Detect local maxima and minima
    resistance_points = []
    support_points = []
    
    # Loop through the data
    for i in range(window, len(df_copy) - window):
        # Check if this point is a local maximum
        if highs[i] == max(highs[i-window:i+window+1]):
            resistance_points.append((i, highs[i]))
            
        # Check if this point is a local minimum
        if lows[i] == min(lows[i-window:i+window+1]):
            support_points.append((i, lows[i]))
    
    # Group similar levels
    def group_levels(levels, tolerance):
        if not levels:
            return []
        
        # Sort levels by price
        sorted_levels = sorted(levels, key=lambda x: x[1])
        
        # Group nearby levels
        grouped = []
        current_group = [sorted_levels[0]]
        
        for i in range(1, len(sorted_levels)):
            current_level = sorted_levels[i]
            prev_level = current_group[-1]
            
            # If levels are close, add to current group
            if abs(current_level[1] - prev_level[1]) <= tolerance:
                current_group.append(current_level)
            else:
                # Calculate average price of current group
                avg_price = sum(level[1] for level in current_group) / len(current_group)
                avg_index = sum(level[0] for level in current_group) // len(current_group)
                grouped.append((avg_index, avg_price))
                
                # Start a new group
                current_group = [current_level]
        
        # Add the last group
        if current_group:
            avg_price = sum(level[1] for level in current_group) / len(current_group)
            avg_index = sum(level[0] for level in current_group) // len(current_group)
            grouped.append((avg_index, avg_price))
            
        return grouped
    
    # Group and sort the levels
    resistance_levels = [price for _, price in group_levels(resistance_points, tolerance)]
    support_levels = [price for _, price in group_levels(support_points, tolerance)]
    
    # Sort from highest to lowest
    resistance_levels = sorted(resistance_levels, reverse=True)
    support_levels = sorted(support_levels, reverse=True)
    
    return {
        'resistance': resistance_levels,
        'support': support_levels
    }


def find_nearest_level(price, levels, direction="BUY"):
    """
    Find the nearest support or resistance level based on current price and direction
    
    Args:
        price: Current price
        levels: Dictionary with support and resistance levels
        direction: "BUY" or "SELL"
        
    Returns:
        Nearest level based on direction
    """
    if not levels:
        return None
    
    if direction == "BUY":
        # For BUY, find nearest support level below current price
        support_levels = [level for level in levels['support'] if level < price]
        if support_levels:
            return max(support_levels)  # Highest support below price
    else:  # SELL
        # For SELL, find nearest resistance level above current price
        resistance_levels = [level for level in levels['resistance'] if level > price]
        if resistance_levels:
            return min(resistance_levels)  # Lowest resistance above price
    
    return None 