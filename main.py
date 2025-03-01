"""
Mario Trader Beta - Main entry point

This script provides a command-line interface for the Mario Trader Bot.
"""
import argparse
import sys
from mario_trader.execution import start_trading, login_trading
from mario_trader.config import MT5_SETTINGS, TRADING_SETTINGS
from mario_trader.utils.logger import logger


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
    
    # Login command
    login_parser = subparsers.add_parser('login', help='Test MT5 login')
    login_parser.add_argument('--login', type=int, help='MT5 account login')
    login_parser.add_argument('--password', type=str, help='MT5 account password')
    login_parser.add_argument('--server', type=str, help='MT5 server name')
    
    # Info command
    subparsers.add_parser('info', help='Display configuration information')
    
    return parser.parse_args()


def display_info():
    """
    Display configuration information
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
    
    print("\nTo start the bot, run:")
    print("  python main.py start")
    print("\nTo test MT5 login, run:")
    print("  python main.py login")
    print("\nFor more options, run:")
    print("  python main.py --help")


def main():
    """
    Main entry point
    """
    args = parse_arguments()
    
    if args.command == 'start':
        logger.info("Starting Mario Trader Bot")
        start_trading(
            login=args.login,
            password=args.password,
            server=args.server,
            currency_pair=args.pair
        )
    
    elif args.command == 'login':
        logger.info("Testing MT5 login")
        if login_trading(
            login=args.login,
            password=args.password,
            server=args.server
        ):
            print("Login successful!")
        else:
            print("Login failed!")
            return 1
    
    elif args.command == 'info':
        display_info()
    
    else:
        # If no command is provided, display info
        display_info()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
 
