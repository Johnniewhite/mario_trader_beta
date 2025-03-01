"""
Trade monitoring and management
"""
import math
import time
import MetaTrader5 as mt5
from mario_trader.utils.mt5_handler import get_current_price, fetch_data, close_trade
from mario_trader.indicators.technical import detect_rsi_divergence
from mario_trader.config import CONTINGENCY_TRADE_SETTINGS
from mario_trader.utils.logger import logger, log_trade, log_error


def check_take_profit(current_price, take_profit, trade_type):
    """
    Check if take profit level is reached
    
    Args:
        current_price: Current price
        take_profit: Take profit price
        trade_type: 'buy' or 'sell'
        
    Returns:
        True if take profit is reached, False otherwise
    """
    if trade_type == 'buy':
        if current_price < take_profit:
            logger.debug(f"Take profit reached: {current_price} < {take_profit}")
            return True
    elif trade_type == 'sell':
        if current_price > take_profit:
            logger.debug(f"Take profit reached: {current_price} > {take_profit}")
            return True

    return False


def check_stop_loss(current_price, stop_loss, trade_type):
    """
    Check if stop loss level is reached
    
    Args:
        current_price: Current price
        stop_loss: Stop loss price
        trade_type: 'buy' or 'sell'
        
    Returns:
        True if stop loss is reached, False otherwise
    """
    if trade_type == 'buy':
        if current_price > stop_loss:
            logger.debug(f"Stop loss reached: {current_price} > {stop_loss}")
            return True

    elif trade_type == 'sell':
        if current_price < stop_loss:
            logger.debug(f"Stop loss reached: {current_price} < {stop_loss}")
            return True

    return False


def monitor_trade(order_id, position, volume, order_type, stop_loss, current_market_price, forex_pair):
    """
    Monitor and manage an open trade
    
    Args:
        order_id: Order ID
        position: Position ID
        volume: Trade volume
        order_type: 'buy' or 'sell'
        stop_loss: Stop loss price
        current_market_price: Current market price
        forex_pair: Currency pair symbol
    """
    try:
        logger.info(f"Monitoring trade {order_id} for {forex_pair}")
        
        # Initialize contingency trades dictionary
        con_trade = {}
        lot_size_multipliers = CONTINGENCY_TRADE_SETTINGS.get("lot_size_multipliers", {})
        
        for key, multiplier in lot_size_multipliers.items():
            con_trade[key] = {
                "lot_size": multiplier,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            }

        contingency_status = False
        
        # Main monitoring loop
        while True:
            try:
                current_price = get_current_price(forex_pair)
                df = fetch_data(forex_pair)
                
                # Check for RSI divergence
                divergence_signal = detect_rsi_divergence(df)
                
                if divergence_signal != 0:
                    logger.info(f"RSI divergence detected: {divergence_signal}")
                    response = close_trade(forex_pair, order_id)
                    log_trade("CLOSE", forex_pair, current_price, volume, order_type.upper(), order_id)
                    break
                
                # Check stop loss
                if check_stop_loss(current_price, stop_loss, order_type):
                    logger.info(f"Stop loss triggered at {current_price}")
                    contingency_status = True
                    break
                
                # Sleep to avoid excessive API calls
                time.sleep(1)
                
            except Exception as e:
                log_error(f"Error in monitoring loop: {str(e)}")
                time.sleep(5)  # Wait a bit longer on error
        
        # If no contingency needed, exit
        if not contingency_status:
            logger.info("Trade closed without contingency")
            return 0
        
        # Setup for contingency trading
        logger.info("Starting contingency trading")
        order_counter_type = "buy"
        order_counter_type_x = "sell"
        open_trade_bool = True
        v_counter_trade = 1
        
        lukki = "sell"
        if order_type == "sell":
            order_counter_type = "sell"
            order_counter_type_x = "buy"
            lukki = "buy"
        
        getta_trade = con_trade[f"v{v_counter_trade}"]
        getta_trade["status"] = True
        getta_trade["trade_type"] = lukki
        
        # Calculate take profit levels
        if order_type == "buy":
            leap = abs(current_market_price - stop_loss)
            counter_take_profit = stop_loss - leap
            normal_take_profit = current_market_price + leap
        elif order_type == "sell":
            leap = abs(stop_loss - current_market_price)
            counter_take_profit = stop_loss + leap
            normal_take_profit = current_market_price - leap
        else:
            return 0
        
        logger.info(f"Contingency take profit: {counter_take_profit}, Normal take profit: {normal_take_profit}")
        
        # Contingency trading loop
        while True:
            try:
                if not contingency_status:
                    break
                
                current_price = get_current_price(forex_pair)
                df = fetch_data(forex_pair)
                
                if not contingency_status:
                    break
                
                if v_counter_trade == 14:
                    logger.info("Maximum contingency trades reached")
                    break
                
                # Open contingency trades
                if open_trade_bool:
                    get_trade = con_trade[f"v{v_counter_trade}"]
                    if get_trade["status"]:
                        new_volume = volume * get_trade["lot_size"]
                        new_volume = math.ceil(new_volume * 100) / 100
                        
                        if order_counter_type == "sell":
                            logger.info(f"Opening contingency SELL trade with volume {new_volume}")
                            order_counter_type = "buy"
                            get_trade["trade_type"] = "sell"
                            v_counter_trade += 1
                            trade_response = open_trade(forex_pair, new_volume, stop_loss, 'sell')
                            get_trade["ticket_id"] = trade_response.order
                            log_trade("CONTINGENCY", forex_pair, current_price, new_volume, "SELL", trade_response.order)
                        
                        elif order_counter_type == "buy":
                            logger.info(f"Opening contingency BUY trade with volume {new_volume}")
                            order_counter_type = "sell"
                            get_trade["trade_type"] = "buy"
                            v_counter_trade += 1
                            trade_response = open_trade(forex_pair, new_volume, stop_loss, 'buy')
                            get_trade["ticket_id"] = trade_response.order
                            log_trade("CONTINGENCY", forex_pair, current_price, new_volume, "BUY", trade_response.order)
                
                # Check if counter take profit is reached
                if check_stop_loss(current_price, counter_take_profit, order_counter_type_x):
                    logger.info(f"Counter take profit reached at {current_price}")
                    close_trade(forex_pair, order_id)
                    
                    for key in con_trade.keys():
                        if con_trade[key]["status"] and con_trade[key]["ticket_id"]:
                            close_trade(forex_pair, con_trade[key]["ticket_id"])
                    
                    log_trade("CLOSE_ALL", forex_pair, current_price, volume, "CONTINGENCY", None)
                    break
                
                # Check if normal take profit is reached
                if check_take_profit(current_price, normal_take_profit, order_type):
                    logger.info(f"Normal take profit reached at {current_price}")
                    close_trade(forex_pair, order_id)
                    
                    for key in con_trade.keys():
                        if con_trade[key]["status"] and con_trade[key]["ticket_id"]:
                            close_trade(forex_pair, con_trade[key]["ticket_id"])
                    
                    log_trade("CLOSE_ALL", forex_pair, current_price, volume, "CONTINGENCY", None)
                    break
                
                # Handle buy scenario
                if order_type == "buy":
                    if order_counter_type == "sell":
                        if current_price < current_market_price:
                            get_trade = con_trade[f"v{v_counter_trade}"]
                            get_trade["status"] = False
                            get_trade["trade_type"] = "buy"
                    
                    elif order_counter_type == "buy":
                        if current_price < stop_loss:
                            get_trade = con_trade[f"v{v_counter_trade}"]
                            get_trade["status"] = False
                            get_trade["trade_type"] = "sell"
                
                # Handle sell scenario
                elif order_type == "sell":
                    if order_counter_type == "buy":
                        if current_price > current_market_price:
                            get_trade = con_trade[f"v{v_counter_trade}"]
                            get_trade["status"] = False
                            get_trade["trade_type"] = "sell"
                    
                    elif order_counter_type == "sell":
                        if current_price < stop_loss:
                            open_trade_bool = True
                            get_trade = con_trade[f"v{v_counter_trade}"]
                            get_trade["status"] = False
                            get_trade["trade_type"] = "buy"
                
                # Sleep to avoid excessive API calls
                time.sleep(1)
                
            except Exception as e:
                log_error(f"Error in contingency loop: {str(e)}")
                time.sleep(5)  # Wait a bit longer on error
    
    except Exception as e:
        log_error(f"Error in monitor_trade: {str(e)}")
        return 0 