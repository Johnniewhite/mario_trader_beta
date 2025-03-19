"""
Trade execution module
"""
import math
import time
import MetaTrader5 as mt5
import numpy as np
from mario_trader.utils.mt5_handler import (
    fetch_data, get_balance, get_contract_size, open_trade, initialize_mt5, shutdown_mt5,
    get_current_price, close_trade
)
from mario_trader.strategies.signal import generate_signal
from mario_trader.strategies.monitor import monitor_trade
from mario_trader.indicators.technical import calculate_indicators
from mario_trader.config import MT5_SETTINGS, TRADING_SETTINGS, ORDER_SETTINGS
from mario_trader.utils.logger import logger, log_trade, log_signal, log_error
from mario_trader.utils.currency_pairs import load_currency_pairs, validate_currency_pair, get_default_pair


def execute(forex_pair):
    """
    Execute trading strategy for a currency pair
    
    Args:
        forex_pair: Currency pair symbol
        
    Returns:
        True if a trade was executed, False otherwise
    """
    try:
        logger.info(f"Executing trading strategy for {forex_pair}")
        dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
        
        if dfs is None or dfs.empty:
            logger.warning(f"No data available for {forex_pair}")
            return False
            
        # Add debug logging for market conditions
        latest = dfs.iloc[-1]
        dfs = calculate_indicators(dfs)  # Calculate indicators for logging
        latest_with_indicators = dfs.iloc[-1]
        
        # Log key market conditions
        logger.debug(f"{forex_pair} - Price: {latest['close']}, 200 SMA: {latest_with_indicators['200_SMA']:.2f}")
        logger.debug(f"{forex_pair} - 21 SMA: {latest_with_indicators['21_SMA']:.2f}, 50 SMA: {latest_with_indicators['50_SMA']:.2f}")
        logger.debug(f"{forex_pair} - RSI: {latest_with_indicators['RSI']:.2f}")
        
        # Check for consecutive candles
        dfs['direction'] = np.sign(dfs['close'] - dfs['open'])
        consecutive_sells = (dfs['direction'].iloc[-5] == -1) and (dfs['direction'].iloc[-4] == -1) and (dfs['direction'].iloc[-3] == -1)
        consecutive_buys = (dfs['direction'].iloc[-5] == 1) and (dfs['direction'].iloc[-4] == 1) and (dfs['direction'].iloc[-3] == 1)
        
        if consecutive_sells:
            logger.debug(f"{forex_pair} - Found 3 consecutive sell candles")
        if consecutive_buys:
            logger.debug(f"{forex_pair} - Found 3 consecutive buy candles")
            
        # Get debug mode setting from configuration
        debug_mode = TRADING_SETTINGS.get("debug_mode", False)
        if debug_mode:
            logger.info(f"Running in DEBUG MODE - strategy conditions may be relaxed for {forex_pair}")
            
        signal, stop_loss_value, current_market_price = generate_signal(dfs, forex_pair, debug_mode)
        
        # Log the signal
        signal_type = "BUY" if signal == 1 else "SELL" if signal == -1 else "NONE"
        log_signal(forex_pair, signal_type, current_market_price, stop_loss_value)
        
        if signal == 0:
            logger.info(f"No trading signal for {forex_pair}")
            return False
            
        balance = get_balance()
        logger.info(f"Account balance: {balance}")

        lot_size = get_contract_size(forex_pair)
        symbol_info = mt5.symbol_info(forex_pair)

        if symbol_info is None:
            log_error(f"Symbol info not found for {forex_pair}")
            return False 

        min_lot_size = symbol_info.volume_min 
        max_lot_size = symbol_info.volume_max 

        # Get the 21 SMA value
        df = fetch_data(forex_pair)
        df = calculate_indicators(df)
        latest = df.iloc[-1]
        sma_21 = latest['21_SMA']
        
        # Calculate distance to 21 SMA instead of stop loss
        distance_to_21_sma = abs(current_market_price - sma_21)
        
        one_lot_price = current_market_price * lot_size
        risk_percentage = 0.02  # 2% risk when price reaches 21 SMA
        risked_capital = (balance * risk_percentage)
        one_pip_movement = 0.01 if "JPY" in forex_pair else 0.0001
        distance_in_pips = distance_to_21_sma / one_pip_movement
        pip_value = (one_pip_movement / current_market_price) * lot_size
        lot_quantity = risked_capital / (distance_in_pips * pip_value)

        # Ensure volume is within allowed limits
        volume = max(min(lot_quantity, max_lot_size), min_lot_size)
        
        logger.info(f"Calculated volume: {volume}, Stop loss: {stop_loss_value}, Distance to 21 SMA: {distance_to_21_sma} pips")

        if signal == -1:
            logger.info(f"Opening SELL trade for {forex_pair}")
            trade_response = open_trade(forex_pair, volume, stop_loss_value, 'sell')
            
            if trade_response and trade_response.retcode == mt5.TRADE_RETCODE_DONE:
                order_id = trade_response.order
                position = trade_response.request.position
                log_trade("OPEN", forex_pair, current_market_price, volume, "SELL", order_id)
                monitor_trade(order_id, position, volume, "sell", stop_loss_value, current_market_price, forex_pair)
                return True
            else:
                error_code = trade_response.retcode if trade_response else "Unknown"
                error_message = trade_response.comment if trade_response else "No response"
                log_error(f"Failed to open SELL trade: {error_message} (code: {error_code})")
                return False

        elif signal == 1:
            logger.info(f"Opening BUY trade for {forex_pair}")
            trade_response = open_trade(forex_pair, volume, stop_loss_value, 'buy')
            
            if trade_response and trade_response.retcode == mt5.TRADE_RETCODE_DONE:
                order_id = trade_response.order
                position = trade_response.request.position
                log_trade("OPEN", forex_pair, current_market_price, volume, "BUY", order_id)
                monitor_trade(order_id, position, volume, "buy", stop_loss_value, current_market_price, forex_pair)
                return True
            else:
                error_code = trade_response.retcode if trade_response else "Unknown"
                error_message = trade_response.comment if trade_response else "No response"
                log_error(f"Failed to open BUY trade: {error_message} (code: {error_code})")
                return False
        
        return False
    
    except Exception as e:
        log_error(f"Error in execute function for {forex_pair}", e)
        return False


def execute_multiple_pairs(login=None, password=None, server=None, interval=60):
    """
    Execute trading strategy for multiple currency pairs
    
    Args:
        login: MT5 account login (optional, uses config if not provided)
        password: MT5 account password (optional, uses config if not provided)
        server: MT5 server name (optional, uses config if not provided)
        interval: Interval between trades in seconds
    """
    # Use provided parameters or fall back to config values
    login = login or MT5_SETTINGS["login"]
    password = password or MT5_SETTINGS["password"]
    server = server or MT5_SETTINGS["server"]
    
    logger.info("Starting multi-pair trading bot")
    
    if not initialize_mt5(login, password, server):
        log_error("Failed to initialize MT5")
        return

    try:
        # Load currency pairs
        currency_pairs = load_currency_pairs()
        if not currency_pairs:
            log_error("No currency pairs found")
            return
            
        logger.info(f"Trading {len(currency_pairs)} currency pairs: {', '.join(currency_pairs)}")
        
        while True:
            for pair in currency_pairs:
                try:
                    logger.info(f"Processing {pair}")
                    execute(pair)
                except Exception as e:
                    log_error(f"Error processing {pair}", e)
                
                # Sleep briefly between pairs to avoid overloading MT5
                time.sleep(2)
                
            # Sleep for the specified interval before the next round
            logger.info(f"Sleeping for {interval} seconds before next round")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user")
    except Exception as e:
        log_error("Unexpected error in trading bot", e)
    finally:
        logger.info("Shutting down MT5 connection")
        shutdown_mt5()


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
    
    # Validate and get default pair if needed
    available_pairs = load_currency_pairs()
    if currency_pair:
        if not validate_currency_pair(currency_pair, available_pairs):
            logger.warning(f"Invalid currency pair: {currency_pair}")
            currency_pair = get_default_pair(available_pairs)
            logger.info(f"Using default currency pair: {currency_pair}")
    else:
        currency_pair = get_default_pair(available_pairs)
    
    logger.info(f"Starting trading bot for {currency_pair}")
    
    if not initialize_mt5(login, password, server):
        log_error("Failed to initialize MT5")
        return

    try:
        logger.info("Trading bot started")
        while True:
            execute(currency_pair)
            # Sleep for a short period to avoid excessive CPU usage
            time.sleep(10)
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