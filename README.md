# Mario Trader Beta

An automated trading bot for MetaTrader 5 that implements a trading strategy based on technical indicators.

## Features

- Automated trading on MetaTrader 5
- Technical analysis using SMA and RSI indicators
- Risk management with stop loss
- Contingency trading strategy
- Multi-currency pair trading support
- Modular code structure
- Command-line interface
- Comprehensive logging

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

### Development Installation

For development, you can install the package in development mode:

```
pip install -e .
```

This will install the package in editable mode, allowing you to make changes to the code without reinstalling.

## Project Structure

```
mario_trader_beta/
├── main.py                  # Main entry point with CLI
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── mario_trader/            # Main package
    ├── __init__.py
    ├── config.py            # Configuration settings
    ├── execution.py         # Trade execution logic
    ├── indicators/          # Technical indicators
    │   ├── __init__.py
    │   └── technical.py     # RSI, SMA, etc.
    ├── strategies/          # Trading strategies
    │   ├── __init__.py
    │   ├── monitor.py       # Trade monitoring
    │   └── signal.py        # Signal generation
    └── utils/               # Utility functions
        ├── __init__.py
        ├── logger.py        # Logging utilities
        └── mt5_handler.py   # MetaTrader 5 operations
```

## Usage

The bot can be controlled via command-line interface using either `main.py` or the more convenient `run.py` script.

### Using run.py (Recommended)

The `run.py` script provides a simplified interface:

```
python run.py start           # Start trading with a single pair
python run.py start-multi     # Start trading with multiple pairs
python run.py login           # Test MT5 login
python run.py info            # Display configuration information
python run.py test            # Run tests
```

With parameters:

```
python run.py start --pair EURUSD --login YOUR_LOGIN --password YOUR_PASSWORD --server YOUR_SERVER
python run.py start-multi --interval 120 --login YOUR_LOGIN --password YOUR_PASSWORD --server YOUR_SERVER
```

### Using main.py

Alternatively, you can use the main.py script directly:

### Display Configuration Information

```
python main.py info
```

To see available currency pairs:

```
python main.py info --pairs
```

### List Available Currency Pairs

```
python main.py list-pairs
```

### Test MT5 Login

```
python main.py login
```

You can provide custom login credentials:

```
python main.py login --login YOUR_LOGIN --password YOUR_PASSWORD --server YOUR_SERVER
```

### Start the Trading Bot

For a single currency pair:

```
python main.py start
```

With custom parameters:

```
python main.py start --pair EURUSD --login YOUR_LOGIN --password YOUR_PASSWORD --server YOUR_SERVER
```

For multiple currency pairs (trades all pairs in currency_pair_list.txt):

```
python main.py start --multi
```

With custom interval between trading cycles:

```
python main.py start --multi --interval 120
```

## Configuration

You can modify the configuration settings in `mario_trader/config.py`:

- MT5 connection settings (login, password, server)
- Trading settings (currency pair, risk percentage, timeframe)
- Technical indicator settings (RSI period, SMA periods)
- Contingency trade settings
- Order settings
- Logging settings

## Logging

The bot logs all activities to both console and a log file (default: mario_trader.log). You can configure logging settings in `mario_trader/config.py`.

## Disclaimer

This trading bot is provided for educational purposes only. Use at your own risk. Trading in financial markets involves substantial risk of loss. 