"""
MetaTrader 5 operations handler
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from mario_trader.config import TRADING_SETTINGS, ORDER_SETTINGS
from mario_trader.utils.logger import logger, log_error


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
        error = mt5.last_error()
        log_error(f"Failed to initialize MT5: {error}")
        return False
    
    logger.info(f"MT5 initialized successfully. Version: {mt5.version()}")
    return True


def shutdown_mt5():
    """
    Shutdown connection to MetaTrader 5
    """
    mt5.shutdown()
    logger.info("MT5 connection shut down")


def fetch_data(pair, timeframe=None, count=None):
    """
    Fetch price data from MetaTrader 5
    
    Args:
        pair: Currency pair symbol
        timeframe: MT5 timeframe constant (optional)
        count: Number of candles to fetch (optional)
        
    Returns:
        DataFrame with price data
    """
    # Use provided parameters or fall back to config values
    if timeframe is None:
        timeframe_str = TRADING_SETTINGS.get("timeframe", "M5")
        timeframe = getattr(mt5, f"TIMEFRAME_{timeframe_str}")
    
    count = count or TRADING_SETTINGS.get("candles_count", 200)
    
    logger.debug(f"Fetching {count} candles for {pair} with timeframe {timeframe}")
    rates = mt5.copy_rates_from_pos(pair, timeframe, 0, count)
    
    if rates is None or len(rates) == 0:
        log_error(f"Failed to fetch data for {pair}")
        return pd.DataFrame()
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    
    logger.debug(f"Fetched {len(df)} candles for {pair}")
    return df


def get_balance():
    """
    Get account balance
    
    Returns:
        Account balance
    """
    account_info = mt5.account_info()
    if account_info is None:
        log_error("Failed to get account info")
        return 0
    
    balance = account_info.balance
    logger.debug(f"Account balance: {balance}")
    return balance


def get_current_price(symbol):
    """
    Get current price for a symbol
    
    Args:
        symbol: Currency pair symbol
        
    Returns:
        Current bid price
    """
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        log_error(f"Failed to get tick info for {symbol}")
        return 0
    
    price = tick.bid
    logger.debug(f"Current price for {symbol}: {price}")
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
    if symbol_info is None:
        log_error(f"Failed to get symbol info for {pair}")
        return 0
    
    trade_contract_size = getattr(symbol_info, 'trade_contract_size', 0)
    logger.debug(f"Contract size for {pair}: {trade_contract_size}")
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
    logger.info(f"Opening {trade_type} trade for {pair} with volume {volume}")
    
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
        "sl": 0.0,  # We'll manage stop loss in our code
        "tp": 0.0,  # We'll manage take profit in our code
        "deviation": ORDER_SETTINGS.get("deviation", 10),
        "magic": ORDER_SETTINGS.get("magic_number", 234000),
        "comment": ORDER_SETTINGS.get("comment", "Trading Bot"),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK
    }

    logger.debug(f"Sending order: {order}")
    result = mt5.order_send(order)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        log_error(f"Order failed: {result.comment}, Retcode: {result.retcode}")
    else:
        logger.info(f"Order executed successfully. Order ID: {result.order}")
    
    return result


def close_trade(symbol, ticket):
    """
    Close a trade
    
    Args:
        symbol: Currency pair symbol
        ticket: Ticket ID
        
    Returns:
        Close result
    """
    logger.info(f"Closing trade {ticket} for {symbol}")
    
    position = mt5.positions_get(ticket=ticket)
    if position is None or len(position) == 0:
        log_error(f"Position {ticket} not found")
        return None
    
    position = position[0]
    
    # Determine the close direction (opposite of the open direction)
    close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(symbol).ask
    
    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": position.volume,
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": ORDER_SETTINGS.get("deviation", 10),
        "magic": ORDER_SETTINGS.get("magic_number", 234000),
        "comment": f"Close {ORDER_SETTINGS.get('comment', 'Trading Bot')}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK
    }
    
    logger.debug(f"Sending close request: {close_request}")
    result = mt5.order_send(close_request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        log_error(f"Close order failed: {result.comment}, Retcode: {result.retcode}")
    else:
        logger.info(f"Trade {ticket} closed successfully")
    
    return result 