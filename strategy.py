import pandas as pd
import ta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def calculate_indicators(df: pd.DataFrame, ema_fast_period: int, ema_slow_period: int, rsi_period: int) -> pd.DataFrame:
    """
    Calculates Fast EMA, Slow EMA, and RSI technical indicators on the given DataFrame.
    """
    if len(df) < max(ema_slow_period, rsi_period) + 5:
        logging.warning("Not enough data to calculate indicators.")
        return df

    # Calculate indicators using the 'ta' library
    df['ema_fast'] = ta.trend.ema_indicator(close=df['close'], window=ema_fast_period)
    df['ema_slow'] = ta.trend.ema_indicator(close=df['close'], window=ema_slow_period)
    df['rsi'] = ta.momentum.rsi(close=df['close'], window=rsi_period)
    
    return df

def check_signals(df: pd.DataFrame, rsi_overbought: float, rsi_oversold: float) -> str:
    """
    Checks the last completed candles for trading signals.
    Returns:
        'BUY'  - Buy signal
        'SELL' - Sell signal
        'HOLD' - No signal
    """
    if df is None or len(df) < 5 or 'ema_fast' not in df.columns:
        return 'HOLD'

    # We evaluate signals on the last CLOSED candle (index -2) to prevent repainting.
    # index -1 is the current candle which is still active and changing.
    # index -2 is the most recently completed candle.
    # index -3 is the candle before index -2.
    
    prev_fast = df['ema_fast'].iloc[-3]
    prev_slow = df['ema_slow'].iloc[-3]
    
    curr_fast = df['ema_fast'].iloc[-2]
    curr_slow = df['ema_slow'].iloc[-2]
    
    curr_rsi = df['rsi'].iloc[-2]
    
    logging.info(f"Checking signals -> Prev Fast: {prev_fast:.5f}, Prev Slow: {prev_slow:.5f} | Curr Fast: {curr_fast:.5f}, Curr Slow: {curr_slow:.5f} | RSI: {curr_rsi:.2f}")

    # BUY Signal: Fast EMA crosses above Slow EMA, and RSI is not overbought
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        if curr_rsi < rsi_overbought:
            logging.info("BUY signal generated: EMA crossover upward & RSI is under overbought threshold.")
            return 'BUY'
        else:
            logging.info("EMA crossover upward occurred, but RSI is overbought. BUY signal filtered.")
            
    # SELL Signal: Fast EMA crosses below Slow EMA, and RSI is not oversold
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        if curr_rsi > rsi_oversold:
            logging.info("SELL signal generated: EMA crossover downward & RSI is above oversold threshold.")
            return 'SELL'
        else:
            logging.info("EMA crossover downward occurred, but RSI is oversold. SELL signal filtered.")

    return 'HOLD'
