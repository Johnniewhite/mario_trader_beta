"""
Mario Trader Beta - Main entry point

This script provides a command-line interface for the Mario Trader Bot.
"""
import argparse
import sys
import time
from mario_trader.execution import start_trading, login_trading, execute_multiple_pairs
from mario_trader.config import MT5_SETTINGS, TRADING_SETTINGS
from mario_trader.utils.logger import logger
from mario_trader.utils.currency_pairs import load_currency_pairs, validate_currency_pair, get_default_pair


def parse_arguments():
    """
    Parse command-line arguments
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Mario Trader Beta - A MetaTrader 5 trading bot')
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start the trading bot')
    start_parser.add_argument('--login', type=int, help='MT5 account login')
    start_parser.add_argument('--password', type=str, help='MT5 account password')
    start_parser.add_argument('--server', type=str, help='MT5 server name')
    start_parser.add_argument('--pair', type=str, help='Currency pair to trade')
    start_parser.add_argument('--multi', action='store_true', help='Trade multiple currency pairs')
    start_parser.add_argument('--interval', type=int, default=60, help='Interval between trades in seconds (for multi-pair mode)')
    
    # Login command
    login_parser = subparsers.add_parser('login', help='Test MT5 login')
    login_parser.add_argument('--login', type=int, help='MT5 account login')
    login_parser.add_argument('--password', type=str, help='MT5 account password')
    login_parser.add_argument('--server', type=str, help='MT5 server name')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Display configuration information')
    info_parser.add_argument('--pairs', action='store_true', help='Display available currency pairs')
    
    # List pairs command
    subparsers.add_parser('list-pairs', help='List available currency pairs')
    
    # Check MT5 command
    subparsers.add_parser('check-mt5', help='Check if MetaTrader 5 is properly installed and accessible')
    
    return parser.parse_args()


def display_info(show_pairs=False):
    """
    Display configuration information
    
    Args:
        show_pairs: Whether to show available currency pairs
    """
    print("\n=== Mario Trader Beta Configuration ===\n")
    
    print("MT5 Connection Settings:")
    print(f"  Login: {MT5_SETTINGS['login']}")
    print(f"  Password: {'*' * len(MT5_SETTINGS['password'])}")
    print(f"  Server: {MT5_SETTINGS['server']}")
    
    print("\nTrading Settings:")
    print(f"  Default Currency Pair: {TRADING_SETTINGS['default_currency_pair']}")
    print(f"  Risk Percentage: {TRADING_SETTINGS['risk_percentage'] * 100}%")
    print(f"  Timeframe: {TRADING_SETTINGS['timeframe']}")
    print(f"  Candles Count: {TRADING_SETTINGS['candles_count']}")
    
    if show_pairs:
        print("\nAvailable Currency Pairs:")
        pairs = load_currency_pairs()
        if pairs:
            for i, pair in enumerate(pairs, 1):
                print(f"  {i}. {pair}")
        else:
            print("  No currency pairs found in currency_pair_list.txt")
    
    print("\nTo start the bot, run:")
    print("  python main.py start")
    print("\nTo start with multiple pairs, run:")
    print("  python main.py start --multi")
    print("\nTo test MT5 login, run:")
    print("  python main.py login")
    print("\nTo list available currency pairs, run:")
    print("  python main.py list-pairs")
    print("\nTo check if MetaTrader 5 is properly installed, run:")
    print("  python main.py check-mt5")
    print("\nFor more options, run:")
    print("  python main.py --help")


def list_currency_pairs():
    """
    List available currency pairs
    """
    print("\n=== Available Currency Pairs ===\n")
    pairs = load_currency_pairs()
    if pairs:
        for i, pair in enumerate(pairs, 1):
            print(f"{i}. {pair}")
    else:
        print("No currency pairs found in currency_pair_list.txt")


def check_mt5_installation():
    """
    Check if MetaTrader 5 is properly installed and accessible
    """
    print("\n=== Checking MetaTrader 5 Installation ===\n")
    
    try:
        import MetaTrader5 as mt5
        print("✓ MetaTrader5 Python package is installed")
        
        # Try to initialize without login credentials
        if mt5.initialize():
            print("✓ MetaTrader 5 terminal is found and accessible")
            print(f"✓ MetaTrader 5 version: {mt5.version()}")
            mt5.shutdown()
            print("\nMetaTrader 5 is properly installed and accessible.")
            return True
        else:
            error = mt5.last_error()
            print(f"✗ Failed to initialize MetaTrader 5: {error}")
            
            if error[0] == -10003 and "MetaTrader 5 x64 not found" in error[1]:
                print("\nMetaTrader 5 x64 is not installed or not found in the default location.")
                print("Please follow these steps:")
                print("1. Install MetaTrader 5 from https://www.metatrader5.com/en/download")
                print("2. Run MetaTrader 5 at least once after installation")
                print("3. Try running the bot again")
            return False
            
    except ImportError:
        print("✗ MetaTrader5 Python package is not installed")
        print("\nPlease install the MetaTrader5 package using:")
        print("pip install MetaTrader5")
        return False
    except Exception as e:
        print(f"✗ Error checking MetaTrader 5 installation: {e}")
        return False


def main():
    """
    Main entry point
    """
    args = parse_arguments()
    
    if args.command == 'start':
        logger.info("Starting Mario Trader Bot")
        
        if args.multi:
            logger.info("Starting in multi-pair mode")
            try:
                execute_multiple_pairs(
                    login=args.login,
                    password=args.password,
                    server=args.server,
                    interval=args.interval
                )
            except Exception as e:
                logger.error(f"Error starting multi-pair trading: {e}")
                print(f"\nError: {e}")
                print("\nIf the error is related to MetaTrader 5 not being found, please:")
                print("1. Install MetaTrader 5 from https://www.metatrader5.com/en/download")
                print("2. Run MetaTrader 5 at least once after installation")
                print("3. Try running the bot again")
                return 1
        else:
            # Validate currency pair if provided
            if args.pair and not validate_currency_pair(args.pair):
                logger.warning(f"Invalid currency pair: {args.pair}")
                print(f"Invalid currency pair: {args.pair}")
                print("Available pairs:")
                list_currency_pairs()
                return 1
            
            try:    
                start_trading(
                    login=args.login,
                    password=args.password,
                    server=args.server,
                    currency_pair=args.pair
                )
            except Exception as e:
                logger.error(f"Error starting trading: {e}")
                print(f"\nError: {e}")
                print("\nIf the error is related to MetaTrader 5 not being found, please:")
                print("1. Install MetaTrader 5 from https://www.metatrader5.com/en/download")
                print("2. Run MetaTrader 5 at least once after installation")
                print("3. Try running the bot again")
                return 1
    
    elif args.command == 'login':
        logger.info("Testing MT5 login")
        try:
            if login_trading(
                login=args.login,
                password=args.password,
                server=args.server
            ):
                print("Login successful!")
            else:
                print("Login failed!")
                print("\nIf the error is related to MetaTrader 5 not being found, please:")
                print("1. Install MetaTrader 5 from https://www.metatrader5.com/en/download")
                print("2. Run MetaTrader 5 at least once after installation")
                print("3. Try running the bot again")
                return 1
        except Exception as e:
            logger.error(f"Error testing login: {e}")
            print(f"\nError: {e}")
            print("\nIf the error is related to MetaTrader 5 not being found, please:")
            print("1. Install MetaTrader 5 from https://www.metatrader5.com/en/download")
            print("2. Run MetaTrader 5 at least once after installation")
            print("3. Try running the bot again")
            return 1
    
    elif args.command == 'info':
        display_info(show_pairs=args.pairs)
    
    elif args.command == 'list-pairs':
        list_currency_pairs()
    
    elif args.command == 'check-mt5':
        if not check_mt5_installation():
            return 1
    
    else:
        # If no command is provided, display info
        display_info()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
 
