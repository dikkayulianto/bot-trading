import time
import os
import logging
import json
import collections
import MetaTrader5 as mt5
import pandas as pd

import strategy

# Configure in-memory logs for the Web UI
log_history = collections.deque(maxlen=200)

class MemoryHandler(logging.Handler):
    def emit(self, record):
        try:
            log_entry = self.format(record)
            log_history.append(log_entry)
        except Exception:
            self.handleError(record)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# File handler
file_handler = logging.FileHandler("bot.log", encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Memory handler for Web UI
mem_handler = MemoryHandler()
mem_handler.setFormatter(formatter)
logger.addHandler(mem_handler)

# Timeframe mapping helper
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1
}

# Bot control flags
bot_running = False

def load_config():
    """
    Loads configuration parameters from config.json.
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load config.json: {e}")
        return None

def initialize_mt5():
    """
    Initializes connection to the MetaTrader 5 terminal.
    """
    if mt5.terminal_info() is not None:
        # Already initialized
        return True

    logging.info("Initializing MetaTrader 5...")
    # Default paths to try
    paths_to_try = [
        None, # Default MT5 path
        "C:/Program Files/MetaTrader 5/terminal64.exe"
    ]
    
    success = False
    for path in paths_to_try:
        try:
            if path:
                logging.info(f"Trying to initialize with path: {path}")
                if mt5.initialize(path=path):
                    success = True
                    break
            else:
                if mt5.initialize():
                    success = True
                    break
        except Exception as e:
            logging.warning(f"Failed to initialize with path {path}: {e}")

    if not success:
        logging.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        return False
    
    terminal_info = mt5.terminal_info()
    if terminal_info is not None:
        logging.info(f"Connected to MT5 terminal: {terminal_info.company} - {terminal_info.name}")
    return True

def get_filling_type(symbol_info):
    """
    Determines the correct order filling mode supported by the broker for the symbol.
    """
    filling_mode = symbol_info.filling_mode
    # Check bitwise flags: 1 = FOK, 2 = IOC
    if filling_mode & 1:
        return mt5.ORDER_FILLING_FOK
    elif filling_mode & 2:
        return mt5.ORDER_FILLING_IOC
    else:
        return mt5.ORDER_FILLING_RETURN

def get_historical_data(symbol, timeframe, count=100):
    """
    Fetches historical bar data from MT5 and returns it as a pandas DataFrame.
    """
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        logging.error(f"Failed to fetch rates for {symbol}. Error code: {mt5.last_error()}")
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def close_position(position, symbol_info):
    """
    Closes a specific open position.
    """
    tick = mt5.symbol_info_tick(position.symbol)
    if tick is None:
        logging.error(f"Failed to get tick info for closing position {position.ticket}")
        return False

    order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if position.type == mt5.POSITION_TYPE_BUY else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": order_type,
        "position": position.ticket,
        "price": price,
        "deviation": 20,
        "magic": position.magic,
        "comment": "UI Bot Close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": get_filling_type(symbol_info)
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Failed to close position {position.ticket}. Code: {result.retcode}, Description: {result.comment}")
        return False
        
    logging.info(f"Closed position {position.ticket} ({position.symbol}) at {price:.5f}")
    return True

def open_position(symbol, order_type, lot_size, sl_pips, tp_pips, magic_number, symbol_info):
    """
    Opens a new position (Buy/Sell) with specified SL and TP.
    """
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logging.error(f"Failed to get current tick for {symbol}")
        return False

    point = symbol_info.point
    digits = symbol_info.digits
    
    pip_multiplier = 10 if digits in [3, 5] else 1
    sl_points = sl_pips * pip_multiplier
    tp_points = tp_pips * pip_multiplier

    if order_type == mt5.ORDER_TYPE_BUY:
        price = tick.ask
        sl = price - (sl_points * point) if sl_pips > 0 else 0.0
        tp = price + (tp_points * point) if tp_pips > 0 else 0.0
        order_name = "BUY"
    else:  # mt5.ORDER_TYPE_SELL
        price = tick.bid
        sl = price + (sl_points * point) if sl_pips > 0 else 0.0
        tp = price - (tp_points * point) if tp_pips > 0 else 0.0
        order_name = "SELL"

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": magic_number,
        "comment": "UI Bot Entry",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": get_filling_type(symbol_info)
    }

    logging.info(f"Sending {order_name} order for {symbol}: Lot={lot_size}, Price={price:.5f}, SL={sl:.5f}, TP={tp:.5f}")
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Order failed. Code: {result.retcode}, Description: {result.comment}")
        return False
        
    logging.info(f"Order executed successfully! Ticket: {result.order}")
    return True

def run_bot_cycle(symbol, timeframe_str, lot_size, sl_pips, tp_pips, magic_number, config_data):
    """
    A single execution cycle of the trading bot for a given symbol.
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logging.error(f"Symbol {symbol} not found.")
        return
        
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            logging.error(f"Failed to select symbol {symbol}.")
            return

    # Convert timeframe string to MT5 constant
    mt5_tf = TIMEFRAME_MAP.get(timeframe_str, mt5.TIMEFRAME_M5)
            
    # 1. Fetch historical data
    df = get_historical_data(symbol, mt5_tf, count=100)
    if df is None:
        return

    # 2. Calculate Strategy Indicators
    df = strategy.calculate_indicators(
        df, 
        config_data.get("ema_fast", 9), 
        config_data.get("ema_slow", 21), 
        config_data.get("rsi_period", 14)
    )
    
    # 3. Check for Trading Signals
    signal = strategy.check_signals(
        df, 
        config_data.get("rsi_overbought", 70), 
        config_data.get("rsi_oversold", 30)
    )
    
    # 4. Get active positions
    positions = mt5.positions_get(symbol=symbol, magic=magic_number)
    if positions is None:
        positions = []
    
    buy_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_BUY]
    sell_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_SELL]
    
    logging.info(f"{symbol} (TF: {timeframe_str}) - Signal: {signal} | Open BUYs: {len(buy_positions)}, Open SELLs: {len(sell_positions)}")

    # 5. Execute trades based on signals
    if signal == 'BUY':
        for pos in sell_positions:
            logging.info(f"Closing opposing SELL position {pos.ticket} before opening BUY.")
            close_position(pos, symbol_info)
            
        if len(buy_positions) == 0:
            open_position(symbol, mt5.ORDER_TYPE_BUY, lot_size, sl_pips, tp_pips, magic_number, symbol_info)

    elif signal == 'SELL':
        for pos in buy_positions:
            logging.info(f"Closing opposing BUY position {pos.ticket} before opening SELL.")
            close_position(pos, symbol_info)
            
        if len(sell_positions) == 0:
            open_position(symbol, mt5.ORDER_TYPE_SELL, lot_size, sl_pips, tp_pips, magic_number, symbol_info)

def start_bot():
    """
    Main loop function to be run inside a background thread.
    """
    global bot_running
    if bot_running:
        logging.info("Bot is already running.")
        return

    if not initialize_mt5():
        return

    bot_running = True
    logging.info("Bot execution started successfully.")

    try:
        while bot_running:
            config_data = load_config()
            if not config_data:
                time.sleep(5)
                continue

            symbols = config_data.get("symbols", ["EURUSD"])
            timeframe_str = config_data.get("timeframe", "M5")
            lot_size = config_data.get("lot_size", 0.01)
            sl_pips = config_data.get("sl_pips", 15.0)
            tp_pips = config_data.get("tp_pips", 30.0)
            magic_number = config_data.get("magic_number", 20260803)
            interval = config_data.get("loop_interval_seconds", 10)

            for symbol in symbols:
                if not bot_running:
                    break
                logging.info(f"--- Processing {symbol} ---")
                try:
                    run_bot_cycle(symbol, timeframe_str, lot_size, sl_pips, tp_pips, magic_number, config_data)
                except Exception as e:
                    logging.error(f"Error in cycle for {symbol}: {e}")

            # Sleep in small increments to respond quickly to a stop request
            for _ in range(int(interval)):
                if not bot_running:
                    break
                time.sleep(1)
                
    except Exception as e:
        logging.error(f"Error in main bot loop: {e}")
    finally:
        bot_running = False
        mt5.shutdown()
        logging.info("Bot execution stopped and MT5 connection shut down.")

def stop_bot():
    """
    Stops the background bot loop.
    """
    global bot_running
    if bot_running:
        bot_running = False
        logging.info("Stop request sent to bot...")
    else:
        logging.info("Bot is not running.")
