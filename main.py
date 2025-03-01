"""
Mario Trader Beta - Main entry point
"""
from mario_trader.execution import start_trading


if __name__ == "__main__":
    # Default credentials
    login = 81338593
    password = "Mario123$$"
    server = "Exness-MT5Trial10"
    currency_pair = 'EURUSD'
    
    # Start the trading bot
    start_trading(login, password, server, currency_pair)
 
