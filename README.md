# Mario Trader Beta

A MetaTrader 5 trading bot using an SMA Crossover Strategy with RSI confirmation.

## Features

- **SMA Crossover Strategy with RSI Confirmation**
  - Uses 21, 50, and 200 SMAs for trend identification
  - RSI for confirming the trade direction
  - Candle pattern detection for entry confirmation

- **Advanced Exit Strategies**
  - RSI divergence detection for exiting profitable trades
  - Support and resistance level detection for smart exits
  - Trailing stop loss based on key technical levels

- **Sophisticated Contingency Plan**
  - Simultaneous entry with stop orders for initial trade management
  - 3x stop and 2x profit targets automatically calculated
  - Cascading trade entries with increasing lot sizes

- **Gemini AI Integration**
  - Pre-trade verification of potential setups using Google's Gemini API
  - Ongoing trade monitoring with AI-assisted exit recommendations
  - Market analysis and insights from AI trading expert

- **Risk Management**
  - 2% risk per trade using proper lot sizing
  - Pip value calculation for accurate position sizing
  - Stop loss placement at key technical levels

- **Multi-Currency Support**
  - Trade multiple currency pairs simultaneously
  - Configurable trading interval for each pair

- **Testing Tools**
  - Debug mode for testing strategy logic
  - Force buy/sell signals for validating execution
  - Support/resistance level detection and visualization
  - Monitoring tool for tracking positions and pending orders

## Contingency Plan Implementation

The new contingency plan implements a sophisticated trading approach:

### Initial Entry:
1. When a BUY or SELL signal is generated, two orders are placed simultaneously:
   - The main trade in the signal direction with no initial stop loss
   - A stop order at the 21 SMA with 2x the lot size of the main trade

### When Stop Order is Triggered:
2. If the stop order gets activated (price reaches 21 SMA):
   - A limit order is placed at the initial entry point with 3x the initial lot size
   
### Lot Size Progression:
- Initial Trade: Base lot size calculated using 2% risk rule
- First Stop Order: 2x initial lot size
- Limit Order: 3x initial lot size
- Each subsequent order: initial lot size × (number of trades + 1)

### Exit Conditions:
- RSI divergence detection (price and RSI moving in opposite directions)
- Price returning to support (for BUY positions) or resistance (for SELL positions) levels
- Gemini AI recommendation based on market analysis
- These exits are only triggered when the position is in profit

## Gemini AI Integration

The system now leverages Google's Gemini AI to enhance trade decisions:

### Setup Verification:
- Gemini analyzes all aspects of a potential trade before execution
- Evaluates trend, entry patterns, and current market conditions
- Provides a confidence score and detailed reasoning for approvals/rejections

### Trade Monitoring:
- Continually evaluates open positions for optimal exit points
- Analyzes technical indicators, price action, and market structure
- Provides exit recommendations with confidence scores

### Configuration Options:
- Enable/disable Gemini verification and monitoring independently
- Set minimum confidence thresholds for trade approvals
- Configure whether Gemini's opinion is advisory or mandatory

### API Requirements:
- Requires a Google Gemini API key (set via GEMINI_API_KEY environment variable)
- Configurable API endpoint and parameters
- Structured JSON responses for consistent decision-making

## Support and Resistance Detection

The system identifies key support and resistance levels using:
- Local price minima/maxima detection within a 20-candle window
- Level grouping with dynamic tolerance for nearby price points
- Automatic ranking of levels by significance (frequency and recency)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/mario_trader_beta.git
cd mario_trader_beta
```

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
`
2. Set up your Gemini API key as an environment variable:
```bash
# Windows PowerShell
$env:GEMINI_API_KEY = "your_gemini_api_key"

# Linux/macOS
export GEMINI_API_KEY="your_gemini_api_key"
```

3. Create a `currency_pair_list.txt` file in the project root directory with the currency pairs you want to trade, one per line:
```
EURUSD
GBPUSD
USDJPY
```

4. Adjust the trading settings in `mario_trader/config.py` if needed.

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

### Test the contingency plan implementation:
```bash
python test_contingency.py --pair EURUSD --force-buy --monitor
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
- Price returning to support/resistance levels while in profit
- Gemini AI exit recommendation with sufficient confidence

## License

This project is licensed under the MIT License - see the LICENSE file for details. 