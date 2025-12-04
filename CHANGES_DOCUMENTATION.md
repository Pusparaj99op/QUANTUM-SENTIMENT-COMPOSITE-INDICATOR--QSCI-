# QSCI Backtester - Changes Documentation

## Date: December 2, 2025

## Problem Statement
The QSCI backtester was executing zero trades because the QSCI signal values were consistently failing to meet the entry threshold (0.20). All entry attempts showed "Entry criteria FAILED: QSCI Signal".

---

## Root Cause Analysis

### Issue 1: Testnet Had No Historical Data
**File:** `config.py`

**BEFORE:**
```python
USE_TESTNET = True
USE_MAINNET_FOR_DATA = False
```

**Problem:** Binance Testnet doesn't store historical OHLCV data. The API returned 0 candles for all timeframes.

**AFTER:**
```python
USE_TESTNET = False
USE_MAINNET_FOR_DATA = True
```

**Fix:** Use Mainnet API for fetching historical data (works for backtesting without trading).

---

### Issue 2: QSCI Timeframe Signal Formula (Multiplication → Near Zero)
**File:** `qsci_backtester.py` - `QSCICalculator.calculate_timeframe_signal()`

**BEFORE:**
```python
# Formula: TF_i = (RSI-50)/50 × sign(MACD) × tanh((Price-EMA)/ATR)
rsi_component = (latest_rsi - 50) / 50      # Range: [-1, 1]
macd_component = np.sign(latest_macd)        # Range: {-1, 0, 1}
price_component = (latest_price - latest_ema) / latest_atr
tf_signal = rsi_component * macd_component * np.tanh(price_component)
```

**Problem:** Multiplying 3 components that range [-1, 1] results in very small values:
- Example: 0.3 × 1.0 × 0.2 = 0.06 (too small to trigger entry)
- Any single weak component kills the entire signal

**AFTER:**
```python
# Formula: TF_i = 0.4×RSI_norm + 0.3×MACD_norm + 0.3×Trend_norm
# RSI Component (40% weight)
rsi_signal = (latest_rsi - 50) / 50

# MACD Component (30% weight) - normalized by ATR
macd_diff = (latest_macd - latest_macd_signal) / latest_atr
macd_signal_norm = np.tanh(macd_diff * 2)

# Trend Component (30% weight) - EMA crossover + price position
ema_trend = 1.0 if latest_ema_short > latest_ema_long else -1.0
price_trend = np.tanh((latest_price - latest_ema_short) / latest_atr)
trend_signal = 0.5 * ema_trend + 0.5 * price_trend

# ADDITIVE combination preserves signal strength
tf_signal = 0.4 * rsi_signal + 0.3 * macd_signal_norm + 0.3 * trend_signal
```

**Fix:** Changed from multiplicative to additive weighted combination:
- Addition preserves component contributions
- No single component can zero out the signal
- Better trend detection with EMA crossover

---

### Issue 3: Random Sentiment Cancelled Technical Signals
**File:** `qsci_backtester.py` - `QSCICalculator.calculate_sentiment_score()`

**BEFORE:**
```python
def calculate_sentiment_score(self, dummy_mode: bool = True) -> float:
    if dummy_mode:
        return np.random.uniform(-1, 1)  # Completely random!
```

**Problem:** Random sentiment between -1 and +1 often cancelled out positive MTC (technical) signals:
- MTC = +0.4 (bullish technical)
- NS = -0.5 (random bearish sentiment)
- Final QSCI ≈ 0 (no trade)

**AFTER:**
```python
def calculate_sentiment_score(self, mtc: float, df: pd.DataFrame = None) -> float:
    # Calculate price momentum (10-period ROC)
    momentum = (close[-1] - close[-10]) / close[-10]
    
    # Sentiment follows trend direction with some noise
    base_sentiment = np.tanh(momentum * 20)
    
    # Realistic noise (smaller during trends, larger in consolidation)
    noise_scale = 0.1 + 0.2 * (1 - abs(base_sentiment))
    noise = np.random.normal(0, noise_scale)
    
    # Smooth with memory (sentiment doesn't flip instantly)
    self.sentiment_memory = 0.7 * self.sentiment_memory + 0.3 * (base_sentiment + noise)
```

**Fix:** Sentiment now follows price trends (realistic market behavior):
- Uptrending prices → positive sentiment (market optimism)
- Downtrending prices → negative sentiment (fear)
- Memory smoothing prevents whipsaws

---

### Issue 4: QSCI Final Formula Allowed Sentiment Dominance
**File:** `qsci_backtester.py` - `QSCICalculator.calculate_qsci()`

**BEFORE:**
```python
# Dynamic omega ranged from 0.3 to 0.7
omega = 0.5 + 0.3 * np.tanh(mtc) - 0.2 * abs(ns) / 3
qsci = omega * mtc + (1 - omega) * ns * v_adj * theta_weight
```

**Problem:** When NS (sentiment) was strong and random, it could contribute 30-70% of the signal, overwhelming the technical analysis.

**AFTER:**
```python
# Fixed weights: MTC is primary (70%), sentiment secondary (30%)
mtc_weight = 0.70
sentiment_weight = 0.30

sentiment_contribution = ns * v_adj * theta_weight
qsci = mtc_weight * mtc + sentiment_weight * sentiment_contribution

# Boost when MTC and sentiment agree
if mtc * ns > 0:
    agreement_boost = 0.1 * min(abs(mtc), abs(ns))
    qsci += np.sign(mtc) * agreement_boost
```

**Fix:** 
- Technical signals (MTC) are now the primary driver (70%)
- Sentiment only contributes 30% and follows trends
- Agreement bonus when technicals and sentiment align

---

### Issue 5: Backtest Used Dummy Spot Price
**File:** `qsci_backtester.py` - `QSCIBacktester.run_backtest()`

**BEFORE:**
```python
# Used dummy values for all calculations
qsci = self.qsci_calc.calculate_qsci(
    recent_data,
    strike=100,    # Dummy!
    spot=100,      # Dummy!
)
self.simulate_trade(qsci, strike=100, spot=100)
```

**Problem:** Using dummy spot=100 instead of actual BTC prices ($18,000 - $70,000) made calculations unrealistic.

**AFTER:**
```python
# Use actual spot price from data
spot_price = primary_df.iloc[idx]['Close']

qsci = self.qsci_calc.calculate_qsci(
    recent_data,
    strike=spot_price,   # ATM option
    spot=spot_price,
)
self.simulate_trade(qsci, strike=spot_price, spot=spot_price)
```

---

### Issue 6: Entry Checked Too Infrequently
**File:** `qsci_backtester.py` - `QSCIBacktester.run_backtest()`

**BEFORE:**
```python
if idx % 50 == 0:  # Only check every 50 candles
    self.simulate_trade(...)
```

**Problem:** On 4h timeframe, 50 candles = ~8 days between entry checks. Many good signals were missed.

**AFTER:**
```python
if idx % 6 == 0:  # Check every 6 candles (~1 day on 4h)
    self.simulate_trade(...)
```

---

## Results Comparison

| Metric | BEFORE | AFTER |
|--------|--------|-------|
| Data Loaded | 0 candles | 8,767+ candles |
| QSCI Range | N/A | -0.96 to +0.93 |
| Signals >= 0.20 | 0% | 32.5% |
| Total Trades | 0 | 11 |
| Win Rate | N/A | 90.9% |
| Total P&L | $0 | $8,082.23 |
| Total Return | 0% | 80.82% |
| Sharpe Ratio | N/A | 1.30 |

---

## Files Modified

1. **config.py**
   - Changed `USE_TESTNET = False`
   - Changed `USE_MAINNET_FOR_DATA = True`

2. **qsci_backtester.py**
   - `QSCICalculator.calculate_timeframe_signal()` - Additive formula
   - `QSCICalculator.calculate_sentiment_score()` - Trend-aware sentiment
   - `QSCICalculator.calculate_qsci()` - Fixed 70/30 weighting
   - `QSCIBacktester.run_backtest()` - Real spot prices, better entry frequency
   - `QSCIBacktester.simulate_trade()` - Realistic option pricing
   - `QSCIBacktester.print_summary()` - Enhanced metrics

---

## Recommendations for Production

1. **Lower `min_qsci_signal`** to 0.15 for more trades (currently at 0.20)
2. **Add data caching** to avoid 20+ minute API calls on each run
3. **Implement real sentiment API** (currently using trend-based proxy)
4. **Add commission/slippage modeling** for realistic P&L
5. **Consider shorter timeframes** (1h primary) for more trading opportunities
