"""
Trade execution module
"""
import math
import MetaTrader5 as mt5
from mario_trader.utils.mt5_handler import (
    fetch_data, get_balance, get_contract_size, open_trade, initialize_mt5, shutdown_mt5
)
from mario_trader.strategies.signal import generate_signal
from mario_trader.strategies.monitor import monitor_trade
from mario_trader.config import MT5_SETTINGS, TRADING_SETTINGS
from mario_trader.utils.logger import logger, log_trade, log_signal, log_error


def execute(forex_pair):
    """
    Execute trading strategy for a currency pair
    
    Args:
        forex_pair: Currency pair symbol
    """
    try:
        logger.info(f"Executing trading strategy for {forex_pair}")
        dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
        signal, stop_loss_value, current_market_price = generate_signal(dfs, forex_pair)
        
        # Log the signal
        signal_type = "BUY" if signal == 1 else "SELL" if signal == -1 else "NONE"
        log_signal(forex_pair, signal_type, current_market_price, stop_loss_value)
        
        if signal == 0:
            logger.info(f"No trading signal for {forex_pair}")
            return
            
        balance = get_balance()
        logger.info(f"Account balance: {balance}")

        lot_size = get_contract_size(forex_pair)
        symbol_info = mt5.symbol_info(forex_pair)

        if symbol_info is None:
            log_error(f"Symbol info not found for {forex_pair}")
            return 

        min_lot_size = symbol_info.volume_min 
        max_lot_size = symbol_info.volume_max 

        one_lot_price = current_market_price * lot_size
        risked_capital = (balance * TRADING_SETTINGS["risk_percentage"])
        one_pip_movement = 0.01 if "JPY" in forex_pair else 0.0001
        stop_loss_in_pip = abs(current_market_price - stop_loss_value) * one_pip_movement
        pip_value = (one_pip_movement / current_market_price) / lot_size
        lot_quantity = (risked_capital) * (stop_loss_in_pip * pip_value)

        # Ensure volume is within allowed limits
        volume = max(min(lot_quantity, max_lot_size), min_lot_size)
        
        logger.info(f"Calculated volume: {volume}, Stop loss: {stop_loss_value}")

        if signal == -1:
            logger.info(f"Opening SELL trade for {forex_pair}")
            trade_response = open_trade(forex_pair, volume, stop_loss_value, 'sell')
            
            if trade_response.retcode == mt5.TRADE_RETCODE_DONE:
                order_id = trade_response.order
                position = trade_response.request.position
                log_trade("OPEN", forex_pair, current_market_price, volume, "SELL", order_id)
                monitor_trade(order_id, position, volume, "sell", stop_loss_value, current_market_price, forex_pair)
            else:
                log_error(f"Failed to open SELL trade: {trade_response.comment}")

        elif signal == 1:
            logger.info(f"Opening BUY trade for {forex_pair}")
            trade_response = open_trade(forex_pair, volume, stop_loss_value, 'buy')
            
            if trade_response.retcode == mt5.TRADE_RETCODE_DONE:
                order_id = trade_response.order
                position = trade_response.request.position
                log_trade("OPEN", forex_pair, current_market_price, volume, "BUY", order_id)
                monitor_trade(order_id, position, volume, "buy", stop_loss_value, current_market_price, forex_pair)
            else:
                log_error(f"Failed to open BUY trade: {trade_response.comment}")
    
    except Exception as e:
        log_error("Error in execute function", e)


def start_trading(login=None, password=None, server=None, currency_pair=None):
    """
    Start the trading bot
    
    Args:
        login: MT5 account login (optional, uses config if not provided)
        password: MT5 account password (optional, uses config if not provided)
        server: MT5 server name (optional, uses config if not provided)
        currency_pair: Currency pair to trade (optional, uses config if not provided)
    """
    # Use provided parameters or fall back to config values
    login = login or MT5_SETTINGS["login"]
    password = password or MT5_SETTINGS["password"]
    server = server or MT5_SETTINGS["server"]
    currency_pair = currency_pair or TRADING_SETTINGS["default_currency_pair"]
    
    logger.info(f"Starting trading bot for {currency_pair}")
    
    if not initialize_mt5(login, password, server):
        log_error("Failed to initialize MT5")
        return

    try:
        logger.info("Trading bot started")
        while True:
            execute(currency_pair)
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user")
    except Exception as e:
        log_error("Unexpected error in trading bot", e)
    finally:
        logger.info("Shutting down MT5 connection")
        shutdown_mt5()


def login_trading(login=None, password=None, server=None):
    """
    Initialize connection to MetaTrader 5
    
    Args:
        login: MT5 account login (optional, uses config if not provided)
        password: MT5 account password (optional, uses config if not provided)
        server: MT5 server name (optional, uses config if not provided)
        
    Returns:
        True if successful, False otherwise
    """
    # Use provided parameters or fall back to config values
    login = login or MT5_SETTINGS["login"]
    password = password or MT5_SETTINGS["password"]
    server = server or MT5_SETTINGS["server"]
    
    logger.info(f"Logging in to MT5 server: {server}")
    return initialize_mt5(login, password, server) 