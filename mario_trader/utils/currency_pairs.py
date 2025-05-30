"""
Currency pairs utility functions
"""
import os
import json
from mario_trader.utils.logger import logger
import MetaTrader5 as mt5


def get_available_broker_symbols():
    """
    Get the list of available symbols from the broker
    
    Returns:
        List of symbols available on the connected broker
    """
    # Make sure MT5 is initialized
    if not mt5.initialize():
        logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
        return []
    
    # Get all symbols
    symbols = mt5.symbols_get()
    if symbols is None:
        logger.error(f"Failed to get symbols: {mt5.last_error()}")
        return []
    
    # Extract symbol names
    symbol_names = [symbol.name for symbol in symbols]
    logger.info(f"Found {len(symbol_names)} total symbols from broker")
    
    # Filter for common forex, indices, metals, and energy symbols
    filtered_symbols = []
    for symbol in symbol_names:
        # Include all major and minor currency pairs
        if (len(symbol) == 6 and symbol[:3] != symbol[3:] and 
            symbol[:3] in ['EUR', 'USD', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF'] and
            symbol[3:] in ['EUR', 'USD', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF']):
            filtered_symbols.append(symbol)
        # Include common metals and energies
        elif symbol.startswith(('XAU', 'XAG', 'XPD', 'XPT')):
            filtered_symbols.append(symbol)
        # Include major indices that might have different names
        elif any(index in symbol for index in ['US30', 'SPX', 'NAS', 'UK100', 'GER30', 'DJ30']):
            filtered_symbols.append(symbol)
        # Include major cryptocurrencies
        elif symbol.startswith(('BTC', 'ETH')) and 'USD' in symbol:
            filtered_symbols.append(symbol)
    
    logger.info(f"Filtered to {len(filtered_symbols)} tradable symbols")
    return filtered_symbols


def load_currency_pairs():
    """
    Load the list of currency pairs to trade
    
    Returns:
        List of currency pairs
    """
    try:
        # First try to get symbols directly from the broker
        available_symbols = get_available_broker_symbols()
        
        # If we got symbols from the broker, use those
        if available_symbols:
            logger.info(f"Using {len(available_symbols)} symbols from broker")
            return available_symbols
        
        # Fallback to default list if broker connection fails
        default_pairs = [
            "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", 
            "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURCHF", "AUDJPY",
            "XAUUSD", "XAGUSD"  # Gold and silver
        ]
        
        logger.warning("Using default pairs list since broker connection failed")
        return default_pairs
    except Exception as e:
        logger.error(f"Error loading currency pairs: {e}")
        # If all else fails, return minimal list
        return ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]


def validate_currency_pair(pair, available_pairs=None):
    """
    Validate if a currency pair is available for trading
    
    Args:
        pair: Currency pair to validate
        available_pairs: List of available pairs (optional)
        
    Returns:
        True if valid, False otherwise
    """
    if available_pairs is None:
        available_pairs = load_currency_pairs()
    
    return pair in available_pairs


def get_default_pair(available_pairs=None):
    """
    Get a default currency pair for trading
    
    Args:
        available_pairs: List of available pairs (optional)
        
    Returns:
        Default currency pair
    """
    if available_pairs is None:
        available_pairs = load_currency_pairs()
    
    priority_pairs = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    
    for pair in priority_pairs:
        if pair in available_pairs:
            return pair
    
    # If none of the priority pairs are available, return the first available pair
    if available_pairs:
        return available_pairs[0]
    
    # Last resort
    return "EURUSD" 