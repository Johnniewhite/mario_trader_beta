# Mario Trader Strategy Guide

## SMA Crossover Strategy with Support/Resistance Exits

This document provides a comprehensive overview of the trading strategy implemented in the Mario Trader system, including entry conditions, exit strategies, contingency plans, and risk management.

## Strategy Overview

The core strategy combines SMA (Simple Moving Average) crossovers with RSI (Relative Strength Index) confirmation and candlestick pattern recognition for entry signals. It employs sophisticated exit mechanisms based on RSI divergence and support/resistance levels, along with a contingency plan for maximizing profit potential while minimizing risk.

## Entry Criteria

### BUY Signal Requirements

All of the following conditions must be met for a BUY signal:

1. **Trend Direction**: Price must be trading above the 200 SMA (bullish trend)
2. **Candle Pattern**: Must see a pattern of 3+ consecutive SELL candles followed by a BUY candle
3. **Momentum Confirmation**: RSI must be above 50 (showing bullish momentum)
4. **Moving Average Separation**: There must be sufficient separation between 21 SMA and 50 SMA (at least 0.0005)

### SELL Signal Requirements

All of the following conditions must be met for a SELL signal:

1. **Trend Direction**: Price must be trading below the 200 SMA (bearish trend)
2. **Candle Pattern**: Must see a pattern of 3+ consecutive BUY candles followed by a SELL candle
3. **Momentum Confirmation**: RSI must be below 50 (showing bearish momentum)
4. **Moving Average Separation**: There must be sufficient separation between 21 SMA and 50 SMA (at least 0.0005)

## Exit Strategies

The strategy employs two primary exit mechanisms, which are only triggered when the position is in profit:

### 1. RSI Divergence Exit

RSI divergence occurs when price movement and RSI indicator movement show a discrepancy, suggesting a potential trend reversal:

- **For BUY positions**: Exit when price makes higher highs but RSI makes lower highs (bearish divergence)
- **For SELL positions**: Exit when price makes lower lows but RSI makes higher lows (bullish divergence)

This is implemented by comparing price action and RSI values over a 5-candle window.

### 2. Support/Resistance Level Exit

The system detects key support and resistance levels using local price extrema:

- **For BUY positions**: Exit when price returns to a detected support level while in profit
- **For SELL positions**: Exit when price returns to a detected resistance level while in profit

The support/resistance detection algorithm:
1. Identifies local minima (support) and maxima (resistance) using a 20-candle window
2. Groups similar price levels to consolidate nearby levels
3. Ranks levels by significance based on frequency and recency

## Contingency Plan Implementation

The contingency plan is designed to:
1. Manage risk by setting a backup stop at the 21 SMA level
2. Allow for scaling into positions when price action confirms the trade direction
3. Maximize profit potential by using increasing lot sizes for follow-up trades

### Initial Trade Setup

When a BUY or SELL signal is generated:

1. **Initial Trade**: 
   - A market order is placed in the signal direction (BUY or SELL)
   - No stop loss is set on this initial order

2. **Simultaneous Stop Order**:
   - For BUY signals: A SELL STOP order is placed at the 21 SMA with 2x the initial lot size
   - For SELL signals: A BUY STOP order is placed at the 21 SMA with 2x the initial lot size

### Contingency Stage 2

If the stop order gets triggered (price reaches the 21 SMA):

1. **Limit Order at Initial Entry**:
   - For original BUY trades: A BUY LIMIT order is placed at the initial entry price with 3x the initial lot size
   - For original SELL trades: A SELL LIMIT order is placed at the initial entry price with 3x the initial lot size

### Lot Size Scaling

The lot size for each stage of the contingency plan follows this progression:
- Initial Trade: Base lot size (calculated using 2% risk rule)
- Stop Order: 2x initial lot size
- Limit Order: 3x initial lot size
- Subsequent orders: Initial lot size × (number of trades + 1)

## Risk Management

### Position Sizing

The system uses sophisticated position sizing to manage risk:

1. **Base Risk Calculation**:
   - Risk per trade is limited to 2% of account balance
   - Distance to 21 SMA is used to determine stop loss distance

2. **Lot Size Formula**:
   ```
   Lot Size = Account Risk Amount / (Stop Loss in Pips × Pip Value)
   ```
   Where:
   - Account Risk Amount = Account Balance × Risk Percentage (2%)
   - Stop Loss in Pips = Distance from entry to 21 SMA in pips
   - Pip Value = Monetary value of one pip movement (varies by currency pair)

3. **Pip Value Calculation**:
   ```
   Pip Value = (One Pip Movement / Exchange Rate) × Lot Size
   ```
   Where:
   - For most forex pairs (e.g., EUR/USD): 1 pip = 0.0001
   - For JPY pairs (e.g., USD/JPY): 1 pip = 0.01

## Support and Resistance Detection

The support and resistance detection algorithm works as follows:

1. **Identify Local Extrema**:
   - Scan price data with a 20-candle window
   - Identify points where price is a local maximum (resistance) or minimum (support)

2. **Group Similar Levels**:
   - Combine levels that are within a small tolerance (default 0.0002 or 2 pips)
   - Calculate the average price for each group

3. **Rank Levels**:
   - Sort support levels from highest to lowest
   - Sort resistance levels from highest to lowest

4. **Find Nearest Level**:
   - For BUY positions, find the nearest support level below current price
   - For SELL positions, find the nearest resistance level above current price

## Testing and Verification

The strategy includes comprehensive testing tools:

1. **Debug Mode**:
   - Enables detailed logging of all conditions
   - Shows intermediate calculations for entry/exit decisions

2. **Force Signals**:
   - Can force BUY or SELL signals to test execution logic
   - Allows testing contingency plan implementation

3. **Monitoring Tool**:
   - Tracks open positions and pending orders
   - Displays detected support/resistance levels
   - Checks for exit conditions continuously

## Example Usage

### Basic Trading:
```bash
python main.py start --pair EURUSD
```

### Testing Contingency Plan:
```bash
python test_contingency.py --pair EURUSD --force-buy --monitor
```

### Multiple Pair Trading:
```bash
python main.py start --multi
```

## Best Practices

1. **Always test in demo mode first** before using real money
2. **Monitor positions regularly**, especially when using the contingency plan
3. **Be cautious with increasing lot sizes** in the contingency plan
4. **Consider market conditions** - this strategy works best in trending markets
5. **Review support/resistance levels** regularly to ensure they're valid
6. **Keep detailed trade logs** to analyze performance

## Common Issues and Solutions

1. **No signals generated**:
   - Ensure you have enough historical data (at least 200 candles)
   - Check that separation between 21 and 50 SMAs is sufficient
   - Verify that RSI conditions are being met

2. **Stop orders not triggering**:
   - Check broker settings for pending order execution
   - Verify if broker requires specific distance for stop orders

3. **Support/resistance levels not accurate**:
   - Adjust the window size and tolerance parameters
   - Consider using higher timeframes for more reliable levels

4. **RSI divergence false signals**:
   - Increase the window size for more reliable divergence detection
   - Add additional confirmation filters 