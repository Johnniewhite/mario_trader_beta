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
from datetime import datetime, timedelta
from mario_trader.utils.mt5_handler import (
    fetch_data, get_balance, get_contract_size, open_trade, initialize_mt5, shutdown_mt5,
    get_current_price, close_trade
)
from mario_trader.strategies.signal import generate_signal
from mario_trader.strategies.monitor import monitor_trade
from mario_trader.indicators.technical import calculate_indicators, detect_support_resistance, find_nearest_level
from mario_trader.config import MT5_SETTINGS, TRADING_SETTINGS, ORDER_SETTINGS, GEMINI_SETTINGS
from mario_trader.utils.logger import logger, log_trade, log_signal, log_error
from mario_trader.utils.currency_pairs import load_currency_pairs, validate_currency_pair, get_default_pair
from mario_trader.utils.gemini_engine import GeminiEngine
import threading

# Initialize the Gemini Engine
gemini_engine = GeminiEngine()

# Dictionary to store last trade time for each currency pair
last_trade_time = {}

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
        
        # Check trade cooldown (minimum 1 hour between trades for the same pair)
        current_time = datetime.now()
        if forex_pair in last_trade_time:
            time_since_last_trade = current_time - last_trade_time[forex_pair]
            if time_since_last_trade < timedelta(hours=1):
                logger.info(f"Trade cooldown active for {forex_pair}. Time remaining: {timedelta(hours=1) - time_since_last_trade}")
                return False
        
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
        
        # Check if price is above 200 SMA for both buy and sell signals
        if current_market_price <= sma_200:
            logger.info(f"Price is below 200 SMA for {forex_pair}, no trade")
            return False
            
        # Check if 21 and 50 SMA are not too close (at least 10 pips apart)
        sma_distance = abs(sma_21 - sma_50)
        min_sma_distance = 0.0010 if not forex_pair.endswith('JPY') else 0.01
        if sma_distance < min_sma_distance:
            logger.info(f"21 and 50 SMA are too close for {forex_pair}, no trade")
            return False
            
        # Check for three consecutive candles in opposite direction
        # and engulfing candle in trade direction
        signal = 0
        
        # Check for BUY signal
        if rsi > 50:  # RSI above 50%
            # Check last 4 candles
            last_4_candles = dfs.iloc[-4:]
            
            # Check if last 3 candles were bearish (lower highs and lower lows)
            bearish_candles = True
            for i in range(1, 4):
                if last_4_candles.iloc[-i]['high'] >= last_4_candles.iloc[-(i+1)]['high'] or \
                   last_4_candles.iloc[-i]['low'] >= last_4_candles.iloc[-(i+1)]['low']:
                    bearish_candles = False
                    break
            
            # Check for bullish engulfing pattern
            current_candle = last_4_candles.iloc[-1]
            previous_candle = last_4_candles.iloc[-2]
            bullish_engulfing = (current_candle['close'] > previous_candle['open'] and
                               current_candle['open'] < previous_candle['close'] and
                               current_candle['close'] - current_candle['open'] > 
                               previous_candle['open'] - previous_candle['close'])
            
            if bearish_candles and bullish_engulfing:
                signal = 1
                
        # Check for SELL signal
        elif rsi < 50:  # RSI below 50%
            # Check last 4 candles
            last_4_candles = dfs.iloc[-4:]
            
            # Check if last 3 candles were bullish (higher highs and higher lows)
            bullish_candles = True
            for i in range(1, 4):
                if last_4_candles.iloc[-i]['high'] <= last_4_candles.iloc[-(i+1)]['high'] or \
                   last_4_candles.iloc[-i]['low'] <= last_4_candles.iloc[-(i+1)]['low']:
                    bullish_candles = False
                    break
            
            # Check for bearish engulfing pattern
            current_candle = last_4_candles.iloc[-1]
            previous_candle = last_4_candles.iloc[-2]
            bearish_engulfing = (current_candle['close'] < previous_candle['open'] and
                               current_candle['open'] > previous_candle['close'] and
                               current_candle['open'] - current_candle['close'] > 
                               previous_candle['close'] - previous_candle['open'])
            
            if bullish_candles and bearish_engulfing:
                signal = -1
        
        if signal == 0:
            logger.info(f"No trading signal for {forex_pair}")
            return False
            
        # Update last trade time
        last_trade_time[forex_pair] = current_time
        
        # Prepare indicator data for Gemini verification
        indicator_data = {
            "200_SMA": sma_200,
            "50_SMA": sma_50,
            "21_SMA": sma_21,
            "RSI": rsi,
        }
        
        # Use Gemini AI to verify the trade setup
        signal_type = "BUY" if signal == 1 else "SELL"
        gemini_verified, gemini_reason, gemini_confidence = gemini_engine.verify_trade_setup(
            forex_pair, 
            signal_type, 
            dfs, 
            indicator_data
        )
        
        # Check if Gemini verification is required and failed
        if GEMINI_SETTINGS["verification"]["required"] and not gemini_verified:
            logger.warning(f"Gemini rejected {signal_type} signal for {forex_pair}: {gemini_reason}")
            return False
        
        # Continue with trade execution even if Gemini rejected (but log the warning)
        if not gemini_verified:
            logger.warning(f"Proceeding with {signal_type} trade for {forex_pair} despite Gemini rejection (not required): {gemini_reason}")
            
        # Calculate lot size based on risk management
        lot_size = calculate_lot_size(forex_pair, abs(current_market_price - sma_21))
        if lot_size <= 0:
            logger.error(f"Invalid lot size calculated for {forex_pair}")
            return False
            
        # Execute trade
        if signal == 1:  # BUY
            # Execute market BUY order at current price
            trade_result = open_buy_trade_without_sl(forex_pair, lot_size)
            
            if trade_result:
                # Calculate take profit at 2× the distance from entry to 21 SMA
                take_profit_distance = abs(current_market_price - sma_21) * 2
                take_profit_price = current_market_price + take_profit_distance
                
                # Set take profit for the main position
                modify_position_sl_tp(forex_pair, trade_result.order, take_profit=take_profit_price)
                
                # Set sell stop at 21 SMA with calculated lot size
                contingency_lot_size = lot_size * 2
                logger.info(f"Setting SELL STOP at 21 SMA ({sma_21:.5f}) with {contingency_lot_size:.2f} lots for {forex_pair}")
                
                # Calculate stop loss and take profit for the SELL STOP order
                stop_loss_price_for_sell_stop = sma_21 + (abs(current_market_price - sma_21) * 3)
                take_profit_price_for_sell_stop = sma_21 - (abs(current_market_price - sma_21) * 2)
                
                set_pending_order(
                    forex_pair, 
                    "SELL_STOP", 
                    sma_21, 
                    contingency_lot_size,
                    comment="Contingency SELL STOP",
                    stop_loss=stop_loss_price_for_sell_stop,
                    take_profit=take_profit_price_for_sell_stop
                )
                
                # Store info for contingency plan
                TRADING_SETTINGS[f"{forex_pair}_contingency"] = {
                    "type": "BUY",
                    "initial_entry": current_market_price,
                    "initial_lot_size": lot_size,
                    "sma_21": sma_21,
                    "take_profit": take_profit_price,
                    "entry_to_sma_distance": abs(current_market_price - sma_21),
                    "gemini_approval": gemini_verified,
                    "gemini_confidence": gemini_confidence
                }
                
                log_trade(forex_pair, "BUY", current_market_price, lot_size, None)
                return True
                
        elif signal == -1:  # SELL
            # Execute market SELL order at current price
            trade_result = open_sell_trade_without_sl(forex_pair, lot_size)
            
            if trade_result:
                # Calculate take profit at 2× the distance from entry to 21 SMA
                take_profit_distance = abs(current_market_price - sma_21) * 2
                take_profit_price = current_market_price - take_profit_distance
                
                # Set take profit for the main position
                modify_position_sl_tp(forex_pair, trade_result.order, take_profit=take_profit_price)
                
                # Set buy stop at 21 SMA with calculated lot size
                contingency_lot_size = lot_size * 2
                logger.info(f"Setting BUY STOP at 21 SMA ({sma_21:.5f}) with {contingency_lot_size:.2f} lots for {forex_pair}")
                
                # Calculate stop loss and take profit for the BUY STOP order
                stop_loss_price_for_buy_stop = sma_21 - (abs(current_market_price - sma_21) * 3)
                take_profit_price_for_buy_stop = sma_21 + (abs(current_market_price - sma_21) * 2)
                
                set_pending_order(
                    forex_pair, 
                    "BUY_STOP", 
                    sma_21, 
                    contingency_lot_size,
                    comment="Contingency BUY STOP",
                    stop_loss=stop_loss_price_for_buy_stop,
                    take_profit=take_profit_price_for_buy_stop
                )
                
                # Store info for contingency plan
                TRADING_SETTINGS[f"{forex_pair}_contingency"] = {
                    "type": "SELL",
                    "initial_entry": current_market_price,
                    "initial_lot_size": lot_size,
                    "sma_21": sma_21,
                    "take_profit": take_profit_price,
                    "entry_to_sma_distance": abs(current_market_price - sma_21),
                    "gemini_approval": gemini_verified,
                    "gemini_confidence": gemini_confidence
                }
                
                log_trade(forex_pair, "SELL", current_market_price, lot_size, None)
                return True
        
        # If we get here, the trade execution failed
        trade_type = "BUY" if signal == 1 else "SELL"
        logger.warning(f"Failed to execute {trade_type} trade for {forex_pair}")
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
    4. Gemini AI recommendation
    
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
    rsi = latest['RSI']
    sma_21 = latest['21_SMA']
    
    # Extract position details from the first open position
    position = open_positions[0]
    position_type = "BUY" if position.type == 0 else "SELL"  # 0 = BUY, 1 = SELL
    entry_price = position.price_open
    
    # Calculate current profit
    if position_type == "BUY":
        is_profitable = current_price > entry_price
        profit_pips = (current_price - entry_price) * 10000
    else:  # SELL
        is_profitable = current_price < entry_price
        profit_pips = (entry_price - current_price) * 10000
    
    # Only check exit conditions if the position is profitable
    if not is_profitable:
        return False, "Position not in profit"
    
    # Calculate trade duration in minutes (roughly based on 5-min candles)
    candle_count = len(dfs)
    trade_duration_minutes = min(candle_count * 5, 1440)  # Cap at 24 hours for estimation
    
    # Prepare indicator data for Gemini
    indicator_data = {
        "200_SMA": latest.get('200_SMA', 0),
        "50_SMA": latest.get('50_SMA', 0),
        "21_SMA": sma_21,
        "RSI": rsi,
    }
            
    # Check for RSI divergence
    rsi_divergence = check_rsi_divergence(dfs, position_type)
    if rsi_divergence:
        return True, f"RSI divergence detected while in profit ({profit_pips:.1f} pips)"
        
    # Check if price has returned to support/resistance level
    if support_resistance_levels:
        # For BUY positions, check if price has returned to a support level
        if position_type == "BUY":
            nearest_support = find_nearest_level(current_price, support_resistance_levels, "BUY")
            if nearest_support and abs(current_price - nearest_support) < 0.0005:  # Within 5 pips
                return True, f"Price returned to support level at {nearest_support:.5f} while in profit ({profit_pips:.1f} pips)"
        
        # For SELL positions, check if price has returned to a resistance level
        else:
            nearest_resistance = find_nearest_level(current_price, support_resistance_levels, "SELL")
            if nearest_resistance and abs(current_price - nearest_resistance) < 0.0005:  # Within 5 pips
                return True, f"Price returned to resistance level at {nearest_resistance:.5f} while in profit ({profit_pips:.1f} pips)"
    
    # Use Gemini AI to monitor the trade if enabled
    if GEMINI_SETTINGS["monitoring"]["enabled"]:
        # Only check every X minutes to avoid API overuse
        if candle_count % GEMINI_SETTINGS["monitoring"]["interval"] == 0 or profit_pips > 20:
            gemini_exit, gemini_reason, gemini_confidence = gemini_engine.monitor_trade(
                forex_pair,
                position_type,
                entry_price,
                current_price,
                trade_duration_minutes,
                dfs,
                indicator_data
            )
            
            # Check if Gemini recommends exit
            if gemini_exit:
                if GEMINI_SETTINGS["monitoring"]["required"] or gemini_confidence >= GEMINI_SETTINGS["min_confidence"]:
                    return True, f"Gemini recommends exit: {gemini_reason} (Confidence: {gemini_confidence:.2f})"
                else:
                    logger.info(f"Gemini suggests exit but confidence too low: {gemini_reason} (Confidence: {gemini_confidence:.2f})")
    
    # No exit conditions met
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

def set_pending_order(forex_pair, order_type, price, lot_size, comment=None, stop_loss=None, take_profit=None):
    """
    Set a pending order
    
    Args:
        forex_pair: Currency pair symbol
        order_type: Order type (BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP)
        price: Price to set the order at
        lot_size: Lot size for the order
        comment: Comment for the order
        stop_loss: Stop loss price
        take_profit: Take profit price
        
    Returns:
        OrderSendResult object if successful, None otherwise
    """
    try:
        # Add price and stop validation based on instrument type
        valid_price, adjusted_price = validate_and_adjust_price(forex_pair, price, order_type)
        if not valid_price:
            logger.error(f"Invalid price for {order_type} order on {forex_pair}: {price}")
            return None
            
        # Adjust stop loss and take profit if provided
        if stop_loss is not None:
            valid_sl, adjusted_sl = validate_and_adjust_price(forex_pair, stop_loss, "STOP_LOSS", price, order_type)
            if not valid_sl:
                logger.warning(f"Invalid stop loss for {forex_pair}, removing stop loss")
                stop_loss = None
            else:
                stop_loss = adjusted_sl
                
        if take_profit is not None:
            valid_tp, adjusted_tp = validate_and_adjust_price(forex_pair, take_profit, "TAKE_PROFIT", price, order_type)
            if not valid_tp:
                logger.warning(f"Invalid take profit for {forex_pair}, removing take profit")
                take_profit = None
            else:
                take_profit = adjusted_tp
        
        # Create and send the order
        order = create_order_request(
            action=mt5.TRADE_ACTION_PENDING,
            symbol=forex_pair,
            volume=lot_size,
            price=adjusted_price,
            sl=stop_loss,
            tp=take_profit,
            type_time=mt5.ORDER_TIME_GTC,
            type=get_order_type(order_type),
            comment=comment or f"{order_type} order"
        )
        
        result = mt5.order_send(order)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to place {order_type} order for {forex_pair}: {get_error_message(result.retcode)}")
            return None
            
        logger.info(f"Successfully placed {order_type} order for {forex_pair}, ticket: {result.order}")
        return result
    except Exception as e:
        logger.error(f"Error setting pending order for {forex_pair}: {e}")
        return None

def validate_and_adjust_price(forex_pair, price, price_type, base_price=None, order_type=None):
    """
    Validate and adjust price based on instrument type and broker requirements
    
    Args:
        forex_pair: Currency pair symbol
        price: Price to validate
        price_type: Type of price (ENTRY, STOP_LOSS, TAKE_PROFIT)
        base_price: Base price for reference (for SL/TP validation)
        order_type: Order type for context
        
    Returns:
        Tuple of (is_valid, adjusted_price)
    """
    try:
        # Get symbol info
        symbol_info = mt5.symbol_info(forex_pair)
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {forex_pair}")
            return False, price
            
        # Get tick size and minimum stop distance
        tick_size = symbol_info.trade_tick_size
        min_stop_distance = symbol_info.trade_stops_level * symbol_info.point
        
        # Round price to valid tick size
        adjusted_price = round(price / tick_size) * tick_size
        
        # Handle special cases for different instrument types
        if forex_pair.startswith('XAU') or forex_pair.startswith('XAG') or forex_pair.startswith('XPD') or forex_pair.startswith('XPT'):
            # For metals, ensure minimum distances are respected
            if price_type == "STOP_LOSS" or price_type == "TAKE_PROFIT":
                if base_price is None:
                    return False, adjusted_price
                    
                # Check if stop loss/take profit is at valid distance
                if price_type == "STOP_LOSS":
                    if order_type and "BUY" in order_type:
                        if base_price - adjusted_price < min_stop_distance:
                            # Too close, adjust
                            adjusted_price = base_price - (min_stop_distance * 1.1)  # Add 10% buffer
                    elif order_type and "SELL" in order_type:
                        if adjusted_price - base_price < min_stop_distance:
                            # Too close, adjust
                            adjusted_price = base_price + (min_stop_distance * 1.1)  # Add 10% buffer
                
                if price_type == "TAKE_PROFIT":
                    if order_type and "BUY" in order_type:
                        if adjusted_price - base_price < min_stop_distance:
                            # Too close, adjust
                            adjusted_price = base_price + (min_stop_distance * 1.1)  # Add 10% buffer
                    elif order_type and "SELL" in order_type:
                        if base_price - adjusted_price < min_stop_distance:
                            # Too close, adjust
                            adjusted_price = base_price - (min_stop_distance * 1.1)  # Add 10% buffer
                            
            # Round again after adjustments
            adjusted_price = round(adjusted_price / tick_size) * tick_size
        
        # For regular forex pairs
        elif "JPY" in forex_pair:
            # JPY pairs typically have 3 decimal places
            adjusted_price = round(adjusted_price, 3)
        else:
            # Standard forex pairs have 5 decimal places
            adjusted_price = round(adjusted_price, 5)
            
        # Check if price is within allowed range
        if price_type != "STOP_LOSS" and price_type != "TAKE_PROFIT":
            current_price = mt5.symbol_info_tick(forex_pair).bid
            if abs(adjusted_price - current_price) < min_stop_distance:
                # Price too close to current market price
                logger.warning(f"Price {adjusted_price} for {forex_pair} is too close to current price {current_price}")
                return False, adjusted_price
                
        return True, adjusted_price
    except Exception as e:
        logger.error(f"Error validating price for {forex_pair}: {e}")
        return False, price

def check_pending_orders(forex_pair):
    """
    Check and manage pending orders
    
    Args:
        forex_pair: Currency pair symbol
        
    Returns:
        True if a contingency plan was executed, False otherwise
    """
    try:
        contingency_key = f"{forex_pair}_contingency"
        
        # Check if there's an open position for this pair
        positions = get_open_positions(forex_pair)
        if len(positions) == 0:
            return False
            
        # Get the latest position
        position = positions[0]
        position_type = "BUY" if position.type == 0 else "SELL"
        
        # Check if we have contingency info for this pair
        if contingency_key in TRADING_SETTINGS:
            contingency_info = TRADING_SETTINGS[contingency_key]
            
            # Calculate entry to SMA distance
            entry_to_sma_distance = contingency_info.get("entry_to_sma_distance", 0)
            
            # If this is a BUY position
            if position_type == "BUY":
                # Get current market price
                current_price = mt5.symbol_info_tick(forex_pair).bid
                
                # Get latest 21 SMA
                dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
                if dfs is None:
                    return False
                    
                dfs = calculate_indicators(dfs)
                latest = dfs.iloc[-1]
                sma_21 = latest['21_SMA']
                
                # If we have a BUY position, check for resistance levels
                resistance_levels = find_resistance_levels(dfs, current_price)
                nearest_resistance = None
                
                if resistance_levels and len(resistance_levels) > 0:
                    # Find the nearest resistance above current price
                    for level in resistance_levels:
                        if level > current_price:
                            nearest_resistance = level
                            break
                
                # Calculate stop loss - use the nearest support level
                support_levels = find_support_levels(dfs, current_price)
                stop_loss = None
                
                if support_levels and len(support_levels) > 0:
                    # Find the nearest support below current price
                    for level in support_levels:
                        if level < current_price:
                            stop_loss = level
                            break
                
                # If no support level found, use a default
                if stop_loss is None:
                    stop_loss = position.price_open - entry_to_sma_distance
                
                # Ensure stop loss is valid
                valid_sl, adjusted_sl = validate_and_adjust_price(
                    forex_pair, 
                    stop_loss, 
                    "STOP_LOSS", 
                    current_price, 
                    "BUY"
                )
                
                if valid_sl:
                    # Update the stop loss
                    result = modify_position_sl_tp(
                        forex_pair, 
                        position.ticket, 
                        stop_loss=adjusted_sl,
                        take_profit=position.tp
                    )
                    
                    if result:
                        logger.info(f"Modified BUY position {position.ticket}: SL={adjusted_sl:.5f}, TP={position.tp:.5f}")
                    else:
                        logger.error(f"Failed to modify position {position.ticket} for {forex_pair}")
                
                # Set up a SELL STOP at the initial entry
                initial_entry = contingency_info.get("initial_entry", None)
                if initial_entry:
                    lot_size = contingency_info.get("initial_lot_size", 0.01) * 2
                    
                    logger.info(f"Setting SELL STOP at initial entry ({initial_entry:.5f}) with {lot_size:.2f} lots for {forex_pair}")
                    
                    # Calculate take profit and stop loss for SELL STOP
                    stop_loss_for_sell = initial_entry + (entry_to_sma_distance * 3)
                    take_profit_for_sell = initial_entry - (entry_to_sma_distance * 2)
                    
                    # Validate prices
                    _, adjusted_price = validate_and_adjust_price(forex_pair, initial_entry, "ENTRY")
                    _, adjusted_sl = validate_and_adjust_price(forex_pair, stop_loss_for_sell, "STOP_LOSS", adjusted_price, "SELL_STOP")
                    _, adjusted_tp = validate_and_adjust_price(forex_pair, take_profit_for_sell, "TAKE_PROFIT", adjusted_price, "SELL_STOP")
                    
                    # Place the order
                    result = set_pending_order(
                        forex_pair,
                        "SELL_STOP",
                        adjusted_price,
                        lot_size,
                        comment="Contingency SELL STOP",
                        stop_loss=adjusted_sl,
                        take_profit=adjusted_tp
                    )
                    
                    if result:
                        # Update contingency info with total trades
                        total_trades = contingency_info.get("total_trades", 1) + 1
                        TRADING_SETTINGS[contingency_key]["total_trades"] = total_trades
                        
            # If this is a SELL position
            elif position_type == "SELL":
                # Get current market price
                current_price = mt5.symbol_info_tick(forex_pair).ask
                
                # Get latest 21 SMA
                dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
                if dfs is None:
                    return False
                    
                dfs = calculate_indicators(dfs)
                latest = dfs.iloc[-1]
                sma_21 = latest['21_SMA']
                
                # If we have a SELL position, check for support levels
                support_levels = find_support_levels(dfs, current_price)
                nearest_support = None
                
                if support_levels and len(support_levels) > 0:
                    # Find the nearest support below current price
                    for level in support_levels:
                        if level < current_price:
                            nearest_support = level
                            break
                
                # Calculate stop loss - use the nearest resistance level
                resistance_levels = find_resistance_levels(dfs, current_price)
                stop_loss = None
                
                if resistance_levels and len(resistance_levels) > 0:
                    # Find the nearest resistance above current price
                    for level in resistance_levels:
                        if level > current_price:
                            stop_loss = level
                            break
                
                # If no resistance level found, use a default
                if stop_loss is None:
                    stop_loss = position.price_open + entry_to_sma_distance
                
                # Ensure stop loss is valid
                valid_sl, adjusted_sl = validate_and_adjust_price(
                    forex_pair, 
                    stop_loss, 
                    "STOP_LOSS", 
                    current_price, 
                    "SELL"
                )
                
                if valid_sl:
                    # Update the stop loss
                    result = modify_position_sl_tp(
                        forex_pair, 
                        position.ticket, 
                        stop_loss=adjusted_sl,
                        take_profit=position.tp
                    )
                    
                    if result:
                        logger.info(f"Modified SELL position {position.ticket}: SL={adjusted_sl:.5f}, TP={position.tp:.5f}")
                    else:
                        logger.error(f"Failed to modify position {position.ticket} for {forex_pair}")
                
                # Set up a BUY STOP at the initial entry
                initial_entry = contingency_info.get("initial_entry", None)
                if initial_entry:
                    lot_size = contingency_info.get("initial_lot_size", 0.01) * 2
                    
                    logger.info(f"Setting BUY STOP at initial entry ({initial_entry:.5f}) with {lot_size:.2f} lots for {forex_pair}")
                    
                    # Calculate take profit and stop loss for BUY STOP
                    stop_loss_for_buy = initial_entry - (entry_to_sma_distance * 3)
                    take_profit_for_buy = initial_entry + (entry_to_sma_distance * 2)
                    
                    # Validate prices
                    _, adjusted_price = validate_and_adjust_price(forex_pair, initial_entry, "ENTRY")
                    _, adjusted_sl = validate_and_adjust_price(forex_pair, stop_loss_for_buy, "STOP_LOSS", adjusted_price, "BUY_STOP")
                    _, adjusted_tp = validate_and_adjust_price(forex_pair, take_profit_for_buy, "TAKE_PROFIT", adjusted_price, "BUY_STOP")
                    
                    # Place the order
                    result = set_pending_order(
                        forex_pair,
                        "BUY_STOP",
                        adjusted_price,
                        lot_size,
                        comment="Contingency BUY STOP",
                        stop_loss=adjusted_sl,
                        take_profit=adjusted_tp
                    )
                    
                    if result:
                        # Update contingency info with total trades
                        total_trades = contingency_info.get("total_trades", 1) + 1
                        TRADING_SETTINGS[contingency_key]["total_trades"] = total_trades
                        
        return True
    except Exception as e:
        logger.error(f"Error checking pending orders for {forex_pair}: {e}")
        return False

def execute_multiple_pairs(login=None, password=None, server=None, interval=1):
    """
    Execute trading strategy for multiple pairs in a continuous loop
    
    Args:
        login: MT5 account login
        password: MT5 account password
        server: MT5 server name
        interval: Interval between trading cycles in seconds (set to 1 second for minimal delay)
    
    Returns:
        None
    """
    try:
        # Initialize MT5 if login credentials provided
        if login is not None:
            if not login_trading(login, password, server):
                logger.error("Failed to login to MT5")
                return False
        
        logger.info(f"Starting continuous trading with minimal delay between cycles")
        
        while True:  # Continuous loop
            try:
                # Get pairs list
                pairs_list = load_currency_pairs()
                
                # Filter out unsupported/disabled symbols
                valid_pairs = []
                for pair in pairs_list:
                    # Check if symbol is enabled in MT5
                    if not mt5.symbol_select(pair, True):
                        logger.error(f"ERROR: Failed to enable symbol {pair}")
                        continue
                        
                    valid_pairs.append(pair)
                    
                if not valid_pairs:
                    logger.error("No valid pairs to trade!")
                    time.sleep(1)  # Brief pause before retrying
                    continue
                    
                for forex_pair in valid_pairs:
                    try:
                        logger.info(f"Processing {forex_pair}")
                        
                        # Get open positions for this pair
                        positions = get_open_positions(forex_pair)
                        
                        # If we have open positions, check exit conditions
                        if positions:
                            # Get market data
                            dfs = fetch_data(forex_pair, count=TRADING_SETTINGS["candles_count"])
                            if dfs is not None:
                                # Calculate indicators
                                dfs = calculate_indicators(dfs)
                                
                                # Get support/resistance levels
                                sr_levels = detect_support_resistance(dfs)
                                
                                # Check exit conditions
                                check_exit_conditions(forex_pair, dfs, positions, sr_levels)
                        
                        # Check for existing positions and manage them
                        check_pending_orders(forex_pair)
                        
                        # Execute trading strategy
                        execute(forex_pair)
                        
                    except Exception as e:
                        logger.error(f"Error processing {forex_pair}: {e}")
                        logger.error(traceback.format_exc())
                
                # Very brief pause between cycles to prevent system overload
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in trading cycle: {e}")
                logger.error(traceback.format_exc())
                time.sleep(1)  # Brief pause before retrying on error
                
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user")
    except Exception as e:
        logger.error(f"Error executing multiple pairs: {e}")
        logger.error(traceback.format_exc())

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