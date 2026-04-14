"""
Pure pandas/numpy technical indicator calculations.
No third-party TA library required — keeps dependencies minimal and stable.
"""

import numpy as np
import pandas as pd


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = _ema(close, fast) - _ema(close, slow)
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    close: pd.Series,
    period: int = 20,
    num_std: int = 2,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return mid + num_std * std, mid, mid - num_std * std


def calculate_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)

    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    # Keep only the dominant direction
    mask = plus_dm >= minus_dm
    plus_dm = plus_dm.where(mask, 0)
    minus_dm = minus_dm.where(~mask, 0)

    atr = _ema(tr, period)
    plus_di = 100 * _ema(plus_dm, period) / atr.replace(0, np.nan)
    minus_di = 100 * _ema(minus_dm, period) / atr.replace(0, np.nan)

    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    adx = _ema(dx, period)
    return adx, plus_di, minus_di


def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (volume * direction).cumsum()


def calculate_all_indicators(hist: pd.DataFrame) -> pd.DataFrame:
    """Add all indicator columns to a copy of *hist* and return it."""
    df = hist.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    df["RSI"] = calculate_rsi(close)

    macd, macd_sig, macd_hist = calculate_macd(close)
    df["MACD"] = macd
    df["MACD_Signal"] = macd_sig
    df["MACD_Hist"] = macd_hist

    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(close)
    df["BB_Upper"] = bb_upper
    df["BB_Mid"] = bb_mid
    df["BB_Lower"] = bb_lower

    df["SMA_50"] = close.rolling(50).mean()
    df["SMA_200"] = close.rolling(200).mean()

    adx, plus_di, minus_di = calculate_adx(high, low, close)
    df["ADX"] = adx
    df["Plus_DI"] = plus_di
    df["Minus_DI"] = minus_di

    df["OBV"] = calculate_obv(close, volume)
    df["Volume_MA20"] = volume.rolling(20).mean()

    df["High_52W"] = close.rolling(252).max()
    df["Low_52W"] = close.rolling(252).min()

    return df
