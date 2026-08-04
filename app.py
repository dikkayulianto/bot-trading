import threading
import json
import os
import logging
from flask import Flask, jsonify, request, render_template
import pandas as pd

import bot
import MetaTrader5 as mt5

app = Flask(__name__)

# Mute Werkzeug logging to prevent HTTP request polling logs from flooding our console
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Ensure absolute paths for config.json
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def read_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        # Return fallback default config
        return {
            "symbols": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
            "timeframe": "M5",
            "lot_size": 0.01,
            "sl_pips": 15.0,
            "tp_pips": 30.0,
            "magic_number": 20260803,
            "ema_fast": 9,
            "ema_slow": 21,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "loop_interval_seconds": 10
        }

def save_config(data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving config.json: {e}")
        return False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        new_config = request.json
        # Convert numeric values to proper types
        try:
            new_config["lot_size"] = float(new_config["lot_size"])
            new_config["sl_pips"] = float(new_config["sl_pips"])
            new_config["tp_pips"] = float(new_config["tp_pips"])
            new_config["magic_number"] = int(new_config["magic_number"])
            new_config["ema_fast"] = int(new_config["ema_fast"])
            new_config["ema_slow"] = int(new_config["ema_slow"])
            new_config["rsi_period"] = int(new_config["rsi_period"])
            new_config["rsi_overbought"] = float(new_config["rsi_overbought"])
            new_config["rsi_oversold"] = float(new_config["rsi_oversold"])
            new_config["loop_interval_seconds"] = int(new_config["loop_interval_seconds"])
            
            # symbols can be a list or comma-separated string
            if isinstance(new_config["symbols"], str):
                new_config["symbols"] = [s.strip().upper() for s in new_config["symbols"].split(",") if s.strip()]
        except (ValueError, TypeError, KeyError) as e:
            return jsonify({"status": "error", "message": f"Invalid configuration values: {e}"}), 400

        if save_config(new_config):
            return jsonify({"status": "success", "message": "Configuration saved successfully."})
        else:
            return jsonify({"status": "error", "message": "Failed to save configuration file."}), 500
            
    # GET method
    return jsonify(read_config())

@app.route("/api/status", methods=["GET"])
def api_status():
    status = {
        "bot_running": bot.bot_running,
        "mt5_connected": False,
        "account": None,
        "positions": []
    }
    
    # Check MT5 connection and pull details
    is_initialized = False
    if bot.bot_running:
        is_initialized = True
    else:
        # If bot is not running, temporarily initialize to fetch info
        try:
            is_initialized = mt5.initialize()
        except Exception:
            is_initialized = False
            
    if is_initialized:
        status["mt5_connected"] = True
        
        # Fetch account info
        acc = mt5.account_info()
        if acc:
            status["account"] = {
                "login": acc.login,
                "server": acc.server,
                "balance": acc.balance,
                "equity": acc.equity,
                "profit": acc.profit,
                "margin": acc.margin,
                "leverage": acc.leverage,
                "currency": acc.currency
            }
            
        # Fetch open positions
        positions = mt5.positions_get()
        if positions:
            for p in positions:
                status["positions"].append({
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                    "volume": p.volume,
                    "price_open": p.price_open,
                    "price_current": p.price_current,
                    "sl": p.sl,
                    "tp": p.tp,
                    "profit": p.profit
                })
        
        # Shutdown if initialized temporarily
        if not bot.bot_running:
            mt5.shutdown()
            
    return jsonify(status)

@app.route("/api/logs", methods=["GET"])
def api_logs():
    # Return in-memory logs list
    return jsonify(list(bot.log_history))

@app.route("/api/start", methods=["POST"])
def api_start():
    if bot.bot_running:
        return jsonify({"status": "error", "message": "Bot is already running."}), 400
        
    # Start bot in a background thread
    t = threading.Thread(target=bot.start_bot, name="TradingBotThread", daemon=True)
    t.start()
    return jsonify({"status": "success", "message": "Trading bot start request triggered."})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    if not bot.bot_running:
        return jsonify({"status": "error", "message": "Bot is not running."}), 400
        
    bot.stop_bot()
    return jsonify({"status": "success", "message": "Trading bot stop request sent."})

import requests

@app.route("/api/ai-analysis", methods=["GET"])
def api_ai_analysis():
    symbol = request.args.get("symbol", "").upper().strip()
    if not symbol:
        return jsonify({"status": "error", "message": "Symbol is required."}), 400

    config_data = read_config()
    api_key = config_data.get("gemini_api_key", "").strip()
    if not api_key:
        return jsonify({"status": "error", "message": "Mohon masukkan Gemini API Key Anda terlebih dahulu di panel pengaturan."}), 400

    # Ensure MT5 is initialized
    is_temp_init = False
    if not bot.bot_running:
        try:
            if not mt5.initialize():
                return jsonify({"status": "error", "message": "Gagal menghubungkan ke terminal MT5."}), 500
            is_temp_init = True
        except Exception as e:
            return jsonify({"status": "error", "message": f"MT5 Init Exception: {e}"}), 500

    try:
        # Get Symbol Info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return jsonify({"status": "error", "message": f"Simbol {symbol} tidak ditemukan di MT5."}), 400
            
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return jsonify({"status": "error", "message": f"Gagal mengambil tick harga untuk {symbol}."}), 500

        # Get historical rates
        tf_str = config_data.get("timeframe", "M5")
        mt5_tf = bot.TIMEFRAME_MAP.get(tf_str, mt5.TIMEFRAME_M5)
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, 100)
        
        if rates is None or len(rates) < 30:
            return jsonify({"status": "error", "message": f"Data historis untuk {symbol} tidak mencukupi."}), 500

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Calculate technical indicators
        import strategy
        df = strategy.calculate_indicators(
            df, 
            config_data.get("ema_fast", 9), 
            config_data.get("ema_slow", 21), 
            config_data.get("rsi_period", 14)
        )
        
        # Current values
        curr_row = df.iloc[-1]
        
        # Form summary of last 10 candles
        candles_summary = []
        last_10 = df.tail(10)
        for _, row in last_10.iterrows():
            candles_summary.append(
                f"Time: {row['time'].strftime('%Y-%m-%d %H:%M')}, O: {row['open']:.5f}, H: {row['high']:.5f}, L: {row['low']:.5f}, C: {row['close']:.5f}, Vol: {row['tick_volume']}"
            )
        candles_summary_str = "\n".join(candles_summary)

        # Prepare Prompt for Gemini
        prompt = f"""
        Anda adalah analis trading Forex profesional yang sangat cerdas.
        Tolong analisis pasangan mata uang {symbol} pada timeframe {tf_str} berdasarkan data harga dan indikator teknis berikut:
        
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

        # Call Google Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
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
        
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": f"Gemini API Error: {response.text}"}), response.status_code

        response_data = response.json()
        
        try:
            # Parse the text response which contains the JSON
            ai_text = response_data['candidates'][0]['content']['parts'][0]['text']
            ai_json = json.loads(ai_text)
            
            # Make sure keys exist
            rec = ai_json.get("recommendation", "HOLD")
            conf = ai_json.get("confidence", 50)
            sup = ai_json.get("support", tick.bid)
            res = ai_json.get("resistance", tick.ask)
            ana = ai_json.get("analysis", "Gagal menganalisis pasar.")
            
            return jsonify({
                "status": "success",
                "data": {
                    "recommendation": rec,
                    "confidence": conf,
                    "support": float(sup),
                    "resistance": float(res),
                    "analysis": ana
                }
            })
        except Exception as parse_err:
            logging.error(f"Failed to parse Gemini response: {parse_err}")
            return jsonify({"status": "error", "message": "Gagal mengurai respon analisis dari AI."}), 500

    except Exception as e:
        logging.error(f"Exception in AI Analysis endpoint: {e}")
        return jsonify({"status": "error", "message": f"Sistem Error: {e}"}), 500
        
    finally:
        if is_temp_init:
            mt5.shutdown()

if __name__ == "__main__":
    # Ensure templates and static folders exist
    os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "static", "css"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "static", "js"), exist_ok=True)
    
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
