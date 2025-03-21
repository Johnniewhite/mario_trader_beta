#!/usr/bin/env python3
"""
Test script for the new contingency plan implementation

This script tests the updated contingency plan that sets stop orders at entry
instead of after closing a profitable position. It also tests the support/resistance
based exit strategy.

Usage:
    python test_contingency.py --pair EURUSD --debug
    python test_contingency.py --pair EURUSD --force-buy
    python test_contingency.py --pair EURUSD --force-sell
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
    get_open_positions, check_pending_orders
)
from mario_trader.utils.mt5_handler import fetch_data
from mario_trader.indicators.technical import calculate_indicators, detect_support_resistance, find_nearest_level
from mario_trader.utils.currency_pairs import validate_currency_pair, get_default_pair

def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Test new contingency plan implementation')
    
    parser.add_argument('--pair', type=str, help='Currency pair to test')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--force-buy', action='store_true', help='Force buy signal')
    parser.add_argument('--force-sell', action='store_true', help='Force sell signal')
    parser.add_argument('--monitor', action='store_true', help='Monitor positions and pending orders continuously')
    
    return parser.parse_args()

def monitor_positions_and_orders(forex_pair, interval=10, max_duration=300):
    """
    Monitor positions and pending orders for a specified duration
    
    Args:
        forex_pair: Currency pair symbol
        interval: Interval between checks in seconds
        max_duration: Maximum duration to monitor in seconds
    """
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            logger.error("Failed to initialize MT5")
            return
        
        start_time = time.time()
        end_time = start_time + max_duration
        
        logger.info(f"Starting to monitor {forex_pair} for {max_duration} seconds")
        
        while time.time() < end_time:
            # Check open positions
            positions = get_open_positions(forex_pair)
            logger.info(f"Found {len(positions)} open positions for {forex_pair}")
            
            for i, position in enumerate(positions):
                position_type = "BUY" if position.type == 0 else "SELL"
                logger.info(f"Position {i+1}: {position_type}, Lot Size: {position.volume}, Entry: {position.price_open}")
            
            # Check pending orders
            pending_orders = mt5.orders_get(symbol=forex_pair)
            if pending_orders is None:
                pending_orders = []
            
            logger.info(f"Found {len(pending_orders)} pending orders for {forex_pair}")
            
            for i, order in enumerate(pending_orders):
                order_type_str = "UNKNOWN"
                if order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                    order_type_str = "BUY LIMIT"
                elif order.type == mt5.ORDER_TYPE_SELL_LIMIT:
                    order_type_str = "SELL LIMIT"
                elif order.type == mt5.ORDER_TYPE_BUY_STOP:
                    order_type_str = "BUY STOP"
                elif order.type == mt5.ORDER_TYPE_SELL_STOP:
                    order_type_str = "SELL STOP"
                
                logger.info(f"Order {i+1}: {order_type_str}, Lot Size: {order.volume_current}, Price: {order.price_open}")
            
            # Check contingency plan status
            contingency_key = f"{forex_pair}_contingency"
            if contingency_key in TRADING_SETTINGS:
                contingency = TRADING_SETTINGS[contingency_key]
                logger.info(f"Contingency plan: {contingency}")
            else:
                logger.info("No active contingency plan")
            
            # Check exit conditions
            if positions:
                dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
                dfs = calculate_indicators(dfs)
                
                # Calculate support/resistance levels
                support_resistance_levels = detect_support_resistance(dfs)
                
                # Check exit conditions
                should_exit, exit_reason = check_exit_conditions(forex_pair, dfs, positions, support_resistance_levels)
                
                if should_exit:
                    logger.info(f"Exit conditions met: {exit_reason}")
                else:
                    logger.info("No exit conditions met")
                
                # Log current price and key levels
                current_price = dfs.iloc[-1]['close']
                sma_21 = dfs.iloc[-1]['21_SMA']
                
                logger.info(f"Current price: {current_price:.5f}, 21 SMA: {sma_21:.5f}")
                
                if support_resistance_levels:
                    if len(support_resistance_levels['support']) > 0:
                        support_levels = ", ".join([f"{level:.5f}" for level in support_resistance_levels['support'][:3]])
                        logger.info(f"Top 3 support levels: {support_levels}")
                    
                    if len(support_resistance_levels['resistance']) > 0:
                        resistance_levels = ", ".join([f"{level:.5f}" for level in support_resistance_levels['resistance'][:3]])
                        logger.info(f"Top 3 resistance levels: {resistance_levels}")
                    
                    # Find nearest levels
                    for position in positions:
                        position_type = "BUY" if position.type == 0 else "SELL"
                        nearest_level = find_nearest_level(current_price, support_resistance_levels, position_type)
                        if nearest_level:
                            logger.info(f"Nearest {'support' if position_type == 'BUY' else 'resistance'} level: {nearest_level:.5f}")
            
            # Process any pending orders that might be triggered
            check_pending_orders(forex_pair)
            
            # Wait for the next check
            logger.info(f"Monitoring cycle complete, sleeping for {interval} seconds")
            logger.info("------------------------------------------------------")
            time.sleep(interval)
            
        logger.info(f"Monitoring completed after {max_duration} seconds")
        
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Error during monitoring: {e}")
        logger.error(traceback.format_exc())

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
        # Execute strategy
        logger.info(f"Executing strategy for {forex_pair}")
        execute_result = execute(forex_pair)
        
        if execute_result:
            logger.info(f"Strategy executed successfully for {forex_pair}")
        else:
            logger.warning(f"Strategy execution did not result in a trade for {forex_pair}")
        
        # Monitor positions and orders if requested
        if args.monitor:
            monitor_positions_and_orders(forex_pair, interval=10, max_duration=300)
            
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