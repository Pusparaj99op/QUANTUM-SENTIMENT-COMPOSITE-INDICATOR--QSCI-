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
from collections import defaultdict
from math import log, sqrt, exp, erf
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

    spot_maker_fee: float = 0.0008  # 0.08%
    spot_taker_fee: float = 0.001   # 0.10%
    futures_maker_fee: float = 0.0002
    futures_taker_fee: float = 0.0004
    options_maker_fee: float = 0.0002
    options_taker_fee: float = 0.0004
    options_exercise_fee: float = 0.0002
    base_slippage: float = 0.0003
    volatility_slippage_mult: float = 0.6
    min_slippage: float = 0.00015

    def calculate_total_cost(self, trade_value: float, spread_pct: float,
                             is_maker: bool = False, trade_type: str = 'options') -> Tuple[float, float]:
        """Return (fees, slippage) for a trade."""

        if trade_type == 'options':
            fee_rate = self.options_maker_fee if is_maker else self.options_taker_fee
        elif trade_type == 'futures':
            fee_rate = self.futures_maker_fee if is_maker else self.futures_taker_fee
        else:
            fee_rate = self.spot_maker_fee if is_maker else self.spot_taker_fee

        fee = trade_value * fee_rate

        impact_component = trade_value * max(self.min_slippage, self.base_slippage)
        spread_component = trade_value * max(spread_pct / 2, self.min_slippage)
        slippage = impact_component + spread_component

        return fee, slippage

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


@dataclass
class OptionMarketModel:
    """Simplified Binance options microstructure model"""

    risk_free_rate: float = 0.015
    min_iv: float = 0.25
    max_iv: float = 2.0
    base_spread: float = 0.001
    vol_spread_mult: float = 1.1
    liquidity_spread: float = 0.0005

    @staticmethod
    def _norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + erf(x / sqrt(2.0)))

    @staticmethod
    def _norm_pdf(x: float) -> float:
        return (1.0 / sqrt(2.0 * np.pi)) * exp(-0.5 * x * x)

    def annualize_vol(self, atr_pct: float) -> float:
        atr_pct = max(atr_pct, 0.0005)
        implied = atr_pct * sqrt(365)
        return min(max(implied, self.min_iv), self.max_iv)

    def calculate_greeks(self, spot: float, strike: float, dte: float, iv: float,
                         option_type: str = "CALL") -> Dict[str, float]:
        """Calculate Delta, Gamma, Vega, Theta"""
        strike = max(strike, 1e-6)
        spot = max(spot, 1e-6)
        time_fraction = max(dte, 0.25) / 365
        sigma = min(max(iv, self.min_iv), self.max_iv)
        vol_sqrt_t = sigma * sqrt(time_fraction)

        if vol_sqrt_t == 0:
            return {'delta': 0.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0}

        d1 = (log(spot / strike) + (self.risk_free_rate + 0.5 * sigma ** 2) * time_fraction) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t

        nd1 = self._norm_cdf(d1)
        nd2 = self._norm_cdf(d2)
        n_prime_d1 = self._norm_pdf(d1)
        discount = exp(-self.risk_free_rate * time_fraction)

        # Gamma (same for Call and Put)
        gamma = n_prime_d1 / (spot * sigma * sqrt(time_fraction))

        # Vega (same for Call and Put) - usually expressed for 1% change in vol
        vega = spot * n_prime_d1 * sqrt(time_fraction) / 100

        if option_type == "CALL":
            delta = nd1
            theta = (- (spot * n_prime_d1 * sigma) / (2 * sqrt(time_fraction))
                     - self.risk_free_rate * strike * discount * nd2) / 365
        else:  # PUT
            delta = nd1 - 1
            theta = (- (spot * n_prime_d1 * sigma) / (2 * sqrt(time_fraction))
                     + self.risk_free_rate * strike * discount * (1 - nd2)) / 365

        return {
            'delta': delta,
            'gamma': gamma,
            'vega': vega,
            'theta': theta
        }

    def price_option(self, spot: float, strike: float, dte: float, iv: float,
                      option_type: str = "CALL") -> Tuple[float, float]:
        strike = max(strike, 1e-6)
        spot = max(spot, 1e-6)
        time_fraction = max(dte, 0.25) / 365
        sigma = min(max(iv, self.min_iv), self.max_iv)
        vol_sqrt_t = sigma * sqrt(time_fraction)

        if vol_sqrt_t == 0:
            if option_type == "CALL":
                intrinsic = max(spot - strike, 0.0)
                delta = 1.0 if spot > strike else 0.0
            else:
                intrinsic = max(strike - spot, 0.0)
                delta = -1.0 if spot < strike else 0.0
            return intrinsic, delta

        d1 = (log(spot / strike) + (self.risk_free_rate + 0.5 * sigma ** 2) * time_fraction) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        nd1 = self._norm_cdf(d1)
        nd2 = self._norm_cdf(d2)
        discount = exp(-self.risk_free_rate * time_fraction)

        if option_type == "CALL":
            price = spot * nd1 - strike * discount * nd2
            delta = nd1
        else:  # PUT
            price = strike * discount * (1 - nd2) - spot * (1 - nd1)
            delta = nd1 - 1  # Put delta is negative

        return max(price, 0.0), delta

    def estimate_fair_value(self, spot: float, strike: float, dte: float,
                            atr_pct: float, option_type: str = "CALL") -> Dict[str, float]:
        iv = self.annualize_vol(atr_pct)
        mid, _ = self.price_option(spot, strike, dte, iv, option_type)
        greeks = self.calculate_greeks(spot, strike, dte, iv, option_type)

        spread_pct = min(self.base_spread + (self.vol_spread_mult * atr_pct) + self.liquidity_spread, 0.02)
        bid = max(mid * (1 - spread_pct / 2), 0.0)
        ask = mid * (1 + spread_pct / 2)

        return {
            'iv': iv,
            'mid': mid,
            'bid': bid,
            'ask': ask,
            'spread_pct': spread_pct,
            'delta': greeks['delta'],
            'gamma': greeks['gamma'],
            'vega': greeks['vega'],
            'theta': greeks['theta'],
            'option_type': option_type
        }

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
    implied_vol: float
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    option_type: str = "CALL"  # CALL or PUT
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
    peak_unrealized: float = 0.0
    multi_tf_score: float = 0.0
    sentiment_score: float = 0.0
    regime: str = "train"
    trade_return: float = 0.0

    def __post_init__(self):
        self.current_price = self.entry_price

    def update_price(self, new_price: float):
        self.current_price = new_price
        self.pnl = (self.current_price - self.entry_price) * self.quantity
        self.peak_unrealized = max(self.peak_unrealized, self.pnl)

    def close(self, exit_price: float, fees: float = 0.0):
        self.exit_price = exit_price
        self.exit_time = datetime.now()
        self.status = "CLOSED"
        self.pnl = (exit_price - self.entry_price) * self.quantity
        self.total_fees_paid += fees
        self.pnl_after_fees = self.pnl - self.total_fees_paid
        notional = self.entry_price * self.quantity if self.entry_price > 0 else 0.0
        self.trade_return = (self.pnl_after_fees / notional) if notional > 0 else 0.0

    def roll(self, new_strike: float, new_dte: int, new_entry_price: float,
             new_implied_vol: float, roll_fee: float = 0.0):
        """Roll position to new strike/expiration"""
        self.rolled_count += 1
        self.strike = new_strike
        self.dte = new_dte
        self.entry_price = new_entry_price
        self.current_price = new_entry_price
        self.implied_vol = new_implied_vol
        self.total_fees_paid += roll_fee
        self.status = "ROLLED"
        logger.info(f"🔄 Position #{self.id} ROLLED: New Strike=${new_strike:.0f}, "
                   f"DTE={new_dte}, Roll #{self.rolled_count}")

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'option_type': self.option_type,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'quantity': self.quantity,
            'dte': self.dte,
            'strike': self.strike,
            'delta': self.delta,
            'qsci': self.qsci,
            'implied_vol': self.implied_vol,
            'pnl': self.pnl,
            'pnl_after_fees': self.pnl_after_fees,
            'total_fees_paid': self.total_fees_paid,
            'rolled_count': self.rolled_count,
            'status': self.status,
            'multi_tf_score': self.multi_tf_score,
            'sentiment_score': self.sentiment_score,
            'regime': self.regime,
            'trade_return': self.trade_return
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

    def __init__(
        self,
        n_simulations: int = 1000,
        confidence_level: float = 0.95,
        block_size: int = 25,  # Larger blocks preserve autocorrelation
        max_return_cap: float = 0.50,  # Cap at 50% per trade (very realistic)
        min_return_floor: float = -0.35  # Floor at -35% (realistic for options)
    ):
        self.n_simulations = n_simulations
        self.confidence_level = confidence_level
        self.block_size = max(block_size, 5)
        self.max_return_cap = max_return_cap
        self.min_return_floor = min_return_floor

    def _prepare_returns(self, trade_returns: List[float]) -> np.ndarray:
        # Winsorize extreme returns at 2nd/98th percentile
        arr = np.array(trade_returns)
        if len(arr) > 20:
            p2, p98 = np.percentile(arr, [2, 98])
            arr = np.clip(arr, p2, p98)
        clipped = np.clip(arr, self.min_return_floor, self.max_return_cap)
        return clipped  # Use simple returns, not log returns for stability

    def _block_bootstrap(self, log_returns: np.ndarray, n_samples: int) -> np.ndarray:
        if len(log_returns) == 0:
            return np.zeros(n_samples)

        if len(log_returns) <= self.block_size:
            return np.random.choice(log_returns, size=n_samples, replace=True)

        samples = []
        max_start = len(log_returns) - self.block_size
        while len(samples) < n_samples:
            start = np.random.randint(0, max_start + 1)
            block = log_returns[start:start + self.block_size]
            samples.extend(block)
        return np.array(samples[:n_samples])

    def simulate_returns(self, trade_returns: List[float], n_trades: int = None) -> Dict:
        if not trade_returns or len(trade_returns) < 5:
            return {'error': 'Insufficient trade data for simulation'}

        prepared_returns = self._prepare_returns(trade_returns)
        n_trades = n_trades or len(prepared_returns)

        final_returns = []
        max_drawdowns = []
        sharpe_ratios = []
        win_rates = []

        for _ in range(self.n_simulations):
            sampled = self._block_bootstrap(prepared_returns, n_trades)
            # Use arithmetic compounding for simple returns
            equity_curve = np.cumprod(1 + sampled)
            final_returns.append(equity_curve[-1] - 1)

            running_max = np.maximum.accumulate(equity_curve)
            drawdowns = 1 - (equity_curve / np.maximum(running_max, 1e-9))
            max_drawdowns.append(np.max(drawdowns))

            std = np.std(sampled)
            if std > 0:
                sharpe = np.mean(sampled) / std * np.sqrt(252)
            else:
                sharpe = 0
            sharpe_ratios.append(sharpe)
            win_rates.append(np.mean(sampled > 0))

        return {
            'n_simulations': self.n_simulations,
            'n_trades': n_trades,
            'return_mean': np.mean(final_returns) * 100,
            'return_median': np.median(final_returns) * 100,
            'return_std': np.std(final_returns) * 100,
            'return_5th_pct': np.percentile(final_returns, 5) * 100,
            'return_95th_pct': np.percentile(final_returns, 95) * 100,
            'return_worst': np.min(final_returns) * 100,
            'return_best': np.max(final_returns) * 100,
            'max_dd_mean': np.mean(max_drawdowns) * 100,
            'max_dd_median': np.median(max_drawdowns) * 100,
            'max_dd_95th_pct': np.percentile(max_drawdowns, 95) * 100,
            'max_dd_worst': np.max(max_drawdowns) * 100,
            'sharpe_mean': np.mean(sharpe_ratios),
            'sharpe_median': np.median(sharpe_ratios),
            'sharpe_5th_pct': np.percentile(sharpe_ratios, 5),
            'win_rate_mean': np.mean(win_rates) * 100,
            'win_rate_5th_pct': np.percentile(win_rates, 5) * 100,
            'prob_profit': np.mean(np.array(final_returns) > 0) * 100,
            'prob_beat_market': np.mean(np.array(final_returns) > 0.10) * 100,
        }

    def scenario_analysis(self, trade_returns: List[float], scenarios: Dict[str, Dict]) -> Dict:
        results = {}
        for scenario_name, params in scenarios.items():
            adjusted_returns = np.array(trade_returns)
            adjusted_returns = (adjusted_returns + params.get('mean_adj', 0))
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
        self.option_model = OptionMarketModel()
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
        self.daily_realized_pnl = defaultdict(float)
        self.daily_loss_limit_pct = 0.05  # 5% daily limit
        self.max_portfolio_drawdown_pct = 0.20  # 20% max DD before pause
        self.max_allowed_volatility = 0.06  # Allow trading in higher vol
        self.trade_cooldown_hours = 2  # Reduced cooldown for more trades
        self.consecutive_losses = 0
        self.consecutive_loss_limit = 5  # Allow 5 consecutive losses before pause
        self.last_trade_timestamp: Optional[datetime] = None
        self.max_vol_for_full_size = 0.025
        self.trailing_stop_factor = 0.5
        self.primary_df: Optional[pd.DataFrame] = None
        self.multi_tf_threshold = STRATEGY_PARAMS.get('multitf_threshold', 0.15)
        self.sentiment_threshold = STRATEGY_PARAMS.get('sentiment_filter_threshold', 0.05)
        self.multi_tf_weights = QSCI_CONFIG.get('timeframe_weights', {})
        self.external_sentiment_df = self._load_external_sentiment()
        self.oos_config = OOS_CONFIG
        self.regime_stats = defaultdict(
            lambda: {'pnl': 0.0, 'wins': 0, 'losses': 0, 'trades': 0, 'returns': []}
        )

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

    def _select_primary_dataframe(self, dataframes: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
        if PRIMARY_TIMEFRAME in dataframes:
            return dataframes[PRIMARY_TIMEFRAME].copy()

        for tf in TIMEFRAMES:
            if tf in dataframes:
                return dataframes[tf].copy()

        if dataframes:
            first_key = next(iter(dataframes))
            return dataframes[first_key].copy()
        return None

    def _apply_multi_timeframe_blend(self, primary_df: pd.DataFrame,
                                     dataframes: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        primary_df = primary_df.sort_values('Open Time').reset_index(drop=True)
        total_weight = 0.0
        mtf_accumulator = np.zeros(len(primary_df))

        for tf, weight in self.multi_tf_weights.items():
            tf_df = dataframes.get(tf)
            if tf_df is None or 'QSCI' not in tf_df:
                continue
            tf_local = tf_df[['Open Time', 'QSCI']].dropna().sort_values('Open Time')
            if tf_local.empty:
                continue
            merged = pd.merge_asof(
                primary_df[['Open Time']],
                tf_local,
                on='Open Time',
                direction='backward'
            )
            col_name = f'QSCI_{tf}'
            primary_df[col_name] = merged['QSCI']
            mtf_accumulator += weight * merged['QSCI'].fillna(0).values
            total_weight += weight

        if total_weight > 0:
            primary_df['MultiTF_QSCI'] = np.clip(mtf_accumulator / total_weight, -1, 1)
        else:
            primary_df['MultiTF_QSCI'] = primary_df.get('QSCI', 0)

        return primary_df

    def _load_external_sentiment(self) -> Optional[pd.DataFrame]:
        news_file = NEWS_SENTIMENT_CONFIG.get('news_data_file')
        if not news_file:
            return None

        path = Path(news_file)
        if not path.exists():
            return None

        try:
            df = pd.read_json(path)
            if 'timestamp' not in df.columns:
                if 'time' in df.columns:
                    df = df.rename(columns={'time': 'timestamp'})
                else:
                    return None
            sentiment_col = 'sentiment' if 'sentiment' in df.columns else None
            if sentiment_col is None:
                for candidate in ('score', 'sentiment_score', 'value'):
                    if candidate in df.columns:
                        sentiment_col = candidate
                        break
            if sentiment_col is None:
                return None

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df[['timestamp', sentiment_col]].dropna()
            df = df.rename(columns={sentiment_col: 'sentiment'})
            df = df.sort_values('timestamp').reset_index(drop=True)
            return df
        except Exception as exc:
            logger.warning(f"Sentiment file load failed: {exc}")
            return None

    def _build_sentiment_signal(self, primary_df: pd.DataFrame) -> pd.DataFrame:
        if 'Momentum' in primary_df:
            momentum_component = primary_df['Momentum']
        else:
            momentum_component = pd.Series(np.zeros(len(primary_df)), index=primary_df.index)

        if 'ROC' in primary_df:
            roc_component = primary_df['ROC']
        else:
            roc_component = pd.Series(np.zeros(len(primary_df)), index=primary_df.index)

        price_sentiment_raw = np.tanh((roc_component.fillna(0) / 10) + (momentum_component.fillna(0) / 50))

        memory = NEWS_SENTIMENT_CONFIG.get('sentiment_memory', 0.7)
        alpha = max(1 - memory, 0.05)
        price_sentiment_series = pd.Series(price_sentiment_raw, index=primary_df.index)
        primary_df['Price_Sentiment'] = price_sentiment_series.ewm(alpha=alpha, adjust=False).mean()

        price_weight = NEWS_SENTIMENT_CONFIG.get('price_weight', 0.4)
        nlp_weight = NEWS_SENTIMENT_CONFIG.get('nlp_weight', 0.6)
        weight_sum = max(price_weight + nlp_weight, 1e-3)

        if self.external_sentiment_df is not None and not self.external_sentiment_df.empty:
            merged = pd.merge_asof(
                primary_df[['Open Time']],
                self.external_sentiment_df,
                left_on='Open Time',
                right_on='timestamp',
                direction='backward'
            )
            nlp_sentiment = merged['sentiment'].fillna(0)
        else:
            nlp_sentiment = pd.Series(np.zeros(len(primary_df)), index=primary_df.index)

        blended = (
            price_weight * primary_df['Price_Sentiment'].fillna(0) +
            nlp_weight * nlp_sentiment.fillna(0)
        ) / weight_sum

        primary_df['Sentiment_Score'] = np.clip(blended, -1, 1)
        return primary_df

    def _apply_regime_labels(self, primary_df: pd.DataFrame) -> pd.DataFrame:
        total_rows = len(primary_df)
        if total_rows == 0 or total_rows < self.oos_config.get('min_samples', 0):
            primary_df['Regime'] = 'train'
            return primary_df

        train_cut = min(int(total_rows * self.oos_config.get('train_fraction', 0.6)), total_rows)
        val_cut = min(
            train_cut + int(total_rows * self.oos_config.get('validation_fraction', 0.2)),
            total_rows
        )

        regimes = np.empty(total_rows, dtype=object)
        regimes[:] = 'train'
        regimes[train_cut:val_cut] = 'validation'
        regimes[val_cut:] = 'test'
        primary_df['Regime'] = regimes
        return primary_df

    def _calibrate_thresholds(self, primary_df: pd.DataFrame):
        train_mask = primary_df['Regime'] == 'train'

        mtf_series = primary_df.loc[train_mask, 'MultiTF_QSCI'].abs().dropna()
        if not mtf_series.empty:
            self.multi_tf_threshold = max(
                np.quantile(mtf_series, 0.55),
                STRATEGY_PARAMS.get('multitf_threshold', 0.15)
            )

        sentiment_series = primary_df.loc[train_mask, 'Sentiment_Score'].abs().dropna()
        if not sentiment_series.empty:
            self.sentiment_threshold = max(
                np.quantile(sentiment_series, 0.55),
                STRATEGY_PARAMS.get('sentiment_filter_threshold', 0.05)
            )

    def prepare_primary_dataframe(self, dataframes: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
        primary_df = self._select_primary_dataframe(dataframes)
        if primary_df is None:
            return None

        primary_df = primary_df.sort_values('Open Time').reset_index(drop=True)
        primary_df = self._apply_multi_timeframe_blend(primary_df, dataframes)
        primary_df = self._build_sentiment_signal(primary_df)
        primary_df = self._apply_regime_labels(primary_df)
        self._calibrate_thresholds(primary_df)

        primary_df['MultiTF_Filter_Pass'] = (
            primary_df['MultiTF_QSCI'].abs() >= self.multi_tf_threshold
        )

        sentiment_alignment = (
            np.sign(primary_df['Sentiment_Score'].fillna(0)) ==
            np.sign(primary_df['MultiTF_QSCI'].fillna(0))
        )
        primary_df['Sentiment_Filter_Pass'] = (
            primary_df['Sentiment_Score'].abs() >= self.sentiment_threshold
        ) & sentiment_alignment

        return primary_df

    def calculate_transaction_cost(self, trade_value: float, spread_pct: float,
                                   is_maker: bool = False) -> Tuple[float, float]:
        """Calculate fees and slippage for a trade"""

        fee, slippage = self.fees.calculate_total_cost(
            trade_value,
            spread_pct,
            is_maker=is_maker,
            trade_type='options'
        )
        return fee, slippage

    def should_block_new_trades(self, current_time: datetime, volatility_pct: float) -> bool:
        if volatility_pct > self.max_allowed_volatility:
            return True

        dd_stats = self.drawdown_tracker.get_stats()
        current_dd = dd_stats.get('current_drawdown_pct', 0) / 100
        if current_dd >= self.max_portfolio_drawdown_pct:
            return True

        day_key = current_time.date()
        daily_loss_limit = -self.initial_balance * self.daily_loss_limit_pct
        if self.daily_realized_pnl.get(day_key, 0.0) <= daily_loss_limit:
            return True

        if self.last_trade_timestamp is not None:
            hours_since = (current_time - self.last_trade_timestamp).total_seconds() / 3600
            if hours_since < self.trade_cooldown_hours:
                return True

        if self.consecutive_losses >= self.consecutive_loss_limit and self.last_trade_timestamp:
            if self.last_trade_timestamp.date() == current_time.date():
                return True

        return False

    def record_realized_pnl(self, timestamp: datetime, pnl: float):
        day_key = timestamp.date()
        self.daily_realized_pnl[day_key] += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def update_trade_statistics(self, position: Position, trade_returns: List[float]):
        if position.entry_price > 0:
            trade_returns.append(position.trade_return)

        regime = position.regime or 'train'
        bucket = self.regime_stats[regime]
        bucket['pnl'] += position.pnl_after_fees
        bucket['trades'] += 1
        if position.pnl_after_fees > 0:
            bucket['wins'] += 1
        else:
            bucket['losses'] += 1
        bucket['returns'].append(position.trade_return)

    def check_rolling_needed(self, position: Position, current_dte: float) -> bool:
        """Check if position needs to be rolled"""
        roll_threshold = EXIT_RULES.get('roll_dte_threshold', 7)
        return current_dte <= roll_threshold and position.status == "OPEN"

    def execute_roll(self, position: Position, spot_price: float, current_time: datetime,
                    volatility_pct: float) -> bool:
        """Execute position roll to new expiration"""

        # Calculate roll cost (exit old + enter new)
        exit_value = position.current_price * position.quantity
        atr_pct = max(volatility_pct, 0.0005)
        spread_pct = min(
            self.option_model.base_spread + (self.option_model.vol_spread_mult * atr_pct) +
            self.option_model.liquidity_spread,
            0.02
        )
        exit_fee, exit_slippage = self.calculate_transaction_cost(exit_value, spread_pct)

        new_dte = 14
        new_strike = round(spot_price / 100) * 100
        new_pricing = self.option_model.estimate_fair_value(spot_price, new_strike, new_dte, atr_pct)
        new_entry_price = max(new_pricing['mid'], new_pricing['bid'])
        new_entry_value = new_entry_price * position.quantity

        entry_fee, entry_slippage = self.calculate_transaction_cost(
            new_entry_value,
            new_pricing['spread_pct']
        )

        total_roll_cost = exit_fee + exit_slippage + entry_fee + entry_slippage

        # Execute roll
        position.roll(new_strike, new_dte, new_entry_price, new_pricing['iv'], total_roll_cost)

        self.total_fees_paid += exit_fee + entry_fee
        self.total_slippage += exit_slippage + entry_slippage
        self.rolls_executed += 1

        logger.info(f"🔄 Roll executed: Total cost ${total_roll_cost:.2f}")
        return True

    def _compute_iv_rank(self, df: pd.DataFrame, lookback_days: int = 90) -> float:
        """Compute IV Rank from historical ATR data
        
        IV Rank = (current IV - min IV) / (max IV - min IV)
        Returns value between 0 (lowest IV) and 1 (highest IV)
        """
        if 'ATR' not in df.columns or 'Close' not in df.columns:
            return 0.5  # Default to neutral if data missing
        
        # Calculate lookback window in rows (approximate based on timeframe)
        lookback_rows = min(lookback_days * 24, len(df) - 1)  # Assume hourly for 1h timeframe
        if lookback_rows < 10:
            return 0.5
        
        # Get recent data
        recent_df = df.iloc[-lookback_rows:].copy()
        
        # Compute IV from ATR percentage
        recent_df['ATR_PCT'] = recent_df['ATR'] / recent_df['Close']
        iv_series = recent_df['ATR_PCT'].apply(lambda x: self.option_model.annualize_vol(x))
        
        if len(iv_series) < 2:
            return 0.5
        
        current_iv = iv_series.iloc[-1]
        min_iv = iv_series.min()
        max_iv = iv_series.max()
        
        # Avoid division by zero
        if max_iv - min_iv < 0.01:
            return 0.5
        
        iv_rank = (current_iv - min_iv) / (max_iv - min_iv)
        return np.clip(iv_rank, 0.0, 1.0)

    def calculate_position_size(self, qsci: float, delta: float, option_price: float,
                                spot_price: float, volatility_pct: float) -> int:
        """Calculate position size with conviction-based scaling
        
        Uses risk_per_trade to bound max loss (premium paid on long options),
        then clips to max_position_size_pct.
        """

        risk_pct = POSITION_CONFIG['risk_per_trade']
        max_size_pct = POSITION_CONFIG['max_position_size_pct']
        
        option_price = max(option_price, spot_price * 0.001)  # Minimum floor

        # Use risk_per_trade as intended: max premium at risk
        risk_amount = self.account_balance * risk_pct
        qty_by_risk = int(max(1, risk_amount / option_price))
        
        # Max trade value cap
        max_trade_val = self.account_balance * max_size_pct
        qty_by_max_val = int(max(1, max_trade_val / option_price))
        
        # Base quantity from risk limits
        base_quantity = min(qty_by_risk, qty_by_max_val)

        # Conviction multiplier: stronger signals get bigger size
        conviction = abs(qsci)
        if conviction > 0.5:
            signal_mult = 1.0 + (conviction - 0.5) * 0.8  # Up to 1.4x for strong signals
        else:
            signal_mult = 0.7 + conviction * 0.6  # 0.7x to 1.0x for weaker signals

        # Delta efficiency: prefer 0.4-0.5 delta for best leverage
        delta_efficiency = 1.0 - abs(abs(delta) - 0.45) * 0.5
        delta_mult = max(0.6, min(1.2, delta_efficiency))

        # Lower vol = more size, higher vol = less size
        vol_penalty = np.clip(0.03 / max(volatility_pct, 0.005), 0.5, 1.5)

        # Reduce size in drawdown
        dd_stats = self.drawdown_tracker.get_stats()
        dd_pct = dd_stats.get('current_drawdown_pct', 0) / 100
        dd_penalty = max(0.4, 1.0 - dd_pct * 1.5)

        # Apply scaling factors
        adjusted_quantity = base_quantity * signal_mult * delta_mult * vol_penalty * dd_penalty
        
        # Ensure we don't exceed max size after scaling
        final_quantity = int(min(adjusted_quantity, qty_by_max_val))

        return max(1, final_quantity)

    def simulate_trade(
        self,
        qsci: float,
        spot_price: float,
        volatility_pct: float,
        current_time: datetime,
        atr_value: float,
        dte: int = 14,
        multi_tf_score: Optional[float] = None,
        sentiment_score: Optional[float] = None,
        multi_tf_ok: bool = True,
        sentiment_ok: bool = True,
        regime: str = 'train',
        adx_value: float = 0.0,
        trend_direction: float = 0.0,
        volume_signal: float = 0.0
    ) -> bool:
        """Simulate directional trade: CALL for bullish, PUT for bearish"""

        open_positions = [p for p in self.positions if p.status == "OPEN"]
        if len(open_positions) >= POSITION_CONFIG['max_concurrent_positions']:
            return False

        # Require minimum signal strength (absolute value)
        abs_qsci = abs(qsci)
        if abs_qsci < ENTRY_CRITERIA['min_qsci_signal']:
            return False

        # Determine direction: positive QSCI = bullish (CALL), negative = bearish (PUT)
        option_type = "CALL" if qsci > 0 else "PUT"

        # ADX trend strength filter - only trade when trend exists
        min_adx = ENTRY_CRITERIA.get('min_adx', 20)
        if adx_value > 0 and adx_value < min_adx:
            return False

        # Trend alignment filter - for high conviction trades
        if ENTRY_CRITERIA.get('require_trend_alignment', True) and abs(trend_direction) > 0.1:
            # CALL needs positive trend, PUT needs negative trend
            if option_type == "CALL" and trend_direction < 0:
                return False
            if option_type == "PUT" and trend_direction > 0:
                return False

        # Volume confirmation filter (positive volume = bullish)
        if STRATEGY_PARAMS.get('require_volume_confirmation'):
            if option_type == "CALL" and volume_signal < -0.2:
                return False
            if option_type == "PUT" and volume_signal > 0.2:
                return False

        if STRATEGY_PARAMS.get('use_multi_timeframe') and not multi_tf_ok:
            return False

        if STRATEGY_PARAMS.get('use_sentiment_filter') and not sentiment_ok:
            return False

        atr_pct = atr_value / spot_price if spot_price > 0 else volatility_pct
        if self.should_block_new_trades(current_time, atr_pct):
            return False

        # For very strong signals, bypass some filters
        is_strong_signal = abs_qsci >= 0.45

        if STRATEGY_PARAMS.get('only_strong_signals') and not is_strong_signal:
            return False

        if dte < ENTRY_CRITERIA.get('min_dte', 5) or dte > ENTRY_CRITERIA.get('max_dte', 21):
            return False

        # Strike selection: OTM for better leverage, adjust by signal strength
        otm_pct = 0.02 + abs_qsci * 0.02  # 2-4% OTM based on conviction
        if option_type == "CALL":
            strike = round(spot_price * (1 + otm_pct) / 100) * 100
        else:
            strike = round(spot_price * (1 - otm_pct) / 100) * 100

        pricing = self.option_model.estimate_fair_value(
            spot_price, strike, dte, atr_pct, option_type
        )
        option_price = pricing['mid']
        delta = pricing['delta']

        quantity = self.calculate_position_size(
            abs_qsci, abs(delta), option_price, spot_price, atr_pct
        )
        if quantity <= 0:
            return False

        trade_value = option_price * quantity
        fee, slippage = self.calculate_transaction_cost(trade_value, pricing['spread_pct'])

        self.position_counter += 1
        position = Position(
            id=self.position_counter,
            entry_price=option_price,
            quantity=quantity,
            dte=dte,
            strike=strike,
            delta=delta,
            qsci=qsci,
            implied_vol=pricing['iv'],
            option_type=option_type,
            entry_time=current_time,
            multi_tf_score=multi_tf_score if multi_tf_score is not None else qsci,
            sentiment_score=sentiment_score if sentiment_score is not None else 0.0,
            regime=regime
        )
        position.total_fees_paid = fee + slippage

        self.positions.append(position)
        self.total_fees_paid += fee
        self.total_slippage += slippage
        self.last_trade_timestamp = current_time

        logger.info(
            f"✓ Position #{self.position_counter}: {option_type} QSCI={qsci:.3f}, "
            f"Price=${option_price:.2f}, Qty={quantity}, Delta={delta:.2f}, Fees=${fee + slippage:.2f}"
        )

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

        self.primary_df = self.prepare_primary_dataframe(dataframes)
        primary_df = self.primary_df if self.primary_df is not None else pd.DataFrame()

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
            row = primary_df.iloc[idx]
            spot_price = row['Close']
            current_time = row['Open Time']

            volatility = row['NATR'] / 100 if 'NATR' in row else 0.02
            atr_value = row['ATR'] if 'ATR' in row else spot_price * 0.02
            atr_pct = atr_value / spot_price if spot_price > 0 else volatility

            qsci = row['QSCI'] if 'QSCI' in row else 0.0
            multi_tf_score = row['MultiTF_QSCI'] if 'MultiTF_QSCI' in row else qsci
            multi_tf_pass = bool(row.get('MultiTF_Filter_Pass', True))
            sentiment_score = row.get('Sentiment_Score', 0.0)
            sentiment_pass = bool(row.get('Sentiment_Filter_Pass', True))
            current_regime = row.get('Regime', 'train')
            qsci_values.append(qsci)

            # ================== POSITION MANAGEMENT ==================
            for pos in self.positions:
                if pos.status != "OPEN":
                    continue

                pos.dte = max(0, pos.dte - (1/6))
                current_dte = max(pos.dte, 0.25)

                pricing_snapshot = self.option_model.estimate_fair_value(
                    spot_price, pos.strike, current_dte, atr_pct, pos.option_type
                )
                blended_iv = pricing_snapshot['iv'] if pos.implied_vol == 0 else (
                    0.5 * pos.implied_vol + 0.5 * pricing_snapshot['iv']
                )
                mid_price, delta = self.option_model.price_option(
                    spot_price, pos.strike, current_dte, blended_iv, pos.option_type
                )
                spread_for_close = pricing_snapshot['spread_pct']
                mark_price = max(mid_price, pricing_snapshot['bid'])
                pos.implied_vol = blended_iv
                pos.delta = delta
                pos.update_price(max(mark_price, 0.001))

                if self.check_rolling_needed(pos, pos.dte):
                    if pos.dte <= EXIT_RULES.get('mandatory_close_dte', 3):
                        fee, slippage = self.calculate_transaction_cost(
                            pos.current_price * pos.quantity,
                            spread_for_close
                        )
                        pos.close(pos.current_price, fee + slippage)
                        self.trades_log.append(pos.to_dict())
                        self.account_balance += pos.pnl_after_fees
                        self.update_trade_statistics(pos, trade_returns)
                        self.total_fees_paid += fee
                        self.total_slippage += slippage
                        self.record_realized_pnl(current_time, pos.pnl_after_fees)
                        logger.info(
                            f"⏰ Position #{pos.id} EXPIRED: P&L=${pos.pnl_after_fees:.2f}"
                        )
                        continue

                    self.execute_roll(pos, spot_price, current_time, atr_pct)
                    pos.status = "OPEN"
                    continue

                profit_pct = pos.pnl / (pos.entry_price * pos.quantity)

                # Asymmetric R/R: bigger TP, tighter SL
                tp_threshold = EXIT_RULES.get('tp1_target', 1.5) * atr_pct
                # Tighter stop for losers, scale SL with signal strength
                sl_base = EXIT_RULES.get('sl_multiplier', 1.2) * atr_pct
                sl_threshold = -sl_base * max(0.6, min(1.0, 1.0 - abs(pos.qsci) * 0.3))

                # Enhanced trailing stop with momentum
                protective_exit = False
                trailing_activation = EXIT_RULES.get('trailing_activation', 0.8) * atr_pct
                trailing_distance = EXIT_RULES.get('trailing_distance', 0.35)

                if pos.peak_unrealized > 0:
                    peak_pct = pos.peak_unrealized / (pos.entry_price * pos.quantity)
                    give_back = peak_pct - profit_pct
                    # Tighter trailing for big winners
                    dynamic_trail = trailing_distance * (1.0 - min(peak_pct * 0.5, 0.3))
                    if peak_pct > trailing_activation and give_back >= peak_pct * dynamic_trail:
                        protective_exit = True

                exit_reason = None
                if profit_pct >= tp_threshold:
                    exit_reason = "TP"
                elif profit_pct <= sl_threshold:
                    exit_reason = "SL"
                elif protective_exit:
                    exit_reason = "TRAIL"

                if exit_reason:
                    fee, slippage = self.calculate_transaction_cost(
                        pos.current_price * pos.quantity,
                        spread_for_close
                    )
                    pos.close(pos.current_price, fee + slippage)
                    self.trades_log.append(pos.to_dict())
                    self.account_balance += pos.pnl_after_fees
                    self.update_trade_statistics(pos, trade_returns)
                    self.total_fees_paid += fee
                    self.total_slippage += slippage
                    self.record_realized_pnl(current_time, pos.pnl_after_fees)
                    logger.info(
                        f"{exit_reason} Position #{pos.id}: ${pos.pnl_after_fees:.2f} "
                        f"({profit_pct*100:.1f}%)"
                    )

            # ================== NEW ENTRIES ==================
            if idx % 1 == 0:  # Check EVERY candle for opportunities
                # Get additional filters from row
                adx_val = row.get('ADX', 0.0) if 'ADX' in row else 0.0
                trend_dir = row.get('Trend_Signal', 0.0) if 'Trend_Signal' in row else 0.0
                vol_sig = row.get('Volume_Signal', 0.0) if 'Volume_Signal' in row else 0.0

                self.simulate_trade(
                    qsci,
                    spot_price,
                    volatility,
                    current_time,
                    atr_value,
                    multi_tf_score=multi_tf_score,
                    sentiment_score=sentiment_score,
                    multi_tf_ok=multi_tf_pass,
                    sentiment_ok=sentiment_pass,
                    regime=current_regime,
                    adx_value=adx_val,
                    trend_direction=trend_dir,
                    volume_signal=vol_sig
                )

            # ================== UPDATE DRAWDOWN ==================
            open_pnl = sum(p.pnl for p in self.positions if p.status == "OPEN")
            current_equity = self.account_balance + open_pnl
            self.drawdown_tracker.update(current_equity, current_time)

        # Close remaining positions
        final_spot = primary_df.iloc[-1]['Close']
        final_time = primary_df.iloc[-1]['Open Time']
        final_volatility = primary_df.iloc[-1]['NATR'] / 100 if 'NATR' in primary_df else 0.02
        final_atr = primary_df.iloc[-1]['ATR'] if 'ATR' in primary_df else final_spot * 0.02
        final_atr_pct = final_atr / final_spot if final_spot > 0 else final_volatility

        for pos in self.positions:
            if pos.status == "OPEN":
                pricing_snapshot = self.option_model.estimate_fair_value(
                    final_spot, pos.strike, max(pos.dte, 0.25), final_atr_pct,
                    pos.option_type
                )
                mid_price, _ = self.option_model.price_option(
                    final_spot, pos.strike, max(pos.dte, 0.25),
                    pricing_snapshot['iv'], pos.option_type
                )
                mark_price = max(mid_price, pricing_snapshot['bid'])
                pos.update_price(mark_price)
                fee, slippage = self.calculate_transaction_cost(
                    mark_price * pos.quantity,
                    pricing_snapshot['spread_pct']
                )
                pos.close(mark_price, fee + slippage)
                self.trades_log.append(pos.to_dict())
                self.account_balance += pos.pnl_after_fees
                self.total_fees_paid += fee
                self.total_slippage += slippage
                self.record_realized_pnl(final_time, pos.pnl_after_fees)
                self.update_trade_statistics(pos, trade_returns)

        # ================== MONTE CARLO SIMULATION ==================
        logger.info("\n" + "="*80)
        logger.info("RUNNING MONTE CARLO SIMULATION...")
        logger.info("="*80)

        mc_results = {}
        scenario_results = {}
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

        oos_summary = self.generate_oos_summary()
        if oos_summary:
            logger.info(f"\n🧪 OOS SPLIT PERFORMANCE:")
            for phase in ['train', 'validation', 'test']:
                stats = oos_summary.get(phase)
                if not stats:
                    continue
                logger.info(
                    f"  {phase.title():>10}: Trades={stats['trades']}, P&L=${stats['pnl']:.2f}, "
                    f"Win%={stats['win_rate']:.1f}%, Avg Trade={stats['avg_return']:.2f}%"
                )

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

    def generate_oos_summary(self) -> Dict[str, Dict[str, float]]:
        summary = {}
        for regime, stats in self.regime_stats.items():
            trades = stats['trades']
            if trades == 0:
                continue
            win_rate = (stats['wins'] / trades) * 100 if trades else 0
            avg_return = np.mean(stats['returns']) * 100 if stats['returns'] else 0
            summary[regime] = {
                'trades': trades,
                'pnl': stats['pnl'],
                'win_rate': win_rate,
                'avg_return': avg_return
            }
        return summary

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
