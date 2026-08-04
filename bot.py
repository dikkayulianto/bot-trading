import time
import os
import logging
import json
import collections
import requests
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

# Tracking last processed candle timestamp per symbol
last_processed_candles = {}

# File path for latest AI analysis persistence
ANALYSIS_JSON_FILE = os.path.join(os.path.dirname(__file__), "latest_ai_analysis.json")

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

def load_latest_ai_results():
    """
    Loads latest AI analysis results from JSON file.
    """
    if os.path.exists(ANALYSIS_JSON_FILE):
        try:
            with open(ANALYSIS_JSON_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_latest_ai_results(results):
    """
    Saves latest AI analysis results to JSON file.
    """
    try:
        with open(ANALYSIS_JSON_FILE, "w") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save latest AI results: {e}")

def initialize_mt5():
    """
    Initializes connection to the MetaTrader 5 terminal.
    """
    if mt5.terminal_info() is not None:
        return True

    logging.info("Initializing MetaTrader 5...")
    paths_to_try = [
        None,
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
        "comment": "Bot Close",
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
        "comment": "Bot Entry",
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

def get_gemini_market_analysis(symbol, timeframe_str, api_key, config_data):
    """
    Calls Google Gemini 3.5 Flash API to analyze the market and returns a recommendation.
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        mt5.symbol_select(symbol, True)
        symbol_info = mt5.symbol_info(symbol)
        
    if symbol_info is None:
        return {"status": "error", "message": f"Simbol {symbol} tidak ditemukan."}

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"status": "error", "message": f"Gagal mengambil harga tick {symbol}."}

    mt5_tf = TIMEFRAME_MAP.get(timeframe_str, mt5.TIMEFRAME_M5)
    df = get_historical_data(symbol, mt5_tf, count=60)
    if df is None or len(df) < 20:
        return {"status": "error", "message": f"Data historis {symbol} tidak cukup."}

    # Calculate indicators
    df = strategy.calculate_indicators(
        df, 
        config_data.get("ema_fast", 9), 
        config_data.get("ema_slow", 21), 
        config_data.get("rsi_period", 14)
    )

    curr_row = df.iloc[-1]
    
    # Compile summary of last 10 candles
    candles_summary = []
    for _, row in df.tail(10).iterrows():
        candles_summary.append(
            f"Time: {row['time'].strftime('%Y-%m-%d %H:%M')}, O: {row['open']:.5f}, H: {row['high']:.5f}, L: {row['low']:.5f}, C: {row['close']:.5f}, Vol: {row['tick_volume']}"
        )
    candles_summary_str = "\n".join(candles_summary)

    # Prompt
    prompt = f"""
    Anda adalah analis trading Forex profesional yang sangat cerdas.
    Tolong analisis pasangan mata uang {symbol} pada timeframe {timeframe_str} berdasarkan data harga dan indikator teknis berikut:
    
    - Harga saat ini: Bid={tick.bid:.5f}, Ask={tick.ask:.5f}
    - Candle Terakhir (OHLC): Open={curr_row['open']:.5f}, High={curr_row['high']:.5f}, Low={curr_row['low']:.5f}, Close={curr_row['close']:.5f}
    - EMA Fast ({config_data.get("ema_fast", 9)}): {curr_row['ema_fast']:.5f}
    - EMA Slow ({config_data.get("ema_slow", 21)}): {curr_row['ema_slow']:.5f}
    - RSI ({config_data.get("rsi_period", 14)}): {curr_row['rsi']:.2f}
    - Tren EMA: {'Bullish (Fast > Slow)' if curr_row['ema_fast'] > curr_row['ema_slow'] else 'Bearish (Fast < Slow)'}
    
    Analisis data historis 10 lilin terakhir (OHLCV):
    {candles_summary_str}
    
    Tolong berikan analisis pasar mendalam, tentukan area Support (S) dan Resistance (R), evaluasi kekuatan tren, lalu berikan rekomendasi keputusan (BUY, SELL, atau HOLD) beserta skor kepercayaan dalam persen (0-100%).
    
    Anda HARUS membalas HANYA dalam format JSON dengan struktur persis seperti di bawah ini tanpa markdown tambahan (seperti ```json):
    {{
      "recommendation": "BUY" atau "SELL" atau "HOLD",
      "confidence": nilai integer antara 0 hingga 100,
      "support": nilai float batas support,
      "resistance": nilai float batas resistance,
      "analysis": "Laporan analisis pasar lengkap Anda dalam Bahasa Indonesia. Gunakan tag HTML seperti <h3>, <p>, <ul>, dan <li> untuk membuat teks rapi."
    }}
    """

    # Call Gemini API (using gemini-3.5-flash which we verified works with v1beta)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.status_code != 200:
            return {"status": "error", "message": f"Gemini API HTTP {response.status_code}"}
        
        response_data = response.json()
        ai_text = response_data['candidates'][0]['content']['parts'][0]['text']
        ai_json = json.loads(ai_text)
        
        return {
            "status": "success",
            "recommendation": ai_json.get("recommendation", "HOLD").upper(),
            "confidence": int(ai_json.get("confidence", 50)),
            "support": float(ai_json.get("support", tick.bid)),
            "resistance": float(ai_json.get("resistance", tick.ask)),
            "analysis": ai_json.get("analysis", "Analisis berhasil diselesaikan.")
        }
    except Exception as e:
        return {"status": "error", "message": f"Gemini API Exception: {e}"}

def run_bot_cycle(symbol, timeframe_str, lot_size, sl_pips, tp_pips, magic_number, config_data):
    """
    A single execution cycle of the trading bot for a given symbol.
    Supports standard TECHNICAL mode and advanced AI-directed mode.
    """
    global last_processed_candles
    
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logging.error(f"Symbol {symbol} not found.")
        return
        
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            logging.error(f"Failed to select symbol {symbol}.")
            return

    mt5_tf = TIMEFRAME_MAP.get(timeframe_str, mt5.TIMEFRAME_M5)
    df = get_historical_data(symbol, mt5_tf, count=100)
    if df is None or len(df) < 5:
        return

    # Check strategy mode
    strategy_mode = config_data.get("strategy_mode", "AI").upper()
    
    # ----------------------------------------------------
    # MODE A: GEMINI AI DIRECTED STRATEGY
    # ----------------------------------------------------
    if strategy_mode == "AI":
        # Check if we have a closed candle
        latest_candle_time = df['time'].iloc[-1]
        
        # If it is the first run, or a new candle timestamp is detected
        is_new_candle = False
        if symbol not in last_processed_candles:
            last_processed_candles[symbol] = latest_candle_time
            is_new_candle = True
            logging.info(f"AI Strategy - Initializing tracking for {symbol} at candle {latest_candle_time}")
        elif latest_candle_time > last_processed_candles[symbol]:
            last_processed_candles[symbol] = latest_candle_time
            is_new_candle = True
            logging.info(f"AI Strategy - New candle detected for {symbol} at {latest_candle_time}. Triggering Gemini analysis...")

        if is_new_candle:
            api_key = config_data.get("gemini_api_key", "").strip()
            if not api_key:
                logging.error(f"AI Strategy - Gemini API Key is missing. Skipping cycle for {symbol}.")
                return

            logging.info(f"AI Strategy - Running Gemini AI Market Analysis for {symbol} on {timeframe_str}...")
            analysis_result = get_gemini_market_analysis(symbol, timeframe_str, api_key, config_data)
            
            if analysis_result["status"] == "success":
                rec = analysis_result["recommendation"]
                conf = analysis_result["confidence"]
                sup = analysis_result["support"]
                res = analysis_result["resistance"]
                ana = analysis_result["analysis"]
                min_conf = config_data.get("min_confidence", 70)
                
                # Update persistent JSON file
                latest_results = load_latest_ai_results()
                latest_results[symbol] = {
                    "recommendation": rec,
                    "confidence": conf,
                    "support": sup,
                    "resistance": res,
                    "analysis": ana,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                save_latest_ai_results(latest_results)

                logging.info(f"AI Strategy - {symbol} recommendation: {rec} (Confidence: {conf}%, threshold: {min_conf}%)")

                # Get open positions
                positions = mt5.positions_get(symbol=symbol, magic=magic_number)
                if positions is None:
                    positions = []
                buy_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_BUY]
                sell_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_SELL]

                if rec == "BUY":
                    if conf >= min_conf:
                        # Close opposing position
                        for pos in sell_positions:
                            logging.info(f"AI Strategy - Closing opposing SELL position {pos.ticket} before opening BUY.")
                            close_position(pos, symbol_info)
                        # Open position
                        if len(buy_positions) == 0:
                            open_position(symbol, mt5.ORDER_TYPE_BUY, lot_size, sl_pips, tp_pips, magic_number, symbol_info)
                    else:
                        logging.info(f"AI Strategy - BUY signal rejected due to confidence score below limit ({conf}% < {min_conf}%).")

                elif rec == "SELL":
                    if conf >= min_conf:
                        # Close opposing position
                        for pos in buy_positions:
                            logging.info(f"AI Strategy - Closing opposing BUY position {pos.ticket} before opening SELL.")
                            close_position(pos, symbol_info)
                        # Open position
                        if len(sell_positions) == 0:
                            open_position(symbol, mt5.ORDER_TYPE_SELL, lot_size, sl_pips, tp_pips, magic_number, symbol_info)
                    else:
                        logging.info(f"AI Strategy - SELL signal rejected due to confidence score below limit ({conf}% < {min_conf}%).")
                
                else: # HOLD
                    logging.info(f"AI Strategy - recommendation for {symbol} is HOLD. Keeping positions.")
            else:
                logging.error(f"AI Strategy - Gemini analysis failed for {symbol}: {analysis_result['message']}")
        else:
            logging.info(f"AI Strategy - {symbol} candle {latest_candle_time} is still forming. Waiting for next close...")

    # ----------------------------------------------------
    # MODE B: TRADITIONAL TECHNICAL STRATEGY
    # ----------------------------------------------------
    else:
        # 1. Calculate Technical Indicators
        df = strategy.calculate_indicators(
            df, 
            config_data.get("ema_fast", 9), 
            config_data.get("ema_slow", 21), 
            config_data.get("rsi_period", 14)
        )
        
        # 2. Check for Trading Signals
        signal = strategy.check_signals(
            df, 
            config_data.get("rsi_overbought", 70), 
            config_data.get("rsi_oversold", 30)
        )
        
        # 3. Get active positions
        positions = mt5.positions_get(symbol=symbol, magic=magic_number)
        if positions is None:
            positions = []
        buy_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_BUY]
        sell_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_SELL]
        
        logging.info(f"{symbol} (TF: {timeframe_str}) - Technical Signal: {signal} | Open BUYs: {len(buy_positions)}, Open SELLs: {len(sell_positions)}")

        # 4. Execute trades based on signals
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
