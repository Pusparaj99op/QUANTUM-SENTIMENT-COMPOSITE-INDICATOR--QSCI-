#!/usr/bin/env python3
"""
Download BTCUSDT historical data from Binance for all timeframes
"""

import os
import sys
import pandas as pd
from binance.client import Client
from datetime import datetime
import time

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *

def download_data():
    # Use mainnet for data
    api_key = BINANCE_MAINNET_API_KEY
    api_secret = BINANCE_MAINNET_API_SECRET

    client = Client(api_key, api_secret)

    symbol = SYMBOL
    start_date = "2024-12-01"  # Download from Dec 2024 onwards
    end_date = datetime.now().strftime('%Y-%m-%d')  # Up to today
    timeframes = TIMEFRAMES

    data_dir = "BTC_DATA"

    for tf in timeframes:
        print(f"Downloading {symbol} data for timeframe {tf}...")

        # Binance interval mapping
        interval_map = {
            '1m': Client.KLINE_INTERVAL_1MINUTE,
            '5m': Client.KLINE_INTERVAL_5MINUTE,
            '15m': Client.KLINE_INTERVAL_15MINUTE,
            '30m': Client.KLINE_INTERVAL_30MINUTE,
            '1h': Client.KLINE_INTERVAL_1HOUR,
            '2h': Client.KLINE_INTERVAL_2HOUR,
            '4h': Client.KLINE_INTERVAL_4HOUR,
        }

        interval = interval_map[tf]

        # Find existing file with old end date
        old_filename = f"{symbol}_{tf}_20130101_to_20241201.csv"
        old_filepath = os.path.join(data_dir, old_filename)
        new_filepath = os.path.join(data_dir, f"{symbol}_{tf}_20130101_to_{end_date.replace('-', '')}.csv")

        if os.path.exists(old_filepath):
            existing_df = pd.read_csv(old_filepath)
            existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'])
            filepath = new_filepath  # save to new
            print(f"Loaded existing {len(existing_df)} rows from {old_filepath}")
        else:
            existing_df = pd.DataFrame()
            filepath = new_filepath
            print(f"No existing file found for {tf}, starting fresh")

        # Fetch new historical klines
        klines = client.get_historical_klines(symbol, interval, start_date, end_date)

        # Convert to DataFrame
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
        new_df = pd.DataFrame(klines, columns=columns)

        if new_df.empty:
            print(f"No new data for {tf}")
            continue

        # Convert timestamp to datetime
        new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
        new_df['close_time'] = pd.to_datetime(new_df['close_time'], unit='ms')

        # Convert price columns to float
        price_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']
        new_df[price_cols] = new_df[price_cols].astype(float)

        # Combine existing and new data, remove duplicates
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset='timestamp').sort_values('timestamp').reset_index(drop=True)

        # Save to CSV
        combined_df.to_csv(filepath, index=False)
        print(f"Saved {len(combined_df)} rows to {filepath} (added {len(new_df)} new rows)")

        # Sleep to avoid rate limits
        time.sleep(1)

    print("Download complete!")

if __name__ == "__main__":
    download_data()
