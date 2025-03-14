"""
MetaTrader 5 operations handler
"""
import MetaTrader5 as mt5
import pandas as pd
import time
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
    # First, ensure MT5 is not already initialized
    shutdown_mt5()
    
    # Try to initialize with a few retries
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            if not mt5.initialize(login=login, password=password, server=server):
                error = mt5.last_error()
                log_error(f"Failed to initialize MT5 (attempt {attempt}/{max_retries}): {error}")
                
                # Check if the error is related to MT5 not being found
                if error[0] == -10003 and "MetaTrader 5 x64 not found" in error[1]:
                    if attempt == max_retries:
                        logger.error("MetaTrader 5 x64 is not installed or not found in the default location.")
                        logger.error("Please install MetaTrader 5 from https://www.metatrader5.com/en/download")
                        logger.error("After installation, make sure to run MetaTrader 5 at least once before using this bot.")
                
                if attempt < max_retries:
                    time.sleep(2)  # Wait before retrying
                    continue
                return False
            
            logger.info(f"MT5 initialized successfully. Version: {mt5.version()}")
            
            # Verify account connection
            account_info = mt5.account_info()
            if account_info is None:
                log_error(f"Failed to get account info (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    time.sleep(2)  # Wait before retrying
                    continue
                return False
                
            logger.info(f"Connected to account: {account_info.login} ({account_info.name})")
            logger.info(f"Balance: {account_info.balance} {account_info.currency}")
            return True
            
        except Exception as e:
            log_error(f"Error initializing MT5 (attempt {attempt}/{max_retries})", e)
            if attempt < max_retries:
                time.sleep(2)  # Wait before retrying
                continue
            return False
    
    return False


def shutdown_mt5():
    """
    Shutdown connection to MetaTrader 5
    """
    try:
        if mt5.terminal_info() is not None:
            mt5.shutdown()
            logger.info("MT5 connection shut down")
    except Exception as e:
        log_error("Error shutting down MT5", e)


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
    try:
        # Map timeframe string to MT5 timeframe constant
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1
        }
        
        tf = timeframe_map.get(TRADING_SETTINGS["timeframe"], mt5.TIMEFRAME_M5)
        if timeframe:
            tf = timeframe_map.get(timeframe, tf)
            
        candles_count = count or TRADING_SETTINGS["candles_count"]
        
        # Ensure the symbol is available
        symbol_info = mt5.symbol_info(pair)
        if symbol_info is None:
            logger.warning(f"Symbol {pair} not found, trying to enable it")
            if not mt5.symbol_select(pair, True):
                log_error(f"Failed to enable symbol {pair}")
                return None
        
        # Fetch the data
        rates = mt5.copy_rates_from_pos(pair, tf, 0, candles_count)
        if rates is None or len(rates) == 0:
            log_error(f"Failed to fetch data for {pair}")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        return df
        
    except Exception as e:
        log_error(f"Error fetching data for {pair}", e)
        return None


def get_balance():
    """
    Get account balance
    
    Returns:
        Account balance
    """
    try:
        account_info = mt5.account_info()
        if account_info is None:
            log_error("Failed to get account info")
            return 0
            
        return account_info.balance
        
    except Exception as e:
        log_error("Error getting balance", e)
        return 0


def get_contract_size(symbol):
    """
    Get contract size for a symbol
    
    Args:
        symbol: Symbol to get contract size for
        
    Returns:
        Contract size
    """
    try:
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            log_error(f"Symbol info not found for {symbol}")
            return 100000  # Default for forex
            
        return symbol_info.trade_contract_size
        
    except Exception as e:
        log_error(f"Error getting contract size for {symbol}", e)
        return 100000  # Default for forex


def get_current_price(symbol, price_type='close'):
    """
    Get current price for a symbol
    
    Args:
        symbol: Symbol to get price for
        price_type: Price type ('close', 'open', 'high', 'low')
        
    Returns:
        Current price
    """
    try:
        # Get the last tick
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            log_error(f"Failed to get tick for {symbol}")
            return None
            
        if price_type == 'close':
            return (tick.bid + tick.ask) / 2
        elif price_type == 'bid':
            return tick.bid
        elif price_type == 'ask':
            return tick.ask
        else:
            return (tick.bid + tick.ask) / 2
            
    except Exception as e:
        log_error(f"Error getting current price for {symbol}", e)
        return None


def open_trade(symbol, volume, stop_loss, trade_type):
    """
    Open a trade
    
    Args:
        symbol: Symbol to trade
        volume: Trade volume
        stop_loss: Stop loss price
        trade_type: Trade type ('buy' or 'sell')
        
    Returns:
        Trade result
    """
    try:
        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            log_error(f"Failed to get tick for {symbol}")
            return None
            
        # Prepare trade request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": mt5.ORDER_TYPE_BUY if trade_type == 'buy' else mt5.ORDER_TYPE_SELL,
            "price": tick.ask if trade_type == 'buy' else tick.bid,
            "sl": stop_loss,
            "deviation": ORDER_SETTINGS["deviation"],
            "magic": ORDER_SETTINGS["magic_number"],
            "comment": ORDER_SETTINGS["comment"],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send the trade request
        result = mt5.order_send(request)
        if result is None:
            log_error(f"Failed to send order for {symbol}")
            return None
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log_error(f"Order failed: {result.comment} (code: {result.retcode})")
            
        return result
        
    except Exception as e:
        log_error(f"Error opening trade for {symbol}", e)
        return None


def close_trade(position_id):
    """
    Close a trade
    
    Args:
        position_id: Position ID to close
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get position info
        position = mt5.positions_get(ticket=position_id)
        if position is None or len(position) == 0:
            log_error(f"Position {position_id} not found")
            return False
            
        position = position[0]
        
        # Prepare close request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": position_id,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
            "deviation": ORDER_SETTINGS["deviation"],
            "magic": ORDER_SETTINGS["magic_number"],
            "comment": f"Close {ORDER_SETTINGS['comment']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send the close request
        result = mt5.order_send(request)
        if result is None:
            log_error(f"Failed to close position {position_id}")
            return False
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log_error(f"Close failed: {result.comment} (code: {result.retcode})")
            return False
            
        return True
        
    except Exception as e:
        log_error(f"Error closing position {position_id}", e)
        return False 