"""
Trade execution module
"""
import math
import time
import MetaTrader5 as mt5
import numpy as np
import os
import sys
import traceback
from datetime import datetime
from mario_trader.utils.mt5_handler import (
    fetch_data, get_balance, get_contract_size, open_trade, initialize_mt5, shutdown_mt5,
    get_current_price, close_trade
)
from mario_trader.strategies.signal import generate_signal
from mario_trader.strategies.monitor import monitor_trade
from mario_trader.indicators.technical import calculate_indicators, detect_support_resistance, find_nearest_level
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
        # Always enable contingency plan
        TRADING_SETTINGS["contingency_plan"]["enabled"] = True
        
        # Get current market data
        dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
        if dfs is None:
            logger.error(f"Failed to fetch data for {forex_pair}")
            return False
            
        # Calculate indicators
        dfs = calculate_indicators(dfs)
        latest = dfs.iloc[-1]
        
        # Get current market price and indicators
        current_market_price = latest['close']
        sma_21 = latest['21_SMA']
        sma_50 = latest['50_SMA']
        sma_200 = latest['200_SMA']
        rsi = latest['RSI']
        
        # Calculate distance from entry to 21 SMA for stop loss and take profit
        stop_loss_distance_points = abs(current_market_price - sma_21)
        
        # Generate trading signal
        signal, stop_loss, current_market_price = generate_signal(dfs, forex_pair, TRADING_SETTINGS["debug_mode"])
        if signal == 0:
            logger.info(f"No trading signal for {forex_pair}")
            return False
            
        # Calculate lot size based on risk management
        lot_size = calculate_lot_size(forex_pair, stop_loss_distance_points)
        if lot_size <= 0:
            logger.error(f"Invalid lot size calculated for {forex_pair}")
            return False
            
        # Execute trade
        if signal == 1:  # BUY
            # Execute market BUY order at current price
            trade_result = open_buy_trade_without_sl(forex_pair, lot_size)
            
            if trade_result:
                # Calculate take profit at 2× the distance from entry to 21 SMA
                take_profit_distance = stop_loss_distance_points * 2
                take_profit_price = current_market_price + take_profit_distance
                
                # Set take profit for the main position
                modify_position_sl_tp(forex_pair, trade_result.order, take_profit=take_profit_price)
                
                # Set sell stop at 21 SMA with 2x initial lot size
                contingency_lot_size = lot_size * 2
                logger.info(f"Setting SELL STOP at 21 SMA ({sma_21:.5f}) with {contingency_lot_size:.2f} lots for {forex_pair}")
                
                # Calculate stop loss and take profit for the SELL STOP order
                # For SELL STOP triggered when price falls to 21 SMA:
                # - Stop loss is 3× the distance from 21 SMA to entry, above 21 SMA (in the losing direction)
                # - Take profit is 2× the distance from 21 SMA to entry, below 21 SMA (in the profit direction)
                stop_loss_price_for_sell_stop = sma_21 + (stop_loss_distance_points * 3)
                take_profit_price_for_sell_stop = sma_21 - (stop_loss_distance_points * 2)
                
                # Set pending order with stop loss and take profit
                set_pending_order(
                    forex_pair, 
                    "SELL_STOP", 
                    sma_21, 
                    contingency_lot_size,
                    comment="Contingency SELL STOP",
                    stop_loss=stop_loss_price_for_sell_stop,
                    take_profit=take_profit_price_for_sell_stop
                )
                
                # Store info for step 2 in settings
                TRADING_SETTINGS[f"{forex_pair}_contingency"] = {
                    "type": "BUY",
                    "initial_entry": current_market_price,
                    "initial_lot_size": lot_size,
                    "step": 1,
                    "sma_21": sma_21,
                    "take_profit": take_profit_price,
                    "entry_to_sma_distance": stop_loss_distance_points
                }
                
                # Log additional information
                logger.info(f"BUY order executed for {forex_pair} at {current_market_price}, Lot size: {lot_size}")
                logger.info(f"Take profit set at: {take_profit_price:.5f} (2× distance to 21 SMA)")
                logger.info(f"Contingency SELL STOP at 21 SMA: {sma_21:.5f} with lot size: {contingency_lot_size:.2f}")
                logger.info(f"SELL STOP SL: {stop_loss_price_for_sell_stop:.5f}, TP: {take_profit_price_for_sell_stop:.5f}")
                
                log_trade(forex_pair, "BUY", current_market_price, lot_size, None)
                return True
                
        elif signal == -1:  # SELL
            # Execute market SELL order at current price
            trade_result = open_sell_trade_without_sl(forex_pair, lot_size)
            
            if trade_result:
                # Calculate take profit at 2× the distance from entry to 21 SMA
                take_profit_distance = stop_loss_distance_points * 2
                take_profit_price = current_market_price - take_profit_distance
                
                # Set take profit for the main position
                modify_position_sl_tp(forex_pair, trade_result.order, take_profit=take_profit_price)
                
                # Set buy stop at 21 SMA with 2x initial lot size
                contingency_lot_size = lot_size * 2
                logger.info(f"Setting BUY STOP at 21 SMA ({sma_21:.5f}) with {contingency_lot_size:.2f} lots for {forex_pair}")
                
                # Calculate stop loss and take profit for the BUY STOP order
                # For BUY STOP triggered when price rises to 21 SMA:
                # - Stop loss is 3× the distance from 21 SMA to entry, below 21 SMA (in the losing direction)
                # - Take profit is 2× the distance from 21 SMA to entry, above 21 SMA (in the profit direction)
                stop_loss_price_for_buy_stop = sma_21 - (stop_loss_distance_points * 3)
                take_profit_price_for_buy_stop = sma_21 + (stop_loss_distance_points * 2)
                
                # Set pending order with stop loss and take profit
                set_pending_order(
                    forex_pair, 
                    "BUY_STOP", 
                    sma_21, 
                    contingency_lot_size,
                    comment="Contingency BUY STOP",
                    stop_loss=stop_loss_price_for_buy_stop,
                    take_profit=take_profit_price_for_buy_stop
                )
                
                # Store info for step 2 in settings
                TRADING_SETTINGS[f"{forex_pair}_contingency"] = {
                    "type": "SELL",
                    "initial_entry": current_market_price,
                    "initial_lot_size": lot_size,
                    "step": 1,
                    "sma_21": sma_21,
                    "take_profit": take_profit_price,
                    "entry_to_sma_distance": stop_loss_distance_points
                }
                
                # Log additional information
                logger.info(f"SELL order executed for {forex_pair} at {current_market_price}, Lot size: {lot_size}")
                logger.info(f"Take profit set at: {take_profit_price:.5f} (2× distance to 21 SMA)")
                logger.info(f"Contingency BUY STOP at 21 SMA: {sma_21:.5f} with lot size: {contingency_lot_size:.2f}")
                logger.info(f"BUY STOP SL: {stop_loss_price_for_buy_stop:.5f}, TP: {take_profit_price_for_buy_stop:.5f}")
                
                log_trade(forex_pair, "SELL", current_market_price, lot_size, None)
                return True
        
        logger.warning(f"Failed to execute {signal_type} trade for {forex_pair}")
        return False
        
    except Exception as e:
        logger.error(f"Error executing trading strategy for {forex_pair}: {e}")
        logger.error(traceback.format_exc())
        return False

def check_exit_conditions(forex_pair, dfs, open_positions, support_resistance_levels=None):
    """
    Check if we should exit existing positions based on:
    1. RSI divergence when in profit
    2. Price reaching support/resistance levels when in profit
    3. Trailing stop loss at support/resistance levels
    
    Args:
        forex_pair: Currency pair symbol
        dfs: DataFrame with price data and indicators
        open_positions: List of open positions
        support_resistance_levels: Support and resistance levels
        
    Returns:
        (should_exit, reason): Tuple with exit decision and reason
    """
    if not open_positions:
        return False, ""
    
    # Get current price and indicators
    latest = dfs.iloc[-1]
    current_price = latest['close']
    
    # Check each position
    for position in open_positions:
        position_type = "BUY" if position.type == 0 else "SELL"
        entry_price = position.price_open
        position_ticket = position.ticket
        
        # Calculate current profit in pips
        pip_multiplier = 10000.0 if not forex_pair.endswith('JPY') else 100.0
        current_profit_pips = (current_price - entry_price) * pip_multiplier if position_type == "BUY" else (entry_price - current_price) * pip_multiplier
        
        # Check if in profit
        is_in_profit = current_profit_pips > 0
        
        # Get current stop loss
        current_sl = position.sl
        
        # For BUY positions
        if position_type == "BUY":
            # Find nearest support level below current price
            if support_resistance_levels and len(support_resistance_levels['support']) > 0:
                nearest_support = find_nearest_level(current_price, support_resistance_levels, "BUY")
                if nearest_support and nearest_support < current_price:
                    # If we have a new higher support level, update stop loss
                    if current_sl == 0 or nearest_support > current_sl:
                        logger.info(f"Updating trailing stop loss for BUY position {position_ticket} to support level: {nearest_support:.5f}")
                        modify_position_sl_tp(forex_pair, position_ticket, stop_loss=nearest_support)
                        continue
            
            # Check for RSI divergence if in profit
            if is_in_profit and check_rsi_divergence(dfs, position_type):
                logger.info(f"RSI divergence detected for BUY position {position_ticket} while in profit")
                return True, f"RSI divergence detected while in profit for BUY position"
        
        # For SELL positions
        else:  # SELL
            # Find nearest resistance level above current price
            if support_resistance_levels and len(support_resistance_levels['resistance']) > 0:
                nearest_resistance = find_nearest_level(current_price, support_resistance_levels, "SELL")
                if nearest_resistance and nearest_resistance > current_price:
                    # If we have a new lower resistance level, update stop loss
                    if current_sl == 0 or nearest_resistance < current_sl:
                        logger.info(f"Updating trailing stop loss for SELL position {position_ticket} to resistance level: {nearest_resistance:.5f}")
                        modify_position_sl_tp(forex_pair, position_ticket, stop_loss=nearest_resistance)
                        continue
            
            # Check for RSI divergence if in profit
            if is_in_profit and check_rsi_divergence(dfs, position_type):
                logger.info(f"RSI divergence detected for SELL position {position_ticket} while in profit")
                return True, f"RSI divergence detected while in profit for SELL position"
        
        # Check if price has returned to the latest support/resistance level
        if support_resistance_levels:
            if position_type == "BUY":
                # For BUY, check if price has returned to support
                nearest_support = find_nearest_level(current_price, support_resistance_levels, "BUY")
                if nearest_support and abs(current_price - nearest_support) < 0.0005:  # Within 5 pips
                    logger.info(f"BUY position {position_ticket} price has returned to support level: {nearest_support:.5f}")
                    return True, f"BUY position price has returned to support level: {nearest_support:.5f}"
            else:  # SELL
                # For SELL, check if price has returned to resistance
                nearest_resistance = find_nearest_level(current_price, support_resistance_levels, "SELL")
                if nearest_resistance and abs(current_price - nearest_resistance) < 0.0005:  # Within 5 pips
                    logger.info(f"SELL position {position_ticket} price has returned to resistance level: {nearest_resistance:.5f}")
                    return True, f"SELL position price has returned to resistance level: {nearest_resistance:.5f}"
    
    return False, ""

def check_rsi_divergence(dfs, position_type):
    """
    Check for RSI divergence:
    - For BUY: Price making higher highs but RSI making lower highs
    - For SELL: Price making lower lows but RSI making higher lows
    
    Args:
        dfs: DataFrame with price data and indicators
        position_type: "BUY" or "SELL"
        
    Returns:
        True if divergence is detected, False otherwise
    """
    # Need at least 5 candles to detect divergence
    if len(dfs) < 5:
        return False
    
    # Check last 5 candles for divergence
    last_candles = dfs.iloc[-5:].copy()
    
    if position_type == "BUY":
        # Look for bearish divergence (price higher high, RSI lower high)
        # First, check if price is making higher highs
        price_higher_high = last_candles['high'].iloc[-1] > last_candles['high'].iloc[-3]
        
        # Now check if RSI is making lower highs
        rsi_lower_high = last_candles['RSI'].iloc[-1] < last_candles['RSI'].iloc[-3]
        
        # Return True if both conditions are met (bearish divergence)
        return price_higher_high and rsi_lower_high
    else:  # SELL
        # Look for bullish divergence (price lower low, RSI higher low)
        # First, check if price is making lower lows
        price_lower_low = last_candles['low'].iloc[-1] < last_candles['low'].iloc[-3]
        
        # Now check if RSI is making higher lows
        rsi_higher_low = last_candles['RSI'].iloc[-1] > last_candles['RSI'].iloc[-3]
        
        # Return True if both conditions are met (bullish divergence)
        return price_lower_low and rsi_higher_low

def apply_contingency_plan(forex_pair, closed_positions, latest_indicators):
    """
    Apply the contingency plan after closing profitable positions:
    
    For BUY:
    1. Set sell stop at 21 SMA with 2x initial lot size
    2. If activated, set buy limit at initial entry with 3x initial lot size
    
    For SELL:
    1. Set buy stop at 21 SMA with 2x initial lot size
    2. If activated, set sell limit at initial entry with 3x initial lot size
    
    Args:
        forex_pair: Currency pair symbol
        closed_positions: List of positions that were closed
        latest_indicators: Latest indicators
    """
    try:
        if not closed_positions:
            return
        
        # Get the first closed position to determine position type
        position = closed_positions[0]
        position_type = "BUY" if position.type == 0 else "SELL"
        initial_entry_price = position.price_open
        initial_lot_size = position.volume
        
        # Get the 21 SMA value
        sma_21 = latest_indicators['21_SMA']
        
        # Contingency plan
        if position_type == "BUY":
            # Step 1: Set sell stop at 21 SMA with 2x initial lot size
            contingency_lot_size = initial_lot_size * 2
            logger.info(f"Setting SELL STOP at 21 SMA ({sma_21:.5f}) with {contingency_lot_size:.2f} lots for {forex_pair}")
            
            # Set pending order
            set_pending_order(
                forex_pair, 
                "SELL_STOP", 
                sma_21, 
                contingency_lot_size,
                comment="Contingency SELL STOP"
            )
            
            # Store info for step 2 in settings
            TRADING_SETTINGS[f"{forex_pair}_contingency"] = {
                "type": "BUY",
                "initial_entry": initial_entry_price,
                "initial_lot_size": initial_lot_size,
                "step": 1
            }
            
        else:  # SELL position
            # Step 1: Set buy stop at 21 SMA with 2x initial lot size
            contingency_lot_size = initial_lot_size * 2
            logger.info(f"Setting BUY STOP at 21 SMA ({sma_21:.5f}) with {contingency_lot_size:.2f} lots for {forex_pair}")
            
            # Set pending order
            set_pending_order(
                forex_pair, 
                "BUY_STOP", 
                sma_21, 
                contingency_lot_size,
                comment="Contingency BUY STOP"
            )
            
            # Store info for step 2 in settings
            TRADING_SETTINGS[f"{forex_pair}_contingency"] = {
                "type": "SELL",
                "initial_entry": initial_entry_price,
                "initial_lot_size": initial_lot_size,
                "step": 1
            }
            
    except Exception as e:
        logger.error(f"Error applying contingency plan for {forex_pair}: {e}")
        logger.error(traceback.format_exc())

def set_pending_order(forex_pair, order_type, price, lot_size, comment="", stop_loss=None, take_profit=None):
    """
    Set a pending order
    
    Args:
        forex_pair: Currency pair symbol
        order_type: "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"
        price: Price level for the pending order
        lot_size: Lot size for the order
        comment: Comment for the order
        stop_loss: Stop loss level (optional)
        take_profit: Take profit level (optional)
        
    Returns:
        True if order was placed successfully, False otherwise
    """
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return False
        
        # Map order type to MT5 constants
        order_type_map = {
            "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
            "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
            "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
            "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP
        }
        
        if order_type not in order_type_map:
            logger.error(f"Invalid order type: {order_type}")
            return False
        
        # Get symbol info
        symbol_info = mt5.symbol_info(forex_pair)
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {forex_pair}")
            return False
        
        # Make sure the symbol is available
        if not symbol_info.visible:
            logger.info(f"Symbol {forex_pair} is not visible, trying to switch on")
            if not mt5.symbol_select(forex_pair, True):
                logger.error(f"Failed to select symbol {forex_pair}")
                return False
        
        # Define order parameters
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": forex_pair,
            "volume": lot_size,
            "type": order_type_map[order_type],
            "price": price,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,  # Good Till Cancelled
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Add stop loss if provided
        if stop_loss is not None:
            request["sl"] = stop_loss
            
        # Add take profit if provided
        if take_profit is not None:
            request["tp"] = take_profit
        
        # Send the order
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to place {order_type} order for {forex_pair}: {result.comment}")
            return False
        
        # Log the information about the placed order
        order_info = f"{order_type} order for {forex_pair} at {price}, lot size: {lot_size}"
        if stop_loss is not None:
            order_info += f", SL: {stop_loss}"
        if take_profit is not None:
            order_info += f", TP: {take_profit}"
            
        logger.info(f"Successfully placed {order_info}")
        return True
        
    except Exception as e:
        logger.error(f"Error setting pending order for {forex_pair}: {e}")
        logger.error(traceback.format_exc())
        return False

def check_pending_orders(forex_pair):
    """
    Check for pending orders and handle step 2 of contingency plan if needed
    
    Args:
        forex_pair: Currency pair symbol
    """
    try:
        import MetaTrader5 as mt5
        
        # Skip if no contingency plan is active
        contingency_key = f"{forex_pair}_contingency"
        if contingency_key not in TRADING_SETTINGS:
            return
        
        contingency = TRADING_SETTINGS[contingency_key]
        
        # Check if we're still in step 1 (waiting for stop order to be triggered)
        if contingency["step"] != 1:
            return
        
        # Get open positions to see if step 1 stop order was triggered
        positions = get_open_positions(forex_pair)
        
        # If no positions, step 1 order wasn't triggered yet or was already closed
        if not positions:
            return
        
        # Check if the position matches our expected contingency position
        # (in opposite direction of original position)
        expected_position_type = 1 if contingency["type"] == "BUY" else 0  # 0=buy, 1=sell
        matching_positions = [p for p in positions if p.type == expected_position_type]
        
        if not matching_positions:
            return
        
        # Step 1 order was triggered, move to step 2
        contingency["step"] = 2
        TRADING_SETTINGS[contingency_key] = contingency
        
        initial_entry = contingency["initial_entry"]
        initial_lot_size = contingency["initial_lot_size"]
        sma_21 = contingency["sma_21"]
        
        # Get the entry to SMA distance from settings
        entry_to_sma_distance = contingency.get("entry_to_sma_distance", abs(initial_entry - sma_21))
        
        # Get the matching position
        position = matching_positions[0]
        position_ticket = position.ticket
        
        # For the newly activated position from the stop order, calculate 3x stop loss 
        # and 2x take profit based on distance from entry to 21 SMA
        entry_to_sma_distance = abs(initial_entry - sma_21)
        
        # Calculate and set stop loss and take profit for the newly activated position
        if contingency["type"] == "BUY":
            # For original BUY, we now have a SELL position
            # Set stop loss at 3x distance above entry in the losing direction (above)
            stop_loss_price = position.price_open + (entry_to_sma_distance * 3)
            # Set take profit at 2x distance below entry in the profitable direction (below)
            take_profit_price = position.price_open - (entry_to_sma_distance * 2)
            
            # Modify the position to add SL/TP
            modify_position_sl_tp(forex_pair, position_ticket, stop_loss_price, take_profit_price)
            logger.info(f"Modified SELL position {position_ticket}: SL={stop_loss_price:.5f}, TP={take_profit_price:.5f}")
            
            # Find and modify the original BUY position to set its stop loss at the contingency's take profit
            original_buy_positions = [p for p in positions if p.type == 0]  # 0=buy
            if original_buy_positions:
                original_buy = original_buy_positions[0]
                modify_position_sl_tp(forex_pair, original_buy.ticket, stop_loss=take_profit_price)
                logger.info(f"Modified original BUY position {original_buy.ticket}: SL={take_profit_price:.5f} (contingency TP)")
            
            # Step 2: Place BUY LIMIT at initial entry with 3x initial lot size
            contingency_lot_size = initial_lot_size * 3
            
            # Calculate stop loss and take profit for the BUY LIMIT order
            # For BUY LIMIT triggered when price returns to initial entry:
            # - Stop loss is at the 21 SMA (below entry)
            # - Take profit is 2× the distance from entry to 21 SMA (above entry)
            buy_limit_sl = sma_21
            buy_limit_tp = initial_entry + (entry_to_sma_distance * 2)
            
            logger.info(f"Setting BUY LIMIT at initial entry ({initial_entry:.5f}) with {contingency_lot_size:.2f} lots for {forex_pair}")
            
            set_pending_order(
                forex_pair, 
                "BUY_LIMIT", 
                initial_entry, 
                contingency_lot_size,
                comment="Contingency BUY LIMIT",
                stop_loss=buy_limit_sl,
                take_profit=buy_limit_tp
            )
        else:  # SELL position
            # For original SELL, we now have a BUY position
            # Set stop loss at 3x distance below entry in the losing direction (below)
            stop_loss_price = position.price_open - (entry_to_sma_distance * 3)
            # Set take profit at 2x distance above entry in the profitable direction (above)
            take_profit_price = position.price_open + (entry_to_sma_distance * 2)
            
            # Modify the position to add SL/TP
            modify_position_sl_tp(forex_pair, position_ticket, stop_loss_price, take_profit_price)
            logger.info(f"Modified BUY position {position_ticket}: SL={stop_loss_price:.5f}, TP={take_profit_price:.5f}")
            
            # Find and modify the original SELL position to set its stop loss at the contingency's take profit
            original_sell_positions = [p for p in positions if p.type == 1]  # 1=sell
            if original_sell_positions:
                original_sell = original_sell_positions[0]
                modify_position_sl_tp(forex_pair, original_sell.ticket, stop_loss=take_profit_price)
                logger.info(f"Modified original SELL position {original_sell.ticket}: SL={take_profit_price:.5f} (contingency TP)")
            
            # Step 2: Place SELL LIMIT at initial entry with 3x initial lot size
            contingency_lot_size = initial_lot_size * 3
            
            # Calculate stop loss and take profit for the SELL LIMIT order
            # For SELL LIMIT triggered when price returns to initial entry:
            # - Stop loss is at the 21 SMA (above entry)
            # - Take profit is 2× the distance from entry to 21 SMA (below entry)
            sell_limit_sl = sma_21
            sell_limit_tp = initial_entry - (entry_to_sma_distance * 2)
            
            logger.info(f"Setting SELL LIMIT at initial entry ({initial_entry:.5f}) with {contingency_lot_size:.2f} lots for {forex_pair}")
            
            set_pending_order(
                forex_pair, 
                "SELL_LIMIT", 
                initial_entry, 
                contingency_lot_size,
                comment="Contingency SELL LIMIT",
                stop_loss=sell_limit_sl,
                take_profit=sell_limit_tp
            )
            
        # Update contingency info for the next stage
        TRADING_SETTINGS[contingency_key].update({
            "step": 2,
            "total_trades": 2,  # Initial trade + stop order
            "total_lot_size": initial_lot_size + (initial_lot_size * 2)  # Initial + contingency so far
        })
        
    except Exception as e:
        logger.error(f"Error checking pending orders for {forex_pair}: {e}")
        logger.error(traceback.format_exc())

def close_all_positions(forex_pair):
    """
    Close all open positions for a currency pair
    
    Args:
        forex_pair: Currency pair symbol
        
    Returns:
        True if all positions were closed successfully, False otherwise
    """
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return False
        
        positions = get_open_positions(forex_pair)
        if not positions:
            logger.info(f"No open positions for {forex_pair}")
            return True
        
        all_closed = True
        for position in positions:
            # Determine position type (buy or sell)
            position_type = mt5.POSITION_TYPE_BUY if position.type == 0 else mt5.POSITION_TYPE_SELL
            
            # Set action type to opposite of position type
            action_type = mt5.ORDER_TYPE_SELL if position_type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # Get symbol info
            symbol_info = mt5.symbol_info(forex_pair)
            if symbol_info is None:
                logger.error(f"Failed to get symbol info for {forex_pair}")
                all_closed = False
                continue
            
            # Request close
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": forex_pair,
                "volume": position.volume,
                "type": action_type,
                "position": position.ticket,
                "comment": "Close position",
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            # Use current bid/ask price for closing
            if action_type == mt5.ORDER_TYPE_SELL:
                request["price"] = mt5.symbol_info_tick(forex_pair).bid
            else:
                request["price"] = mt5.symbol_info_tick(forex_pair).ask
                
            # Send the order
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to close position {position.ticket} for {forex_pair}: {result.comment}")
                all_closed = False
            else:
                logger.info(f"Successfully closed position {position.ticket} for {forex_pair}")
        
        return all_closed
        
    except Exception as e:
        logger.error(f"Error closing positions for {forex_pair}: {e}")
        logger.error(traceback.format_exc())
        return False

def execute_multiple_pairs(login=None, password=None, server=None, interval=60):
    """
    Execute trading strategy for multiple currency pairs
    
    Args:
        login: MT5 account login
        password: MT5 account password
        server: MT5 server name
        interval: Interval between trades in seconds
    """
    # Initialize MT5
    if not login_trading(login, password, server):
        logger.error("Failed to login to MT5")
        return False
    
    # Load currency pairs
    pairs = load_currency_pairs()
    if not pairs:
        logger.error("No currency pairs available")
        return False
    
    logger.info(f"Starting trading for {len(pairs)} currency pairs")
    logger.info(f"Trading interval: {interval} seconds")
    
    try:
        while True:
            for pair in pairs:
                try:
                    logger.info(f"Processing {pair}")
                    
                    # Check pending orders first (for contingency plan)
                    check_pending_orders(pair)
                    
                    # Execute trading strategy
                    execute(pair)
                    
                    # Sleep briefly to avoid rate limits
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing {pair}: {e}")
                    logger.error(traceback.format_exc())
                    # Continue with next pair instead of stopping the entire bot
                    continue
            
            logger.info(f"Completed cycle for all pairs, sleeping for {interval} seconds")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("Trading stopped by user")
        return True
    except Exception as e:
        logger.error(f"Error in multi-pair trading: {e}")
        logger.error(traceback.format_exc())
        return False

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
            # Check pending orders and manage contingency plan
            check_pending_orders(currency_pair)
            
            # Execute trading strategy
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

def get_open_positions(forex_pair):
    """
    Get all open positions for a currency pair
    
    Args:
        forex_pair: Currency pair symbol
        
    Returns:
        List of open positions or empty list if none
    """
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return []
        
        # Get all open positions
        positions = mt5.positions_get(symbol=forex_pair)
        if positions is None:
            error = mt5.last_error()
            if error[0] != 0:
                logger.error(f"Failed to get positions for {forex_pair}: {error}")
            return []
        
        # Convert to list if needed
        positions_list = list(positions)
        logger.debug(f"Found {len(positions_list)} open positions for {forex_pair}")
        return positions_list
        
    except Exception as e:
        logger.error(f"Error getting open positions for {forex_pair}: {e}")
        logger.error(traceback.format_exc())
        return []

def calculate_lot_size(forex_pair, stop_loss_distance_points):
    """
    Calculate proper lot size based on risk management
    
    Formula:
    Lot Size = Account Risk Amount / (Stop Loss in Pips * Pip Value)
    
    Args:
        forex_pair: Currency pair symbol
        stop_loss_distance_points: Distance from entry to stop loss in price points
        
    Returns:
        Lot size based on risk management
    """
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return 0.01  # Default minimum lot size
        
        # Get account info and symbol info
        account_info = mt5.account_info()
        if account_info is None:
            logger.error(f"Failed to get account info: {mt5.last_error()}")
            return 0.01
        
        symbol_info = mt5.symbol_info(forex_pair)
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {forex_pair}: {mt5.last_error()}")
            return 0.01
        
        # Get current price (average of bid/ask)
        symbol_tick = mt5.symbol_info_tick(forex_pair)
        if symbol_tick is None:
            logger.error(f"Failed to get symbol tick for {forex_pair}: {mt5.last_error()}")
            return 0.01
        
        current_price = (symbol_tick.bid + symbol_tick.ask) / 2
        
        # Get risk percentage from settings (default 2%)
        risk_percentage = TRADING_SETTINGS.get("risk_percentage", 0.02)
        
        # Calculate account risk amount
        account_balance = account_info.balance
        account_risk_amount = account_balance * risk_percentage
        logger.debug(f"Account balance: {account_balance}, Risk amount: {account_risk_amount}")
        
        # Apply a minimum stop loss distance to prevent excessive lot sizes
        # Typically 10 pips (0.0010) for most pairs, 100 pips (0.01) for JPY pairs
        min_stop_loss_distance = 0.0010
        if forex_pair.endswith('JPY'):
            min_stop_loss_distance = 0.01
        
        # Apply the minimum stop loss distance if the current distance is too small
        if stop_loss_distance_points < min_stop_loss_distance:
            logger.warning(f"Stop loss distance ({stop_loss_distance_points:.5f}) is too small, using minimum ({min_stop_loss_distance:.5f})")
            stop_loss_distance_points = min_stop_loss_distance
        
        # Determine pip value based on currency pair
        one_pip_movement = 0.01 if forex_pair.endswith('JPY') else 0.0001
        
        # Convert point distance to pip distance
        if not forex_pair.endswith('JPY') and symbol_info.digits == 5:  # 5-digit broker for non-JPY pairs
            pip_multiplier = 0.1  # 1 pip = 10 points
        elif forex_pair.endswith('JPY') and symbol_info.digits == 3:  # 3-digit broker for JPY pairs
            pip_multiplier = 0.1  # 1 pip = 10 points
        else:
            pip_multiplier = 1.0  # 1 pip = 1 point (standard 4-digit broker)
        
        stop_loss_in_pips = stop_loss_distance_points / pip_multiplier
        
        # Ensure stop_loss_in_pips is not zero to avoid division by zero
        if stop_loss_in_pips <= 0:
            logger.warning(f"Stop loss in pips is {stop_loss_in_pips}, using minimum 10 pips")
            stop_loss_in_pips = 10.0
        
        # Calculate pip value (monetary value of 1 pip for 1 standard lot)
        # Formula: (one_pip / exchange_rate) * lot_size
        standard_lot = 100000.0  # 1 standard lot
        
        # For pairs where account currency is the base currency (e.g., USD/xxx for USD account)
        # Pip value is fixed (10 USD per pip for 1 standard lot for USD account)
        account_currency = account_info.currency
        
        # Determine if the account currency is the base or quote currency of the pair
        base_currency = forex_pair[:3]
        quote_currency = forex_pair[3:]
        
        if account_currency == quote_currency:
            # For pairs like xxx/USD for USD account
            pip_value_per_lot = one_pip_movement * standard_lot  # Direct calculation
        else:
            # For pairs like xxx/yyy for USD account (neither base nor quote is account currency)
            # or for pairs like USD/yyy for USD account (account currency is base)
            pip_value_per_lot = (one_pip_movement / current_price) * standard_lot
            
            # If account currency is not part of the pair, need to convert using another rate
            if account_currency != base_currency and account_currency != quote_currency:
                # Try to find a conversion rate (e.g., via USD/account_currency)
                # This is simplified - in a real system you'd lookup the actual conversion rate
                conversion_pair = f"{account_currency}USD"
                conversion_tick = mt5.symbol_info_tick(conversion_pair)
                if conversion_tick is not None:
                    conversion_rate = (conversion_tick.bid + conversion_tick.ask) / 2
                    pip_value_per_lot *= conversion_rate
        
        # Calculate lot size based on risk amount
        lot_size = account_risk_amount / (stop_loss_in_pips * pip_value_per_lot)
        
        # Apply maximum lot size restriction (20% of account balance at max)
        account_equity = account_info.equity
        max_lot_size_by_balance = account_equity / (current_price * 100) * 0.2  # 20% of equity in standard lots
        
        # Also respect broker's max lot size
        max_lot_size = min(symbol_info.volume_max, max_lot_size_by_balance)
        
        # Ensure lot size is within allowed range
        min_lot_size = symbol_info.volume_min
        lot_size = max(min(lot_size, max_lot_size), min_lot_size)
        
        # Round to nearest allowed lot step
        lot_step = symbol_info.volume_step
        lot_size = round(lot_size / lot_step) * lot_step
        
        logger.info(f"Calculated lot size: {lot_size:.2f}, Stop loss distance: {stop_loss_in_pips:.1f} pips")
        return lot_size
        
    except Exception as e:
        logger.error(f"Error calculating lot size for {forex_pair}: {e}")
        logger.error(traceback.format_exc())
        return 0.01  # Default to minimum lot size

def open_buy_trade_without_sl(forex_pair, lot_size):
    """
    Open a BUY trade without a stop loss
    
    Args:
        forex_pair: Currency pair symbol
        lot_size: Lot size for the trade
        
    Returns:
        Order result if trade was successfully opened, False otherwise
    """
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return False
        
        # Get symbol info
        symbol_info = mt5.symbol_info(forex_pair)
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {forex_pair}")
            return False
        
        # Make sure the symbol is available
        if not symbol_info.visible:
            logger.info(f"Symbol {forex_pair} is not visible, trying to switch on")
            if not mt5.symbol_select(forex_pair, True):
                logger.error(f"Failed to select symbol {forex_pair}")
                return False
        
        # Get current price
        symbol_tick = mt5.symbol_info_tick(forex_pair)
        if symbol_tick is None:
            logger.error(f"Failed to get symbol tick for {forex_pair}")
            return False
        
        # Define trade request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": forex_pair,
            "volume": lot_size,
            "type": mt5.ORDER_TYPE_BUY,
            "price": symbol_tick.ask,  # Buy at ask price
            "deviation": 10,  # Allow price deviation in points
            "magic": 234000,  # Magic number to identify trades
            "comment": "Mario Trader",
            "type_time": mt5.ORDER_TIME_GTC,  # Good Till Cancelled
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send the order
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to place BUY order for {forex_pair}: {result.comment}")
            return False
        
        logger.info(f"Successfully opened BUY trade for {forex_pair}, ticket: {result.order}")
        return result
        
    except Exception as e:
        logger.error(f"Error opening BUY trade for {forex_pair}: {e}")
        logger.error(traceback.format_exc())
        return False

def open_sell_trade_without_sl(forex_pair, lot_size):
    """
    Open a SELL trade without a stop loss
    
    Args:
        forex_pair: Currency pair symbol
        lot_size: Lot size for the trade
        
    Returns:
        Order result if trade was successfully opened, False otherwise
    """
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return False
        
        # Get symbol info
        symbol_info = mt5.symbol_info(forex_pair)
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {forex_pair}")
            return False
        
        # Make sure the symbol is available
        if not symbol_info.visible:
            logger.info(f"Symbol {forex_pair} is not visible, trying to switch on")
            if not mt5.symbol_select(forex_pair, True):
                logger.error(f"Failed to select symbol {forex_pair}")
                return False
        
        # Get current price
        symbol_tick = mt5.symbol_info_tick(forex_pair)
        if symbol_tick is None:
            logger.error(f"Failed to get symbol tick for {forex_pair}")
            return False
        
        # Define trade request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": forex_pair,
            "volume": lot_size,
            "type": mt5.ORDER_TYPE_SELL,
            "price": symbol_tick.bid,  # Sell at bid price
            "deviation": 10,  # Allow price deviation in points
            "magic": 234000,  # Magic number to identify trades
            "comment": "Mario Trader",
            "type_time": mt5.ORDER_TIME_GTC,  # Good Till Cancelled
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send the order
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to place SELL order for {forex_pair}: {result.comment}")
            return False
        
        logger.info(f"Successfully opened SELL trade for {forex_pair}, ticket: {result.order}")
        return result
        
    except Exception as e:
        logger.error(f"Error opening SELL trade for {forex_pair}: {e}")
        logger.error(traceback.format_exc())
        return False

def log_trade(forex_pair, action, price, lot_size, stop_loss):
    """
    Log a trade for record keeping
    
    Args:
        forex_pair: Currency pair symbol
        action: BUY or SELL
        price: Entry price
        lot_size: Lot size for the trade
        stop_loss: Stop loss price
    """
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create trades directory if it doesn't exist
        trades_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "trades")
        os.makedirs(trades_dir, exist_ok=True)
        
        # Create or append to the trades log file
        trades_file = os.path.join(trades_dir, f"{forex_pair}_trades.csv")
        file_exists = os.path.isfile(trades_file)
        
        with open(trades_file, "a") as f:
            if not file_exists:
                # Write the header row
                f.write("Time,Pair,Action,Price,LotSize,StopLoss\n")
            
            # Write the trade record
            f.write(f"{current_time},{forex_pair},{action},{price},{lot_size},{stop_loss}\n")
        
        logger.info(f"Trade logged: {action} {forex_pair} at {price}, Lot: {lot_size}, SL: {stop_loss}")
    
    except Exception as e:
        logger.error(f"Error logging trade: {e}")
        logger.error(traceback.format_exc())

def modify_position_sl_tp(forex_pair, position_ticket, stop_loss=None, take_profit=None):
    """
    Modify an existing position to set stop loss and take profit
    
    Args:
        forex_pair: Currency pair symbol
        position_ticket: Ticket number of the position
        stop_loss: Stop loss price level (None to leave unchanged)
        take_profit: Take profit price level (None to leave unchanged)
        
    Returns:
        True if modification was successful, False otherwise
    """
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return False
        
        # Get the position details
        position = mt5.positions_get(ticket=position_ticket)
        if position is None or len(position) == 0:
            logger.error(f"Failed to get position {position_ticket} for {forex_pair}")
            return False
        
        # Get current position details
        position = position[0]
        
        # Prepare modification request
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": forex_pair,
            "position": position_ticket,
            "magic": position.magic
        }
        
        # Set stop loss if provided
        if stop_loss is not None:
            request["sl"] = stop_loss
        
        # Set take profit if provided
        if take_profit is not None:
            request["tp"] = take_profit
        
        # Send the modification request
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to modify position {position_ticket} for {forex_pair}: {result.comment}")
            return False
        
        logger.info(f"Successfully modified position {position_ticket} for {forex_pair}: SL={stop_loss}, TP={take_profit}")
        return True
        
    except Exception as e:
        logger.error(f"Error modifying position for {forex_pair}: {e}")
        logger.error(traceback.format_exc())
        return False 