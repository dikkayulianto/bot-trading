import MetaTrader5 as mt5

# Trading Configuration
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]  # List of symbols to monitor and trade
TIMEFRAME = mt5.TIMEFRAME_M5  # Timeframe: 5 Minutes
LOT_SIZE = 0.01               # Lot size for each trade
SL_PIPS = 15.0                # Stop Loss in pips (e.g. 1.5 pips is 15 points, 15 pips is 150 points for 5-digit broker)
TP_PIPS = 30.0                # Take Profit in pips (e.g. 30 pips is 300 points)
MAGIC_NUMBER = 20260803       # Unique magic number for the bot's orders

# Strategy Parameters (EMA Crossover + RSI)
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Bot Execution Settings
LOOP_INTERVAL_SECONDS = 10    # Time to wait between checks (in seconds)
