import time
import logging
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_ticker_data(symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Fetch historical OHLCV data for a single ticker via yfinance."""
    try:
        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty:
            logger.warning(f"{symbol}: no data returned")
            return None
        return hist
    except Exception as exc:
        logger.error(f"{symbol}: history fetch failed — {exc}")
        return None


def get_ticker_info(symbol: str) -> dict:
    """Return a lightweight metadata dict for the ticker."""
    try:
        info = yf.Ticker(symbol).info
        return {
            "market_cap": info.get("marketCap", 0),
            "avg_volume": info.get("averageVolume", 0),
            "name": info.get("shortName", symbol),
            "sector": info.get("sector", "Unknown"),
        }
    except Exception as exc:
        logger.error(f"{symbol}: info fetch failed — {exc}")
        return {"market_cap": 0, "avg_volume": 0, "name": symbol, "sector": "Unknown"}


def fetch_all_tickers(symbols: list, period: str = "1y", delay: float = 0.5) -> dict:
    """
    Fetch data + metadata for every ticker in *symbols*.

    Returns:
        {symbol: {"hist": DataFrame, "info": dict}}
    """
    results = {}
    for i, symbol in enumerate(symbols):
        logger.info(f"Fetching {symbol} ({i + 1}/{len(symbols)})")
        hist = fetch_ticker_data(symbol, period)
        info = get_ticker_info(symbol)
        if hist is not None:
            results[symbol] = {"hist": hist, "info": info}
        time.sleep(delay)
    return results


def filter_by_fundamentals(
    ticker_data: dict,
    min_market_cap: int,
    min_avg_volume: int,
) -> dict:
    """Drop tickers that don't meet market cap and average volume thresholds."""
    filtered = {}
    for symbol, data in ticker_data.items():
        mc = data["info"].get("market_cap", 0)
        vol = data["info"].get("avg_volume", 0)
        if mc >= min_market_cap and vol >= min_avg_volume:
            filtered[symbol] = data
        else:
            logger.info(
                f"Filtered out {symbol}: "
                f"market_cap=${mc / 1e9:.1f}B  avg_volume={vol / 1e6:.1f}M"
            )
    return filtered
