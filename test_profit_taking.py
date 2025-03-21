#!/usr/bin/env python3
"""
Test script for profit-taking and contingency plan implementation

This script tests the profit-taking strategy and contingency plan implementation
by executing the strategy on a specified currency pair with options to:
1. Enable debug mode for detailed logging
2. Force initial buy or sell signals for testing
3. Simulate a profitable position to test profit taking
4. Test the contingency plan implementation

Usage:
    python test_profit_taking.py --pair EURUSD --debug
    python test_profit_taking.py --pair EURUSD --force-buy --debug
    python test_profit_taking.py --pair EURUSD --force-sell --debug
    python test_profit_taking.py --pair EURUSD --simulate-profit
    python test_profit_taking.py --pair EURUSD --test-contingency
"""

import argparse
import sys
import time
import traceback
from datetime import datetime

# Add the project directory to the Python path
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules from mario_trader
from mario_trader.config import MT5_SETTINGS, TRADING_SETTINGS, logger
from mario_trader.execution import (
    login_trading, execute, check_exit_conditions,
    apply_contingency_plan, get_open_positions
)
from mario_trader.utils.currency_pairs import validate_currency_pair, get_default_pair
from mario_trader.utils.mt5_handler import fetch_data
from mario_trader.indicators.technical import calculate_indicators

def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Test profit-taking and contingency plan')
    
    parser.add_argument('--pair', type=str, help='Currency pair to test')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--force-buy', action='store_true', help='Force buy signal')
    parser.add_argument('--force-sell', action='store_true', help='Force sell signal')
    parser.add_argument('--simulate-profit', action='store_true', help='Simulate a profitable position')
    parser.add_argument('--test-contingency', action='store_true', help='Test contingency plan')
    
    return parser.parse_args()

def simulate_position(forex_pair, position_type="BUY"):
    """
    Simulate an open position for testing profit-taking
    
    Args:
        forex_pair: Currency pair symbol
        position_type: "BUY" or "SELL"
        
    Returns:
        Simulated position object
    """
    try:
        import MetaTrader5 as mt5
        
        # Get current price
        if not mt5.initialize():
            logger.error("Failed to initialize MT5")
            return None
            
        symbol_info = mt5.symbol_info(forex_pair)
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {forex_pair}")
            return None
            
        # Make sure the symbol is available
        if not symbol_info.visible:
            if not mt5.symbol_select(forex_pair, True):
                logger.error(f"Failed to select symbol {forex_pair}")
                return None
                
        # Get current price
        tick = mt5.symbol_info_tick(forex_pair)
        if tick is None:
            logger.error(f"Failed to get tick for {forex_pair}")
            return None
            
        current_price = tick.bid if position_type == "BUY" else tick.ask
        
        # Fetch data and calculate indicators
        dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
        dfs = calculate_indicators(dfs)
        latest = dfs.iloc[-1]
        
        # Get 21 SMA
        sma_21 = latest['21_SMA']
        
        # Create a simulated position
        class SimulatedPosition:
            def __init__(self):
                self.type = 0 if position_type == "BUY" else 1  # 0=buy, 1=sell
                
                # Simulate entry price that would give a profitable position
                if position_type == "BUY":
                    # For a BUY, set entry below current price
                    distance = abs(current_price - sma_21) * 0.5
                    self.price_open = current_price - distance
                else:
                    # For a SELL, set entry above current price
                    distance = abs(current_price - sma_21) * 0.5
                    self.price_open = current_price + distance
                    
                self.volume = 0.01  # 0.01 lot
                self.ticket = 123456  # Dummy ticket number
                
        position = SimulatedPosition()
        logger.info(f"Simulated {position_type} position created:")
        logger.info(f"  Entry price: {position.price_open}")
        logger.info(f"  Current price: {current_price}")
        logger.info(f"  21 SMA: {sma_21}")
        
        return position
        
    except Exception as e:
        logger.error(f"Error simulating position: {e}")
        logger.error(traceback.format_exc())
        return None

def test_profit_taking(forex_pair, simulated_position=None):
    """
    Test the profit-taking logic
    
    Args:
        forex_pair: Currency pair symbol
        simulated_position: Optional simulated position for testing
        
    Returns:
        (should_exit, reason): Tuple with exit decision and reason
    """
    try:
        # Get open positions
        if simulated_position:
            positions = [simulated_position]
        else:
            positions = get_open_positions(forex_pair)
            
        if not positions:
            logger.error(f"No open positions for {forex_pair}")
            return False, "No open positions"
            
        # Fetch data and calculate indicators
        dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
        dfs = calculate_indicators(dfs)
        
        # Check exit conditions
        should_exit, reason = check_exit_conditions(forex_pair, dfs, positions)
        
        # Log the result
        if should_exit:
            logger.info(f"Exit conditions met: {reason}")
        else:
            logger.info("No exit conditions met")
            
        return should_exit, reason
        
    except Exception as e:
        logger.error(f"Error testing profit taking: {e}")
        logger.error(traceback.format_exc())
        return False, f"Error: {str(e)}"

def test_contingency_plan(forex_pair, position_type="BUY"):
    """
    Test the contingency plan implementation
    
    Args:
        forex_pair: Currency pair symbol
        position_type: "BUY" or "SELL"
        
    Returns:
        True if test was successful, False otherwise
    """
    try:
        # Simulate a position for testing
        position = simulate_position(forex_pair, position_type)
        if not position:
            return False
            
        # Fetch data and calculate indicators
        dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
        dfs = calculate_indicators(dfs)
        latest = dfs.iloc[-1]
        
        # Apply contingency plan
        logger.info(f"Testing contingency plan for {position_type} position")
        apply_contingency_plan(forex_pair, [position], latest)
        
        # Check if contingency plan was applied
        contingency_key = f"{forex_pair}_contingency"
        if contingency_key in TRADING_SETTINGS:
            logger.info(f"Contingency plan was applied: {TRADING_SETTINGS[contingency_key]}")
            return True
        else:
            logger.error("Contingency plan was not applied")
            return False
            
    except Exception as e:
        logger.error(f"Error testing contingency plan: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function"""
    args = parse_arguments()
    
    # Get currency pair
    forex_pair = args.pair or get_default_pair()
    
    # Validate currency pair
    if not validate_currency_pair(forex_pair):
        logger.error(f"Invalid currency pair: {forex_pair}")
        return 1
        
    # Set debug mode if requested
    if args.debug:
        TRADING_SETTINGS["debug_mode"] = True
        logger.info(f"Debug mode enabled for {forex_pair}")
        
    # Set force buy/sell if requested
    if args.force_buy:
        TRADING_SETTINGS["force_buy"] = True
        TRADING_SETTINGS["force_sell"] = False
        logger.info(f"Forcing BUY signal for {forex_pair}")
    elif args.force_sell:
        TRADING_SETTINGS["force_buy"] = False
        TRADING_SETTINGS["force_sell"] = True
        logger.info(f"Forcing SELL signal for {forex_pair}")
    else:
        TRADING_SETTINGS["force_buy"] = False
        TRADING_SETTINGS["force_sell"] = False
        
    # Login to MT5
    if not login_trading(
        MT5_SETTINGS["login"],
        MT5_SETTINGS["password"],
        MT5_SETTINGS["server"]
    ):
        logger.error("Failed to login to MT5")
        return 1
        
    try:
        if args.simulate_profit:
            # Test profit taking with a simulated position
            position_type = "BUY" if args.force_buy else "SELL" if args.force_sell else "BUY"
            logger.info(f"Testing profit taking with simulated {position_type} position for {forex_pair}")
            
            # Create a simulated position
            position = simulate_position(forex_pair, position_type)
            if not position:
                logger.error("Failed to create simulated position")
                return 1
                
            # Test profit taking
            should_exit, reason = test_profit_taking(forex_pair, position)
            
            # Apply contingency plan if exit conditions met
            if should_exit and "profit" in reason.lower():
                # Fetch data for contingency plan
                dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
                dfs = calculate_indicators(dfs)
                latest = dfs.iloc[-1]
                
                # Apply contingency plan
                logger.info(f"Applying contingency plan for {forex_pair}")
                apply_contingency_plan(forex_pair, [position], latest)
                
            return 0
            
        elif args.test_contingency:
            # Test contingency plan
            position_type = "BUY" if args.force_buy else "SELL" if args.force_sell else "BUY"
            if test_contingency_plan(forex_pair, position_type):
                logger.info(f"Contingency plan test successful for {forex_pair}")
                return 0
            else:
                logger.error(f"Contingency plan test failed for {forex_pair}")
                return 1
        else:
            # Normal execution
            logger.info(f"Executing strategy for {forex_pair}")
            if execute(forex_pair):
                logger.info(f"Strategy executed successfully for {forex_pair}")
                return 0
            else:
                logger.warning(f"Strategy execution did not result in a trade for {forex_pair}")
                return 0
                
    except KeyboardInterrupt:
        logger.info("Test stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Error in test: {e}")
        logger.error(traceback.format_exc())
        return 1
        
if __name__ == "__main__":
    sys.exit(main()) 