"""
QSCI BTC Options Backtester v2.0
Quantum-Sentiment Composite Indicator for Bitcoin Call Options Trading
Multi-Timeframe Analysis with Sentiment Integration
Author: Quantitative Trading System
Date: December 2, 2025

Configuration File for API Keys and Settings
"""

import os
from datetime import datetime

# ============================================================================
# BINANCE TESTNET CONFIGURATION
# ============================================================================

# Binance Testnet API Keys (Demo - No Real Money)
BINANCE_TESTNET_API_KEY = "-------------------------"
BINANCE_TESTNET_API_SECRET = "Thank God I hide this all"

# Binance Mainnet API Keys (Optional - for live data only)
BINANCE_MAINNET_API_KEY = "------------------------------------------------------------"
BINANCE_MAINNET_API_SECRET = "---------------------------------------------------------"

# API Configuration
USE_TESTNET = False  # Set to True for demo, False for live data only
USE_MAINNET_FOR_DATA = True  # Use mainnet for historical data (testnet has limited data)

# ============================================================================
# BACKTEST CONFIGURATION
# ============================================================================

# Date Range
BACKTEST_START_DATE = "2020-12-01"  # Format: YYYY-MM-DD
BACKTEST_END_DATE = "2024-12-01"    # Format: YYYY-MM-DD
SYMBOL = "BTCUSDT"
OPTION_SYMBOL = "BTC"

# Timeframes
TIMEFRAMES = ["4h", "1h", "30m", "15m", "5m", "1m"]  # For QSCI calculation
PRIMARY_TIMEFRAME = "1d"  # Main analysis timeframe

# QSCI Parameters
QSCI_CONFIG = {
    "timeframe_weights": {
        "4h": 0.35,
        "1h": 0.25,
        "30m": 0.15,
        "15m": 0.10,
        "5m": 0.10,
        "1m": 0.05
    },
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "ema_period": 20,
    "atr_period": 14,
}

# News Sentiment Configuration
NEWS_SENTIMENT_CONFIG = {
    "source_weights": {
        "bloomberg": 1.0,
        "reuters": 1.0,
        "coindesk": 0.6,
        "cointelegraph": 0.6,
        "twitter": 0.3,
        "reddit": 0.2
    },
    "decay_lambda": 0.1,  # Exponential decay rate
    "sentiment_range": [-3, 3],  # Min and max sentiment scores
    "use_dummy_sentiment": True  # Set True for backtest without live sentiment API
}

# ============================================================================
# OPTIONS TRADING CONFIGURATION
# ============================================================================

# Position Management
POSITION_CONFIG = {
    "account_balance": 10000,  # Demo account: $10,000
    "risk_per_trade": 0.02,  # 2% risk per trade
    "max_concurrent_positions": 3,  # Max 3 BTC call positions
    "max_position_size_pct": 0.05,  # Max 5% of account per trade
}

# DTE (Days to Expiration) Multipliers
DTE_MULTIPLIERS = {
    "above_14": 1.0,
    "7_to_14": 0.95,
    "3_to_7": 0.80,
    "1_to_3": 0.50,
    "below_1": 0.0  # DO NOT TRADE
}

# Entry Criteria
ENTRY_CRITERIA = {
    "min_qsci_signal": 0.20,  # Minimum QSCI for entry
    "min_liquidity_adjustment": 0.5,
    "min_dte": 2,  # Minimum 2 days to expiration
    "max_dte": 60,  # Maximum 60 days to expiration
    "min_delta": 0.20,  # Minimum delta (avoid deep OTM)
    "max_delta": 0.95,  # Maximum delta (avoid deep ITM)
    "target_moneyness": 1.0,  # 1.0 = ATM (0.97-1.03 acceptable)
    "max_spread_pct": 0.02,  # Max 2% spread
}

# Greeks Configuration
GREEKS_CONFIG = {
    "delta_weight": 0.40,
    "gamma_weight": 0.25,
    "vega_weight": 0.20,
    "theta_weight": 0.15,
    "max_gamma_risk": 0.015,  # Alert if gamma > 0.015
    "max_theta_decay": -0.05,  # Alert if theta < -0.05
}

# Exit Rules
EXIT_RULES = {
    "tp1_target": 1.5,  # TP1 at Entry + (1.5 × ATR) - 50% exit
    "tp2_target": 2.5,  # TP2 at Entry + (2.5 × ATR) - 30% exit
    "tp3_target": 4.0,  # TP3 at Entry + (4.0 × ATR) - 20% exit
    "sl_multiplier": 2.0,  # SL at Entry - (2 × ATR × |QSCI|)
    "roll_dte_threshold": 7,  # Roll when DTE = 7
    "mandatory_close_dte": 3,  # Close if not rolled by DTE = 3
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
    "only_strong_signals": False,  # Only trade QSCI > 0.70 (very conservative)
    "use_sentiment_filter": True,  # Include sentiment in calculations
    "use_multi_timeframe": True,  # Use all timeframes (vs. only primary)
    "dynamic_position_sizing": True,  # Adjust size based on QSCI confidence
    "use_kelly_criterion": False,  # Use Kelly fraction for sizing
    "kelly_fraction": 0.25,  # Use 25% of Kelly (conservative)
}

# ============================================================================
# DATABASE (Optional)
# ============================================================================

DATABASE_CONFIG = {
    "use_database": False,  # Set True to use SQLite for data storage
    "db_file": "qsci_backtest.db",
    "auto_backup": True,
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
