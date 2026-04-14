"""
Google Sheets output layer.

Authentication priority:
  1. GOOGLE_CREDENTIALS env var  (JSON string — for GitHub Actions secrets)
  2. credentials.json file       (local dev)

The spreadsheet is created automatically if it doesn't exist.
Three worksheets are maintained:
  • Top Picks    — clean daily summary, top 15 by score
  • Full Data    — all scored stocks with every indicator sub-score
  • History Log  — running append of the top-5 each day
"""

import json
import logging
import os

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

_TOP_PICKS_COLS = [
    "Symbol", "Name", "Sector", "Price", "Score",
    "RSI", "MACD_Signal", "Fresh_MACD_Cross",
    "Above_50SMA", "Above_200SMA", "Crossed_50SMA_Recently",
    "ADX", "From_52W_High_%", "From_52W_Low_%",
    "Market_Cap_B", "Avg_Volume_M", "Run_Date",
]

_HISTORY_COLS = [
    "Run_Date", "Rank", "Symbol", "Name", "Score",
    "RSI", "MACD_Signal", "Above_50SMA", "Price",
]


def _get_client() -> gspread.Client:
    creds_env = os.environ.get("GOOGLE_CREDENTIALS")
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")

    if creds_env:
        creds = Credentials.from_service_account_info(
            json.loads(creds_env), scopes=_SCOPES
        )
    elif os.path.exists(creds_file):
        creds = Credentials.from_service_account_file(creds_file, scopes=_SCOPES)
    else:
        raise EnvironmentError(
            "Google credentials not found.\n"
            "  • Set the GOOGLE_CREDENTIALS env var (JSON string), OR\n"
            "  • Place a credentials.json file in the project root."
        )
    return gspread.authorize(creds)


def _get_or_create_sheet(spreadsheet, name: str, rows: int = 200, cols: int = 30):
    try:
        return spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(name, rows=rows, cols=cols)


def _safe_values(df: pd.DataFrame) -> list[list]:
    """Convert DataFrame to a list of lists that gspread can serialise."""
    return df.where(pd.notna(df), other="").values.tolist()


def write_to_sheets(results_df: pd.DataFrame, spreadsheet_name: str) -> str:
    """
    Write screening results to Google Sheets.
    Returns the spreadsheet URL.
    """
    client = _get_client()

    try:
        ss = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        ss = client.create(spreadsheet_name)
        logger.info(f"Created new spreadsheet: '{spreadsheet_name}'")

    _write_top_picks(ss, results_df)
    _write_full_data(ss, results_df)
    _write_history_log(ss, results_df)

    logger.info(f"Sheets updated → {ss.url}")
    return ss.url


def _write_top_picks(ss, df: pd.DataFrame) -> None:
    ws = _get_or_create_sheet(ss, "Top Picks")
    ws.clear()

    run_date = df["Run_Date"].iloc[0]
    run_time = df["Run_Time_UTC"].iloc[0]
    n_screened = len(df)

    top15 = df[_TOP_PICKS_COLS].head(15)

    header_block = [
        ["DAILY STOCK SCREENER — Bullish Shift Candidates"],
        [f"Last run: {run_date} {run_time} UTC   |   Universe: {n_screened} stocks screened"],
        [],  # blank spacer
        _TOP_PICKS_COLS,
    ]
    ws.update("A1", header_block + _safe_values(top15))


def _write_full_data(ss, df: pd.DataFrame) -> None:
    ws = _get_or_create_sheet(ss, "Full Data")
    ws.clear()
    ws.update("A1", [df.columns.tolist()] + _safe_values(df))


def _write_history_log(ss, df: pd.DataFrame) -> None:
    ws = _get_or_create_sheet(ss, "History Log", rows=2000, cols=10)

    # Add header if the sheet is empty
    if ws.row_count == 0 or not ws.get("A1"):
        ws.update("A1", [_HISTORY_COLS])

    run_date = df["Run_Date"].iloc[0]
    rows = []
    for rank, (_, row) in enumerate(df.head(5).iterrows(), start=1):
        rows.append([
            run_date, rank,
            row["Symbol"], row["Name"], row["Score"],
            row["RSI"], row["MACD_Signal"], row["Above_50SMA"], row["Price"],
        ])
    ws.append_rows(rows, value_input_option="RAW")
