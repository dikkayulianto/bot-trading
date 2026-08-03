import threading
import json
import os
import logging
from flask import Flask, jsonify, request, render_template

import bot
import MetaTrader5 as mt5

app = Flask(__name__)

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

if __name__ == "__main__":
    # Ensure templates and static folders exist
    os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "static", "css"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "static", "js"), exist_ok=True)
    
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
