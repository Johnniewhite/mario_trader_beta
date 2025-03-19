# Mario Trader Beta

A MetaTrader 5 trading bot using an SMA Crossover Strategy with RSI confirmation.

## Features

- **SMA Crossover Strategy with RSI Confirmation**
  - Uses 21, 50, and 200 SMAs for trend identification
  - RSI for confirming the trade direction
  - Candle pattern detection for entry confirmation

- **Profit-Taking Mechanisms**
  - RSI divergence detection for exiting profitable trades
  - Profit target of 2x the entry-to-21SMA distance in pips
  - Contingency plan for maximizing profit potential

- **Risk Management**
  - 2% risk per trade using proper lot sizing
  - Pip value calculation for accurate position sizing
  - Stop loss at the 21 SMA level

- **Multi-Currency Support**
  - Trade multiple currency pairs simultaneously
  - Configurable trading interval for each pair

- **Testing Tools**
  - Debug mode for testing strategy logic
  - Force buy/sell signals for validating execution
  - Simulate profitable positions to test profit-taking
  - Test contingency plan implementation

## Contingency Plan

The strategy includes a sophisticated contingency plan that activates after closing a profitable trade:

### For BUY trades:
1. When the initial BUY trade is closed in profit:
   - A SELL STOP order is placed at the 21 SMA level with 2x the initial lot size
2. If the SELL STOP is triggered:
   - A BUY LIMIT order is placed at the initial entry point with 3x the initial lot size

### For SELL trades:
1. When the initial SELL trade is closed in profit:
   - A BUY STOP order is placed at the 21 SMA level with 2x the initial lot size
2. If the BUY STOP is triggered:
   - A SELL LIMIT order is placed at the initial entry point with 3x the initial lot size

Each contingency trade uses an increasing lot size formula: initial lot size × (number of trades + 1).

## Installation

2. Install the required packages:
```bash
pip install -r requirements.txt
```

3. Make sure MetaTrader 5 is installed and running on your system.

## Configuration

1. Edit the `mario_trader/config.py` file to set your MT5 login credentials:
```python
MT5_SETTINGS = {
    "login": 12345678,  # Your MT5 account login
    "password": "your_password",  # Your MT5 account password
    "server": "MetaQuotes-Demo",  # MT5 server name
}
```

2. Create a `currency_pair_list.txt` file in the project root directory with the currency pairs you want to trade, one per line:
```
EURUSD
GBPUSD
USDJPY
```

3. Adjust the trading settings in `mario_trader/config.py` if needed.

## Usage

### Start the bot:
```bash
python main.py start
```

### Start with a specific currency pair:
```bash
python main.py start --pair EURUSD
```

### Start in multi-pair mode:
```bash
python main.py start --multi
```

### Test MT5 login credentials:
```bash
python main.py login
```

### Display configuration information:
```bash
python main.py info
```

### List available currency pairs:
```bash
python main.py list-pairs
```

### Check if MetaTrader 5 is properly installed:
```bash
python main.py check-mt5
```

### Test the profit-taking mechanism:
```bash
python test_profit_taking.py --pair EURUSD --debug
```

### Test the contingency plan:
```bash
python test_profit_taking.py --pair EURUSD --test-contingency
```

## Strategy Logic

The SMA Crossover strategy with RSI confirmation works as follows:

### BUY Signal Criteria:
- Price is above the 200 SMA
- Pattern of 3+ consecutive SELL candles followed by a BUY candle
- RSI is above 50
- Sufficient separation between 21 and 50 SMAs

### SELL Signal Criteria:
- Price is below the 200 SMA
- Pattern of 3+ consecutive BUY candles followed by a SELL candle
- RSI is below 50
- Sufficient separation between 21 and 50 SMAs

### Exit Criteria:
- RSI divergence detected while in profit
- Profit target reached (2x the distance from entry to 21 SMA in pips)

## License

This project is licensed under the MIT License - see the LICENSE file for details. 