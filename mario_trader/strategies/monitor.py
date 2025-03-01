"""
Trade monitoring and management
"""
import math
import MetaTrader5 as mt5
from mario_trader.utils.mt5_handler import get_current_price, fetch_data
from mario_trader.indicators.technical import detect_rsi_divergence


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
            return True
    elif trade_type == 'sell':
        if current_price > take_profit:
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
            return True

    elif trade_type == 'sell':
        if current_price < stop_loss:
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
    FOREX_PAIR = forex_pair
    para_para_stop_loss = stop_loss
    con_trade = {
        "v1":
            {
                "lot_size": 1,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v2":
            {
                "lot_size": 1.33,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v3":
            {
                "lot_size": 1,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v4":
            {
                "lot_size": 1.33,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v5":
            {
                "lot_size": 2.44,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v6":
            {
                "lot_size": 3.99,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v7":
            {
                "lot_size": 4.5,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v8":
            {
                "lot_size": 6.7,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v9":
            {
                "lot_size": 9.5,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v10":
            {
                "lot_size": 11.33,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v11":
            {
                "lot_size": 14.5,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v12":
            {
                "lot_size": 17.53,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
        "v13":
            {
                "lot_size": 19.65,
                "trade_type": "",
                "status": False,
                "ticket_id": "",
            },
    }

    contingency_status = False

    while True:
        current_price = get_current_price(FOREX_PAIR)

        df = fetch_data(FOREX_PAIR)

        divergence_signal = detect_rsi_divergence(df)

        if divergence_signal == 1:  
            if order_type == "buy":
                response = mt5.Close(FOREX_PAIR, ticket=order_id)
                break
            elif order_type == "sell":
                response = mt5.Close(FOREX_PAIR, ticket=order_id)
                break

        if divergence_signal == -1: 
            if order_type == "buy":
                response = mt5.Close(FOREX_PAIR, ticket=order_id)
                break

            elif order_type == "sell":
                response = mt5.Close(FOREX_PAIR, ticket=order_id)
                break

        if check_stop_loss(current_price, stop_loss, order_type):
            contingency_status = True
            break

    if not contingency_status:
        return 0

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

    counter_take_profit = counter_take_profit
    normal_take_profit = normal_take_profit

    while True:
        if not contingency_status:
            break

        current_price = get_current_price(FOREX_PAIR)

        df = fetch_data(FOREX_PAIR)

        if not contingency_status:
            break
            
        if v_counter_trade == 14:
            break

        if open_trade_bool:
            get_trade = con_trade[f"v{v_counter_trade}"]
            if get_trade["status"]:
                new_volume = volume * get_trade["lot_size"]
                new_volume = math.ceil(new_volume * 100) / 100
 
                if order_counter_type == "sell":
                    order_counter_type = "buy"
                    get_trade["trade_type"] = "sell"
                    v_counter_trade += 1
                    trade_response = open_trade(FOREX_PAIR, new_volume, stop_loss, 'sell')
                    get_trade["ticket_id"] = trade_response.order

                elif order_counter_type == "buy":
                    order_counter_type = "sell"
                    get_trade["trade_type"] = "buy"
                    v_counter_trade += 1
                    trade_response = open_trade(FOREX_PAIR, new_volume, stop_loss, 'buy')
                    get_trade["ticket_id"] = trade_response.order

        if check_stop_loss(current_price, counter_take_profit, order_counter_type_x):
            response = mt5.Close(FOREX_PAIR, ticket=order_id)
            for key in con_trade.keys():
                if con_trade[key]["status"]:
                    response = mt5.Close(FOREX_PAIR, ticket=con_trade[key]["ticket_id"])
            break

        if check_take_profit(current_price, normal_take_profit, order_type):
            response = mt5.Close(FOREX_PAIR, ticket=order_id)
            for key in con_trade.keys():
                if con_trade[key]["status"]:
                    response = mt5.Close(FOREX_PAIR, ticket=con_trade[key]["ticket_id"])
            break


        if order_type == "buy":
            if order_counter_type == "sell":
                if current_price < current_market_price:
                    get_trade = con_trade[f"v{v_counter_trade}"]
                    get_trade["status"] = False
                    get_trade["trade_type"] = "buy"
                    pass

            elif order_counter_type == "buy":
                # current price must be above stop loss price
                if current_price < stop_loss:
                    get_trade = con_trade[f"v{v_counter_trade}"]
                    get_trade["status"] = False
                    get_trade["trade_type"] = "sell"
                    pass

        elif order_type == "sell":
            if order_counter_type == "buy":
                if current_price > current_market_price:
                    get_trade = con_trade[f"v{v_counter_trade}"]
                    get_trade["status"] = False
                    get_trade["trade_type"] = "sell"
                    pass

            elif order_counter_type == "sell":
                if current_price < stop_loss:
                    open_trade_bool = True
                    get_trade = con_trade[f"v{v_counter_trade}"]
                    get_trade["status"] = False
                    get_trade["trade_type"] = "buy"
                    pass 