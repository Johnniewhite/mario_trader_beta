"""
Test script for Mario Trader Bot
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock MetaTrader5 if it's not installed
try:
    import MetaTrader5 as mt5
except ImportError:
    # Create a mock module
    sys.modules['MetaTrader5'] = MagicMock()
    print("Warning: MetaTrader5 module not found. Using mock module for testing.")

from mario_trader.utils.currency_pairs import load_currency_pairs, validate_currency_pair
from mario_trader.indicators.technical import calculate_rsi, calculate_indicators
from mario_trader.strategies.signal import generate_signal


class TestCurrencyPairs(unittest.TestCase):
    """Test currency pairs functionality"""
    
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data='"EURUSD", "GBPUSD", "USDJPY"')
    def test_load_currency_pairs(self, mock_open, mock_exists):
        """Test loading currency pairs"""
        pairs = load_currency_pairs()
        self.assertIsInstance(pairs, list)
        self.assertGreater(len(pairs), 0)
        
    def test_validate_currency_pair(self):
        """Test validating currency pairs"""
        pairs = ["EURUSD", "GBPUSD", "USDJPY"]
        # Test a valid pair
        self.assertTrue(validate_currency_pair("EURUSD", pairs))
        # Test an invalid pair
        self.assertFalse(validate_currency_pair("INVALID", pairs))


class TestIndicators(unittest.TestCase):
    """Test technical indicators"""
    
    def setUp(self):
        """Set up test data"""
        # Create a sample DataFrame with price data
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=100)
        close_prices = np.random.normal(100, 5, 100).cumsum()
        self.df = pd.DataFrame({
            'open': close_prices - np.random.normal(0, 1, 100),
            'high': close_prices + np.random.normal(1, 0.5, 100),
            'low': close_prices - np.random.normal(1, 0.5, 100),
            'close': close_prices,
            'tick_volume': np.random.randint(100, 1000, 100),
            'spread': np.random.randint(1, 10, 100),
            'real_volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
    
    def test_calculate_rsi(self):
        """Test RSI calculation"""
        rsi = calculate_rsi(self.df)
        self.assertIsInstance(rsi, pd.Series)
        self.assertEqual(len(rsi), len(self.df))
        # RSI should be between 0 and 100
        self.assertTrue(all(0 <= x <= 100 for x in rsi.dropna()))
    
    def test_calculate_indicators(self):
        """Test calculating multiple indicators"""
        df_with_indicators = calculate_indicators(self.df)
        self.assertIsInstance(df_with_indicators, pd.DataFrame)
        # Check that indicators were added
        self.assertIn('200_SMA', df_with_indicators.columns)
        self.assertIn('21_SMA', df_with_indicators.columns)
        self.assertIn('50_SMA', df_with_indicators.columns)
        self.assertIn('RSI', df_with_indicators.columns)


class TestSignalGeneration(unittest.TestCase):
    """Test signal generation"""
    
    @patch('mario_trader.indicators.technical.calculate_indicators')
    def test_generate_signal(self, mock_calculate_indicators):
        """Test signal generation"""
        # Create a sample DataFrame with indicators
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=100)
        close_prices = np.random.normal(100, 5, 100).cumsum()
        df = pd.DataFrame({
            'open': close_prices - np.random.normal(0, 1, 100),
            'high': close_prices + np.random.normal(1, 0.5, 100),
            'low': close_prices - np.random.normal(1, 0.5, 100),
            'close': close_prices,
            'tick_volume': np.random.randint(100, 1000, 100),
            'spread': np.random.randint(1, 10, 100),
            'real_volume': np.random.randint(1000, 10000, 100),
            '200_SMA': close_prices - 5,
            '21_SMA': close_prices + 1,
            '50_SMA': close_prices - 1,
            'RSI': np.random.uniform(30, 70, 100)
        }, index=dates)
        
        # Mock the calculate_indicators function to return our DataFrame
        mock_calculate_indicators.return_value = df
        
        # Test signal generation
        signal, stop_loss, price = generate_signal(df, "EURUSD")
        
        # Signal should be one of -1, 0, or 1
        self.assertIn(signal, [-1, 0, 1])
        
        # If signal is not 0, stop_loss should be a float
        if signal != 0:
            self.assertIsInstance(stop_loss, float)
        
        # Price should be the last close price
        self.assertEqual(price, df['close'].iloc[-1])


if __name__ == '__main__':
    unittest.main() 