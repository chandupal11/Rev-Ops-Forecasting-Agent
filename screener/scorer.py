"""
Bullish 'shift higher' scoring engine.

Each indicator contributes a sub-score; all sub-scores sum to a max of 10.
The final Score is normalised to the 0–10 range and rounded to 2 dp.

Sub-score breakdown
-------------------
RSI       0–2   (oversold-to-recovering zone is most bullish)
MACD      0–2   (fresh crossover scores highest)
MA        0–2   (price vs 50/200 SMA position)
BB        0–1   (proximity to lower band = bounce candidate)
Volume    0–1   (recent volume surge vs 20-day average)
OBV       0–1   (positive 10-day OBV slope)
ADX       0–1   (strong uptrend confirmed by DI alignment)
Total max = 10
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_MAX_SCORE = 10  # RSI(2) + MACD(2) + MA(2) + BB(1) + Vol(1) + OBV(1) + ADX(1)


def score_stock(df: pd.DataFrame, symbol: str, info: dict) -> dict | None:
    """Score a single stock and return a result dict, or None if data is thin."""
    if df.empty or len(df) < 200:
        logger.warning(f"{symbol}: skipped — need ≥200 rows, got {len(df)}")
        return None

    latest = df.iloc[-1]
    prev5 = df.iloc[-5:]

    price = latest["Close"]

    # ------------------------------------------------------------------ RSI
    rsi = latest.get("RSI", 50)
    if 30 <= rsi <= 45:
        rsi_score = 2.0   # prime oversold-bounce zone
    elif 45 < rsi <= 55:
        rsi_score = 1.5   # recovering momentum
    elif 55 < rsi <= 65:
        rsi_score = 1.0   # mild bullish drift
    elif rsi < 30:
        rsi_score = 0.5   # deeply oversold — signal present but risky
    else:
        rsi_score = 0.0   # overbought

    # ------------------------------------------------------------------ MACD
    macd_val = latest.get("MACD", 0)
    sig_val = latest.get("MACD_Signal", 0)
    bullish_macd = macd_val > sig_val

    # Fresh crossover: was bearish 3 sessions ago, now bullish
    fresh_cross = (
        len(df) > 3
        and df["MACD"].iloc[-4] < df["MACD_Signal"].iloc[-4]
        and bullish_macd
    )
    if fresh_cross:
        macd_score = 2.0
    elif bullish_macd and latest.get("MACD_Hist", 0) > 0:
        macd_score = 1.5
    elif bullish_macd:
        macd_score = 1.0
    else:
        macd_score = 0.0

    # ------------------------------------------------------------------ Moving averages
    sma50 = latest.get("SMA_50", price)
    sma200 = latest.get("SMA_200", price)
    above_50 = price > sma50
    above_200 = price > sma200

    # Crossed above 50 SMA within the last 5 sessions
    crossed_50 = (
        len(df) > 6
        and df["Close"].iloc[-7] < df["SMA_50"].iloc[-7]
        and above_50
    )
    if crossed_50:
        ma_score = 2.0
    elif above_50 and above_200:
        ma_score = 1.5
    elif above_50:
        ma_score = 1.0
    elif price > sma200 * 0.98:
        ma_score = 0.5   # close to 50 SMA from below
    else:
        ma_score = 0.0

    # ------------------------------------------------------------------ Bollinger Bands
    bb_upper = latest.get("BB_Upper", price)
    bb_lower = latest.get("BB_Lower", price)
    bb_width = bb_upper - bb_lower

    if bb_width > 0:
        bb_pos = (price - bb_lower) / bb_width   # 0 = at lower, 1 = at upper
        if bb_pos <= 0.10:
            bb_score = 1.0
        elif bb_pos <= 0.25:
            bb_score = 0.75
        elif bb_pos <= 0.45:
            bb_score = 0.5
        else:
            bb_score = 0.0
    else:
        bb_score = 0.0

    # ------------------------------------------------------------------ Volume
    recent_vol = prev5["Volume"].mean()
    avg_vol = latest.get("Volume_MA20", recent_vol) or recent_vol

    vol_ratio = recent_vol / avg_vol if avg_vol else 1.0
    if vol_ratio >= 1.5:
        vol_score = 1.0
    elif vol_ratio >= 1.2:
        vol_score = 0.5
    else:
        vol_score = 0.0

    # ------------------------------------------------------------------ OBV trend
    obv_series = df["OBV"].iloc[-10:].values
    if len(obv_series) >= 2:
        slope = np.polyfit(range(len(obv_series)), obv_series, 1)[0]
        obv_score = 1.0 if slope > 0 else 0.0
    else:
        obv_score = 0.0

    # ------------------------------------------------------------------ ADX
    adx = latest.get("ADX", 0)
    plus_di = latest.get("Plus_DI", 0)
    minus_di = latest.get("Minus_DI", 0)

    if adx > 25 and plus_di > minus_di:
        adx_score = 1.0
    elif adx > 20 and plus_di > minus_di:
        adx_score = 0.5
    else:
        adx_score = 0.0

    # ------------------------------------------------------------------ Total
    raw_total = rsi_score + macd_score + ma_score + bb_score + vol_score + obv_score + adx_score
    final_score = round((raw_total / _MAX_SCORE) * 10, 2)

    # ------------------------------------------------------------------ Context fields
    high_52w = latest.get("High_52W", price)
    low_52w = latest.get("Low_52W", price)
    from_52w_high = round(((price - high_52w) / high_52w) * 100, 1) if high_52w else None
    from_52w_low = round(((price - low_52w) / low_52w) * 100, 1) if low_52w else None

    now = datetime.utcnow()

    return {
        "Symbol": symbol,
        "Name": info.get("name", symbol),
        "Sector": info.get("sector", "Unknown"),
        "Price": round(price, 2),
        "Score": final_score,
        # Readable indicator signals
        "RSI": round(rsi, 1),
        "MACD_Signal": "Bullish" if bullish_macd else "Bearish",
        "Fresh_MACD_Cross": "Yes" if fresh_cross else "No",
        "Above_50SMA": "Yes" if above_50 else "No",
        "Above_200SMA": "Yes" if above_200 else "No",
        "Crossed_50SMA_Recently": "Yes" if crossed_50 else "No",
        "ADX": round(adx, 1),
        "From_52W_High_%": from_52w_high,
        "From_52W_Low_%": from_52w_low,
        # Sub-scores (useful for debugging / tuning weights)
        "Sub_RSI": rsi_score,
        "Sub_MACD": macd_score,
        "Sub_MA": ma_score,
        "Sub_BB": bb_score,
        "Sub_Volume": vol_score,
        "Sub_OBV": obv_score,
        "Sub_ADX": adx_score,
        # Metadata
        "Market_Cap_B": round(info.get("market_cap", 0) / 1e9, 1),
        "Avg_Volume_M": round(info.get("avg_volume", 0) / 1e6, 1),
        "Run_Date": now.strftime("%Y-%m-%d"),
        "Run_Time_UTC": now.strftime("%H:%M"),
    }
