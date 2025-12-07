
import os
import sys
import pandas as pd
import numpy as np
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any

# Mock environment variables BEFORE imports
os.environ["TRADING_MODE"] = "backtest_simulation"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHANNEL_ID"] = ""
os.environ["MONGODB_URI"] = ""
os.environ["LOG_LEVEL"] = "INFO"
os.environ["INITIAL_BALANCE"] = "100000"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the live trader class
from qsci_live_trader import QSCILiveTrader
import qsci_live_trader # Import module to patch config
from qsci_backtester_v3 import VectorizedTechnicalAnalysis

# === PATCH CONFIGURATION FOR OPTIMIZED RETURNS ===
logger.info("⚡ Optimizing Strategy Parameters for Highest Returns...")
if hasattr(qsci_live_trader, 'ENTRY_CRITERIA'):
    qsci_live_trader.ENTRY_CRITERIA['min_qsci_signal'] = 0.12 # Optimized for multi-TF
    qsci_live_trader.ENTRY_CRITERIA['min_adx'] = 18           # Filter chop
    logger.info(f"✅ Patched ENTRY_CRITERIA: {qsci_live_trader.ENTRY_CRITERIA}")

class MockMongoDB:
    is_connected = False
    def save_state(self, key, value): return True
    def get_state(self, key): return None
    def close(self): pass
    def save_trade(self, trade): pass
    def update_trade(self, tid, tdict): pass
    def save_ohlcv(self, data, timeframe="1h"): pass

class MockTelegram:
    def send_message(self, *args, **kwargs): pass
    def send_trade_opened(self, *args, **kwargs): pass
    def send_trade_closed(self, *args, **kwargs): pass
    def send_startup_message(self, *args, **kwargs): pass
    def send_daily_summary(self, *args, **kwargs): pass
    def send_error_alert(self, *args, **kwargs): pass

class QSCIBacktestSimulator(QSCILiveTrader):
    """
    Wrapper to backtest the QSCILiveTrader logic on historical data
    """
    def __init__(self):
        super().__init__()

        # Replace components with Mocks
        self.mongodb = MockMongoDB()
        self.telegram = MockTelegram()

        self.history = {}
        self.simulation_times = []
        self.current_simulation_time = None

        # Ensure we have weights
        if not hasattr(self, 'multi_tf_weights') or not self.multi_tf_weights:
            from config import QSCI_CONFIG
            self.multi_tf_weights = QSCI_CONFIG.get('timeframe_weights', {})
            logger.info("Loaded weights from config manually")

    def preload_data(self, months=12):
        """Load historical data from CSVs"""
        logger.info("Loading historical data for simulation...")

        from config import TIMEFRAMES

        for tf in TIMEFRAMES:
            df = self.data_manager.load_local_csv("BTCUSDT", tf)
            if not df.empty:
                df = df.sort_values('Open Time').reset_index(drop=True)
                self.history[tf] = df
                logger.info(f"Loaded {tf}: {len(df)} candles")

        if '1h' in self.history:
            df_1h = self.history['1h']
            if df_1h.empty:
                logger.error("1h data empty!")
                sys.exit(1)

            end_date = df_1h['Open Time'].max()
            start_date = end_date - timedelta(days=30*months)

            mask = df_1h['Open Time'] >= start_date
            self.simulation_times = df_1h.loc[mask, 'Open Time'].values

            if len(self.simulation_times) == 0:
                logger.error("No data in range!")
                sys.exit(1)

            logger.info(f"Simulation Range: {start_date} to {end_date} ({len(self.simulation_times)} steps)")
        else:
            logger.error("1h data missing!")
            sys.exit(1)

    def _load_multi_timeframe_data(self) -> Dict[str, pd.DataFrame]:
        """Override: Return sliced historical data up to current_simulation_time"""
        sliced_data = {}

        for tf, df in self.history.items():
            # timestamps must be sorted.
            # searchsorted: index-1 is candle starts <= current_time
            times = df['Open Time'].values
            idx = times.searchsorted(self.current_simulation_time, side='right') - 1

            if idx >= 0:
                # IMPORTANT: Use 100 rows lookback to pass 'len(df) < 50' check in _check_entry_signal
                start_slice = max(0, idx - 100)
                sliced_data[tf] = df.iloc[start_slice : idx+1]

        return sliced_data

    def precalculate_indicators(self):
        """Pre-calculate indicators for speed"""
        logger.info("Pre-calculating indicators (this may take a moment)...")
        for tf, df in self.history.items():
            try:
                df = VectorizedTechnicalAnalysis.calculate_all_indicators_vectorized(df)
                df = VectorizedTechnicalAnalysis.calculate_signals_vectorized(df)
                self.history[tf] = df
                logger.info(f"Indicators calculated for {tf} ({len(df)} rows)")
            except Exception as e:
                logger.error(f"Error calculating indicators for {tf}: {e}")

    def run_simulation(self):
        """Run the backtest loop"""
        logger.info("=" * 60)
        logger.info("STARTING SIMULATION OF LIVE TRADER LOGIC")
        logger.info(f"Param: min_qsci={qsci_live_trader.ENTRY_CRITERIA['min_qsci_signal']}")
        logger.info("=" * 60)

        start_time = time.time()

        total_steps = len(self.simulation_times)

        for i, current_ts in enumerate(self.simulation_times):
            self.current_simulation_time = current_ts

            if i % 100 == 0:
                elapsed = time.time() - start_time
                rate = (i+1) / elapsed if elapsed > 0 else 0
                sys.stdout.write(f"\rProgress: {i}/{total_steps} ({i/total_steps*100:.1f}%) | Bal: ${self.account_balance:,.0f} | Rate: {rate:.0f} steps/s")
                sys.stdout.flush()

            dataframes = self._load_multi_timeframe_data()

            primary_df = dataframes.get("1h")
            if primary_df is None or primary_df.empty:
                continue

            current_price = primary_df.iloc[-1]['Close']

            # 1. Update existing positions
            self._update_positions(current_price, primary_df)

            # 2. Blend Signals
            blended_qsci = self._blend_multi_timeframe_signal(dataframes)

            # 3. Check Entry
            signal = self._check_entry_signal_multitf(primary_df, blended_qsci)

            if signal:
                signal['timestamp'] = pd.to_datetime(current_ts)
                self._execute_trade(signal)

        elapsed = time.time() - start_time
        print(f"\n\nSimulation Complete in {elapsed:.1f}s")
        print("=" * 60)
        print(f"Final Balance: ${self.account_balance:,.2f}")
        print(f"Profit: ${self.account_balance - self.initial_balance:,.2f}")
        total_ret = ((self.account_balance - self.initial_balance)/self.initial_balance)*100
        print(f"Total Return: {total_ret:+.2f}%")
        print(f"Total Trades: {len(self.trades_log)}")

        wins = len([t for t in self.trades_log if t.get('pnl_after_fees', 0) > 0])
        total = len(self.trades_log)
        win_rate = (wins/total*100) if total > 0 else 0
        print(f"Win Rate: {win_rate:.1f}%")
        print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--months":
        m = int(sys.argv[2])
    else:
        m = 12

    try:
        sim = QSCIBacktestSimulator()
        sim.preload_data(months=m)
        sim.precalculate_indicators()
        sim.run_simulation()
    except KeyboardInterrupt:
        print("\nSimulation stopped by user")
