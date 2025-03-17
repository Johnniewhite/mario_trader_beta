# SMA Crossover Strategy with RSI Confirmation

This document describes the SMA Crossover Strategy implemented in the Mario Trader Bot.

## Strategy Overview

This strategy generates trading signals based on the following conditions:

### For a BUY signal:
- The closing price must be above the 200-day SMA
- There must be sufficient separation between the 21-day and 50-day SMAs (except if price recently crossed the 200 SMA)
- There must be 3 or more consecutive sell candles and then a buy candle
- RSI must be above 50

### For a SELL signal:
- The closing price must be below the 200-day SMA
- There must be sufficient separation between the 21-day and 50-day SMAs (except if price recently crossed the 200 SMA)
- There must be 3 or more consecutive buy candles and a sell candle
- RSI must be below 50

## Implementation Details

The strategy is implemented in the `mario_trader/strategies/sma_crossover_strategy.py` file. The main function is `generate_sma_crossover_signal()`, which takes a DataFrame with price data and a currency pair symbol as input and returns a tuple of (signal, stop_loss, current_market_price).

### Key Components:

1. **SMA Calculation**:
   - 200-day SMA: Used to determine the overall trend
   - 21-day SMA: Used for short-term trend analysis
   - 50-day SMA: Used for medium-term trend analysis

2. **RSI Calculation**:
   - 14-period RSI: Used to confirm trend strength
   - Above 50 for buy signals
   - Below 50 for sell signals

3. **Candle Pattern Analysis**:
   - Checks for 3 or more consecutive candles in the opposite direction
   - Followed by a candle in the direction of the potential trade

4. **Stop Loss Calculation**:
   - Based on the distance between the current price and the 21-day SMA

## Usage

To use this strategy, simply run the Mario Trader Bot as usual:

```bash
python main.py start
```

For multiple currency pairs:

```bash
python main.py start --multi
```

## Customization

You can customize the strategy by modifying the following parameters in the `mario_trader/strategies/sma_crossover_strategy.py` file:

- `lookback` in `check_price_crossed_200sma_recently()`: Number of candles to look back for 200 SMA crossovers
- `count` in `check_consecutive_candles()`: Number of consecutive candles required for a signal
- `sufficient_separation` threshold: Currently set to 0.0001, can be adjusted based on the currency pair

## Logging

The strategy logs detailed information about market conditions and signals:

- Price and SMA values
- RSI values
- SMA separation
- Recent 200 SMA crossovers
- Consecutive candle patterns
- Signal generation details

Check the `mario_trader.log` file for detailed logs. 