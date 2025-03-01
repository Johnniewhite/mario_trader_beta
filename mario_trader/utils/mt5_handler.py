"""
MetaTrader 5 operations handler
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime


def initialize_mt5(login, password, server):
    """
    Initialize connection to MetaTrader 5
    
    Args:
        login: MT5 account login
        password: MT5 account password
        server: MT5 server name
        
    Returns:
        True if successful, False otherwise
    """
    if not mt5.initialize(login=login, password=password, server=server):
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return False
    return True


def shutdown_mt5():
    """
    Shutdown connection to MetaTrader 5
    """
    mt5.shutdown()


def fetch_data(pair, timeframe=mt5.TIMEFRAME_M5, count=200):
    """
    Fetch price data from MetaTrader 5
    
    Args:
        pair: Currency pair symbol
        timeframe: MT5 timeframe constant
        count: Number of candles to fetch
        
    Returns:
        DataFrame with price data
    """
    rates = mt5.copy_rates_from_pos(pair, timeframe, 0, count)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df


def get_balance():
    """
    Get account balance
    
    Returns:
        Account balance
    """
    account_info = mt5.account_info()
    balance = account_info.balance if account_info else 0
    return balance


def get_current_price(symbol):
    """
    Get current price for a symbol
    
    Args:
        symbol: Currency pair symbol
        
    Returns:
        Current bid price
    """
    price = mt5.symbol_info_tick(symbol).bid
    return price


def get_contract_size(pair):
    """
    Get contract size for a symbol
    
    Args:
        pair: Currency pair symbol
        
    Returns:
        Contract size
    """
    symbol_info = mt5.symbol_info(pair)
    trade_contract_size = getattr(symbol_info, 'trade_contract_size', None)
    return trade_contract_size


def open_trade(pair, volume, stop_loss, trade_type):
    """
    Open a trade
    
    Args:
        pair: Currency pair symbol
        volume: Trade volume
        stop_loss: Stop loss price
        trade_type: 'buy' or 'sell'
        
    Returns:
        Trade result
    """
    current_price = mt5.symbol_info_tick(pair).ask if trade_type == 'buy' else mt5.symbol_info_tick(pair).bid

    order_type = mt5.ORDER_TYPE_BUY if trade_type == 'buy' else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(pair).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(pair).bid
    sl_price = price - stop_loss if order_type == mt5.ORDER_TYPE_BUY else price + stop_loss

    order = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pair,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": 0.0,
        "tp": 0.0,
        "deviation": 10,
        "magic": 234000,
        "comment": "Trading Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK
    }

    result = mt5.order_send(order)
    return result 