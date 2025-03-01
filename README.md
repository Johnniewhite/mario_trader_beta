# Mario Trader Beta

An automated trading bot for MetaTrader 5 that implements a trading strategy based on technical indicators.

## Features

- Automated trading on MetaTrader 5
- Technical analysis using SMA and RSI indicators
- Risk management with stop loss
- Contingency trading strategy

## Requirements

- Python 3.8+
- MetaTrader 5 platform installed
- Required Python packages (see requirements.txt)

## Installation

1. Clone this repository
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Make sure MetaTrader 5 is installed and configured

## Usage

1. Update the login credentials in the `login_trading()` function
2. Run the script:
   ```
   python main.py
   ```

## Configuration

You can modify the following parameters in the code:
- Currency pair (default: 'EURUSD')
- Risk percentage (default: 2% of balance)
- Timeframe (default: 5-minute candles)
- Technical indicators (SMA periods, RSI period)

## Disclaimer

This trading bot is provided for educational purposes only. Use at your own risk. Trading in financial markets involves substantial risk of loss. 