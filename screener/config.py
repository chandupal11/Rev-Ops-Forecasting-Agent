# Stock universe - top 25 per index by market cap (updated April 2026)
NASDAQ_TOP_25 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META",
    "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "QCOM", "TXN",
    "AMAT", "HON", "MU", "KLAC", "LRCX",
    "PANW", "MRVL", "FTNT", "CDNS", "SNPS",
]

SP500_TOP_25 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META",
    "GOOGL", "GOOG", "TSLA", "BRK-B", "AVGO",
    "JPM", "V", "MA", "UNH", "XOM",
    "HD", "PG", "COST", "JNJ", "ABBV",
    "BAC", "LLY", "WMT", "MRK", "CVX",
]

# Filters
MIN_MARKET_CAP = 10_000_000_000   # $10 billion
MIN_AVG_VOLUME = 2_000_000        # 2 million shares/day

# Indicator parameters
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2
ADX_PERIOD = 14
SMA_SHORT = 50
SMA_LONG = 200
VOLUME_LOOKBACK = 20
DATA_PERIOD = "1y"

# API rate limiting (seconds between yfinance calls)
FETCH_DELAY = 0.5
