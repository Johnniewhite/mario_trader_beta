def get_available_broker_symbols():
    """
    Get the list of available symbols from the broker
    
    Returns:
        List of symbols available on the connected broker
    """
    import MetaTrader5 as mt5
    
    # Make sure MT5 is initialized
    if not mt5.initialize():
        return []
    
    # Get all symbols
    symbols = mt5.symbols_get()
    if symbols is None:
        return []
    
    # Extract symbol names
    symbol_names = [symbol.name for symbol in symbols]
    
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
        # Include major indices
        elif symbol in ['US30', 'SPX500', 'NAS100', 'UK100', 'GER30']:
            filtered_symbols.append(symbol)
        # Include major cryptocurrencies
        elif symbol in ['BTCUSD', 'ETHUSD']:
            filtered_symbols.append(symbol)
    
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
            print(f"Found {len(available_symbols)} symbols from broker: {available_symbols[:10]}...")
            return available_symbols
        
        # Fallback to default list if broker connection fails
        default_pairs = [
            "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", 
            "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURCHF", "AUDJPY",
            "XAUUSD", "XAGUSD"  # Gold and silver
        ]
        
        return default_pairs
    except Exception as e:
        # If all else fails, return minimal list
        return ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"] 