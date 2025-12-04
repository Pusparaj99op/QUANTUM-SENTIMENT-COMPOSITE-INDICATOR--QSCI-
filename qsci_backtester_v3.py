"""
QSCI BTC Options Backtester v3.0
Advanced Backtesting Engine with:
- Transaction Costs (Binance Fees + Slippage)
- Auto-Rolling Positions Before Expiration
- Max Drawdown Tracking
- Vectorized Calculations for Speed
- Monte Carlo Simulation for Robustness Testing

File: qsci_backtester_v3.py
Run: python3 qsci_backtester_v3.py
"""

import os
import sys
import pandas as pd
import numpy as np
np.seterr(divide='ignore', invalid='ignore')
import talib as ta
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional
import json
from pathlib import Path
import glob
import re
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

# NLP Sentiment Analysis
try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    HAS_VADER = True
except ImportError:
    HAS_VADER = False

try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
except ImportError:
    print("ERROR: python-binance not installed. Run: pip install python-binance")
    sys.exit(1)

try:
    from config import *
except ImportError:
    print("ERROR: config.py not found")
    sys.exit(1)

# ============================================================================
# BINANCE FEE STRUCTURE (Regular User)
# ============================================================================

@dataclass
class BinanceFees:
    """Binance fee structure for regular users"""
    # Spot Trading Fees (Maker/Taker)
    spot_maker_fee: float = 0.001  # 0.1%
    spot_taker_fee: float = 0.001  # 0.1%

    # Futures Trading Fees (Maker/Taker)
    futures_maker_fee: float = 0.0002  # 0.02%
    futures_taker_fee: float = 0.0004  # 0.04%

    # Options Trading Fees
    options_trading_fee: float = 0.0003  # 0.03%
    options_exercise_fee: float = 0.0002  # 0.02%

    # Slippage (market impact)
    base_slippage: float = 0.001  # 0.1% base
    volatility_slippage_mult: float = 0.5  # Additional slippage based on volatility

    # Funding Rate (for perpetuals, applied every 8 hours)
    avg_funding_rate: float = 0.0001  # 0.01% average

    def calculate_total_cost(self, trade_value: float, is_maker: bool = False,
                            volatility: float = 0.02, trade_type: str = 'options') -> float:
        """Calculate total transaction cost for a trade"""

        if trade_type == 'options':
            base_fee = self.options_trading_fee
        elif trade_type == 'futures':
            base_fee = self.futures_maker_fee if is_maker else self.futures_taker_fee
        else:
            base_fee = self.spot_maker_fee if is_maker else self.spot_taker_fee

        # Dynamic slippage based on volatility
        slippage = self.base_slippage + (volatility * self.volatility_slippage_mult)

        # Total cost percentage
        total_cost_pct = base_fee + slippage

        return trade_value * total_cost_pct

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    log_file = LOG_CONFIG.get('log_file', 'qsci_backtest_v3.log')

    logging.basicConfig(
        level=getattr(logging, LOG_CONFIG.get('log_level', 'INFO')),
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================================================
# DATA MANAGEMENT
# ============================================================================

class BinanceDataManager:
    """Handle Binance data with local CSV support"""

    def __init__(self, use_testnet=True):
        self.use_testnet = use_testnet
        self.local_data_dir = Path(__file__).parent / 'BTC_DATA'
        self.client = None

        if use_testnet:
            api_key = BINANCE_TESTNET_API_KEY
            api_secret = BINANCE_TESTNET_API_SECRET
        else:
            api_key = BINANCE_MAINNET_API_KEY
            api_secret = BINANCE_MAINNET_API_SECRET

        try:
            self.client = Client(api_key, api_secret)
            if use_testnet:
                self.client.API_URL = 'https://testnet.binance.vision/api'
            logger.info(f"✓ Connected to Binance {'Testnet' if use_testnet else 'Mainnet'}")
        except Exception as e:
            logger.warning(f"Could not connect to Binance API: {e}")

    def load_local_csv(self, symbol: str, interval: str) -> pd.DataFrame:
        """Load from local CSV files"""
        pattern = f"{symbol}_{interval}_*.csv"
        csv_files = list(self.local_data_dir.glob(pattern))

        if not csv_files:
            return pd.DataFrame()

        csv_file = sorted(csv_files)[-1]
        logger.info(f"Loading from: {csv_file.name}")

        try:
            df = pd.read_csv(csv_file, low_memory=False)

            column_mapping = {
                'timestamp': 'Open Time', 'open': 'Open', 'high': 'High',
                'low': 'Low', 'close': 'Close', 'volume': 'Volume'
            }

            for old, new in column_mapping.items():
                if old in df.columns:
                    df = df.rename(columns={old: new})

            if 'Open Time' in df.columns:
                df['Open Time'] = pd.to_datetime(df['Open Time'])

            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            logger.info(f"✓ Loaded {len(df)} candles")
            return df

        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            return pd.DataFrame()

    def fetch_klines(self, symbol: str, interval: str, start_date: str, end_date: str):
        """Fetch OHLCV data"""
        df = self.load_local_csv(symbol, interval)

        if len(df) > 0:
            if 'Open Time' in df.columns:
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                df = df[(df['Open Time'] >= start_dt) & (df['Open Time'] <= end_dt)]
            return df

        if self.client is None:
            return pd.DataFrame()

        try:
            klines = self.client.get_historical_klines(symbol, interval, start_date, end_date)

            df = pd.DataFrame(klines, columns=[
                'Open Time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close Time', 'Quote Asset Volume', 'Number of Trades',
                'Taker Buy Base', 'Taker Buy Quote', 'Ignore'
            ])

            df['Open Time'] = pd.to_datetime(df['Open Time'], unit='ms')
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            return pd.DataFrame()

# ============================================================================
# VECTORIZED TECHNICAL INDICATORS
# ============================================================================

class VectorizedTechnicalAnalysis:
    """Vectorized technical indicators for maximum speed"""

    @staticmethod
    def calculate_all_indicators_vectorized(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators at once using vectorization"""

        close = df['Close'].values.astype(np.float64)
        high = df['High'].values.astype(np.float64)
        low = df['Low'].values.astype(np.float64)
        volume = df['Volume'].values.astype(np.float64) if 'Volume' in df else np.ones_like(close)

        # Pre-allocate result dataframe
        result = df.copy()

        # === MOMENTUM INDICATORS (Vectorized) ===
        result['RSI'] = ta.RSI(close, timeperiod=14)
        result['StochRSI_K'], result['StochRSI_D'] = ta.STOCHRSI(close, timeperiod=14)
        result['Williams_R'] = ta.WILLR(high, low, close, timeperiod=14)
        result['MFI'] = ta.MFI(high, low, close, volume, timeperiod=14)
        result['CCI'] = ta.CCI(high, low, close, timeperiod=20)
        result['ROC'] = ta.ROC(close, timeperiod=10)
        result['Momentum'] = ta.MOM(close, timeperiod=10)
        result['UltOsc'] = ta.ULTOSC(high, low, close)

        # === TREND INDICATORS (Vectorized) ===
        result['MACD'], result['MACD_Signal'], result['MACD_Hist'] = ta.MACD(close)
        result['ADX'] = ta.ADX(high, low, close, timeperiod=14)
        result['Plus_DI'] = ta.PLUS_DI(high, low, close, timeperiod=14)
        result['Minus_DI'] = ta.MINUS_DI(high, low, close, timeperiod=14)
        result['EMA_20'] = ta.EMA(close, timeperiod=20)
        result['EMA_50'] = ta.EMA(close, timeperiod=50)
        result['SMA_20'] = ta.SMA(close, timeperiod=20)
        result['Aroon_Up'], result['Aroon_Down'] = ta.AROON(high, low, timeperiod=25)
        result['PSAR'] = ta.SAR(high, low)

        # === VOLATILITY INDICATORS (Vectorized) ===
        result['ATR'] = ta.ATR(high, low, close, timeperiod=14)
        result['NATR'] = ta.NATR(high, low, close, timeperiod=14)
        result['BB_Upper'], result['BB_Middle'], result['BB_Lower'] = ta.BBANDS(close, timeperiod=20)
        result['StdDev'] = ta.STDDEV(close, timeperiod=20)

        # === VOLUME INDICATORS (Vectorized) ===
        result['OBV'] = ta.OBV(close, volume)
        result['AD'] = ta.AD(high, low, close, volume)
        result['ADOSC'] = ta.ADOSC(high, low, close, volume)

        # === VWAP (Vectorized) ===
        typical_price = (high + low + close) / 3
        cumulative_tp_vol = np.cumsum(typical_price * volume)
        cumulative_vol = np.cumsum(volume)
        result['VWAP'] = np.where(cumulative_vol != 0, cumulative_tp_vol / cumulative_vol, 0)

        # === CMF (Vectorized) ===
        hl_diff = high - low
        mfm = np.where(hl_diff != 0, ((close - low) - (high - close)) / hl_diff, 0)
        mfv = mfm * volume

        # Rolling sum for CMF
        period = 20
        mfv_sum = pd.Series(mfv).rolling(window=period).sum()
        vol_sum = pd.Series(volume).rolling(window=period).sum()
        result['CMF'] = np.where(vol_sum != 0, mfv_sum / vol_sum, 0)

        # === Keltner Channels (Vectorized) ===
        kc_middle = result['EMA_20'].values
        kc_atr = result['ATR'].values * 2.0
        result['KC_Upper'] = kc_middle + kc_atr
        result['KC_Lower'] = kc_middle - kc_atr

        return result

    @staticmethod
    def calculate_signals_vectorized(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate trading signals using vectorized operations"""

        result = df.copy()

        # === MOMENTUM SIGNAL (Vectorized) ===
        rsi_signal = (df['RSI'] - 50) / 50
        stoch_signal = (df['StochRSI_K'] - 50) / 50
        willr_signal = (df['Williams_R'] + 50) / 50
        mfi_signal = (df['MFI'] - 50) / 50
        cci_signal = np.tanh(df['CCI'] / 100)
        uo_signal = (df['UltOsc'] - 50) / 50

        result['Momentum_Signal'] = (
            0.25 * rsi_signal +
            0.20 * stoch_signal +
            0.15 * willr_signal +
            0.15 * mfi_signal +
            0.15 * cci_signal +
            0.10 * uo_signal
        )

        # === TREND SIGNAL (Vectorized) ===
        atr = df['ATR'].values
        safe_atr = np.where(atr > 0, atr, 1)

        macd_norm = np.tanh((df['MACD'] - df['MACD_Signal']) / safe_atr * 2)

        trend_strength = np.minimum(df['ADX'] / 50, 1.0)
        trend_direction = np.tanh((df['Plus_DI'] - df['Minus_DI']) / 20)
        adx_signal = trend_strength * trend_direction

        ema_trend = np.where(df['EMA_20'] > df['EMA_50'], 1.0, -1.0)
        price_trend = np.tanh((df['Close'] - df['EMA_20']) / safe_atr)
        ema_signal = 0.6 * ema_trend + 0.4 * price_trend

        aroon_signal = (df['Aroon_Up'] - df['Aroon_Down']) / 100

        result['Trend_Signal'] = (
            0.30 * macd_norm +
            0.25 * adx_signal +
            0.25 * ema_signal +
            0.20 * aroon_signal
        )

        # === VOLUME SIGNAL (Vectorized) ===
        obv_ema = ta.EMA(df['OBV'].values, timeperiod=20)
        safe_obv_ema = np.where(obv_ema != 0, obv_ema, 1)
        obv_signal = np.tanh((df['OBV'].values - obv_ema) / np.abs(safe_obv_ema) * 10)

        cmf_signal = np.clip(df['CMF'].values * 5, -1, 1)

        vwap_signal = np.tanh((df['Close'].values - df['VWAP'].values) / safe_atr)

        result['Volume_Signal'] = (
            0.35 * obv_signal +
            0.35 * cmf_signal +
            0.30 * vwap_signal
        )

        # === VOLATILITY SIGNAL (Vectorized - Mean Reversion) ===
        bb_range = df['BB_Upper'] - df['BB_Lower']
        safe_bb_range = np.where(bb_range > 0, bb_range, 1)
        bb_position = 2 * (df['Close'] - df['BB_Lower']) / safe_bb_range - 1
        bb_signal = -np.tanh(bb_position * 1.5)

        kc_range = df['KC_Upper'] - df['KC_Lower']
        safe_kc_range = np.where(kc_range > 0, kc_range, 1)
        kc_position = 2 * (df['Close'] - df['KC_Lower']) / safe_kc_range - 1
        kc_signal = -np.tanh(kc_position * 1.5)

        result['Volatility_Signal'] = 0.5 * bb_signal + 0.5 * kc_signal

        # === PATTERN SIGNAL (Vectorized) ===
        lookback = 10

        recent_high_mean = df['High'].rolling(window=lookback).mean()
        prior_high_mean = df['High'].shift(lookback).rolling(window=lookback).mean()
        recent_low_mean = df['Low'].rolling(window=lookback).mean()
        prior_low_mean = df['Low'].shift(lookback).rolling(window=lookback).mean()

        hh_score = np.where(recent_high_mean > prior_high_mean, 1, 0)
        hl_score = np.where(recent_low_mean > prior_low_mean, 1, 0)
        lh_score = np.where(recent_high_mean < prior_high_mean, 1, 0)
        ll_score = np.where(recent_low_mean < prior_low_mean, 1, 0)

        uptrend = (hh_score + hl_score) / 2
        downtrend = (lh_score + ll_score) / 2

        result['Pattern_Signal'] = np.clip(uptrend - downtrend, -1, 1)

        # === COMBINED QSCI SIGNAL (Vectorized) ===
        result['MTC'] = (
            0.35 * result['Momentum_Signal'] +
            0.30 * result['Trend_Signal'] +
            0.15 * result['Volume_Signal'] +
            0.10 * result['Volatility_Signal'] +
            0.10 * result['Pattern_Signal']
        )

        result['QSCI'] = np.clip(result['MTC'], -1, 1)

        return result

# ============================================================================
# POSITION MANAGEMENT WITH ROLLING
# ============================================================================

@dataclass
class Position:
    """Position with rolling capability"""
    id: int
    entry_price: float
    quantity: int
    dte: float
    strike: float
    delta: float
    qsci: float
    entry_time: datetime = field(default_factory=datetime.now)
    current_price: float = 0.0
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_after_fees: float = 0.0
    status: str = "OPEN"
    tp1_triggered: bool = False
    tp2_triggered: bool = False
    tp3_triggered: bool = False
    rolled_count: int = 0
    total_fees_paid: float = 0.0

    def __post_init__(self):
        self.current_price = self.entry_price

    def update_price(self, new_price: float):
        self.current_price = new_price
        self.pnl = (self.current_price - self.entry_price) * self.quantity

    def close(self, exit_price: float, fees: float = 0.0):
        self.exit_price = exit_price
        self.exit_time = datetime.now()
        self.status = "CLOSED"
        self.pnl = (exit_price - self.entry_price) * self.quantity
        self.total_fees_paid += fees
        self.pnl_after_fees = self.pnl - self.total_fees_paid

    def roll(self, new_strike: float, new_dte: int, new_entry_price: float, roll_fee: float = 0.0):
        """Roll position to new strike/expiration"""
        self.rolled_count += 1
        self.strike = new_strike
        self.dte = new_dte
        self.entry_price = new_entry_price
        self.current_price = new_entry_price
        self.total_fees_paid += roll_fee
        self.status = "ROLLED"
        logger.info(f"🔄 Position #{self.id} ROLLED: New Strike=${new_strike:.0f}, "
                   f"DTE={new_dte}, Roll #{self.rolled_count}")

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'quantity': self.quantity,
            'dte': self.dte,
            'strike': self.strike,
            'delta': self.delta,
            'qsci': self.qsci,
            'pnl': self.pnl,
            'pnl_after_fees': self.pnl_after_fees,
            'total_fees_paid': self.total_fees_paid,
            'rolled_count': self.rolled_count,
            'status': self.status
        }

# ============================================================================
# DRAWDOWN TRACKER
# ============================================================================

@dataclass
class DrawdownTracker:
    """Track maximum drawdown and equity curve"""
    peak_equity: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration: int = 0
    current_drawdown_start: Optional[int] = None
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)

    def update(self, current_equity: float, timestamp: datetime = None):
        """Update drawdown metrics"""
        self.equity_curve.append(current_equity)
        self.timestamps.append(timestamp or datetime.now())

        # Update peak
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            if self.current_drawdown_start is not None:
                duration = len(self.equity_curve) - self.current_drawdown_start
                self.max_drawdown_duration = max(self.max_drawdown_duration, duration)
            self.current_drawdown_start = None

        # Calculate current drawdown
        if self.peak_equity > 0:
            current_dd = self.peak_equity - current_equity
            current_dd_pct = current_dd / self.peak_equity

            self.drawdown_curve.append(current_dd_pct)

            # Update max drawdown
            if current_dd > self.max_drawdown:
                self.max_drawdown = current_dd
                self.max_drawdown_pct = current_dd_pct
                if self.current_drawdown_start is None:
                    self.current_drawdown_start = len(self.equity_curve) - 1
        else:
            self.drawdown_curve.append(0.0)

    def get_stats(self) -> Dict:
        return {
            'peak_equity': self.peak_equity,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct * 100,
            'max_drawdown_duration': self.max_drawdown_duration,
            'current_equity': self.equity_curve[-1] if self.equity_curve else 0,
            'current_drawdown_pct': self.drawdown_curve[-1] * 100 if self.drawdown_curve else 0
        }

# ============================================================================
# MONTE CARLO SIMULATOR
# ============================================================================

class MonteCarloSimulator:
    """Monte Carlo simulation for strategy robustness testing"""

    def __init__(self, n_simulations: int = 1000, confidence_level: float = 0.95):
        self.n_simulations = n_simulations
        self.confidence_level = confidence_level

    def simulate_returns(self, trade_returns: List[float], n_trades: int = None) -> Dict:
        """
        Run Monte Carlo simulation on trade returns

        Args:
            trade_returns: List of percentage returns from each trade
            n_trades: Number of trades to simulate (default: same as input)

        Returns:
            Dict with simulation results
        """
        if not trade_returns or len(trade_returns) < 5:
            return {'error': 'Insufficient trade data for simulation'}

        trade_returns = np.array(trade_returns)
        n_trades = n_trades or len(trade_returns)

        # Store simulation results
        final_returns = []
        max_drawdowns = []
        sharpe_ratios = []
        win_rates = []

        for _ in range(self.n_simulations):
            # Bootstrap sampling with replacement
            simulated_trades = np.random.choice(trade_returns, size=n_trades, replace=True)

            # Calculate cumulative returns
            cumulative = np.cumprod(1 + simulated_trades)
            final_returns.append(cumulative[-1] - 1)

            # Calculate max drawdown
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = (running_max - cumulative) / running_max
            max_drawdowns.append(np.max(drawdowns))

            # Calculate Sharpe ratio (assuming daily returns)
            if np.std(simulated_trades) > 0:
                sharpe = np.mean(simulated_trades) / np.std(simulated_trades) * np.sqrt(252)
            else:
                sharpe = 0
            sharpe_ratios.append(sharpe)

            # Win rate
            win_rates.append(np.mean(simulated_trades > 0))

        # Calculate percentiles
        confidence_low = (1 - self.confidence_level) / 2
        confidence_high = 1 - confidence_low

        return {
            'n_simulations': self.n_simulations,
            'n_trades': n_trades,
            # Return statistics
            'return_mean': np.mean(final_returns) * 100,
            'return_median': np.median(final_returns) * 100,
            'return_std': np.std(final_returns) * 100,
            'return_5th_pct': np.percentile(final_returns, 5) * 100,
            'return_95th_pct': np.percentile(final_returns, 95) * 100,
            'return_worst': np.min(final_returns) * 100,
            'return_best': np.max(final_returns) * 100,
            # Drawdown statistics
            'max_dd_mean': np.mean(max_drawdowns) * 100,
            'max_dd_median': np.median(max_drawdowns) * 100,
            'max_dd_95th_pct': np.percentile(max_drawdowns, 95) * 100,
            'max_dd_worst': np.max(max_drawdowns) * 100,
            # Sharpe statistics
            'sharpe_mean': np.mean(sharpe_ratios),
            'sharpe_median': np.median(sharpe_ratios),
            'sharpe_5th_pct': np.percentile(sharpe_ratios, 5),
            # Win rate statistics
            'win_rate_mean': np.mean(win_rates) * 100,
            'win_rate_5th_pct': np.percentile(win_rates, 5) * 100,
            # Probability of profit
            'prob_profit': np.mean(np.array(final_returns) > 0) * 100,
            'prob_beat_market': np.mean(np.array(final_returns) > 0.10) * 100,  # Beat 10%
        }

    def scenario_analysis(self, trade_returns: List[float], scenarios: Dict[str, Dict]) -> Dict:
        """
        Run scenario analysis with different market conditions

        Args:
            trade_returns: Historical trade returns
            scenarios: Dict of scenario names to adjustment parameters
                Example: {'Bull': {'mean_adj': 0.02}, 'Bear': {'mean_adj': -0.03}}
        """
        results = {}

        for scenario_name, params in scenarios.items():
            adjusted_returns = np.array(trade_returns) + params.get('mean_adj', 0)
            adjusted_returns *= params.get('vol_mult', 1.0)

            results[scenario_name] = self.simulate_returns(
                adjusted_returns.tolist(),
                n_trades=params.get('n_trades', len(trade_returns))
            )

        return results

# ============================================================================
# ENHANCED QSCI BACKTESTER v3.0
# ============================================================================

class QSCIBacktesterV3:
    """Enhanced backtester with fees, rolling, drawdown tracking, and Monte Carlo"""

    def __init__(self):
        self.dm = BinanceDataManager(use_testnet=USE_TESTNET)
        self.fees = BinanceFees()
        self.positions: List[Position] = []
        self.account_balance = POSITION_CONFIG['account_balance']
        self.initial_balance = self.account_balance
        self.trades_log: List[Dict] = []
        self.position_counter = 0
        self.drawdown_tracker = DrawdownTracker()
        self.monte_carlo = MonteCarloSimulator(n_simulations=1000)

        # Performance tracking
        self.total_fees_paid = 0.0
        self.total_slippage = 0.0
        self.rolls_executed = 0

        # NLP for sentiment
        self.vader_analyzer = None
        if HAS_VADER:
            self.vader_analyzer = SentimentIntensityAnalyzer()

    def load_historical_data(self) -> Dict[str, pd.DataFrame]:
        """Load and precompute all indicators"""
        logger.info("Loading historical data and computing indicators...")

        dataframes = {}

        for tf in TIMEFRAMES:
            df = self.dm.fetch_klines(SYMBOL, tf, BACKTEST_START_DATE, BACKTEST_END_DATE)

            if len(df) > 0:
                # Vectorized indicator calculation
                df = VectorizedTechnicalAnalysis.calculate_all_indicators_vectorized(df)
                df = VectorizedTechnicalAnalysis.calculate_signals_vectorized(df)
                dataframes[tf] = df
                logger.info(f"✓ {tf}: {len(df)} candles with indicators")

        return dataframes

    def calculate_transaction_cost(self, trade_value: float, spot_price: float,
                                   volatility: float = None) -> Tuple[float, float]:
        """Calculate fees and slippage for a trade"""

        if volatility is None:
            volatility = 0.02  # Default 2% volatility

        # Fee calculation
        fee = trade_value * self.fees.options_trading_fee

        # Slippage calculation (increases with volatility and trade size)
        base_slippage = trade_value * self.fees.base_slippage
        vol_slippage = trade_value * volatility * self.fees.volatility_slippage_mult
        slippage = base_slippage + vol_slippage

        return fee, slippage

    def check_rolling_needed(self, position: Position, current_dte: float) -> bool:
        """Check if position needs to be rolled"""
        roll_threshold = EXIT_RULES.get('roll_dte_threshold', 7)
        return current_dte <= roll_threshold and position.status == "OPEN"

    def execute_roll(self, position: Position, spot_price: float, current_time: datetime,
                    volatility: float) -> bool:
        """Execute position roll to new expiration"""

        # Calculate roll cost (exit old + enter new)
        exit_value = position.current_price * position.quantity
        exit_fee, exit_slippage = self.calculate_transaction_cost(exit_value, spot_price, volatility)

        # New position parameters
        new_dte = 14  # Roll to 2 weeks out
        new_strike = round(spot_price / 100) * 100  # ATM strike

        # New entry price (ATM option ~3% of spot)
        new_entry_price = spot_price * (0.02 + 0.01 * np.sqrt(new_dte / 30))
        new_entry_value = new_entry_price * position.quantity

        entry_fee, entry_slippage = self.calculate_transaction_cost(new_entry_value, spot_price, volatility)

        total_roll_cost = exit_fee + exit_slippage + entry_fee + entry_slippage

        # Execute roll
        position.roll(new_strike, new_dte, new_entry_price, total_roll_cost)

        self.total_fees_paid += exit_fee + entry_fee
        self.total_slippage += exit_slippage + entry_slippage
        self.rolls_executed += 1

        logger.info(f"🔄 Roll executed: Total cost ${total_roll_cost:.2f}")
        return True

    def calculate_position_size(self, qsci: float, delta: float, spot_price: float) -> int:
        """Calculate position size with Kelly-inspired sizing"""
        risk_pct = POSITION_CONFIG['risk_per_trade']
        risk_amount = self.account_balance * risk_pct

        # Signal-based multiplier (stronger signal = larger position)
        signal_mult = 0.5 + abs(qsci)  # 0.5x to 1.5x

        # Delta adjustment (ATM = full size)
        delta_mult = 1 - abs(0.5 - delta)

        # Option price estimate
        option_price = spot_price * (0.02 + 0.01 * delta)

        # Position size
        raw_size = (risk_amount * signal_mult * delta_mult) / option_price

        # Apply limits
        max_size = self.account_balance * POSITION_CONFIG['max_position_size_pct'] / option_price

        return max(1, min(int(raw_size), int(max_size)))

    def simulate_trade(self, qsci: float, spot_price: float, volatility: float,
                      current_time: datetime, dte: int = 14) -> bool:
        """Simulate trade entry with transaction costs"""

        # Check concurrent positions
        open_positions = [p for p in self.positions if p.status == "OPEN"]
        if len(open_positions) >= POSITION_CONFIG['max_concurrent_positions']:
            return False

        # Entry criteria
        if qsci < ENTRY_CRITERIA['min_qsci_signal']:
            return False

        delta = 0.5  # ATM
        strike = round(spot_price / 100) * 100

        # Calculate position size
        quantity = self.calculate_position_size(qsci, delta, spot_price)

        # Option pricing
        time_value = spot_price * 0.02 * np.sqrt(dte / 30)
        delta_premium = spot_price * (0.01 + 0.02 * delta)
        entry_price = time_value + delta_premium

        # Calculate transaction costs
        trade_value = entry_price * quantity
        fee, slippage = self.calculate_transaction_cost(trade_value, spot_price, volatility)

        # Adjust entry price for slippage (pay more)
        adjusted_entry = entry_price * (1 + self.fees.base_slippage)

        # Create position
        self.position_counter += 1
        position = Position(
            id=self.position_counter,
            entry_price=adjusted_entry,
            quantity=quantity,
            dte=dte,
            strike=strike,
            delta=delta,
            qsci=qsci,
            entry_time=current_time
        )
        position.total_fees_paid = fee + slippage

        self.positions.append(position)
        self.total_fees_paid += fee
        self.total_slippage += slippage

        logger.info(f"✓ Position #{self.position_counter}: QSCI={qsci:.3f}, "
                   f"Price=${adjusted_entry:.2f}, Qty={quantity}, "
                   f"Fees=${fee + slippage:.2f}")

        return True

    def run_backtest(self):
        """Execute full backtest with all enhancements"""
        logger.info("="*80)
        logger.info("QSCI BTC OPTIONS BACKTESTER v3.0")
        logger.info("Features: Transaction Costs | Rolling | Drawdown | Monte Carlo")
        logger.info("="*80)

        # Load data
        dataframes = self.load_historical_data()

        if not dataframes:
            logger.error("No data loaded")
            return

        primary_df = dataframes.get('4h', pd.DataFrame())
        if len(primary_df) == 0:
            logger.error("No primary timeframe data")
            return

        logger.info(f"Starting backtest with {len(primary_df)} candles...")

        # Initialize drawdown tracker
        self.drawdown_tracker = DrawdownTracker()
        self.drawdown_tracker.peak_equity = self.account_balance

        qsci_values = []
        trade_returns = []

        # Simulation loop
        for idx in range(60, len(primary_df)):
            spot_price = primary_df.iloc[idx]['Close']
            current_time = primary_df.iloc[idx]['Open Time']

            # Get volatility (NATR)
            volatility = primary_df.iloc[idx]['NATR'] / 100 if 'NATR' in primary_df else 0.02

            # Get QSCI from precomputed signals
            qsci = primary_df.iloc[idx]['QSCI'] if 'QSCI' in primary_df else 0.0
            qsci_values.append(qsci)

            # ================== POSITION MANAGEMENT ==================
            for pos in self.positions:
                if pos.status == "OPEN":
                    # Update DTE
                    pos.dte = max(0, pos.dte - (1/6))

                    # Check if rolling needed
                    if self.check_rolling_needed(pos, pos.dte):
                        if pos.dte <= EXIT_RULES.get('mandatory_close_dte', 3):
                            # Too late to roll, close position
                            fee, slippage = self.calculate_transaction_cost(
                                pos.current_price * pos.quantity, spot_price, volatility
                            )
                            pos.close(pos.current_price, fee + slippage)
                            self.trades_log.append(pos.to_dict())
                            self.account_balance += pos.pnl_after_fees

                            if pos.pnl > 0:
                                trade_returns.append(pos.pnl_after_fees / (pos.entry_price * pos.quantity))
                            else:
                                trade_returns.append(pos.pnl_after_fees / (pos.entry_price * pos.quantity))

                            logger.info(f"⏰ Position #{pos.id} EXPIRED: "
                                       f"P&L=${pos.pnl_after_fees:.2f}")
                            continue
                        else:
                            # Execute roll
                            self.execute_roll(pos, spot_price, current_time, volatility)
                            pos.status = "OPEN"  # Reset status after roll

                    # Update position price (Greeks-based)
                    spot_change = spot_price - pos.strike
                    delta_pnl = pos.delta * spot_change
                    theta_decay = pos.entry_price * 0.02 * (1/6) / np.sqrt(max(pos.dte, 1))
                    gamma_effect = 0.01 * (spot_change / max(pos.strike, 1)) ** 2 * pos.entry_price

                    new_price = pos.entry_price + delta_pnl - theta_decay + gamma_effect
                    new_price = max(0.001, new_price)
                    pos.update_price(new_price)

                    # Check exit conditions
                    profit_pct = pos.pnl / (pos.entry_price * pos.quantity)
                    atr = primary_df.iloc[idx]['ATR'] if 'ATR' in primary_df else spot_price * 0.02

                    tp_threshold = 0.30 + (atr / spot_price)
                    sl_threshold = -0.20 - (atr / spot_price) / 2

                    # Take Profit
                    if profit_pct > tp_threshold:
                        fee, slippage = self.calculate_transaction_cost(
                            new_price * pos.quantity, spot_price, volatility
                        )
                        pos.close(new_price, fee + slippage)
                        self.trades_log.append(pos.to_dict())
                        self.account_balance += pos.pnl_after_fees
                        trade_returns.append(profit_pct)

                        self.total_fees_paid += fee
                        self.total_slippage += slippage

                        logger.info(f"✓ Position #{pos.id} TP: ${pos.pnl_after_fees:.2f} "
                                   f"({profit_pct*100:.1f}%)")

                    # Stop Loss
                    elif profit_pct < sl_threshold:
                        fee, slippage = self.calculate_transaction_cost(
                            new_price * pos.quantity, spot_price, volatility
                        )
                        pos.close(new_price, fee + slippage)
                        self.trades_log.append(pos.to_dict())
                        self.account_balance += pos.pnl_after_fees
                        trade_returns.append(profit_pct)

                        self.total_fees_paid += fee
                        self.total_slippage += slippage

                        logger.info(f"✗ Position #{pos.id} SL: ${pos.pnl_after_fees:.2f} "
                                   f"({profit_pct*100:.1f}%)")

            # ================== NEW ENTRIES ==================
            if idx % 6 == 0:  # Check every ~day
                self.simulate_trade(qsci, spot_price, volatility, current_time)

            # ================== UPDATE DRAWDOWN ==================
            open_pnl = sum(p.pnl for p in self.positions if p.status == "OPEN")
            current_equity = self.account_balance + open_pnl
            self.drawdown_tracker.update(current_equity, current_time)

        # Close remaining positions
        final_spot = primary_df.iloc[-1]['Close']
        final_volatility = primary_df.iloc[-1]['NATR'] / 100 if 'NATR' in primary_df else 0.02

        for pos in self.positions:
            if pos.status == "OPEN":
                fee, slippage = self.calculate_transaction_cost(
                    pos.current_price * pos.quantity, final_spot, final_volatility
                )
                pos.close(pos.current_price, fee + slippage)
                self.trades_log.append(pos.to_dict())
                self.account_balance += pos.pnl_after_fees

                if pos.entry_price > 0:
                    trade_returns.append(pos.pnl_after_fees / (pos.entry_price * pos.quantity))

        # ================== MONTE CARLO SIMULATION ==================
        logger.info("\n" + "="*80)
        logger.info("RUNNING MONTE CARLO SIMULATION...")
        logger.info("="*80)

        mc_results = {}
        if trade_returns:
            mc_results = self.monte_carlo.simulate_returns(trade_returns)

            # Scenario analysis
            scenarios = {
                'Bull Market': {'mean_adj': 0.02, 'vol_mult': 0.8},
                'Bear Market': {'mean_adj': -0.03, 'vol_mult': 1.2},
                'High Volatility': {'mean_adj': 0, 'vol_mult': 1.5},
                'Low Volatility': {'mean_adj': 0, 'vol_mult': 0.6}
            }
            scenario_results = self.monte_carlo.scenario_analysis(trade_returns, scenarios)

        # Print summary
        self.print_summary(mc_results, scenario_results if trade_returns else {})

    def print_summary(self, mc_results: Dict, scenario_results: Dict):
        """Print comprehensive backtest summary"""
        logger.info("\n" + "="*80)
        logger.info("BACKTEST SUMMARY")
        logger.info("="*80)

        closed_trades = self.trades_log

        logger.info(f"\n📊 TRADE STATISTICS:")
        logger.info(f"Total Trades: {len(closed_trades)}")

        if closed_trades:
            pnl_list = [t['pnl_after_fees'] for t in closed_trades]
            wins = len([p for p in pnl_list if p > 0])
            losses = len([p for p in pnl_list if p <= 0])

            logger.info(f"Wins: {wins}, Losses: {losses}")
            logger.info(f"Win Rate: {wins/len(closed_trades)*100:.1f}%")
            logger.info(f"Total P&L (after fees): ${sum(pnl_list):.2f}")
            logger.info(f"Average P&L: ${np.mean(pnl_list):.2f}")
            logger.info(f"Max Win: ${max(pnl_list):.2f}")
            logger.info(f"Max Loss: ${min(pnl_list):.2f}")

            if np.std(pnl_list) > 0:
                sharpe = np.mean(pnl_list) / np.std(pnl_list) * np.sqrt(252)
                logger.info(f"Sharpe Ratio: {sharpe:.2f}")

        logger.info(f"\n💰 TRANSACTION COSTS:")
        logger.info(f"Total Fees Paid: ${self.total_fees_paid:.2f}")
        logger.info(f"Total Slippage: ${self.total_slippage:.2f}")
        logger.info(f"Total Transaction Costs: ${self.total_fees_paid + self.total_slippage:.2f}")

        logger.info(f"\n🔄 ROLLING STATISTICS:")
        logger.info(f"Positions Rolled: {self.rolls_executed}")

        logger.info(f"\n📉 DRAWDOWN ANALYSIS:")
        dd_stats = self.drawdown_tracker.get_stats()
        logger.info(f"Peak Equity: ${dd_stats['peak_equity']:.2f}")
        logger.info(f"Max Drawdown: ${dd_stats['max_drawdown']:.2f} ({dd_stats['max_drawdown_pct']:.1f}%)")
        logger.info(f"Max DD Duration: {dd_stats['max_drawdown_duration']} periods")
        logger.info(f"Current Drawdown: {dd_stats['current_drawdown_pct']:.1f}%")

        if mc_results and 'error' not in mc_results:
            logger.info(f"\n🎲 MONTE CARLO SIMULATION ({mc_results['n_simulations']} runs):")
            logger.info(f"Expected Return: {mc_results['return_mean']:.1f}%")
            logger.info(f"Return 5th-95th Percentile: {mc_results['return_5th_pct']:.1f}% to {mc_results['return_95th_pct']:.1f}%")
            logger.info(f"Worst Case Return: {mc_results['return_worst']:.1f}%")
            logger.info(f"Expected Max Drawdown: {mc_results['max_dd_mean']:.1f}%")
            logger.info(f"95th Percentile Max DD: {mc_results['max_dd_95th_pct']:.1f}%")
            logger.info(f"Expected Sharpe: {mc_results['sharpe_mean']:.2f}")
            logger.info(f"Probability of Profit: {mc_results['prob_profit']:.1f}%")
            logger.info(f"Probability of >10% Return: {mc_results['prob_beat_market']:.1f}%")

        if scenario_results:
            logger.info(f"\n📈 SCENARIO ANALYSIS:")
            for scenario, results in scenario_results.items():
                if 'error' not in results:
                    logger.info(f"  {scenario}:")
                    logger.info(f"    Expected Return: {results['return_mean']:.1f}%")
                    logger.info(f"    Probability of Profit: {results['prob_profit']:.1f}%")

        logger.info(f"\n💼 FINAL RESULTS:")
        logger.info(f"Initial Balance: ${self.initial_balance:,.2f}")
        logger.info(f"Final Balance: ${self.account_balance:,.2f}")
        total_return = (self.account_balance - self.initial_balance) / self.initial_balance * 100
        logger.info(f"Total Return: {total_return:.2f}%")
        logger.info("="*80)

# ============================================================================
# MAIN
# ============================================================================

def main():
    try:
        backtester = QSCIBacktesterV3()
        backtester.run_backtest()

        if backtester.trades_log:
            df_trades = pd.DataFrame(backtester.trades_log)
            df_trades.to_csv('backtest_results_v3.csv', index=False)
            logger.info("✓ Results saved to backtest_results_v3.csv")

            # Save drawdown data
            dd_df = pd.DataFrame({
                'timestamp': backtester.drawdown_tracker.timestamps,
                'equity': backtester.drawdown_tracker.equity_curve,
                'drawdown_pct': backtester.drawdown_tracker.drawdown_curve
            })
            dd_df.to_csv('drawdown_curve.csv', index=False)
            logger.info("✓ Drawdown curve saved to drawdown_curve.csv")

    except KeyboardInterrupt:
        logger.info("Backtest interrupted")
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
