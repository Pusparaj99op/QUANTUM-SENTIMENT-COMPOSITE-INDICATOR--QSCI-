# Changelog

All notable changes to the QSCI (Quantum-Sentiment Composite Indicator) Trading System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Webhook support for Telegram (lower latency than polling)
- Advanced position sizing using full Kelly Criterion
- Real-time IV surface calibration
- Multi-asset support (ETH, SOL options)

---

## [3.0.0] - 2025-12-11

### 🚀 Highlights
This is a major release introducing **Black-Scholes Greeks modeling**, **Monte Carlo simulation**, **multi-timeframe blending**, and **interactive Telegram commands**. The backtester is now production-ready with realistic transaction costs and auto-rolling positions.

---

### 🔧 Core Backtester (`qsci_backtester_v3.py`)

#### Added
- **Black-Scholes Options Pricing**: Full implementation with analytical Greeks calculation
  - Delta (Δ): Directional exposure tracking
  - Gamma (Γ): Convexity risk monitoring
  - Vega (ν): Volatility sensitivity analysis
  - Theta (Θ): Time decay impact measurement
- **Transaction Costs Model**: Realistic Binance fee structure
  - Maker/Taker fee differentiation (0.02%/0.04% for options)
  - Dynamic slippage based on ATR volatility
  - Spread impact modeling with liquidity adjustment
- **Auto-Rolling Positions**: Automatic roll-forward before expiration
  - Configurable DTE threshold (default: 7 days)
  - Roll cost calculation including entry/exit fees
  - Mandatory close at critical DTE (default: 3 days)
- **Monte Carlo Simulation**: Robustness testing with 1000+ simulations
  - Block bootstrap preserving autocorrelation
  - Return distribution analysis (5th-95th percentile)
  - Scenario analysis (Bull/Bear/High Vol/Low Vol)
  - Probability of profit and beating benchmark
- **Max Drawdown Tracking**: Real-time portfolio risk monitoring
  - Peak equity tracking
  - Drawdown duration measurement
  - Equity curve persistence to CSV
- **Vectorized Calculations**: Performance optimization
  - All 15+ indicators calculated in single pass
  - Numpy/TA-Lib vectorized operations
  - ~10x speed improvement over iterative calculation
- **NLP Sentiment Integration**: VADER & TextBlob support
  - Price momentum-based sentiment fallback
  - External sentiment file ingestion (JSON)
  - Configurable NLP/price sentiment weighting
- **Directional Trading**: Both CALL and PUT options
  - Positive QSCI → CALL (bullish)
  - Negative QSCI → PUT (bearish)
- **Out-of-Sample Validation**: Train/Validation/Test split
  - Configurable split ratios (60/20/20 default)
  - Per-regime performance tracking

#### Changed
- Position sizing now scales with signal conviction (0.7x-1.4x multiplier)
- Delta efficiency targeting 0.40-0.50 for optimal leverage
- Drawdown penalty reduces position size during losses
- Trailing stop dynamically tightens for larger winners

#### Fixed
- Division by zero in spread calculation when ATR is zero
- NaN propagation in multi-timeframe blending
- Timezone handling for historical data

#### Breaking Changes
- `Position` dataclass now requires `option_type` parameter
- `simulate_trade()` signature changed to include directional parameters
- Config parameter names changed (see migration guide below)

---

### 📊 Configuration (`config.py`)

#### Added
- **Multi-Timeframe Configuration**: 7 timeframes with weights
  ```python
  TIMEFRAMES = ["4h", "2h", "1h", "30m", "15m", "5m", "1m"]
  timeframe_weights = {"4h": 0.25, "2h": 0.20, "1h": 0.15, ...}
  ```
- **Extended Indicator Parameters**: 15+ configurable indicators
  - Momentum: RSI, StochRSI, Williams %R, MFI, CCI, ROC, Ultimate Oscillator
  - Trend: MACD, ADX, EMA, Aroon, Parabolic SAR, Ichimoku
  - Volatility: ATR, Bollinger Bands, Keltner Channels
  - Volume: OBV, CMF, AD Oscillator, VWAP
- **Kelly Criterion Support**: Optional dynamic position sizing
  ```python
  "use_kelly_criterion": False,
  "kelly_fraction": 0.15  # Fractional Kelly for safety
  ```
- **DTE Multipliers**: Risk adjustment based on time to expiration
- **Multi-Tiered Exits**: TP1/TP2/TP3 with trailing activation
- **MongoDB Configuration**: Connection and TTL settings
- **Telegram Configuration**: Notification preferences
- **News API Configuration**: CryptoPanic integration settings

#### Changed
- `min_qsci_signal` lowered to 0.05 for more aggressive trading
- `min_adx` lowered to 10 for maximum trade opportunities
- Entry criteria now support PUT options with negative signals

---

### 🤖 Telegram Notifier (`telegram_notifier.py`)

#### Added
- **Interactive Commands**: Real-time bot control
  - `/status` - Current trading status and uptime
  - `/balance` - Detailed balance and P&L breakdown
  - `/trades` - Recent trade history (last 5)
  - `/positions` - Open positions with live P&L
  - `/stop` - Pause trading (no new entries)
  - `/start` - Resume trading
  - `/setbalance <amt>` - Manual balance adjustment
  - `/help` - Command reference
- **Background Command Polling**: Threaded message listener
  - Configurable polling interval (default: 5s)
  - Graceful error handling with retry
- **Rate Limiting**: Prevent API spam
  - Minimum message interval (1 second)
  - Message queue for burst handling
- **Rich HTML Notifications**: Structured trade alerts
  - Entry/exit with full details
  - Support/Resistance levels
  - Sentiment score display
  - Greeks summary
- **Test Modes**: Standalone validation
  - `--test` for connection and single message test
  - `--interactive` for 30-second polling test

#### Changed
- Notifications now respect `is_trading_paused` flag
- Daily summary resets counters properly

---

### 🗄 MongoDB Manager (`mongodb_manager.py`)

#### Added
- **MongoDB Atlas Integration**: Full persistence layer
  - `btc_ohlcv` - Price data collection
  - `trades` - Trade history collection
  - `telegram_logs` - Message tracking
  - `system_state` - Bot state persistence
  - `balance_history` - Equity curve tracking
- **TTL Indexes**: Automatic data cleanup
  - OHLCV: 365 days retention
  - Trades: 180 days retention
  - Logs: 180 days retention
- **Connection Pooling**: Reliable connections
  - 5-second connection timeout
  - Retry writes enabled
  - Graceful degradation if unavailable
- **Storage Management**: Stay within free tier
  - Storage stats monitoring
  - Manual cleanup trigger
  - Configurable max storage (480MB default)

#### Changed
- All timestamps stored as UTC

---

### 🧪 Live Trader (`qsci_live_trader.py`)

#### Added
- **Real-Time Paper Trading**: Production-ready execution
  - Binance WebSocket/REST data feed
  - QSCI signal generation on live data
  - Paper trade execution with realistic fills
- **Multi-Timeframe Data Loading**: Robust indicator calculation
  - Extended lookback for indicator stability
  - NaN detection and validation
  - Minimum 200 candles per timeframe
- **Signal Blending**: Weighted multi-TF QSCI
  - Individual timeframe logging
  - Fallback to primary timeframe
- **Health Check Server**: HTTP endpoint for monitoring
  - `GET /health` returns JSON status
  - Balance and position info included
  - Required for Koyeb deployment
- **Graceful Shutdown**: Signal handling
  - SIGTERM/SIGINT handling
  - State persistence on shutdown
  - Telegram shutdown notification

---

### 🏗 Infrastructure

#### Added
- **Docker Support**: Containerized deployment
  - `Dockerfile` for main application
  - `Dockerfile.pinger` for keep-alive service
  - `koyeb.yaml` for Koyeb deployment
- **Environment Variables**: Externalized configuration
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`
  - `MONGODB_URI`
  - `TRADING_MODE`, `INITIAL_BALANCE`
  - `CHECK_INTERVAL_MINUTES`, `LOG_LEVEL`

#### Changed
- Logging now configurable via `LOG_CONFIG`

---

### 📝 Documentation

#### Added
- `DEPENDENCIES.txt` in installation folder
- `env.example` template for environment variables

---

## [2.0.0] - 2025-12-02

### Added
- Initial multi-timeframe support (3 timeframes)
- Basic Telegram notifications (one-way)
- SQLite database for local storage
- Position auto-rolling (basic implementation)

### Changed
- Backtester refactored to v2 architecture
- Config moved to separate file

---

## [1.0.0] - 2025-11-15

### Added
- Initial release
- Single timeframe backtester
- Basic options pricing model
- CSV trade logging
- Simple position management

---

## Migration Guide

### From v2.x to v3.x

1. **Config Changes**:
   ```python
   # Old
   QSCI_CONFIG["signal_threshold"] = 0.25

   # New
   ENTRY_CRITERIA["min_qsci_signal"] = 0.05
   ```

2. **Position Initialization**:
   ```python
   # Old
   Position(id=1, entry_price=100, ...)

   # New
   Position(id=1, entry_price=100, option_type="CALL", ...)
   ```

3. **Environment Variables** (new required):
   ```bash
   export TELEGRAM_BOT_TOKEN="your-token"
   export TELEGRAM_CHANNEL_ID="your-channel-id"
   export MONGODB_URI="mongodb+srv://..."  # Optional
   ```

4. **Database Migration**:
   - SQLite is deprecated; MongoDB Atlas recommended
   - Historical trades can be imported via CSV

---

## Contributors

- QSCI Trading System Team

---

## License

Proprietary - All Rights Reserved
