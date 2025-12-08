"""
QSCI Live Trading Bot
Real-time paper trading with Telegram notifications and MongoDB persistence

Author: QSCI Trading System
Version: 1.0.0

This is the main entry point for Koyeb deployment.
"""

import os
import sys
import time
import signal
import logging
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Setup logging first
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Import local modules
from telegram_notifier import TelegramNotifier, TelegramConfig
from mongodb_manager import MongoDBManager, MongoDBConfig

# Try to import trading modules
try:
    from config import POSITION_CONFIG, ENTRY_CRITERIA, QSCI_CONFIG, TIMEFRAMES, PRIMARY_TIMEFRAME
    from qsci_backtester_v3 import (
        BinanceDataManager,
        VectorizedTechnicalAnalysis,
        OptionMarketModel,
        Position,
        BinanceFees
    )
    HAS_TRADING = True
except ImportError as e:
    logger.error(f"Failed to import trading modules: {e}")
    HAS_TRADING = False
    TIMEFRAMES = ["1h"]
    PRIMARY_TIMEFRAME = "1h"


class QSCILiveTrader:
    """
    Live paper trading bot for QSCI strategy

    Features:
    - Real-time Binance data
    - QSCI signal generation
    - Paper trading execution
    - Telegram notifications
    - MongoDB persistence
    """

    def __init__(self):
        # Configuration from environment
        self.trading_mode = os.getenv("TRADING_MODE", "paper")
        self.initial_balance = float(os.getenv("INITIAL_BALANCE", "10000"))
        self.check_interval = int(os.getenv("CHECK_INTERVAL_MINUTES", "5")) * 60

        # Initialize components
        self.telegram = TelegramNotifier()
        self.mongodb = MongoDBManager()

        # Trading state
        self.account_balance = self.initial_balance
        self.positions: List[Position] = []
        self.trades_log: List[Dict] = []
        self.position_counter = 0
        self.total_pnl = 0.0
        self.running = False

        # Daily tracking
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.daily_wins = 0
        self.daily_losses = 0
        self.last_daily_summary = datetime.utcnow().date()

        # Load state from MongoDB if available
        self._load_state()

        # Initialize Binance data manager
        if HAS_TRADING:
            self.data_manager = BinanceDataManager(use_testnet=False)
            self.option_model = OptionMarketModel()
            self.fees = BinanceFees()
            # Multi-timeframe weights from config
            self.multi_tf_weights = QSCI_CONFIG.get('timeframe_weights', {})
        else:
            self.data_manager = None
            self.option_model = None
            self.fees = None
            self.multi_tf_weights = {}

        logger.info("=" * 60)
        logger.info("QSCI Live Trading Bot Initialized")
        logger.info("=" * 60)
        logger.info(f"Mode: {self.trading_mode}")
        logger.info(f"Initial Balance: ${self.initial_balance:,.2f}")
        logger.info(f"Check Interval: {self.check_interval // 60} minutes")
        logger.info(f"Timeframes: {', '.join(TIMEFRAMES)}")
        logger.info("=" * 60)

    def _load_state(self):
        """Load trading state from MongoDB"""
        if not self.mongodb.is_connected:
            return

        # Load account balance
        saved_balance = self.mongodb.get_state("account_balance")
        if saved_balance is not None:
            self.account_balance = float(saved_balance)
            logger.info(f"Loaded saved balance: ${self.account_balance:,.2f}")

        # Load position counter
        saved_counter = self.mongodb.get_state("position_counter")
        if saved_counter is not None:
            self.position_counter = int(saved_counter)

        # Load total P&L
        saved_pnl = self.mongodb.get_state("total_pnl")
        if saved_pnl is not None:
            self.total_pnl = float(saved_pnl)

    def _save_state(self):
        """Save trading state to MongoDB"""
        if not self.mongodb.is_connected:
            return

        self.mongodb.save_state("account_balance", self.account_balance)
        self.mongodb.save_state("position_counter", self.position_counter)
        self.mongodb.save_state("total_pnl", self.total_pnl)
        self.mongodb.save_state("last_update", datetime.utcnow().isoformat())

    def _load_multi_timeframe_data(self) -> Dict[str, any]:
        """
        Load data for ALL timeframes defined in config
        Returns dict of {timeframe: dataframe}
        """
        import pandas as pd
        import numpy as np

        dataframes = {}
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = datetime.utcnow().strftime("%Y-%m-%d")

        for tf in TIMEFRAMES:
            try:
                df = self.data_manager.fetch_klines("BTCUSDT", tf, start_date, end_date)

                if len(df) > 50:
                    # Calculate indicators for this timeframe
                    df = VectorizedTechnicalAnalysis.calculate_all_indicators_vectorized(df)
                    df = VectorizedTechnicalAnalysis.calculate_signals_vectorized(df)
                    dataframes[tf] = df
                    logger.debug(f"Loaded {tf}: {len(df)} candles, QSCI={df['QSCI'].iloc[-1]:.3f}")

            except Exception as e:
                logger.warning(f"Failed to load {tf} data: {e}")

        logger.info(f"📊 Loaded {len(dataframes)}/{len(TIMEFRAMES)} timeframes")
        return dataframes

    def _blend_multi_timeframe_signal(self, dataframes: Dict[str, any]) -> float:
        """
        Blend QSCI signals from all timeframes using weighted average

        Weights from config.py QSCI_CONFIG['timeframe_weights']:
        - 4h: 0.25 (most weight - longer term trend)
        - 2h: 0.20
        - 1h: 0.15
        - 30m: 0.15
        - 15m: 0.10
        - 5m: 0.10
        - 1m: 0.05 (least weight - noise)
        """
        import numpy as np

        total_weight = 0.0
        weighted_signal = 0.0

        for tf, weight in self.multi_tf_weights.items():
            if tf not in dataframes:
                continue

            df = dataframes[tf]
            if 'QSCI' not in df.columns:
                continue

            qsci = df['QSCI'].iloc[-1]
            if not np.isnan(qsci):
                weighted_signal += weight * qsci
                total_weight += weight

        if total_weight > 0:
            blended = weighted_signal / total_weight
            return float(np.clip(blended, -1, 1))

        return 0.0

    def _calculate_support_resistance(self, df) -> Dict[str, float]:
        """Calculate support and resistance levels from price data"""
        if df is None or len(df) < 20:
            return {"support": 0, "resistance": 0}

        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values

        # Simple pivot-based S/R
        recent_high = high[-20:].max()
        recent_low = low[-20:].max()
        recent_close = close[-1]

        pivot = (recent_high + recent_low + recent_close) / 3
        r1 = 2 * pivot - recent_low
        s1 = 2 * pivot - recent_high

        return {
            "support": round(s1, 2),
            "resistance": round(r1, 2),
            "pivot": round(pivot, 2)
        }

    def _check_entry_signal(self, df) -> Optional[Dict]:
        """
        Check if current market conditions meet entry criteria

        Returns:
            Trade setup dict if signal valid, None otherwise
        """
        if df is None or len(df) < 50:
            return None

        # Calculate indicators
        df = VectorizedTechnicalAnalysis.calculate_all_indicators_vectorized(df)
        df = VectorizedTechnicalAnalysis.calculate_signals_vectorized(df)

        # Get latest values
        latest = df.iloc[-1]
        qsci_score = latest.get('QSCI', 0)
        adx = latest.get('ADX', 0)
        close = latest.get('Close', 0)
        atr = latest.get('ATR', 0)

        # Check entry criteria
        min_signal = ENTRY_CRITERIA.get('min_qsci_signal', 0.20)
        min_adx = ENTRY_CRITERIA.get('min_adx', 15)

        if abs(qsci_score) < min_signal:
            logger.debug(f"Signal too weak: {qsci_score:.3f} < {min_signal}")
            return None

        if adx < min_adx:
            logger.debug(f"ADX too low: {adx:.1f} < {min_adx}")
            return None

        # Determine direction
        option_type = "CALL" if qsci_score > 0 else "PUT"

        # Calculate S/R
        sr_levels = self._calculate_support_resistance(df)

        # Calculate strike price (OTM)
        target_moneyness = ENTRY_CRITERIA.get('target_moneyness', 1.03)
        if option_type == "CALL":
            strike = close * target_moneyness
        else:
            strike = close / target_moneyness

        # Get option pricing
        atr_pct = atr / close if close > 0 else 0.02
        option_data = self.option_model.estimate_fair_value(
            close, strike, 14, atr_pct, option_type
        )

        return {
            "timestamp": datetime.utcnow(),
            "option_type": option_type,
            "qsci": qsci_score,
            "adx": adx,
            "close": close,
            "strike": round(strike, 0),
            "entry_price": option_data['ask'],  # Buy at ask
            "delta": option_data['delta'],
            "implied_vol": option_data['iv'],
            "support": sr_levels['support'],
            "resistance": sr_levels['resistance'],
            "sentiment_score": 0.0,  # TODO: Add news sentiment
        }

    def _check_entry_signal_multitf(self, primary_df, blended_qsci: float) -> Optional[Dict]:
        """
        Check entry using BLENDED multi-timeframe QSCI signal

        This is the key difference from single-timeframe:
        - Uses weighted average of all 7 timeframes
        - Reduces false signals from noise in lower timeframes
        - More reliable signals when all timeframes agree

        Args:
            primary_df: Primary timeframe dataframe (for price, ADX, ATR)
            blended_qsci: Pre-calculated blended QSCI from all timeframes
        """
        if primary_df is None or len(primary_df) < 50:
            return None

        # Get latest values from primary timeframe
        latest = primary_df.iloc[-1]
        adx = latest.get('ADX', 0)
        close = latest.get('Close', 0)
        atr = latest.get('ATR', 0)

        # Check entry criteria using BLENDED QSCI
        min_signal = ENTRY_CRITERIA.get('min_qsci_signal', 0.20)
        min_adx = ENTRY_CRITERIA.get('min_adx', 15)

        if abs(blended_qsci) < min_signal:
            logger.debug(f"Multi-TF signal too weak: {blended_qsci:.3f} < {min_signal}")
            return None

        if adx < min_adx:
            logger.debug(f"ADX too low: {adx:.1f} < {min_adx}")
            return None

        # Determine direction based on BLENDED signal
        option_type = "CALL" if blended_qsci > 0 else "PUT"

        # Calculate S/R
        sr_levels = self._calculate_support_resistance(primary_df)

        # Calculate strike price (OTM)
        target_moneyness = ENTRY_CRITERIA.get('target_moneyness', 1.03)
        if option_type == "CALL":
            strike = close * target_moneyness
        else:
            strike = close / target_moneyness

        # Get option pricing
        atr_pct = atr / close if close > 0 else 0.02
        option_data = self.option_model.estimate_fair_value(
            close, strike, 14, atr_pct, option_type
        )

        return {
            "timestamp": datetime.utcnow(),
            "option_type": option_type,
            "qsci": blended_qsci,  # Use blended multi-TF score
            "adx": adx,
            "close": close,
            "strike": round(strike, 0),
            "entry_price": option_data['ask'],
            "delta": option_data['delta'],
            "implied_vol": option_data['iv'],
            "support": sr_levels['support'],
            "resistance": sr_levels['resistance'],
            "sentiment_score": 0.0,
        }

    def _execute_trade(self, signal: Dict) -> Optional[Position]:
        """
        Execute paper trade based on signal

        Returns:
            Position object if executed, None otherwise
        """
        # Check position limits
        max_positions = POSITION_CONFIG.get('max_concurrent_positions', 4)
        open_positions = [p for p in self.positions if p.status == "OPEN"]

        if len(open_positions) >= max_positions:
            logger.info(f"Max positions reached ({max_positions})")
            return None

        # Calculate position size
        risk_per_trade = POSITION_CONFIG.get('risk_per_trade', 0.025)
        max_size_pct = POSITION_CONFIG.get('max_position_size_pct', 0.05)

        max_trade_value = self.account_balance * max_size_pct
        entry_price = signal['entry_price']

        if entry_price <= 0:
            logger.warning("Invalid entry price")
            return None

        quantity = max(1, int(max_trade_value / entry_price))
        trade_value = entry_price * quantity

        # Create position
        self.position_counter += 1
        position = Position(
            id=self.position_counter,
            entry_price=entry_price,
            quantity=quantity,
            dte=14,  # Default 14 DTE
            strike=signal['strike'],
            delta=signal['delta'],
            qsci=signal['qsci'],
            implied_vol=signal['implied_vol'],
            option_type=signal['option_type'],
            entry_time=signal['timestamp'],
        )

        # Calculate fees
        spread_pct = 0.005  # Estimated spread
        fee, slippage = self.fees.calculate_total_cost(trade_value, spread_pct)
        position.total_fees_paid = fee + slippage

        # Add to positions
        self.positions.append(position)

        # Update daily stats
        self.daily_trades += 1

        # Save to MongoDB
        if self.mongodb.is_connected:
            self.mongodb.save_trade(position.to_dict())

        # Send Telegram notification
        trade_data = {
            **position.to_dict(),
            "support": signal['support'],
            "resistance": signal['resistance'],
            "sentiment_score": signal['sentiment_score'],
            "adx": signal['adx'],
        }

        total_trades = len([t for t in self.trades_log if t.get('status') == 'CLOSED']) + 1
        self.telegram.send_trade_opened(trade_data, self.account_balance, total_trades)

        logger.info(f"🟢 OPENED {signal['option_type']} #{self.position_counter}: "
                   f"Strike=${signal['strike']:.0f}, Entry=${entry_price:.2f}, Qty={quantity}")

        return position

    def _update_positions(self, current_price: float, df):
        """Update all open positions and check for exits"""
        if not HAS_TRADING:
            return

        atr = df.iloc[-1].get('ATR', 100) if df is not None and len(df) > 0 else 100
        atr_pct = atr / current_price if current_price > 0 else 0.02

        for position in self.positions:
            if position.status != "OPEN":
                continue

            # Update option price
            option_data = self.option_model.estimate_fair_value(
                current_price,
                position.strike,
                max(position.dte - 1, 1),  # Decay DTE
                atr_pct,
                position.option_type
            )

            new_price = option_data['mid']
            position.update_price(new_price)

            # Check exit conditions
            should_exit, exit_reason = self._check_exit_conditions(position, atr)

            if should_exit:
                self._close_position(position, new_price, exit_reason)

    def _check_exit_conditions(self, position: Position, atr: float) -> tuple:
        """Check if position should be closed"""
        entry = position.entry_price
        current = position.current_price
        pnl_pct = (current - entry) / entry if entry > 0 else 0

        # Take profit levels (based on ATR multiples)
        if pnl_pct >= 0.50:  # 50% profit
            return True, "TP3_HIT"
        if pnl_pct >= 0.30:  # 30% profit
            return True, "TP2_HIT"
        if pnl_pct >= 0.15:  # 15% profit
            return True, "TP1_HIT"

        # Stop loss
        if pnl_pct <= -0.20:  # 20% loss
            return True, "STOP_LOSS"

        # Time-based (DTE too low)
        if position.dte <= 3:
            return True, "DTE_EXIT"

        return False, None

    def _close_position(self, position: Position, exit_price: float, reason: str):
        """Close a position and record the trade"""
        # Calculate fees
        trade_value = exit_price * position.quantity
        spread_pct = 0.005
        fee, slippage = self.fees.calculate_total_cost(trade_value, spread_pct)

        # Close position
        position.close(exit_price, fee + slippage)
        position.status = f"CLOSED_{reason}"

        # Update account
        self.account_balance += position.pnl_after_fees
        self.total_pnl += position.pnl_after_fees

        # Update daily stats
        if position.pnl_after_fees > 0:
            self.daily_wins += 1
        else:
            self.daily_losses += 1
        self.daily_pnl += position.pnl_after_fees

        # Add to trades log
        self.trades_log.append(position.to_dict())

        # Update MongoDB
        if self.mongodb.is_connected:
            self.mongodb.update_trade(position.id, position.to_dict())

        # Save state
        self._save_state()

        # Send Telegram notification
        self.telegram.send_trade_closed(
            position.to_dict(),
            self.account_balance,
            self.total_pnl
        )

        emoji = "✅" if position.pnl_after_fees > 0 else "❌"
        logger.info(f"{emoji} CLOSED #{position.id}: P&L=${position.pnl_after_fees:+.2f} ({reason})")

    def _send_daily_summary(self):
        """Send daily summary to Telegram"""
        today = datetime.utcnow().date()

        if today <= self.last_daily_summary:
            return

        # Prepare stats
        total_trades = len([t for t in self.trades_log if t.get('status', '').startswith('CLOSED')])
        wins = len([t for t in self.trades_log if t.get('pnl_after_fees', 0) > 0])

        stats = {
            "date": str(today),
            "trades_today": self.daily_trades,
            "wins": self.daily_wins,
            "losses": self.daily_losses,
            "daily_pnl": self.daily_pnl,
            "total_trades": total_trades,
            "total_pnl": self.total_pnl,
            "win_rate": (wins / total_trades * 100) if total_trades > 0 else 0,
            "overall_win_rate": (wins / total_trades * 100) if total_trades > 0 else 0,
            "balance": self.account_balance,
            "max_drawdown_pct": 0,  # TODO: Calculate proper drawdown
            "open_positions": len([p for p in self.positions if p.status == "OPEN"]),
        }

        self.telegram.send_daily_summary(stats)

        # Reset daily counters
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.daily_wins = 0
        self.daily_losses = 0
        self.last_daily_summary = today

        logger.info("Daily summary sent to Telegram")

    def run(self):
        """Main trading loop"""
        self.running = True

        # Send startup notification
        self.telegram.send_startup_message(
            self.account_balance,
            self.check_interval // 60
        )

        logger.info("Starting main trading loop...")

        # Track last health ping to prevent Koyeb autoscaling sleep
        last_health_ping = time.time()
        health_ping_interval = 30 * 60  # Ping every 30 minutes

        while self.running:
            try:
                cycle_start = time.time()

                # Ping health endpoint periodically to prevent Koyeb autoscaling sleep
                current_time = time.time()
                if current_time - last_health_ping >= health_ping_interval:
                    try:
                        health_port = int(os.getenv("PORT", "8000"))
                        urllib.request.urlopen(f"http://localhost:{health_port}/health", timeout=5)
                        logger.debug("Health endpoint pinged to prevent autoscaling sleep")
                        last_health_ping = current_time
                    except Exception as e:
                        logger.debug(f"Health ping failed (non-critical): {e}")
                        last_health_ping = current_time  # Reset timer anyway

                # Check for daily summary
                if datetime.utcnow().hour == 0 and datetime.utcnow().minute < 10:
                    self._send_daily_summary()

                if HAS_TRADING and self.data_manager:
                    # Load ALL timeframes for multi-timeframe analysis
                    dataframes = self._load_multi_timeframe_data()

                    # Get primary timeframe for price and position updates
                    primary_df = dataframes.get(PRIMARY_TIMEFRAME)

                    if primary_df is not None and len(primary_df) > 0:
                        current_price = primary_df.iloc[-1]['Close']
                        logger.info(f"BTC Price: ${current_price:,.2f}")

                        # Calculate blended multi-timeframe QSCI
                        blended_qsci = self._blend_multi_timeframe_signal(dataframes)
                        logger.info(f"📊 Multi-TF QSCI: {blended_qsci:.3f} (blend of {len(dataframes)} timeframes)")

                        # Log individual timeframe signals
                        tf_signals = []
                        for tf in TIMEFRAMES:
                            if tf in dataframes and 'QSCI' in dataframes[tf].columns:
                                qsci = dataframes[tf]['QSCI'].iloc[-1]
                                tf_signals.append(f"{tf}={qsci:.2f}")
                        if tf_signals:
                            logger.debug(f"   TF Signals: {', '.join(tf_signals)}")

                        # Save OHLCV to MongoDB (all timeframes)
                        if self.mongodb.is_connected:
                            for tf, df in dataframes.items():
                                self.mongodb.save_ohlcv(
                                    df.tail(5).to_dict('records'),
                                    timeframe=tf
                                )

                        # Update existing positions
                        self._update_positions(current_price, primary_df)

                        # Check for new entry signals using BLENDED multi-TF QSCI
                        signal = self._check_entry_signal_multitf(primary_df, blended_qsci)

                        if signal:
                            logger.info(f"📊 Signal detected: {signal['option_type']} "
                                       f"(Multi-TF QSCI={signal['qsci']:.2f})")
                            self._execute_trade(signal)

                        # Save state periodically
                        self._save_state()
                    else:
                        logger.warning("No data received from Binance")
                else:
                    logger.debug("Trading modules not available - simulation mode")

                # Sleep until next check
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.check_interval - elapsed)

                if sleep_time > 0:
                    logger.debug(f"Sleeping {sleep_time:.0f}s until next check...")
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.running = False
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                self.telegram.send_error_alert("Trading Loop Error", str(e))
                time.sleep(60)  # Wait before retrying

        # Cleanup
        self._shutdown()

    def _shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down...")

        # Save final state
        self._save_state()

        # Send shutdown notification
        self.telegram.send_message(
            "🛑 <b>QSCI Trading Bot Stopped</b>\n"
            f"Final Balance: ${self.account_balance:,.2f}\n"
            f"Total P&L: ${self.total_pnl:+,.2f}",
            parse_mode="HTML"
        )

        # Close connections
        if self.mongodb.is_connected:
            self.mongodb.close()

        logger.info("Shutdown complete")


# ============================================================
# Health Check HTTP Server (for Web Service deployment)
# ============================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks"""

    # Class-level reference to trader for status info
    trader_instance = None

    def log_message(self, format, *args):
        # Suppress default HTTP logging to reduce noise
        pass

    def do_GET(self):
        if self.path in ('/', '/health', '/healthz'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            status = {
                "status": "healthy",
                "service": "QSCI Trading Bot",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }

            # Add trading info if available
            if self.trader_instance:
                status["balance"] = f"${self.trader_instance.account_balance:,.2f}"
                status["running"] = self.trader_instance.running
                status["open_positions"] = len([p for p in self.trader_instance.positions if p.status == "OPEN"])

            self.wfile.write(json.dumps(status).encode())
        else:
            self.send_response(404)
            self.end_headers()


def start_health_server(port: int = 8000, trader=None):
    """Start HTTP health check server in background thread"""
    HealthCheckHandler.trader_instance = trader

    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    logger.info(f"✓ Health check server running on port {port}")
    return server


def main():
    """Entry point for Koyeb deployment"""
    logger.info("=" * 60)
    logger.info("QSCI LIVE TRADING BOT")
    logger.info("=" * 60)

    # Validate configuration
    required_vars = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"]
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        logger.warning(f"Missing environment variables: {missing}")
        logger.warning("Telegram notifications will be disabled")

    # Handle signals for graceful shutdown
    trader = QSCILiveTrader()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        trader.running = False

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start health check server for Web Service deployment
    health_port = int(os.getenv("PORT", "8000"))
    start_health_server(port=health_port, trader=trader)

    # Run the trader
    try:
        trader.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
