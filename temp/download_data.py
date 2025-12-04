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
    start_date = BACKTEST_START_DATE
    end_date = BACKTEST_END_DATE
    timeframes = TIMEFRAMES

    data_dir = "temp"

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

        # Fetch historical klines
        klines = client.get_historical_klines(symbol, interval, start_date, end_date)

        # Convert to DataFrame
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
        df = pd.DataFrame(klines, columns=columns)

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

        # Convert price columns to float
        price_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']
        df[price_cols] = df[price_cols].astype(float)

        # Save to CSV
        filename = f"{symbol}_{tf}_{start_date.replace('-', '')}_to_{end_date.replace('-', '')}.csv"
        filepath = os.path.join(data_dir, filename)
        df.to_csv(filepath, index=False)
        print(f"Saved {len(df)} rows to {filepath}")

        # Sleep to avoid rate limits
        time.sleep(1)

    print("Download complete!")

if __name__ == "__main__":
    download_data()
