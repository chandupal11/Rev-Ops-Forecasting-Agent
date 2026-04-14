"""
Stock Screener — entry point.

Run locally:
    python main.py

Environment variables:
    GOOGLE_CREDENTIALS   JSON string of your service account key (required for Sheets output)
    SPREADSHEET_NAME     Name of the target Google Sheet (default: "Stock Screener Results")
"""

import logging
import os

import pandas as pd

from screener.config import (
    DATA_PERIOD,
    FETCH_DELAY,
    MIN_AVG_VOLUME,
    MIN_MARKET_CAP,
    NASDAQ_TOP_25,
    SP500_TOP_25,
)
from screener.data_fetcher import fetch_all_tickers, filter_by_fundamentals
from screener.indicators import calculate_all_indicators
from screener.scorer import score_stock
from screener.sheets_writer import write_to_sheets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_screener() -> pd.DataFrame:
    # Deduplicated union of both index lists
    universe = list(dict.fromkeys(NASDAQ_TOP_25 + SP500_TOP_25))
    logger.info(f"Universe: {len(universe)} unique tickers  (NASDAQ top 25 + S&P 500 top 25)")

    logger.info("Fetching market data from Yahoo Finance...")
    raw_data = fetch_all_tickers(universe, period=DATA_PERIOD, delay=FETCH_DELAY)

    logger.info(
        f"Applying filters — market cap > ${MIN_MARKET_CAP / 1e9:.0f}B, "
        f"avg volume > {MIN_AVG_VOLUME / 1e6:.0f}M"
    )
    filtered = filter_by_fundamentals(raw_data, MIN_MARKET_CAP, MIN_AVG_VOLUME)
    logger.info(f"{len(filtered)} / {len(universe)} tickers passed filters")

    results = []
    for symbol, data in filtered.items():
        logger.info(f"Scoring {symbol}...")
        df_ind = calculate_all_indicators(data["hist"])
        result = score_stock(df_ind, symbol, data["info"])
        if result:
            results.append(result)

    if not results:
        logger.error("No scoreable results — check data quality or filter thresholds")
        return pd.DataFrame()

    results_df = (
        pd.DataFrame(results)
        .sort_values("Score", ascending=False)
        .reset_index(drop=True)
    )

    _print_summary(results_df)
    return results_df


def _print_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("  TOP 10 BULLISH SHIFT CANDIDATES")
    print("=" * 60)
    cols = ["Symbol", "Name", "Score", "RSI", "MACD_Signal", "Above_50SMA", "Price"]
    print(df[cols].head(10).to_string(index=True))
    print("=" * 60 + "\n")


def main() -> None:
    results_df = run_screener()
    if results_df.empty:
        return

    spreadsheet_name = os.environ.get("SPREADSHEET_NAME", "Stock Screener Results")
    has_creds = bool(os.environ.get("GOOGLE_CREDENTIALS")) or os.path.exists("credentials.json")

    if has_creds:
        logger.info("Writing results to Google Sheets...")
        url = write_to_sheets(results_df, spreadsheet_name)
        print(f"Google Sheet updated: {url}")
    else:
        out_path = "screener_results.csv"
        results_df.to_csv(out_path, index=False)
        logger.warning(f"No Google credentials found — saved to {out_path}")


if __name__ == "__main__":
    main()
