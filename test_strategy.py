"""
Test script for the SMA Crossover Strategy.

This script helps with testing the strategy by:
1. Enabling debug mode
2. Running the strategy on a specific currency pair
3. Providing detailed logging of all conditions
"""
import argparse
import sys
from mario_trader.execution import execute
from mario_trader.utils.mt5_handler import initialize_mt5, shutdown_mt5
from mario_trader.config import MT5_SETTINGS, TRADING_SETTINGS
from mario_trader.utils.logger import logger
from mario_trader.utils.currency_pairs import validate_currency_pair, get_default_pair


def main():
    """
    Main entry point for the test script
    """
    parser = argparse.ArgumentParser(description='Test the SMA Crossover Strategy')
    parser.add_argument('--pair', type=str, help='Currency pair to test')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode to force signals')
    parser.add_argument('--force', choices=['buy', 'sell'], help='Force a specific signal type for testing')
    
    args = parser.parse_args()
    
    # Set debug mode if requested
    if args.debug:
        TRADING_SETTINGS["debug_mode"] = True
        print("Debug mode enabled - strategy conditions will be relaxed for testing")
    
    # Get the currency pair to test
    currency_pair = args.pair if args.pair else get_default_pair()
    if not validate_currency_pair(currency_pair):
        print(f"Invalid currency pair: {currency_pair}")
        return 1
        
    print(f"\n=== Testing SMA Crossover Strategy on {currency_pair} ===\n")
    
    # Initialize MT5
    logger.info(f"Connecting to MT5 server: {MT5_SETTINGS['server']}")
    print(f"Connecting to MT5 server: {MT5_SETTINGS['server']}...")
    
    if not initialize_mt5(
        login=MT5_SETTINGS["login"],
        password=MT5_SETTINGS["password"],
        server=MT5_SETTINGS["server"]
    ):
        logger.error("Failed to initialize MT5")
        print("Failed to connect to MT5 server.")
        return 1
        
    print("Successfully connected to MT5 server.")
    
    # Force specific signal type if requested
    if args.force:
        if args.force == "buy":
            print("Forcing BUY signal for testing")
            TRADING_SETTINGS["force_buy"] = True
        elif args.force == "sell":
            print("Forcing SELL signal for testing")
            TRADING_SETTINGS["force_sell"] = True
    
    try:
        # Execute the strategy
        print(f"Testing strategy on {currency_pair}...")
        result = execute(currency_pair)
        
        if result:
            print(f"\nStrategy test successful! A trade signal was generated for {currency_pair}.")
            print("Check the log file for detailed information.")
        else:
            print(f"\nNo trade signal was generated for {currency_pair}.")
            print("Check the log file for detailed information on why no signal was generated.")
            print("\nCommon reasons for no signal:")
            print("1. No consecutive candle pattern as required (3+ sell candles followed by buy, or 3+ buy candles followed by sell)")
            print("2. RSI conditions not met (above 50 for buy, below 50 for sell)")
            print("3. Price not on the correct side of 200 SMA (above for buy, below for sell)")
            print("4. Insufficient separation between 21 and 50 SMAs")
            
        return 0
        
    except Exception as e:
        logger.error(f"Error testing strategy: {e}")
        print(f"\nError testing strategy: {e}")
        return 1
        
    finally:
        # Shutdown MT5
        shutdown_mt5()


if __name__ == "__main__":
    sys.exit(main()) 