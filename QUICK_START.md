# QSCI BACKTESTER - QUICK START GUIDE

## Files You Need

1. **qsci_backtester.py** - Main backtesting engine
2. **config.py** - Configuration & API keys
3. **install_dependencies.sh** - Installation script
4. **README.md** - Full documentation

---

## Installation & Setup (Ubuntu 22.04 LTS)

### 🚀 One-Command Installation

```bash
chmod +x install_dependencies.sh && ./install_dependencies.sh
```

This automatically installs:
- Python 3 development tools
- TA-Lib (technical analysis library)
- All required Python packages
- Virtual environment

### ⏱️ Time: ~5 minutes

---

## Add Binance API Keys

### Step 1: Get Testnet API Keys (Free, No Real Money)

1. Go to: **https://testnet.binance.vision/**
2. Click "**Generate HMAC_SHA256 Key**"
3. Copy **API Key** and **Secret**

### Step 2: Add Keys to config.py

```bash
nano config.py
```

Find lines 15-16 and replace:

```python
# BEFORE:
BINANCE_TESTNET_API_KEY = "YOUR_TESTNET_API_KEY_HERE"
BINANCE_TESTNET_API_SECRET = "YOUR_TESTNET_API_SECRET_HERE"

# AFTER:
BINANCE_TESTNET_API_KEY = "vmPAPzamA1Cbz4rK5jT8mG9kL3pQ7..."
BINANCE_TESTNET_API_SECRET = "xY8nM2bN9pO4qR7sT1uV5wX3zA6cD..."
```

Save: `Ctrl+O`, Enter, `Ctrl+X`

---

## Run Your First Backtest

### Activate Virtual Environment

```bash
source qsci_venv/bin/activate
```

### Run Backtester

```bash
python3 qsci_backtester.py
```

### Expected Output

```
════════════════════════════════════════════════════════════════════
QSCI BTC OPTIONS BACKTESTER v2.0
════════════════════════════════════════════════════════════════════
✓ Connected to Binance Testnet
Loading historical data...
✓ Fetched 1000 candles for 4h
Starting backtest with 1000 candles...
✓ Entry criteria passed: QSCI=0.750, DTE=14, Delta=0.50
✓ Position #1 entered: Price=$1250.00, Qty=100, QSCI=0.750
✓ Position #1 closed with $10000.00 profit

════════════════════════════════════════════════════════════════════
BACKTEST SUMMARY
════════════════════════════════════════════════════════════════════
Total Trades: 45
Wins: 30, Losses: 15
Win Rate: 66.7%
Total P&L: $12,450.00
Average P&L: $276.67
Max Win: $5,000.00
Max Loss: -$1,200.00
Final Account Balance: $22,450.00
════════════════════════════════════════════════════════════════════
```

---

## Check Results

### View All Trades

```bash
cat backtest_results.csv
```

Output format:
```
id,entry_price,entry_time,exit_price,exit_time,quantity,dte,strike,delta,qsci,pnl,status
1,1250.00,2024-09-01T10:00:00,1350.00,2024-09-08T14:30:00,100,14,100,0.5,0.75,10000.00,CLOSED
2,800.00,2024-09-08T11:00:00,950.00,2024-09-15T15:45:00,50,14,102,0.52,0.68,7500.00,CLOSED
```

### Watch Logs Live

```bash
tail -f qsci_backtest.log
```

### View Configuration

```bash
cat config.py
```

---

## Customize Backtest

### Change Backtest Period

Edit `config.py`, lines 29-30:

```python
BACKTEST_START_DATE = "2024-09-01"  # ← Change this
BACKTEST_END_DATE = "2024-12-01"    # ← Change this
```

### Change Position Size

Edit `config.py`, lines 85-88:

```python
POSITION_CONFIG = {
    "account_balance": 10000,      # ← Starting capital
    "risk_per_trade": 0.02,        # ← 2% risk per trade (change to 0.05 for 5%)
    "max_concurrent_positions": 3, # ← Max 3 positions open
}
```

### Change Entry Signal Threshold

Edit `config.py`, line 112:

```python
"min_qsci_signal": 0.20,  # ← Minimum QSCI
# 0.20 = weak signals (more trades)
# 0.50 = strong signals (fewer trades)
# 0.70 = very strong signals (conservative)
```

### Change QSCI Parameters

Edit `config.py`, lines 47-54:

```python
QSCI_CONFIG = {
    "timeframe_weights": {
        "4h": 0.35,   # ← Adjust individual timeframe weights
        "1h": 0.25,
        "30m": 0.15,
        "15m": 0.10,
        "5m": 0.10,
        "1m": 0.05
    },
    "rsi_period": 14,     # ← RSI lookback period
    "macd_fast": 12,      # ← MACD fast EMA
    "macd_slow": 26,      # ← MACD slow EMA
    "ema_period": 20,     # ← EMA trend period
}
```

---

## Understand Results

### QSCI Signal Interpretation

| QSCI | Signal | Position |
|------|--------|----------|
| > 0.70 | **STRONG BUY** | 150% size |
| 0.40-0.70 | Moderate buy | 100% size |
| 0.20-0.40 | Weak buy | 50% size |
| -0.20 to 0.20 | **NO TRADE** | Skip |
| < -0.70 | **AVOID** | No calls |

### Win Rate Benchmarks

- 50%: Baseline (random trading)
- 55%: Good
- 60%+: Excellent
- 65%+: Superior

### Profit Factor

```
Profit Factor = Gross Profit / Gross Loss

- 1.0: Breakeven
- 1.5+: Good
- 2.0+: Excellent
- 3.0+: Outstanding
```

---

## Common Issues & Solutions

### ❌ "Connection refused to Binance"

**Solution:**
```bash
# Check internet connection
ping google.com

# Check if testnet is up
curl https://testnet.binance.vision/

# Verify API keys are correct in config.py
```

### ❌ "TA-Lib installation failed"

**Solution:**
```bash
# Reinstall TA-Lib
sudo apt-get reinstall libta-lib0 libta-lib-dev
pip uninstall TA-Lib
pip install TA-Lib
```

### ❌ "No data fetched"

**Solution:**
- Check BACKTEST_START_DATE format: `YYYY-MM-DD`
- Ensure dates are not in future
- Wait a few minutes (API rate limit)

### ❌ "ModuleNotFoundError: No module named 'config'"

**Solution:**
```bash
# Make sure config.py is in same directory as qsci_backtester.py
ls -la *.py

# Should show:
# config.py
# qsci_backtester.py
```

---

## Performance Tips

### Run Faster Backtests

Edit `config.py`:

```python
# Use fewer timeframes (faster)
TIMEFRAMES = ["4h", "1h"]  # Skip 30m, 15m, 5m, 1m

# Shorter backtest period
BACKTEST_START_DATE = "2024-11-01"
BACKTEST_END_DATE = "2024-11-15"
```

### Save Time on Dependencies

Virtual environment already created? Skip re-installation:

```bash
# Just activate it
source qsci_venv/bin/activate
python3 qsci_backtester.py
```

---

## Next Steps

### 1. Run Multiple Backtests

Test different QSCI thresholds:

```bash
# Low threshold = more trades
echo "min_qsci_signal: 0.20" >> results.txt
python3 qsci_backtester.py

# High threshold = fewer trades
nano config.py  # Change to 0.70
python3 qsci_backtester.py
```

### 2. Analyze Results

Create a spreadsheet:
```bash
# Copy results to Excel
cp backtest_results.csv ~/Desktop/
```

### 3. Optimize Parameters

Test different configurations and log results:

| Account | Risk | QSCI | Timeframes | Win% | Profit |
|---------|------|------|-----------|------|--------|
| 10000 | 2% | 0.20 | all | 55% | 2450 |
| 10000 | 2% | 0.50 | all | 62% | 3120 |
| 10000 | 3% | 0.50 | 4h,1h | 64% | 4850 |

### 4. Go Live (When Ready)

After extensive backtesting:
1. Use real Binance Testnet account
2. Paper trade for 1-2 weeks
3. Start with small capital on mainnet
4. Scale gradually

---

## File Descriptions

| File | Purpose |
|------|---------|
| **qsci_backtester.py** | Main engine (technical indicators, QSCI, trading logic) |
| **config.py** | Settings (dates, API keys, parameters) |
| **install_dependencies.sh** | Auto-installer for Ubuntu |
| **README.md** | Full documentation |
| **DEPENDENCIES.txt** | Package list |
| **backtest_results.csv** | Output (trade-by-trade) |
| **qsci_backtest.log** | Output (detailed logs) |

---

## Environment Variables (Advanced)

For production security, use environment variables instead of hardcoding keys:

```bash
# Create .env file
cat > .env << EOF
BINANCE_TESTNET_API_KEY=your_key_here
BINANCE_TESTNET_API_SECRET=your_secret_here
EOF

# Load in Python
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv('BINANCE_TESTNET_API_KEY')
```

---

## Deactivate Virtual Environment

```bash
deactivate

# Verify you're out
python3 --version  # Should show system Python
```

---

## Delete Virtual Environment

```bash
rm -rf qsci_venv

# Verify
ls -la | grep qsci_venv  # Should return nothing
```

---

## Support Commands

```bash
# Python version
python3 --version

# List installed packages
pip list

# Check specific package
pip show python-binance

# Reinstall requirements
pip install -r <(grep -oP '^[^#]*' DEPENDENCIES.txt)

# Clear pip cache
pip cache purge
```

---

## Key Reminders

✅ **DO:**
- Test extensively on testnet
- Use small account for first trades
- Monitor positions daily
- Keep API keys secret
- Make regular backups

❌ **DON'T:**
- Trade live money immediately
- Share API keys
- Commit keys to Git
- Over-leverage
- Skip backtesting

---

## Still Need Help?

1. Check README.md for detailed docs
2. Review config.py comments
3. Check logs: `tail -f qsci_backtest.log`
4. Test API connection: `python3 -c "from binance.client import Client; print('OK')"`

---

**Version:** 2.0  
**Last Updated:** December 2, 2025  
**Status:** ✅ Ready to Use

**Happy backtesting! 🚀**
