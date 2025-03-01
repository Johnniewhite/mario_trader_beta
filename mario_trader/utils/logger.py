"""
Logging utility for the trading bot
"""
import logging
import os
from datetime import datetime
from mario_trader.config import LOGGING_SETTINGS


def setup_logger(name="mario_trader"):
    """
    Set up and configure the logger
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Set logging level based on configuration
    level = getattr(logging, LOGGING_SETTINGS.get("level", "INFO"))
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if enabled
    if LOGGING_SETTINGS.get("log_to_file", False):
        log_file = LOGGING_SETTINGS.get("log_file", "mario_trader.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Create a default logger instance
logger = setup_logger()


def log_trade(action, currency_pair, price, volume, trade_type, order_id=None):
    """
    Log trade information
    
    Args:
        action: Trade action (open, close, etc.)
        currency_pair: Currency pair
        price: Trade price
        volume: Trade volume
        trade_type: Trade type (buy, sell)
        order_id: Order ID (optional)
    """
    if not LOGGING_SETTINGS.get("enabled", True):
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_info = f"Order ID: {order_id}" if order_id else ""
    
    logger.info(f"TRADE: {action} {trade_type} {currency_pair} - Price: {price}, Volume: {volume} {order_info}")


def log_signal(currency_pair, signal_type, price, stop_loss=None):
    """
    Log signal information
    
    Args:
        currency_pair: Currency pair
        signal_type: Signal type (buy, sell, none)
        price: Current price
        stop_loss: Stop loss price (optional)
    """
    if not LOGGING_SETTINGS.get("enabled", True):
        return
    
    stop_loss_info = f", Stop Loss: {stop_loss}" if stop_loss else ""
    
    logger.info(f"SIGNAL: {signal_type} {currency_pair} - Price: {price}{stop_loss_info}")


def log_error(message, exception=None):
    """
    Log error information
    
    Args:
        message: Error message
        exception: Exception object (optional)
    """
    if not LOGGING_SETTINGS.get("enabled", True):
        return
    
    if exception:
        logger.error(f"ERROR: {message} - {str(exception)}")
    else:
        logger.error(f"ERROR: {message}") 