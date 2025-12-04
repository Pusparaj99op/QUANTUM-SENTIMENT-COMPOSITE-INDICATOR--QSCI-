# QSCI BTC Options Backtester v2.0

## Complete Setup Guide for Ubuntu 22.04 LTS

A professional-grade backtesting system for Bitcoin call options trading using the Quantum-Sentiment Composite Indicator (QSCI) with Binance API integration.

---

## 📋 Project Structure

```
qsci_backtester/
├── qsci_backtester.py          # Main backtesting engine
├── config.py                   # Configuration & API keys
├── DEPENDENCIES.txt            # Required packages
├── README.md                   # This file
├── install_dependencies.sh     # Auto-install script
├── backtest_results.csv        # Results output
├── qsci_backtest.log          # Logging output
└── data_cache/                # Cached OHLCV data
```

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Clone/Download Files

Save all three Python files to a single directory:
- `qsci_backtester.py`
- `config.py`
- `DEPENDENCIES.txt`

### Step 2: Install Dependencies

**Option A: Automatic (Recommended)**

```bash
# Make script executable
chmod +x install_dependencies.sh

# Run installation
./install_dependencies.sh
```

**Option B: Manual Installation**

```bash
# Update system
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev build-essential

# Install TA-Lib system dependencies
sudo apt-get install -y libta-lib0 libta-lib-dev

# Create virtual environment
python3 -m venv qsci_venv
source qsci_venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install pandas numpy scipy
pip install python-binance
pip install TA-Lib
pip install pandas-ta matplotlib python-dotenv
```

### Step 3: Add API Keys

Edit `config.py` and add your Binance Testnet API keys:

```python
# Line ~15-16 in config.py
BINANCE_TESTNET_API_KEY = "your_testnet_api_key_here"
BINANCE_TESTNET_API_SECRET = "your_testnet_api_secret_here"

# Keep USE_TESTNET = True for demo trading (no real money)
USE_TESTNET = True
```

### Step 4: Run Backtest

```bash
# Activate virtual environment (if not already active)
source qsci_venv/bin/activate

# Run backtester
python3 qsci_backtester.py
```

**Expected Output:**
```
2025-12-02 10:47:45,123 - INFO - ✓ Connected to Binance Testnet
2025-12-02 10:47:45,456 - INFO - Loading historical data...
2025-12-02 10:47:50,789 - INFO - Fetched 1000 candles for 4h
2025-12-02 10:47:55,234 - INFO - ✓ Position #1 entered: Price=$1250.00, Qty=100, QSCI=0.750
...
2025-12-02 10:48:15,567 - INFO - BACKTEST SUMMARY
2025-12-02 10:48:15,678 - INFO - Total Trades: 45
2025-12-02 10:48:15,789 - INFO - Win Rate: 66.7%
2025-12-02 10:48:15,890 - INFO - Total P&L: $12,450.00
```

---

## 🔑 Binance API Key Setup

### Get Testnet API Keys (Free, No Real Money)

1. Go to: https://testnet.binance.vision/
2. Click "Generate HMAC_SHA256 Key"
3. Copy **API Key** and **Secret Key**
4. Paste into `config.py`

### Get Mainnet API Keys (Optional, For Live Data)

1. Go to: https://www.binance.com/en/account/api-management
2. Create new API key
3. Label: "QSCI Backtester"
4. Permissions: **Read only** (for demo)
5. Copy keys to `config.py`

⚠️ **SECURITY WARNING:**
- Never commit API keys to Git
- Use environment variables in production
- Keep Secret Key private
- Use IP whitelist on Binance

---

## ⚙️ Configuration Guide

### Backtest Period

Edit `config.py` lines 29-30:

```python
BACKTEST_START_DATE = "2024-09-01"  # Start date
BACKTEST_END_DATE = "2024-12-01"    # End date
```

### QSCI Parameters

Edit lines 47-54 to adjust indicator periods:

```python
QSCI_CONFIG = {
    "rsi_period": 14,          # RSI lookback
    "macd_fast": 12,           # MACD fast EMA
    "macd_slow": 26,           # MACD slow EMA
    "ema_period": 20,          # EMA for trend
    "atr_period": 14,          # ATR for volatility
}
```

### Position Management

Edit lines 85-88:

```python
POSITION_CONFIG = {
    "account_balance": 10000,          # Starting capital ($)
    "risk_per_trade": 0.02,            # 2% risk per trade
    "max_concurrent_positions": 3,     # Max 3 open positions
    "max_position_size_pct": 0.05,     # Max 5% per trade
}
```

### Entry Rules

Edit lines 112-120:

```python
ENTRY_CRITERIA = {
    "min_qsci_signal": 0.20,           # Min QSCI for entry
    "min_dte": 2,                      # Min days to expiration
    "max_dte": 60,                     # Max days to expiration
    "min_delta": 0.20,                 # Min delta (avoid deep OTM)
    "max_delta": 0.95,                 # Max delta (avoid deep ITM)
    "target_moneyness": 1.0,           # ATM (0.97-1.03 acceptable)
}
```

### Exit Rules

Edit lines 136-141:

```python
EXIT_RULES = {
    "tp1_target": 1.5,                 # TP1: 1.5×ATR (50% exit)
    "tp2_target": 2.5,                 # TP2: 2.5×ATR (30% exit)
    "tp3_target": 4.0,                 # TP3: 4.0×ATR (20% exit)
    "sl_multiplier": 2.0,              # SL: 2×ATR
    "roll_dte_threshold": 7,           # Roll at 7 DTE
    "mandatory_close_dte": 3,          # Close at 3 DTE
}
```

---

## 📊 Output Files

### 1. `backtest_results.csv`
Trade-by-trade results:
```csv
id,entry_price,entry_time,exit_price,exit_time,quantity,dte,strike,delta,qsci,pnl,status
1,1250.00,2024-09-01T10:00:00,1350.00,2024-09-08T14:30:00,100,14,100,0.5,0.75,10000.00,CLOSED
2,800.00,2024-09-08T11:00:00,950.00,2024-09-15T15:45:00,50,14,102,0.52,0.68,7500.00,CLOSED
```

### 2. `qsci_backtest.log`
Detailed logging:
```
2025-12-02 10:47:45 - INFO - ✓ Connected to Binance Testnet
2025-12-02 10:47:50 - INFO - Fetched 1000 candles for 4h
2025-12-02 10:47:55 - INFO - ✓ Entry criteria passed: QSCI=0.750, DTE=14, Delta=0.50
```

---

## 🛠️ Troubleshooting

### Issue: "python-binance not installed"

**Solution:**
```bash
pip install python-binance
# Or
pip install python-binance==1.0.17
```

### Issue: "TA-Lib failed to build"

**Solution (Ubuntu):**
```bash
sudo apt-get install libta-lib0 libta-lib-dev
pip install --upgrade TA-Lib
```

**Solution (macOS):**
```bash
brew install ta-lib
pip install TA-Lib
```

### Issue: "Connection refused to Binance"

**Check:**
1. Internet connection
2. API keys are correct
3. Testnet is working: https://testnet.binance.vision/
4. Firewall/VPN not blocking

### Issue: "No data fetched"

**Check:**
1. BACKTEST_START_DATE and BACKTEST_END_DATE are valid
2. Date format is YYYY-MM-DD
3. API rate limit not exceeded (100 requests/minute)

---

## 📈 Understanding QSCI Signals

### QSCI Interpretation

| QSCI Value | Signal | Action |
|-----------|--------|--------|
| > +0.70 | **STRONG BUY** | Full size position (150%) |
| +0.40 to +0.70 | Moderate buy | Standard size (100%) |
| +0.20 to +0.40 | Weak buy | Reduced size (50%) |
| -0.20 to +0.20 | **NEUTRAL** | NO TRADE |
| -0.40 to -0.20 | Weak sell | AVOID |
| < -0.70 | **STRONG SELL** | NO CALL OPTIONS |

### Timeframe Weights

```
4H:  35% (Primary trend)
1H:  25% (Confirmation)
30m: 15% (Intermediate)
15m: 10% (Short-term)
5m:  10% (Entry timing)
1m:   5% (Micro-momentum)
```

---

## 💻 System Requirements

- **OS:** Ubuntu 22.04 LTS (or any Linux/macOS)
- **Python:** 3.8 or higher
- **RAM:** 2GB minimum, 4GB recommended
- **Disk:** 500MB minimum
- **Network:** Internet connection for Binance API

---

## 📝 Example Workflow

```bash
# 1. Clone to local directory
git clone <repo> qsci_backtester
cd qsci_backtester

# 2. Install dependencies (one-time)
chmod +x install_dependencies.sh
./install_dependencies.sh

# 3. Add API keys to config.py
nano config.py
# Edit lines 15-16 with your testnet keys

# 4. Run backtest
source qsci_venv/bin/activate
python3 qsci_backtester.py

# 5. Check results
cat backtest_results.csv
tail -f qsci_backtest.log

# 6. Analyze results
python3 analyze_results.py  # (Optional)
```

---

## 🔄 Backtest Cycle

1. **Load Data** - Fetch OHLCV from Binance Testnet
2. **Calculate Indicators** - RSI, MACD, EMA, ATR
3. **Calculate QSCI** - Multi-timeframe signal
4. **Check Entry** - Compare QSCI to thresholds
5. **Simulate Trade** - Open position if criteria met
6. **Update Greeks** - Recalculate delta, gamma, theta
7. **Monitor Exit** - Check TP/SL levels
8. **Close Position** - Exit and log trade
9. **Generate Report** - Summary statistics

---

## 🚀 Advanced Features

### Enable Sentiment Analysis

Edit `config.py`:
```python
USE_SENTIMENT = True
NEWS_SENTIMENT_CONFIG['use_dummy_sentiment'] = False
```

### Use Live Data Only

```python
USE_MAINNET_FOR_DATA = True  # Fetch from mainnet (more data)
USE_TESTNET = True            # But trade on testnet (demo)
```

### Kelly Criterion Sizing

```python
STRATEGY_PARAMS['use_kelly_criterion'] = True
STRATEGY_PARAMS['kelly_fraction'] = 0.25  # 25% Kelly
```

---

## 📞 Support & Debugging

### Check API Connection

```python
python3 -c "from binance.client import Client; c = Client('KEY', 'SECRET'); print(c.get_account())"
```

### Test Data Fetch

```python
python3 -c "
from config import *
from qsci_backtester import BinanceDataManager
dm = BinanceDataManager(use_testnet=True)
df = dm.fetch_klines('BTCUSDT', '4h', '2024-09-01', '2024-12-01')
print(f'Fetched {len(df)} candles')
"
```

### Enable Debug Logging

Edit `config.py`:
```python
LOG_CONFIG['log_level'] = 'DEBUG'  # Verbose output
```

---

## ⚠️ Important Disclaimers

- **Demo Only:** This runs on Binance Testnet (no real money)
- **Not Financial Advice:** Not a recommendation to trade
- **Backtest Risks:** Past performance ≠ future results
- **Paper Trading:** Test extensively before live trading
- **API Security:** Never share API keys
- **Market Risks:** Cryptocurrency markets are highly volatile

---

## 📚 References

- [Binance Testnet Docs](https://testnet.binance.vision)
- [Binance API Docs](https://binance-docs.github.io/apidocs/)
- [TA-Lib Documentation](https://mrjbq7.github.io/ta-lib/)
- [Python-Binance](https://github.com/sammchardy/python-binance)
- [QSCI Formula Docs](./QSCI_FORMULA.md)

---

## 📄 License

This code is provided for educational purposes.

---

**Version:** 2.0  
**Last Updated:** December 2, 2025  
**Status:** Ready for Production Backtesting

---

## Quick Command Reference

```bash
# Activate environment
source qsci_venv/bin/activate

# Run backtest
python3 qsci_backtester.py

# Check logs
tail -f qsci_backtest.log

# View results
cat backtest_results.csv

# Deactivate environment
deactivate

# Remove virtual environment
rm -rf qsci_venv
```

---

**Ready to backtest? Run: `python3 qsci_backtester.py`** 🚀
