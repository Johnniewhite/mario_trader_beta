"""
Trade monitoring and management
"""
import math
import time
import MetaTrader5 as mt5
from mario_trader.utils.mt5_handler import get_current_price, fetch_data, close_trade, get_balance, open_trade
from mario_trader.indicators.technical import detect_rsi_divergence, calculate_indicators
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
    Monitor an open trade and handle contingency trades if needed
    
    Args:
        order_id: Order ID
        position: Position
        volume: Trade volume
        order_type: 'buy' or 'sell'
        stop_loss: Stop loss price
        current_market_price: Current market price
        forex_pair: Currency pair symbol
    """
    try:
        logger.info(f"Monitoring trade {order_id} for {forex_pair}")
        
        # Get initial account balance
        initial_balance = get_balance()
        entry_price = current_market_price
        
        # Calculate the distance from entry point to 21 SMA
        df = fetch_data(forex_pair)
        df = calculate_indicators(df)
        latest = df.iloc[-1]
        distance_to_21_sma = abs(entry_price - latest['21_SMA'])
        
        # Initialize contingency trades dictionary
        contingency_trades = []
        contingency_status = False
        num_contingency_trades = 0
        
        # Main monitoring loop
        while True:
            try:
                current_price = get_current_price(forex_pair)
                df = fetch_data(forex_pair)
                df = calculate_indicators(df)
                latest = df.iloc[-1]
                
                # Check if account is down 20%
                current_balance = get_balance()
                balance_change_percent = ((current_balance - initial_balance) / initial_balance) * 100
                if balance_change_percent <= -20:
                    logger.warning(f"Account down 20% ({balance_change_percent:.2f}%). Closing all trades.")
                    close_trade(order_id)
                    for contingency_trade in contingency_trades:
                        if contingency_trade["ticket_id"]:
                            close_trade(contingency_trade["ticket_id"])
                    log_trade("CLOSE_ALL", forex_pair, current_price, volume, "ACCOUNT_DOWN", None)
                    break
                
                # Check if account is up 2x of the pips from entry to 21 SMA
                profit_distance = 2 * distance_to_21_sma
                if (order_type == "buy" and current_price >= entry_price + profit_distance) or \
                   (order_type == "sell" and current_price <= entry_price - profit_distance):
                    logger.info(f"Account up 2x of pips from entry to 21 SMA. Taking profit.")
                    close_trade(order_id)
                    for contingency_trade in contingency_trades:
                        if contingency_trade["ticket_id"]:
                            close_trade(contingency_trade["ticket_id"])
                    log_trade("CLOSE_ALL", forex_pair, current_price, volume, "PROFIT_TARGET", None)
                    break
                
                # Check for RSI divergence
                divergence_signal = detect_rsi_divergence(df)
                
                # Only close on RSI divergence if in profit
                if divergence_signal != 0:
                    is_in_profit = (order_type == "buy" and current_price > entry_price) or \
                                  (order_type == "sell" and current_price < entry_price)
                    
                    if is_in_profit:
                        logger.info(f"RSI divergence detected while in profit: {divergence_signal}")
                        close_trade(order_id)
                        for contingency_trade in contingency_trades:
                            if contingency_trade["ticket_id"]:
                                close_trade(contingency_trade["ticket_id"])
                        log_trade("CLOSE_ALL", forex_pair, current_price, volume, "RSI_DIVERGENCE", None)
                        break
                    else:
                        logger.info(f"RSI divergence detected but trade is in loss. Not closing.")
                
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
        
        # For buy signals
        if order_type == "buy":
            # Step 1: Set a sell stop at the 21 moving average with lot size of (initial lot size x 2)
            sell_stop_volume = volume * 2
            sell_stop_price = latest['21_SMA']
            logger.info(f"Setting sell stop at 21 SMA ({sell_stop_price}) with volume {sell_stop_volume}")
            
            # Open the sell stop order
            sell_stop_response = open_trade(forex_pair, sell_stop_volume, stop_loss, 'sell')
            if sell_stop_response:
                contingency_trades.append({
                    "ticket_id": sell_stop_response.order,
                    "trade_type": "sell",
                    "volume": sell_stop_volume,
                    "entry_price": sell_stop_price
                })
                num_contingency_trades += 1
                log_trade("CONTINGENCY", forex_pair, sell_stop_price, sell_stop_volume, "SELL", sell_stop_response.order)
                
                # Step 2: If sell stop is activated, set a buy limit at the entry point with lot size of (initial lot size x 3)
                buy_limit_volume = volume * 3
                buy_limit_price = entry_price
                logger.info(f"Setting buy limit at entry point ({buy_limit_price}) with volume {buy_limit_volume}")
                
                # Wait for the sell stop to be activated
                while True:
                    current_price = get_current_price(forex_pair)
                    if current_price <= sell_stop_price:
                        # Sell stop activated, open buy limit
                        buy_limit_response = open_trade(forex_pair, buy_limit_volume, stop_loss, 'buy')
                        if buy_limit_response:
                            contingency_trades.append({
                                "ticket_id": buy_limit_response.order,
                                "trade_type": "buy",
                                "volume": buy_limit_volume,
                                "entry_price": buy_limit_price
                            })
                            num_contingency_trades += 1
                            log_trade("CONTINGENCY", forex_pair, buy_limit_price, buy_limit_volume, "BUY", buy_limit_response.order)
                        break
                    time.sleep(1)
        
        # For sell signals
        elif order_type == "sell":
            # Step 1: Set a buy stop at the 21 moving average with lot size of (initial lot size x 2)
            buy_stop_volume = volume * 2
            buy_stop_price = latest['21_SMA']
            logger.info(f"Setting buy stop at 21 SMA ({buy_stop_price}) with volume {buy_stop_volume}")
            
            # Open the buy stop order
            buy_stop_response = open_trade(forex_pair, buy_stop_volume, stop_loss, 'buy')
            if buy_stop_response:
                contingency_trades.append({
                    "ticket_id": buy_stop_response.order,
                    "trade_type": "buy",
                    "volume": buy_stop_volume,
                    "entry_price": buy_stop_price
                })
                num_contingency_trades += 1
                log_trade("CONTINGENCY", forex_pair, buy_stop_price, buy_stop_volume, "BUY", buy_stop_response.order)
                
                # Step 2: If buy stop is activated, set a sell limit at the entry point with lot size of (initial lot size x 3)
                sell_limit_volume = volume * 3
                sell_limit_price = entry_price
                logger.info(f"Setting sell limit at entry point ({sell_limit_price}) with volume {sell_limit_volume}")
                
                # Wait for the buy stop to be activated
                while True:
                    current_price = get_current_price(forex_pair)
                    if current_price >= buy_stop_price:
                        # Buy stop activated, open sell limit
                        sell_limit_response = open_trade(forex_pair, sell_limit_volume, stop_loss, 'sell')
                        if sell_limit_response:
                            contingency_trades.append({
                                "ticket_id": sell_limit_response.order,
                                "trade_type": "sell",
                                "volume": sell_limit_volume,
                                "entry_price": sell_limit_price
                            })
                            num_contingency_trades += 1
                            log_trade("CONTINGENCY", forex_pair, sell_limit_price, sell_limit_volume, "SELL", sell_limit_response.order)
                        break
                    time.sleep(1)
        
        # Continue with contingency trading
        while num_contingency_trades < 10:  # Limit to 10 contingency trades
            try:
                current_price = get_current_price(forex_pair)
                
                # Check for any activated contingency trades
                for i, trade in enumerate(contingency_trades):
                    if trade["trade_type"] == "buy" and current_price >= trade["entry_price"]:
                        # Buy limit activated, set a sell limit at the 21 SMA
                        new_volume = volume * (num_contingency_trades + 1)
                        sell_limit_price = latest['21_SMA']
                        logger.info(f"Setting sell limit at 21 SMA ({sell_limit_price}) with volume {new_volume}")
                        
                        sell_limit_response = open_trade(forex_pair, new_volume, stop_loss, 'sell')
                        if sell_limit_response:
                            contingency_trades.append({
                                "ticket_id": sell_limit_response.order,
                                "trade_type": "sell",
                                "volume": new_volume,
                                "entry_price": sell_limit_price
                            })
                            num_contingency_trades += 1
                            log_trade("CONTINGENCY", forex_pair, sell_limit_price, new_volume, "SELL", sell_limit_response.order)
                    
                    elif trade["trade_type"] == "sell" and current_price <= trade["entry_price"]:
                        # Sell limit activated, set a buy limit at the 21 SMA
                        new_volume = volume * (num_contingency_trades + 1)
                        buy_limit_price = latest['21_SMA']
                        logger.info(f"Setting buy limit at 21 SMA ({buy_limit_price}) with volume {new_volume}")
                        
                        buy_limit_response = open_trade(forex_pair, new_volume, stop_loss, 'buy')
                        if buy_limit_response:
                            contingency_trades.append({
                                "ticket_id": buy_limit_response.order,
                                "trade_type": "buy",
                                "volume": new_volume,
                                "entry_price": buy_limit_price
                            })
                            num_contingency_trades += 1
                            log_trade("CONTINGENCY", forex_pair, buy_limit_price, new_volume, "BUY", buy_limit_response.order)
                
                # Sleep to avoid excessive API calls
                time.sleep(1)
                
            except Exception as e:
                log_error(f"Error in contingency loop: {str(e)}")
                time.sleep(5)  # Wait a bit longer on error
        
        logger.info("Contingency trading completed")
        return 0
        
    except Exception as e:
        log_error(f"Error in monitor_trade: {str(e)}")
        return -1 