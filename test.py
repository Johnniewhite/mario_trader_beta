import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import talib
from datetime import datetime
import time

# Initialize the MetaTrader 5 connection
def initialize_mt5():
    # Rely on automatic path detection or running terminal
    if not mt5.initialize():
        print(f"MetaTrader 5 initialization failed, error code: {mt5.last_error()}")
        return False
    print("MetaTrader 5 initialized successfully")
    return True

# Function to calculate SMA
def calculate_sma(data, period):
    # Ensure data has enough non-NaN values for the period
    if data.notna().sum() < period:
        return pd.Series([np.nan] * len(data), index=data.index)
    return talib.SMA(data.astype(float), period) # Ensure data is float

# Function to calculate RSI
def calculate_rsi(data, period):
     # Ensure data has enough non-NaN values for the period + 1 (RSI needs one more)
    if data.notna().sum() < period + 1:
        return pd.Series([np.nan] * len(data), index=data.index)
    return talib.RSI(data.astype(float), period) # Ensure data is float

# Fetch historical data for a given symbol
def fetch_historical_data(symbol, timeframe, n_bars=100):
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n_bars)
        if rates is None:
            print(f"Failed to fetch rates for {symbol}, error: {mt5.last_error()}")
            return pd.DataFrame() # Return empty DataFrame if fetch fails

        data = pd.DataFrame(rates)
        # print(f"Columns available for {symbol}: {data.columns.tolist()}") # Debugging line

        # The 'time' column holds seconds since epoch, convert it
        if 'time' in data.columns:
             data['time'] = pd.to_datetime(data['time'], unit='s')
        else:
             print(f"Error: 'time' column not found in data for {symbol}. Available columns: {data.columns.tolist()}")
             return pd.DataFrame()

        # Ensure other essential columns exist
        essential_cols = ['open', 'high', 'low', 'close']
        if not all(col in data.columns for col in essential_cols):
            print(f"Error: Missing essential price columns in data for {symbol}. Available: {data.columns.tolist()}")
            return pd.DataFrame()

        return data
    except Exception as e:
        print(f"Exception during fetch_historical_data for {symbol}: {e}")
        return pd.DataFrame()

# Function to check if the RSI divergence is present
def is_rsi_divergence(data):
    # Detect RSI divergence (basic approach)
    # Ideally, use more sophisticated divergence detection here.
    # For simplicity, this is just an example
    if data['rsi'][-1] > 50:
        return True
    return False

# Function to calculate trade size based on account balance and risk
# NOTE: This is a simplified calculation. Accurate pip value depends on account currency
#       and the quote currency of the symbol. trade_tick_value might be more direct.
def calculate_lot_size(account_balance, risk_percent, stop_loss_pips, symbol_info):
    if symbol_info is None or stop_loss_pips <= 0:
        return 0.0

    point = symbol_info.point
    contract_size = symbol_info.trade_contract_size
    tick_value = symbol_info.trade_tick_value
    tick_size = symbol_info.trade_tick_size
    volume_step = symbol_info.volume_step
    volume_min = symbol_info.volume_min
    volume_max = symbol_info.volume_max
    digits = symbol_info.digits # For formatting output

    risk_amount = account_balance * (risk_percent / 100.0)

    # Calculate value per pip
    # More direct method using tick value if available and seems valid
    if tick_value > 0 and tick_size > 0:
         value_per_point = tick_value / tick_size
         value_per_pip = value_per_point * (point * 10) # Assuming 1 pip = 10 points (adjust if needed for specific symbols)
         print(f"Using tick_value method for {symbol_info.name}: tick_value={tick_value}, tick_size={tick_size}, value_per_pip={value_per_pip}")
    else:
         # Fallback approximation (may be inaccurate, especially for non-USD pairs/accounts or non-forex)
         value_per_point = point * contract_size # Rough estimate for USD quoted pairs
         print(f"Warning: Using fallback pip value calculation for {symbol_info.name} (point={point}, contract_size={contract_size}). Verify accuracy.")
         value_per_pip = value_per_point * 10 # Assuming 1 pip = 10 points

    if value_per_pip <= 0 or stop_loss_pips <= 0:
        print(f"Error: Invalid pip value ({value_per_pip:.5f}) or stop loss pips ({stop_loss_pips}) for {symbol_info.name}")
        return 0.0

    # Calculate Lot Size: risk_amount / (pips_to_risk * value_per_pip_per_lot)
    stop_loss_currency_per_lot = stop_loss_pips * value_per_pip

    if stop_loss_currency_per_lot <= 0:
        print(f"Error: Invalid stop_loss_currency_per_lot ({stop_loss_currency_per_lot:.5f}) for {symbol_info.name}")
        return 0.0

    lot_size = risk_amount / stop_loss_currency_per_lot

    # --- Adjust lot size based on symbol limits ---
    # Ensure lot size is a multiple of volume_step
    lot_size = round(lot_size / volume_step) * volume_step
    # Clamp between min and max volume
    lot_size = max(volume_min, lot_size)
    lot_size = min(volume_max, lot_size)

    # Final check if lot size is valid after adjustments
    if lot_size < volume_min:
         print(f"Calculated lot size {lot_size} is below minimum {volume_min} for {symbol_info.name}. Cannot place order.")
         return 0.0 # Return 0 if we can't even meet minimum lot size

    print(f"Calculated Lot Size for {symbol_info.name}: {lot_size:.{digits}f}") # Format to symbol digits
    return lot_size

# Function to place a market order
def place_market_order(symbol, order_type, lot_size, stop_loss, take_profit):
    # Request the latest tick data
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Error: Failed to get tick data for {symbol}. Cannot place order. Error: {mt5.last_error()}")
        return None

    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    symbol_info = mt5.symbol_info(symbol) # Get info for rounding
    if symbol_info is None:
         print(f"Error: Failed to get symbol_info for rounding SL/TP for {symbol}. Error: {mt5.last_error()}")
         return None # Cannot proceed without digits
    digits = symbol_info.digits

    # Ensure SL/TP are rounded to the symbol's digits BEFORE sending
    stop_loss = round(stop_loss, digits)
    take_profit = round(take_profit, digits)

    # Prepare the request dictionary
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": 10, # Allowable price deviation in points
        "magic": 234000, # Example magic number
        "comment": "python script open",
        "type_time": mt5.ORDER_TIME_GTC, # Good till cancelled
        "type_filling": mt5.ORDER_FILLING_IOC, # Immediate or Cancel
        # "type_filling": mt5.ORDER_FILLING_FOK, # Fill or Kill might be safer for market orders if supported
    }

    # Send the order
    print(f"Sending order request: {request}") # Debug: Print the request
    result = mt5.order_send(request)

    if result is None:
        print(f"Error: order_send failed for {symbol}, error code: {mt5.last_error()}")
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Error: Order failed for {symbol}: retcode={result.retcode} comment={result.comment}")
        # Consider printing mt5.last_error() details too
        print(f"       Last Error: {mt5.last_error()}")
        return None
    else:
        print(f"Order placed successfully for {symbol}: ticket={result.order}, price={result.price}, volume={result.volume}")
        return result.order # Return the ticket number on success

# Main trading loop
def main():
    if not initialize_mt5():
        return

    # Login
    ACCOUNT_ID = 81338593
    YOUR_PASSWORD = "Mario123$$"
    YOUR_SERVER = "Exness-MT5Trial10"

    authorized = mt5.login(login=ACCOUNT_ID, password=YOUR_PASSWORD, server=YOUR_SERVER)
    if not authorized:
        print(f"Failed to connect to trade account {ACCOUNT_ID} on {YOUR_SERVER}, error code: {mt5.last_error()}")
        mt5.shutdown()
        return
    else:
        print(f"Connected to trade account {ACCOUNT_ID} on {YOUR_SERVER}")


    symbols = ["BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD", "XPDUSD", "XPTUSD", "XRPUSD", "BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD", "XPDUSD", "XPTUSD", "XRPUSD", "ETHUSD"]
    risk_percent = 1  # Risk per trade in percentage
    stop_loss_pips = 50
    take_profit_pips = 100

    account_info = mt5.account_info()
    if account_info is None:
        print(f"Failed to get account info. Error: {mt5.last_error()}")
        mt5.shutdown()
        return

    account_balance = account_info.balance
    print(f"Account Balance: {account_balance}")

    while True: # Run continuously
        # Check connection status periodically
        terminal_info = mt5.terminal_info()
        if terminal_info is None or not terminal_info.connected:
             print(f"MT5 disconnected or terminal info unavailable (Info: {terminal_info}). Attempting to reconnect...")
             # Simple retry logic
             if not initialize_mt5() or not mt5.login(login=ACCOUNT_ID, password=YOUR_PASSWORD, server=YOUR_SERVER):
                 print("Reconnection failed. Sleeping for 60 seconds before next attempt...")
                 time.sleep(60)
                 continue # Skip the rest of the loop and retry connection
             else:
                 print("Reconnected successfully.")
                 # Refresh account info after reconnecting
                 account_info = mt5.account_info()
                 if account_info:
                     account_balance = account_info.balance
                     print(f"Account Balance Refreshed: {account_balance}")
                 else:
                     print("Failed to refresh account info after reconnect.")
                     time.sleep(60)
                     continue


        for symbol in symbols:
            print(f"--- Processing {symbol} ---")
            try:
                # --- Get Symbol Info ---
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    print(f"Symbol {symbol} info not found by broker, skipping. Error: {mt5.last_error()}")
                    continue # Skip to next symbol

                # --- Ensure Symbol Enabled in Market Watch ---
                if not symbol_info.visible:
                    print(f"Symbol {symbol} not visible in MarketWatch, attempting to select.")
                    if not mt5.symbol_select(symbol, True):
                        print(f"Failed to select {symbol} in MarketWatch, skipping. Error: {mt5.last_error()}")
                        continue
                    # Re-fetch info after selecting to ensure it's updated
                    symbol_info = mt5.symbol_info(symbol)
                    if symbol_info is None or not symbol_info.visible:
                         print(f"Still cannot get visible symbol info for {symbol} after select, skipping.")
                         continue
                    else:
                         print(f"Symbol {symbol} selected successfully.")

                # --- Check if Market is Open / Trading Allowed ---
                # More robust check using trade_mode
                trade_mode = symbol_info.trade_mode
                market_open = False
                if trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
                    print(f"Trading is explicitly disabled for {symbol}, skipping.")
                elif trade_mode == mt5.SYMBOL_TRADE_MODE_CLOSEONLY:
                    print(f"Trading is close only for {symbol}, skipping new orders.")
                elif trade_mode == mt5.SYMBOL_TRADE_MODE_LONGONLY:
                    print(f"Trading is long only for {symbol}.")
                    market_open = True # Can place buy orders
                elif trade_mode == mt5.SYMBOL_TRADE_MODE_SHORTONLY:
                     print(f"Trading is short only for {symbol}.")
                     market_open = True # Can place sell orders
                elif trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
                    market_open = True # All orders allowed
                else:
                    print(f"Unknown trade mode ({trade_mode}) for {symbol}, assuming market closed.")

                # Add a check for tick data availability as another proxy for market open
                current_tick = mt5.symbol_info_tick(symbol)
                if current_tick is None or current_tick.time_msc == 0:
                    print(f"No current tick data available for {symbol}, market might be closed or symbol inactive. Skipping.")
                    market_open = False # Override if no tick

                if not market_open:
                    continue # Skip order placement if market closed/disabled

                # --- Fetch Data ---
                print(f"Fetching historical data for {symbol}")
                # Request slightly more bars to ensure enough for indicator calculation
                data = fetch_historical_data(symbol, mt5.TIMEFRAME_M5, n_bars=120) 

                if data.empty or len(data) < 22: # Need at least 21 for SMA, 15 for RSI(14) + 1 burn-in
                    print(f"Insufficient data returned for {symbol} (got {len(data)} bars), skipping calculations.")
                    continue

                # --- Calculate Indicators ---
                data['sma21'] = calculate_sma(data['close'], 21)
                data['rsi'] = calculate_rsi(data['close'], 14)

                # Check calculation results on the last complete bar (iloc[-2] might be safer than [-1])
                if len(data) < 2: # Should not happen due to check above, but safety first
                     continue
                     
                last_complete_idx = -2 # Use second-to-last bar as last one might be incomplete
                
                if pd.isna(data['sma21'].iloc[last_complete_idx]) or pd.isna(data['rsi'].iloc[last_complete_idx]):
                    print(f"Indicator calculation resulted in NaN for {symbol} on last complete bar. Insufficient data? ({len(data)} bars). Skipping trade logic.")
                    continue

                # --- Calculate Lot Size ---
                lot_size = calculate_lot_size(account_balance, risk_percent, stop_loss_pips, symbol_info)
                if lot_size == 0.0: # Check if calculation failed or resulted in zero
                    print(f"Lot size calculation failed or resulted in 0 for {symbol}. Skipping order.")
                    continue

                # --- Calculate SL/TP Prices ---
                point = symbol_info.point
                stops_level = symbol_info.trade_stops_level # Minimum distance in points from current price
                digits = symbol_info.digits

                # Use the tick fetched earlier
                if current_tick is None: # Should have skipped earlier, but double-check
                    print(f"Tick data became unavailable for SL/TP calculation for {symbol}. Skipping order.")
                    continue

                # Assuming 1 pip = 10 points for standard forex/metals/crypto
                # This might need adjustment for specific instruments if pip definition differs
                pip_multiplier = 10
                sl_distance_points = stop_loss_pips * pip_multiplier
                tp_distance_points = take_profit_pips * pip_multiplier

                # Initial SL/TP calculation in points relative to current prices
                sl_buy_points = current_tick.ask - sl_distance_points * point
                tp_buy_points = current_tick.ask + tp_distance_points * point
                sl_sell_points = current_tick.bid + sl_distance_points * point
                tp_sell_points = current_tick.bid - tp_distance_points * point

                # Adjust SL/TP based on stops_level (minimum distance from current price in points)
                min_stop_distance_price = stops_level * point

                print(f"Debug {symbol}: Ask={current_tick.ask}, Bid={current_tick.bid}, StopsLevel={stops_level}, MinStopDist={min_stop_distance_price:.{digits}f}")

                sl_buy_adjusted = round(min(sl_buy_points, current_tick.ask - min_stop_distance_price), digits)
                tp_buy_adjusted = round(max(tp_buy_points, current_tick.ask + min_stop_distance_price), digits)
                sl_sell_adjusted = round(max(sl_sell_points, current_tick.bid + min_stop_distance_price), digits)
                tp_sell_adjusted = round(min(tp_sell_points, current_tick.bid - min_stop_distance_price), digits)
                
                print(f"Debug {symbol}: SL Buy Initial={sl_buy_points:.{digits}f} Adjusted={sl_buy_adjusted:.{digits}f}")
                print(f"Debug {symbol}: TP Buy Initial={tp_buy_points:.{digits}f} Adjusted={tp_buy_adjusted:.{digits}f}")
                print(f"Debug {symbol}: SL Sell Initial={sl_sell_points:.{digits}f} Adjusted={sl_sell_adjusted:.{digits}f}")
                print(f"Debug {symbol}: TP Sell Initial={tp_sell_points:.{digits}f} Adjusted={tp_sell_adjusted:.{digits}f}")
                
                # Check if adjusted SL/TP crossed over (e.g., if spread > SL) - this indicates an impossible order
                if sl_buy_adjusted >= current_tick.ask or tp_buy_adjusted <= current_tick.ask:
                     print(f"Error: Adjusted BUY SL/TP ({sl_buy_adjusted}/{tp_buy_adjusted}) invalid relative to Ask ({current_tick.ask}) for {symbol}. Check stops_level/spread.")
                     continue
                if sl_sell_adjusted <= current_tick.bid or tp_sell_adjusted >= current_tick.bid:
                     print(f"Error: Adjusted SELL SL/TP ({sl_sell_adjusted}/{tp_sell_adjusted}) invalid relative to Bid ({current_tick.bid}) for {symbol}. Check stops_level/spread.")
                     continue


                # --- Trading Logic ---
                last_close = data['close'].iloc[last_complete_idx]
                last_sma = data['sma21'].iloc[last_complete_idx]
                last_rsi = data['rsi'].iloc[last_complete_idx]

                print(f"{symbol}: LastClose={last_close:.{digits}f}, SMA21={last_sma:.{digits}f}, RSI={last_rsi:.2f}")

                # Check trade mode compatibility with signal
                order_placed = False
                if last_close > last_sma and last_rsi > 50:
                    signal = "BUY"
                    if trade_mode == mt5.SYMBOL_TRADE_MODE_FULL or trade_mode == mt5.SYMBOL_TRADE_MODE_LONGONLY:
                         print(f"BUY signal for {symbol}. Lots: {lot_size:.{digits}f}, SL: {sl_buy_adjusted:.{digits}f}, TP: {tp_buy_adjusted:.{digits}f}")
                         place_market_order(symbol, mt5.ORDER_TYPE_BUY, lot_size, stop_loss=sl_buy_adjusted, take_profit=tp_buy_adjusted)
                         order_placed = True
                    else:
                         print(f"BUY signal for {symbol} ignored due to trade mode {trade_mode}.")
                elif last_close < last_sma and last_rsi < 50:
                     signal = "SELL"
                     if trade_mode == mt5.SYMBOL_TRADE_MODE_FULL or trade_mode == mt5.SYMBOL_TRADE_MODE_SHORTONLY:
                         print(f"SELL signal for {symbol}. Lots: {lot_size:.{digits}f}, SL: {sl_sell_adjusted:.{digits}f}, TP: {tp_sell_adjusted:.{digits}f}")
                         place_market_order(symbol, mt5.ORDER_TYPE_SELL, lot_size, stop_loss=sl_sell_adjusted, take_profit=tp_sell_adjusted)
                         order_placed = True
                     else:
                          print(f"SELL signal for {symbol} ignored due to trade mode {trade_mode}.")
                else:
                    print(f"No signal for {symbol}.")
                    signal = "NONE"

            except Exception as e:
                print(f"!!! Exception occurred during processing for {symbol}: {e}")
                import traceback
                traceback.print_exc() # Print full traceback for debugging

        print("--- Loop finished, sleeping for 60 seconds ---")
        time.sleep(60) # Sleep at the end of each loop through symbols

    # Shutdown connection (will not be reached in infinite loop unless break is added)
    # mt5.shutdown()


if __name__ == '__main__':
    main()