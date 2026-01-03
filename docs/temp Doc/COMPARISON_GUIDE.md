# Before/After Comparison Guide

## How to Compare Performance

### Step 1: Create a Baseline (Original Settings)

1. **Backup current config:**
   ```bash
   cp config.py config_improved.py
   ```

2. **Restore original settings in config.py:**
   ```python
   ENTRY_CRITERIA = {
       "min_qsci_signal": 0.05,  # Original
       "min_adx": 10,             # Original
       # Comment out or set to 1.0 to disable:
       "max_iv_rank": 1.0,        # Disabled
   }
   ```

3. **Run baseline backtest:**
   ```bash
   python3 qsci_backtester_v3.py
   mv backtest_results.csv backtest_baseline.csv
   mv trades.csv trades_baseline.csv
   mv performance.csv performance_baseline.csv
   ```

### Step 2: Run Improved Version

1. **Restore improved config:**
   ```bash
   cp config_improved.py config.py
   ```

2. **Run improved backtest:**
   ```bash
   python3 qsci_backtester_v3.py
   mv backtest_results.csv backtest_improved.csv
   mv trades.csv trades_improved.csv
   mv performance.csv performance_improved.csv
   ```

### Step 3: Analyze Differences

Compare these key metrics:

#### Trade Frequency
- **Baseline**: Expected ~many trades (low threshold)
- **Improved**: Expected ~30-50% fewer trades (higher quality)

#### Risk Metrics
- **Max Drawdown**: Should be lower with improved sizing
- **Win Rate**: Should be higher with stricter filters
- **Sharpe Ratio**: Should increase (better risk-adjusted returns)

#### Profitability
- **Total Return**: May be lower (fewer trades) but more consistent
- **Profit Factor**: Should improve significantly
- **Average Win/Loss Ratio**: Should improve

### Step 4: Quick Python Analysis

```python
import pandas as pd

# Load results
baseline = pd.read_csv('backtest_baseline.csv')
improved = pd.read_csv('backtest_improved.csv')

# Compare key metrics
print("=== COMPARISON ===")
print(f"\nTotal Trades:")
print(f"  Baseline: {len(baseline)}")
print(f"  Improved: {len(improved)}")
print(f"  Change: {(len(improved)/len(baseline)-1)*100:.1f}%")

# Add more comparisons as needed
```

## Expected Improvements

### ✅ What Should Improve
1. **Win Rate**: +5-10 percentage points
2. **Profit Factor**: +15-30%
3. **Sharpe Ratio**: +0.2 to +0.4
4. **Max Drawdown**: -10-20% (smaller)
5. **Average Win**: +10-20% (better entry prices)

### ⚠️ Trade-offs
1. **Trade Frequency**: -30-50% (by design)
2. **Total Return**: May decrease if baseline had many lucky trades
3. **Opportunity Cost**: Might miss some winners due to stricter filters

### 🎯 Success Criteria

The improvements are successful if:
- ✅ Sharpe Ratio increases (better risk-adjusted returns)
- ✅ Max Drawdown decreases (better downside protection)
- ✅ Win Rate increases (higher quality trades)
- ✅ Profit Factor > 1.5 (profitable after all costs)

## Advanced Analysis

### Monte Carlo Comparison

Run Monte Carlo on both:
```python
# In qsci_backtester_v3.py, the Monte Carlo section will show:
# - Probability of positive returns
# - Value at Risk (VaR)
# - Expected Shortfall
```

### Distribution Analysis

Compare trade return distributions:
```python
import matplotlib.pyplot as plt

trades_base = pd.read_csv('trades_baseline.csv')
trades_imp = pd.read_csv('trades_improved.csv')

plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.hist(trades_base['pnl_pct'], bins=50, alpha=0.7, label='Baseline')
plt.xlabel('Return %')
plt.ylabel('Frequency')
plt.legend()
plt.title('Baseline Return Distribution')

plt.subplot(1, 2, 2)
plt.hist(trades_imp['pnl_pct'], bins=50, alpha=0.7, label='Improved', color='green')
plt.xlabel('Return %')
plt.ylabel('Frequency')
plt.legend()
plt.title('Improved Return Distribution')

plt.tight_layout()
plt.savefig('comparison_distributions.png')
```

## Key Metrics to Watch

### 1. Risk-Adjusted Performance
- **Sharpe Ratio**: Return per unit of volatility
- **Sortino Ratio**: Return per unit of downside risk
- **Calmar Ratio**: Return per unit of max drawdown

### 2. Consistency Metrics
- **Win Rate %**: Percentage of profitable trades
- **Profit Factor**: Gross profit / gross loss
- **Max Consecutive Losses**: Longest losing streak

### 3. Risk Metrics
- **Max Drawdown %**: Largest peak-to-trough decline
- **Max Drawdown Duration**: Days in drawdown
- **Value at Risk (95%)**: 95th percentile loss

### 4. Trade Quality
- **Average Win / Average Loss**: Asymmetry ratio
- **Expectancy**: Average profit per trade
- **Reward/Risk Ratio**: Average of all trades

## Validation Checklist

- [ ] Baseline backtest completed
- [ ] Improved backtest completed
- [ ] Trade count comparison done
- [ ] Performance metrics compared
- [ ] Sharpe ratio improved
- [ ] Max drawdown reduced
- [ ] Win rate increased
- [ ] Monte Carlo shows improvement
- [ ] Distribution is tighter/better
- [ ] Documentation updated

## Troubleshooting

### Issue: Too Few Trades
**Solution**: Slightly relax thresholds:
```python
ENTRY_CRITERIA = {
    "min_qsci_signal": 0.10,  # Down from 0.12
    "min_adx": 18,            # Down from 20
    "max_iv_rank": 0.65,      # Up from 0.60
}
```

### Issue: Still High Drawdown
**Solution**: Reduce risk per trade:
```python
POSITION_CONFIG = {
    "risk_per_trade": 0.02,      # Down from 0.025
    "max_position_size_pct": 0.04, # Down from 0.05
}
```

### Issue: Low Profit Factor
**Solution**: Increase selectivity:
```python
ENTRY_CRITERIA = {
    "min_qsci_signal": 0.15,  # Up from 0.12
    "max_iv_rank": 0.5,       # Down from 0.60
}
```

## Next Steps After Validation

1. **If Results are Good:**
   - Deploy to paper trading
   - Monitor live performance
   - Collect additional data

2. **If Results are Mixed:**
   - Run parameter optimization
   - Try walk-forward analysis
   - Adjust risk parameters

3. **If Results are Poor:**
   - Review individual trades
   - Check for data issues
   - Re-examine assumptions

---

**Remember**: Backtesting shows what *could have* happened. Real trading introduces:
- Execution delays
- Partial fills
- Unexpected market events
- Psychological factors

Always validate with paper trading before going live!
