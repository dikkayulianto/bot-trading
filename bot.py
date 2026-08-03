import time
import os
import logging
import MetaTrader5 as mt5
import pandas as pd

import config
import strategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

def initialize_mt5():
    """
    Initializes connection to the MetaTrader 5 terminal.
    """
    logging.info("Initializing MetaTrader 5...")
    if not mt5.initialize():
        logging.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        print("\n=== KONEKSI MT5 GAGAL ===")
        print("Silakan pastikan aplikasi MetaTrader 5 (MT5) sudah terbuka dan Anda sudah masuk ke akun trading Anda.")
        print("=========================\n")
        return False
    
    # Print connection status
    terminal_info = mt5.terminal_info()
    if terminal_info is not None:
        logging.info(f"Connected to MT5 terminal: {terminal_info.company} - {terminal_info.name}")
    else:
        logging.warning("Connected, but terminal info is unavailable.")
        
    return True

def get_filling_type(symbol_info):
    """
    Determines the correct order filling mode supported by the broker for the symbol.
    """
    filling_mode = symbol_info.filling_mode
    if filling_mode & mt5.SYMBOL_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    elif filling_mode & mt5.SYMBOL_FILLING_IOC:
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
        
    # Convert numpy structured array to pandas DataFrame
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

    # Close buy with sell, close sell with buy
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
        "comment": "Antigravity Close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": get_filling_type(symbol_info)
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Failed to close position {position.ticket}. Code: {result.retcode}, Description: {result.comment}")
        return False
        
    logging.info(f"Position {position.ticket} closed successfully at {price}.")
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
    
    # Calculate SL and TP levels based on 5-digit vs 4-digit pips
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

    # Set up request dictionary
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
        "comment": "Antigravity Entry",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": get_filling_type(symbol_info)
    }

    logging.info(f"Sending {order_name} order: Lot={lot_size}, Price={price:.5f}, SL={sl:.5f}, TP={tp:.5f}")
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Order failed. Code: {result.retcode}, Description: {result.comment}")
        return False
        
    logging.info(f"Order executed successfully! Ticket: {result.order}")
    return True

def run_bot_cycle(symbol, timeframe, lot_size, sl_pips, tp_pips, magic_number):
    """
    A single execution cycle of the trading bot.
    """
    # Ensure symbol is selected and visible
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logging.error(f"Symbol {symbol} not found.")
        return
        
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            logging.error(f"Failed to select symbol {symbol}.")
            return
            
    # 1. Fetch historical data
    df = get_historical_data(symbol, timeframe, count=100)
    if df is None:
        return

    # 2. Calculate Strategy Indicators
    df = strategy.calculate_indicators(df, config.EMA_FAST, config.EMA_SLOW, config.RSI_PERIOD)
    
    # 3. Check for Trading Signals
    signal = strategy.check_signals(df, config.RSI_OVERBOUGHT, config.RSI_OVERSOLD)
    
    # 4. Get active positions for this magic number and symbol
    positions = mt5.positions_get(symbol=symbol, magic=magic_number)
    
    buy_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_BUY]
    sell_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_SELL]
    
    logging.info(f"Signal: {signal} | Open BUYs: {len(buy_positions)}, Open SELLs: {len(sell_positions)}")

    # 5. Execute trades based on signals
    if signal == 'BUY':
        # Close any existing sell positions first
        for pos in sell_positions:
            logging.info(f"Closing opposing SELL position {pos.ticket} before opening BUY.")
            close_position(pos, symbol_info)
            
        # Open BUY position if we don't have one
        if len(buy_positions) == 0:
            open_position(symbol, mt5.ORDER_TYPE_BUY, lot_size, sl_pips, tp_pips, magic_number, symbol_info)
        else:
            logging.info("BUY signal generated, but we already have an open BUY position. Skipping.")

    elif signal == 'SELL':
        # Close any existing buy positions first
        for pos in buy_positions:
            logging.info(f"Closing opposing BUY position {pos.ticket} before opening SELL.")
            close_position(pos, symbol_info)
            
        # Open SELL position if we don't have one
        if len(sell_positions) == 0:
            open_position(symbol, mt5.ORDER_TYPE_SELL, lot_size, sl_pips, tp_pips, magic_number, symbol_info)
        else:
            logging.info("SELL signal generated, but we already have an open SELL position. Skipping.")
            
    else:
        logging.info("No actionable signal. Holding position.")

def main():
    if not initialize_mt5():
        return
        
    logging.info("Trading Bot started. Entering main loop...")
    print("\n==========================================")
    print(f"BOT TRADING MT5 AKTIF - MEMANTAU: {', '.join(config.SYMBOLS)}")
    print("Tekan Ctrl+C di terminal ini untuk mematikan bot.")
    print("==========================================\n")
    
    try:
        while True:
            for symbol in config.SYMBOLS:
                logging.info(f"--- Processing {symbol} ---")
                run_bot_cycle(
                    symbol=symbol,
                    timeframe=config.TIMEFRAME,
                    lot_size=config.LOT_SIZE,
                    sl_pips=config.SL_PIPS,
                    tp_pips=config.TP_PIPS,
                    magic_number=config.MAGIC_NUMBER
                )
            time.sleep(config.LOOP_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logging.info("Bot execution stopped by user (Ctrl+C).")
    finally:
        mt5.shutdown()
        logging.info("Connection to MetaTrader 5 shut down.")

if __name__ == "__main__":
    main()
