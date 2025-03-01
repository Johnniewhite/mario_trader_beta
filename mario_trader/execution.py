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


def execute(forex_pair):
    """
    Execute trading strategy for a currency pair
    
    Args:
        forex_pair: Currency pair symbol
    """
    dfs = fetch_data(forex_pair)
    signal, stop_loss_value, current_market_price = generate_signal(dfs, forex_pair)
    balance = get_balance()

    lot_size = get_contract_size(forex_pair)

    symbol_info = mt5.symbol_info(forex_pair)

    if symbol_info is None:
        return 

    min_lot_size = symbol_info.volume_min 
    max_lot_size = symbol_info.volume_max 

    one_lot_price = current_market_price * lot_size

    risked_capital = (balance * 0.02)

    one_pip_movement = 0.01 if "JPY" in forex_pair else 0.0001

    stop_loss_in_pip = abs(current_market_price - stop_loss_value) * one_pip_movement

    pip_value = (one_pip_movement / current_market_price) / lot_size

    lot_quantity = (risked_capital) * (stop_loss_in_pip * pip_value)

    volume = lot_quantity

    units = volume
    if signal == -1:
        trade_response = open_trade(forex_pair, units, stop_loss_value, 'sell')
        order_id = trade_response.order
        position = trade_response.request.position
        monitor_trade(order_id, position, units, "sell", stop_loss_value, current_market_price, forex_pair)

    elif signal == 1:
        trade_response = open_trade(forex_pair, units, stop_loss_value, 'buy')
        order_id = trade_response.order
        position = trade_response.request.position  
        monitor_trade(order_id, position, units, "buy", stop_loss_value, current_market_price, forex_pair)

    else:
        pass


def start_trading(login=81338593, password="Mario123$$", server="Exness-MT5Trial10", currency_pair='EURUSD'):
    """
    Start the trading bot
    
    Args:
        login: MT5 account login
        password: MT5 account password
        server: MT5 server name
        currency_pair: Currency pair to trade
    """
    if not initialize_mt5(login, password, server):
        shutdown_mt5()
        exit()

    try:
        while True:
            execute(currency_pair)
    except KeyboardInterrupt:
        print("Trading bot stopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        shutdown_mt5()


def login_trading(login=81338593, password="Mario123$$", server="Exness-MT5Trial10"):
    """
    Initialize connection to MetaTrader 5
    
    Args:
        login: MT5 account login
        password: MT5 account password
        server: MT5 server name
        
    Returns:
        True if successful, False otherwise
    """
    return initialize_mt5(login, password, server) 