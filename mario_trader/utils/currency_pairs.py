"""
Currency pairs utility functions
"""
import os
import json
from mario_trader.utils.logger import logger


def load_currency_pairs(file_path="currency_pair_list.txt"):
    """
    Load currency pairs from the file
    
    Args:
        file_path: Path to the currency pairs file
        
    Returns:
        List of currency pairs
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Currency pairs file not found: {file_path}")
            return []
            
        with open(file_path, 'r') as f:
            content = f.read().strip()
            
        # Parse the content as a JSON array
        try:
            # Add square brackets to make it a valid JSON array
            pairs = json.loads(f"[{content}]")
            # Remove duplicates while preserving order
            unique_pairs = []
            for pair in pairs:
                if pair not in unique_pairs:
                    unique_pairs.append(pair)
            return unique_pairs
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse currency pairs: {e}")
            # Fallback to manual parsing
            pairs = [p.strip(' "\'') for p in content.split(',')]
            # Remove duplicates and empty strings
            unique_pairs = []
            for pair in pairs:
                if pair and pair not in unique_pairs:
                    unique_pairs.append(pair)
            return unique_pairs
            
    except Exception as e:
        logger.error(f"Error loading currency pairs: {e}")
        return []


def validate_currency_pair(pair, available_pairs=None):
    """
    Validate if a currency pair is available for trading
    
    Args:
        pair: Currency pair to validate
        available_pairs: List of available pairs (optional)
        
    Returns:
        True if valid, False otherwise
    """
    if not pair:
        return False
        
    if available_pairs is None:
        available_pairs = load_currency_pairs()
        
    return pair in available_pairs


def get_default_pair(available_pairs=None):
    """
    Get the default currency pair (EURUSD if available)
    
    Args:
        available_pairs: List of available pairs (optional)
        
    Returns:
        Default currency pair
    """
    if available_pairs is None:
        available_pairs = load_currency_pairs()
        
    # Prefer EURUSD as default
    if "EURUSD" in available_pairs:
        return "EURUSD"
        
    # Otherwise return the first available pair
    return available_pairs[0] if available_pairs else "EURUSD" 