"""
QSCI BTC Options Backtester v3.0
Quantum-Sentiment Composite Indicator for Bitcoin Call Options Trading
Multi-Timeframe Analysis with Sentiment Integration
Author: Quantitative Trading System
Date: December 11, 2025

Configuration File for API Keys and Settings
"""

import os
from datetime import datetime

# ============================================================================
# BINANCE TESTNET CONFIGURATION
# ============================================================================

# Binance Testnet API Keys (Demo - No Real Money)
BINANCE_TESTNET_API_KEY = "0nEdzlzOmXUqu9dVt4TmTVXtlr9MGTiwKwOqj1QUktN9jmTOmsKam9YlGwyOgzXq"
BINANCE_TESTNET_API_SECRET = "9trLkyBGwSFr404IH6NcjUQwNcXIuOLw8tvUcOJoWkOq0i89qBuHaLQ2jwF1KcUU"

# Binance Mainnet API Keys (Optional - for live data only)
BINANCE_MAINNET_API_KEY = "0nEdzlzOmXUqu9dVt4TmTVXtlr9MGTiwKwOqj1QUktN9jmTOmsKam9YlGwyOgzXq"
BINANCE_MAINNET_API_SECRET = "9trLkyBGwSFr404IH6NcjUQwNcXIuOLw8tvUcOJoWkOq0i89qBuHaLQ2jwF1KcUU"

# API Configuration
USE_TESTNET = False  # Set to True for demo, False for live data only
USE_MAINNET_FOR_DATA = True  # Use mainnet for historical data (testnet has limited data)

# ============================================================================
# BACKTEST CONFIGURATION
# ============================================================================

# Date Range
BACKTEST_START_DATE = "2013-01-01"  # Format: YYYY-MM-DD
BACKTEST_END_DATE = "2025-12-01"    # Format: YYYY-MM-DD
SYMBOL = "BTCUSDT"
OPTION_SYMBOL = "BTC"

# Out-of-sample split configuration (fractions must sum to 1)
OOS_CONFIG = {
    "train_fraction": 0.60,
    "validation_fraction": 0.20,
    "test_fraction": 0.20,
    "min_samples": 500,
}

# Timeframes
TIMEFRAMES = ["4h", "2h", "1h", "30m", "15m", "5m", "1m"]  # For QSCI calculation
PRIMARY_TIMEFRAME = "1h"  # Main analysis timeframe

# QSCI Parameters - Enhanced v3.0 with 15+ indicators
QSCI_CONFIG = {
    "timeframe_weights": {
        "4h": 0.25,
        "2h": 0.20,
        "1h": 0.15,
        "30m": 0.15,
        "15m": 0.10,
        "5m": 0.10,
        "1m": 0.05
    },
    # === MOMENTUM INDICATORS ===
    "rsi_period": 14,
    "stoch_rsi_period": 14,
    "stoch_rsi_fastk": 5,
    "stoch_rsi_fastd": 3,
    "williams_r_period": 14,
    "mfi_period": 14,
    "cci_period": 20,
    "roc_period": 10,
    "ultimate_osc_periods": [7, 14, 28],

    # === TREND INDICATORS ===
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "ema_period": 20,
    "ema_long_period": 50,
    "adx_period": 14,
    "aroon_period": 25,
    "psar_acceleration": 0.02,
    "psar_maximum": 0.2,

    # === ICHIMOKU SETTINGS ===
    "ichimoku_tenkan": 9,
    "ichimoku_kijun": 26,
    "ichimoku_senkou_b": 52,

    # === VOLATILITY INDICATORS ===
    "atr_period": 14,
    "bb_period": 20,
    "bb_std": 2,
    "keltner_period": 20,
    "keltner_atr_mult": 2.0,

    # === VOLUME INDICATORS ===
    "obv_ema_period": 20,
    "cmf_period": 20,
    "adosc_fast": 3,
    "adosc_slow": 10,

    # === SIGNAL CATEGORY WEIGHTS ===
    "momentum_weight": 0.35,
    "trend_weight": 0.30,
    "volume_weight": 0.15,
    "volatility_weight": 0.10,
    "pattern_weight": 0.10,

    # === QSCI FINAL WEIGHTS ===
    "mtc_weight": 0.70,  # Technical signals weight
    "sentiment_weight": 0.30,  # Sentiment weight
}

# News Sentiment Configuration - Enhanced v3.0 with NLP
NEWS_SENTIMENT_CONFIG = {
    "source_weights": {
        "bloomberg": 1.0,
        "reuters": 1.0,
        "wsj": 0.9,
        "ft": 0.9,
        "coindesk": 0.6,
        "cointelegraph": 0.6,
        "cryptonews": 0.5,
        "twitter": 0.3,
        "reddit": 0.2
    },
    "decay_lambda": 0.1,  # Exponential decay rate for news recency
    "sentiment_range": [-3, 3],  # Min and max sentiment scores
    "use_dummy_sentiment": False,  # Set True for backtest without sentiment

    # NLP Configuration
    "use_vader": True,  # Use VADER sentiment analyzer (preferred)
    "use_textblob": True,  # Use TextBlob as fallback
    "sentiment_threshold": 0.05,  # Minimum sentiment magnitude to consider

    # Sentiment blending
    "nlp_weight": 0.6,  # Weight for NLP-based sentiment
    "price_weight": 0.4,  # Weight for price-based sentiment
    "sentiment_memory": 0.7,  # Memory factor for smoothing (0-1)

    # News data settings
    "news_data_file": "temp/news_data.json",
    "news_lookback_hours": 48,  # How far back to consider news
}

# ============================================================================
# OPTIONS TRADING CONFIGURATION
# ============================================================================

# Position Management - Optimized for Positive EV
POSITION_CONFIG = {
    "account_balance": 10000,  # Demo account: $10,000
    "risk_per_trade": 0.02,  # 2% risk per trade (conservative for +EV)
    "max_concurrent_positions": 1,  # Single position for higher quality
    "max_position_size_pct": 0.04,  # Max 4% of account per trade
    "scale_in_enabled": False,
    "scale_in_threshold": 0.3,
}

# DTE (Days to Expiration) Multipliers
DTE_MULTIPLIERS = {
    "above_14": 1.0,
    "7_to_14": 0.95,
    "3_to_7": 0.80,
    "1_to_3": 0.50,
    "below_1": 0.0  # DO NOT TRADE
}

# Entry Criteria - Optimized for Higher Win Rate (+EV)
ENTRY_CRITERIA = {
    "min_qsci_signal": 0.15,  # Raised from 0.12 for higher quality signals
    "min_liquidity_adjustment": 0.5,
    "min_dte": 7,  # Slightly longer for less theta decay pressure
    "max_dte": 21,  # Max 3 weeks - less theta decay exposure
    "min_delta": 0.40,  # Higher delta for better directional exposure
    "max_delta": 0.55,  # Narrower range for optimal delta
    "target_moneyness": 1.02,  # 2% OTM (closer to ATM)
    "max_spread_pct": 0.015,  # Tighter spreads for better fills
    "min_adx": 25,  # Raised from 20 for stronger trends
    "require_trend_alignment": True,  # Keep trend alignment
    "max_iv_rank": 0.50,  # Lowered from 0.6 - avoid expensive options

    # Filters for higher quality trades
    "require_volume_confirmation": True,
    "use_strongest_tf_signal": False,
}# Greeks Configuration
GREEKS_CONFIG = {
    "delta_weight": 0.40,
    "gamma_weight": 0.25,
    "vega_weight": 0.20,
    "theta_weight": 0.15,
    "max_gamma_risk": 0.015,  # Alert if gamma > 0.015
    "max_theta_decay": -0.05,  # Alert if theta < -0.05
}

# Exit Rules - Optimized for Better R/R (+EV)
EXIT_RULES = {
    "tp1_target": 2.0,  # Raised from 1.5x - let winners run more
    "tp2_target": 3.5,  # Raised from 3.0x ATR
    "tp3_target": 5.5,  # Big winners to 5.5x ATR
    "sl_multiplier": 1.0,  # Tighter SL at 1.0x (was 1.2) - cut losers faster
    "roll_dte_threshold": 10,  # Roll earlier (was 8)
    "mandatory_close_dte": 5,  # Close if not rolled (was 4)
    "trailing_activation": 1.0,  # Activate trail after 1.0 ATR profit
    "trailing_distance": 0.30,  # Tighter trail at 30% of peak
}

# ============================================================================
# FEES AND COSTS
# ============================================================================

FEES = {
    "binance_trading_fee": 0.001,  # 0.1% trading fee
    "binance_options_fee": 0.0002,  # 0.02% options fee
    "slippage_pct": 0.002,  # 0.2% slippage assumption
}

# ============================================================================
# LOGGING AND OUTPUT
# ============================================================================

LOG_CONFIG = {
    "log_file": "qsci_backtest.log",
    "log_level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "console_output": True,
    "save_trades": True,
    "trade_log_file": "trades.csv",
    "performance_log_file": "performance.csv",
}

# ============================================================================
# VISUALIZATION
# ============================================================================

CHART_CONFIG = {
    "plot_results": True,
    "save_plots": True,
    "plot_directory": "./plots",
    "plot_dpi": 100,
    "plot_style": "seaborn-v0_8-darkgrid",
    "figure_size": (16, 10),
}

# ============================================================================
# BACKTEST MODES
# ============================================================================

BACKTEST_MODES = {
    "mode": "HISTORICAL_DATA",  # Options: HISTORICAL_DATA, LIVE_PAPER, SIMULATION
    "use_cached_data": True,  # Use cached OHLCV data if available
    "cache_dir": "./data_cache",
    "update_cache": False,  # Re-download data from Binance
}

# ============================================================================
# ALERT THRESHOLDS
# ============================================================================

ALERTS = {
    "large_spread_alert": 0.015,  # Alert if spread > 1.5%
    "low_volume_alert": 10,  # Alert if volume < 10 contracts
    "gamma_risk_alert": 0.01,  # Alert if gamma > 0.01
    "theta_decay_alert": -0.03,  # Alert if theta < -0.03
    "liquidation_alert": 0.05,  # Alert if liquidation risk > 5%
}

# ============================================================================
# STRATEGY PARAMETERS
# ============================================================================

STRATEGY_PARAMS = {
    "only_strong_signals": False,  # Allow moderate signals too
    "use_sentiment_filter": False,  # Disable for cleaner signals
    "use_multi_timeframe": True,  # Use all timeframes
    "dynamic_position_sizing": True,  # Scale size with conviction
    "use_kelly_criterion": False,
    "kelly_fraction": 0.15,
    "multitf_threshold": 0.12,  # Lower threshold
    "sentiment_filter_threshold": 0.05,
    "require_volume_confirmation": False,
    "min_win_probability": 0.40,
}

# ============================================================================
# DATABASE - MongoDB Atlas Configuration
# ============================================================================

DATABASE_CONFIG = {
    "use_database": True,  # Set True to use MongoDB for data storage
    "db_file": "qsci_backtest.db",  # Legacy SQLite (for backtest mode)
    "auto_backup": True,
}

# MongoDB Configuration (for live trading)
MONGODB_CONFIG = {
    "uri": os.getenv("MONGODB_URI", ""),
    "database": "qsci_trading",
    "data_retention_days": 365,  # Keep OHLCV data for 1 year
    "log_retention_days": 180,   # Keep logs/trades for 6 months
    "max_storage_mb": 480,       # Leave buffer from 512MB free tier limit
}

# ============================================================================
# TELEGRAM CONFIGURATION
# ============================================================================

TELEGRAM_CONFIG = {
    "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "channel_id": os.getenv("TELEGRAM_CHANNEL_ID", ""),
    "log_retention_days": 180,   # Clear messages older than 6 months
    "notification_level": "ALL", # ALL, TRADES_ONLY, SUMMARY_ONLY
    "send_signals": True,        # Send signals even without trades
    "send_daily_summary": True,  # Send daily P&L summary
    "summary_hour_utc": 0,       # Hour (UTC) to send daily summary
}

# ============================================================================
# NEWS API CONFIGURATION
# ============================================================================

NEWS_CONFIG = {
    # CryptoPanic API (recommended - free tier: 1000 requests/day)
    "use_cryptopanic": True,
    "cryptopanic_api_key": os.getenv("CRYPTOPANIC_API_KEY", ""),
    "cryptopanic_url": "https://cryptopanic.com/api/v1/posts/",

    # Fallback to simulated sentiment if news API fails
    "fallback_to_dummy": True,

    # News processing settings
    "max_news_age_hours": 24,
    "min_news_for_signal": 3,

    # Source weights for sentiment calculation
    "source_weights": {
        "cryptopanic": 0.8,
        "twitter": 0.3,
        "reddit": 0.2,
    }
}

# ============================================================================
# LIVE TRADING CONFIGURATION
# ============================================================================

LIVE_TRADING_CONFIG = {
    "mode": os.getenv("TRADING_MODE", "paper"),  # paper, backtest
    "initial_balance": float(os.getenv("INITIAL_BALANCE", "10000")),
    "check_interval_minutes": int(os.getenv("CHECK_INTERVAL_MINUTES", "5")),
    "max_daily_loss_pct": float(os.getenv("MAX_DAILY_LOSS_PCT", "5")),
    "max_drawdown_pct": float(os.getenv("MAX_DRAWDOWN_PCT", "20")),
    "auto_restart_on_error": True,
    "error_cooldown_minutes": 5,
}

# ============================================================================
# HELPERS
# ============================================================================

def get_config_summary():
    """Print current configuration summary"""
    print("\n" + "="*80)
    print("QSCI BACKTESTER CONFIGURATION")
    print("="*80)
    print(f"Mode: {'TESTNET' if USE_TESTNET else 'MAINNET'}")
    print(f"Backtest Period: {BACKTEST_START_DATE} to {BACKTEST_END_DATE}")
    print(f"Account Balance: ${POSITION_CONFIG['account_balance']:,.2f}")
    print(f"Risk Per Trade: {POSITION_CONFIG['risk_per_trade']*100}%")
    print(f"Max Concurrent Positions: {POSITION_CONFIG['max_concurrent_positions']}")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"Min QSCI Signal: {ENTRY_CRITERIA['min_qsci_signal']}")
    print("="*80 + "\n")

if __name__ == "__main__":
    get_config_summary()
