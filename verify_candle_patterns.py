"""
Script to verify the candle pattern detection logic

This script creates test data with known candle patterns and verifies
that our pattern detection logic works correctly.
"""
import pandas as pd
import numpy as np
from mario_trader.strategies.sma_crossover_strategy import check_consecutive_candles
from mario_trader.utils.logger import logger


def create_test_data(pattern):
    """
    Create test data with a specific candle pattern
    
    Args:
        pattern: List of directions (1 for buy, -1 for sell)
                The LAST element is the MOST RECENT candle
        
    Returns:
        DataFrame with test data
    """
    # Create empty DataFrame with required columns
    df = pd.DataFrame({
        'open': np.zeros(len(pattern)),
        'close': np.zeros(len(pattern)),
        'high': np.zeros(len(pattern)),
        'low': np.zeros(len(pattern)),
        'direction': pattern
    })
    
    # Set open/close values based on direction
    for i, direction in enumerate(pattern):
        if direction == 1:  # Buy candle
            df.loc[i, 'open'] = 100
            df.loc[i, 'close'] = 101
        else:  # Sell candle
            df.loc[i, 'open'] = 101
            df.loc[i, 'close'] = 100
        
        df.loc[i, 'high'] = max(df.loc[i, 'open'], df.loc[i, 'close']) + 0.5
        df.loc[i, 'low'] = min(df.loc[i, 'open'], df.loc[i, 'close']) - 0.5
    
    return df


def verify_pattern_detection():
    """
    Verify that the pattern detection logic works correctly
    """
    print("\n=== Verifying Candle Pattern Detection Logic ===\n")
    
    # Test case 1: 3 sell candles followed by a buy candle (should detect pattern)
    # Pattern is [oldest ... newest]
    pattern1 = [-1, -1, -1, 1]  # Last element is the most recent
    df1 = create_test_data(pattern1)
    print(f"Test 1 pattern: {pattern1} (newest on right)")
    result1 = check_consecutive_candles(df1, -1, 3)
    print(f"Test 1: 3 sell candles followed by a buy candle: {result1} (Expected: True)")
    
    # Test case 2: 3 buy candles followed by a sell candle (should detect pattern)
    pattern2 = [1, 1, 1, -1]  # Last element is the most recent
    df2 = create_test_data(pattern2)
    print(f"Test 2 pattern: {pattern2} (newest on right)")
    result2 = check_consecutive_candles(df2, 1, 3)
    print(f"Test 2: 3 buy candles followed by a sell candle: {result2} (Expected: True)")
    
    # Test case 3: Mixed pattern, no clear signal (should not detect pattern)
    pattern3 = [1, -1, 1, -1]  # Last element is the most recent
    df3 = create_test_data(pattern3)
    print(f"Test 3 pattern: {pattern3} (newest on right)")
    result3a = check_consecutive_candles(df3, -1, 3)
    result3b = check_consecutive_candles(df3, 1, 3)
    print(f"Test 3a: Mixed pattern (checking sell->buy): {result3a} (Expected: False)")
    print(f"Test 3b: Mixed pattern (checking buy->sell): {result3b} (Expected: False)")
    
    # Test case 4: 2 sell candles followed by a buy candle (not enough consecutive)
    pattern4 = [1, -1, -1, 1]  # Last element is the most recent
    df4 = create_test_data(pattern4)
    print(f"Test 4 pattern: {pattern4} (newest on right)")
    result4 = check_consecutive_candles(df4, -1, 3)
    print(f"Test 4: 2 sell candles followed by a buy: {result4} (Expected: False)")
    
    # Test case 5: 4 sell candles followed by a buy candle (more than enough)
    pattern5 = [-1, -1, -1, -1, 1]  # Last element is the most recent
    df5 = create_test_data(pattern5)
    print(f"Test 5 pattern: {pattern5} (newest on right)")
    result5 = check_consecutive_candles(df5, -1, 3)
    print(f"Test 5: 4 sell candles followed by a buy: {result5} (Expected: True)")
    
    print("\nIf all tests pass as expected, the pattern detection logic is working correctly.")


if __name__ == "__main__":
    verify_pattern_detection() 