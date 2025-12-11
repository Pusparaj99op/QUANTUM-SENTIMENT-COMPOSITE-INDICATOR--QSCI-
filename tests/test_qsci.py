"""
QSCI Trading System - Comprehensive Test Suite
Unit and Integration tests for all critical components

Run with: python -m pytest tests/ -v
Or:       python tests/test_qsci.py
"""

import unittest
import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qsci_backtester_v3 import (
    OptionMarketModel,
    Position,
    BinanceFees,
    VectorizedTechnicalAnalysis,
    DrawdownTracker,
    MonteCarloSimulator,
)


# ============================================================================
# TEST: Option Market Model (Black-Scholes & Greeks)
# ============================================================================

class TestOptionMarketModel(unittest.TestCase):
    """Test Black-Scholes pricing and Greeks calculations"""

    def setUp(self):
        self.model = OptionMarketModel()

    def test_call_option_greeks_atm(self):
        """Test ATM Call option Greeks are within expected ranges"""
        spot = 100.0
        strike = 100.0
        dte = 30.0
        iv = 0.50

        greeks = self.model.calculate_greeks(spot, strike, dte, iv, "CALL")

        # ATM Call Delta should be ~0.5
        self.assertAlmostEqual(greeks['delta'], 0.5, delta=0.15)
        # Gamma should be positive
        self.assertGreater(greeks['gamma'], 0)
        # Vega should be positive
        self.assertGreater(greeks['vega'], 0)
        # Theta should be negative (time decay)
        self.assertLess(greeks['theta'], 0)

    def test_put_option_greeks_atm(self):
        """Test ATM Put option Greeks are within expected ranges"""
        spot = 100.0
        strike = 100.0
        dte = 30.0
        iv = 0.50

        greeks = self.model.calculate_greeks(spot, strike, dte, iv, "PUT")

        # ATM Put Delta should be ~-0.5
        self.assertAlmostEqual(greeks['delta'], -0.5, delta=0.15)
        # Gamma is same for call/put
        self.assertGreater(greeks['gamma'], 0)
        # Vega is same for call/put
        self.assertGreater(greeks['vega'], 0)
        # Theta should be negative
        self.assertLess(greeks['theta'], 0)

    def test_itm_call_delta(self):
        """ITM Call should have delta close to 1"""
        spot = 110.0
        strike = 100.0
        dte = 30.0
        iv = 0.30

        greeks = self.model.calculate_greeks(spot, strike, dte, iv, "CALL")
        self.assertGreater(greeks['delta'], 0.7)

    def test_otm_call_delta(self):
        """OTM Call should have delta close to 0"""
        spot = 90.0
        strike = 100.0
        dte = 30.0
        iv = 0.30

        greeks = self.model.calculate_greeks(spot, strike, dte, iv, "CALL")
        self.assertLess(greeks['delta'], 0.3)

    def test_price_option_positive(self):
        """Option price should always be positive"""
        spot = 100.0
        strike = 100.0
        dte = 365.0
        iv = 0.20

        price, delta = self.model.price_option(spot, strike, dte, iv, "CALL")
        self.assertGreater(price, 0)
        self.assertGreater(delta, 0)
        self.assertLess(delta, 1)

    def test_price_option_put_call_parity(self):
        """Test approximate put-call parity"""
        spot = 100.0
        strike = 100.0
        dte = 365.0
        iv = 0.25

        call_price, _ = self.model.price_option(spot, strike, dte, iv, "CALL")
        put_price, _ = self.model.price_option(spot, strike, dte, iv, "PUT")

        # Put-Call Parity: C - P ≈ S - K*e^(-rT)
        r = self.model.risk_free_rate
        T = dte / 365
        discount = np.exp(-r * T)
        expected_diff = spot - strike * discount

        actual_diff = call_price - put_price
        self.assertAlmostEqual(actual_diff, expected_diff, delta=0.5)

    def test_estimate_fair_value_returns_all_fields(self):
        """Test estimate_fair_value returns complete pricing info"""
        spot = 50000.0  # BTC price
        strike = 52000.0
        dte = 14.0
        atr_pct = 0.025

        result = self.model.estimate_fair_value(spot, strike, dte, atr_pct, "CALL")

        required_fields = ['iv', 'mid', 'bid', 'ask', 'spread_pct', 'delta', 'gamma', 'vega', 'theta']
        for field in required_fields:
            self.assertIn(field, result)
            self.assertIsNotNone(result[field])

    def test_annualize_vol_bounds(self):
        """Test IV is bounded between min_iv and max_iv"""
        # Very low ATR should hit min_iv
        iv_low = self.model.annualize_vol(0.0001)
        self.assertGreaterEqual(iv_low, self.model.min_iv)

        # Very high ATR should hit max_iv
        iv_high = self.model.annualize_vol(0.5)
        self.assertLessEqual(iv_high, self.model.max_iv)


# ============================================================================
# TEST: Binance Fees
# ============================================================================

class TestBinanceFees(unittest.TestCase):
    """Test transaction cost calculations"""

    def setUp(self):
        self.fees = BinanceFees()

    def test_options_taker_fee(self):
        """Test options taker fee calculation"""
        trade_value = 1000.0
        spread_pct = 0.01

        fee, slippage = self.fees.calculate_total_cost(
            trade_value, spread_pct, is_maker=False, trade_type='options'
        )

        expected_fee = 1000.0 * 0.0004  # 0.04% taker fee
        self.assertAlmostEqual(fee, expected_fee, places=4)
        self.assertGreater(slippage, 0)

    def test_options_maker_fee(self):
        """Test options maker fee (lower than taker)"""
        trade_value = 1000.0
        spread_pct = 0.01

        fee, slippage = self.fees.calculate_total_cost(
            trade_value, spread_pct, is_maker=True, trade_type='options'
        )

        expected_fee = 1000.0 * 0.0002  # 0.02% maker fee
        self.assertAlmostEqual(fee, expected_fee, places=4)

    def test_spot_fees(self):
        """Test spot trading fees"""
        trade_value = 10000.0
        spread_pct = 0.005

        fee, _ = self.fees.calculate_total_cost(
            trade_value, spread_pct, is_maker=False, trade_type='spot'
        )

        expected_fee = 10000.0 * 0.001  # 0.1% spot taker fee
        self.assertAlmostEqual(fee, expected_fee, places=4)

    def test_slippage_includes_spread(self):
        """Test that slippage accounts for bid-ask spread"""
        trade_value = 1000.0
        wide_spread = 0.02
        narrow_spread = 0.001

        _, slippage_wide = self.fees.calculate_total_cost(trade_value, wide_spread)
        _, slippage_narrow = self.fees.calculate_total_cost(trade_value, narrow_spread)

        self.assertGreater(slippage_wide, slippage_narrow)


# ============================================================================
# TEST: Position Management
# ============================================================================

class TestPosition(unittest.TestCase):
    """Test Position dataclass and methods"""

    def create_position(self, **kwargs):
        """Helper to create test position"""
        defaults = {
            'id': 1,
            'entry_price': 100.0,
            'quantity': 10,
            'dte': 14,
            'strike': 50000.0,
            'delta': 0.45,
            'qsci': 0.35,
            'implied_vol': 0.50,
            'option_type': 'CALL',
        }
        defaults.update(kwargs)
        return Position(**defaults)

    def test_position_initialization(self):
        """Test position is created with correct defaults"""
        pos = self.create_position()

        self.assertEqual(pos.status, "OPEN")
        self.assertEqual(pos.pnl, 0.0)
        self.assertEqual(pos.rolled_count, 0)
        self.assertFalse(pos.tp1_triggered)

    def test_update_price(self):
        """Test price update calculates PnL"""
        pos = self.create_position(entry_price=100.0, quantity=10)

        pos.update_price(120.0)

        self.assertEqual(pos.current_price, 120.0)
        self.assertEqual(pos.pnl, 200.0)  # (120-100) * 10

    def test_peak_unrealized_tracking(self):
        """Test peak unrealized PnL is tracked"""
        pos = self.create_position(entry_price=100.0, quantity=10)

        pos.update_price(150.0)  # Peak
        peak = pos.peak_unrealized

        pos.update_price(130.0)  # Pullback

        self.assertEqual(pos.peak_unrealized, peak)
        self.assertGreater(pos.peak_unrealized, pos.pnl)

    def test_close_position(self):
        """Test position close calculates final PnL"""
        pos = self.create_position(entry_price=100.0, quantity=10)

        pos.close(exit_price=110.0, fees=5.0)

        self.assertEqual(pos.status, "CLOSED")
        self.assertEqual(pos.pnl, 100.0)  # (110-100) * 10
        self.assertEqual(pos.pnl_after_fees, 95.0)
        self.assertEqual(pos.trade_return, 0.095)  # 95/1000

    def test_roll_position(self):
        """Test position rolling"""
        pos = self.create_position()

        pos.roll(
            new_strike=52000.0,
            new_dte=21,
            new_entry_price=120.0,
            new_implied_vol=0.55,
            roll_fee=10.0
        )

        self.assertEqual(pos.rolled_count, 1)
        self.assertEqual(pos.strike, 52000.0)
        self.assertEqual(pos.dte, 21)
        self.assertEqual(pos.entry_price, 120.0)
        self.assertEqual(pos.status, "ROLLED")

    def test_to_dict(self):
        """Test position serialization"""
        pos = self.create_position()
        d = pos.to_dict()

        self.assertIn('id', d)
        self.assertIn('option_type', d)
        self.assertIn('entry_price', d)
        self.assertEqual(d['option_type'], 'CALL')


# ============================================================================
# TEST: Vectorized Technical Analysis
# ============================================================================

class TestVectorizedTechnicalAnalysis(unittest.TestCase):
    """Test indicator calculations"""

    def setUp(self):
        """Create sample OHLCV data"""
        np.random.seed(42)
        n = 500
        dates = pd.date_range(start='2024-01-01', periods=n, freq='1h')

        # Generate random walk for price
        returns = np.random.randn(n) * 0.01
        close = 50000 * np.cumprod(1 + returns)

        self.df = pd.DataFrame({
            'Open Time': dates,
            'Open': close * (1 + np.random.randn(n) * 0.001),
            'High': close * (1 + np.abs(np.random.randn(n)) * 0.005),
            'Low': close * (1 - np.abs(np.random.randn(n)) * 0.005),
            'Close': close,
            'Volume': np.random.uniform(100, 1000, n)
        })

    def test_calculate_all_indicators(self):
        """Test all indicators are calculated"""
        result = VectorizedTechnicalAnalysis.calculate_all_indicators_vectorized(self.df)

        expected_columns = [
            'RSI', 'StochRSI_K', 'StochRSI_D', 'Williams_R', 'MFI', 'CCI',
            'MACD', 'MACD_Signal', 'ADX', 'EMA_20', 'EMA_50',
            'ATR', 'BB_Upper', 'BB_Middle', 'BB_Lower',
            'OBV', 'VWAP', 'CMF'
        ]

        for col in expected_columns:
            self.assertIn(col, result.columns, f"Missing indicator: {col}")

    def test_calculate_signals(self):
        """Test signal generation"""
        df_with_indicators = VectorizedTechnicalAnalysis.calculate_all_indicators_vectorized(self.df)
        result = VectorizedTechnicalAnalysis.calculate_signals_vectorized(df_with_indicators)

        signal_columns = ['Momentum_Signal', 'Trend_Signal', 'Volume_Signal',
                          'Volatility_Signal', 'Pattern_Signal', 'MTC', 'QSCI']

        for col in signal_columns:
            self.assertIn(col, result.columns)

    def test_qsci_bounded(self):
        """Test QSCI is bounded between -1 and 1"""
        df_with_indicators = VectorizedTechnicalAnalysis.calculate_all_indicators_vectorized(self.df)
        result = VectorizedTechnicalAnalysis.calculate_signals_vectorized(df_with_indicators)

        qsci = result['QSCI'].dropna()
        self.assertTrue((qsci >= -1).all())
        self.assertTrue((qsci <= 1).all())

    def test_no_division_by_zero(self):
        """Test no NaN/Inf from division by zero"""
        # Create data with zero volume
        self.df['Volume'] = 0

        result = VectorizedTechnicalAnalysis.calculate_all_indicators_vectorized(self.df)
        result = VectorizedTechnicalAnalysis.calculate_signals_vectorized(result)

        # Should not have inf values
        self.assertFalse(np.isinf(result['QSCI'].dropna()).any())


# ============================================================================
# TEST: Drawdown Tracker
# ============================================================================

class TestDrawdownTracker(unittest.TestCase):
    """Test drawdown tracking functionality"""

    def setUp(self):
        self.tracker = DrawdownTracker()

    def test_initial_state(self):
        """Test tracker starts with zero values"""
        self.assertEqual(self.tracker.peak_equity, 0.0)
        self.assertEqual(self.tracker.max_drawdown, 0.0)
        self.assertEqual(len(self.tracker.equity_curve), 0)

    def test_update_peak(self):
        """Test peak equity tracking"""
        self.tracker.update(10000)
        self.tracker.update(12000)
        self.tracker.update(11000)

        self.assertEqual(self.tracker.peak_equity, 12000)

    def test_drawdown_calculation(self):
        """Test drawdown percentage calculation"""
        self.tracker.update(10000)
        self.tracker.update(8000)  # 20% drawdown

        stats = self.tracker.get_stats()
        self.assertAlmostEqual(stats['max_drawdown_pct'], 20.0, places=1)

    def test_drawdown_recovery(self):
        """Test max drawdown preserved after recovery"""
        self.tracker.update(10000)
        self.tracker.update(8000)  # 20% drawdown
        self.tracker.update(12000)  # New high

        stats = self.tracker.get_stats()
        self.assertAlmostEqual(stats['max_drawdown_pct'], 20.0, places=1)
        self.assertEqual(stats['peak_equity'], 12000)

    def test_equity_curve_recorded(self):
        """Test equity curve is recorded"""
        for i in range(10):
            self.tracker.update(10000 + i * 100)

        self.assertEqual(len(self.tracker.equity_curve), 10)


# ============================================================================
# TEST: Monte Carlo Simulator
# ============================================================================

class TestMonteCarloSimulator(unittest.TestCase):
    """Test Monte Carlo simulation"""

    def setUp(self):
        self.mc = MonteCarloSimulator(n_simulations=100)  # Reduced for faster tests

    def test_insufficient_data(self):
        """Test error handling for insufficient data"""
        result = self.mc.simulate_returns([0.01, 0.02])  # Only 2 trades
        self.assertIn('error', result)

    def test_simulation_returns_all_metrics(self):
        """Test simulation returns all expected metrics"""
        # Generate realistic trade returns
        np.random.seed(42)
        trade_returns = np.random.normal(0.02, 0.10, 50).tolist()

        result = self.mc.simulate_returns(trade_returns)

        expected_metrics = [
            'n_simulations', 'n_trades', 'return_mean', 'return_median',
            'return_5th_pct', 'return_95th_pct', 'max_dd_mean', 'sharpe_mean',
            'prob_profit', 'win_rate_mean'
        ]

        for metric in expected_metrics:
            self.assertIn(metric, result)

    def test_return_percentiles_ordered(self):
        """Test return percentiles are logically ordered"""
        np.random.seed(42)
        trade_returns = np.random.normal(0.01, 0.08, 100).tolist()

        result = self.mc.simulate_returns(trade_returns)

        self.assertLess(result['return_5th_pct'], result['return_median'])
        self.assertLess(result['return_median'], result['return_95th_pct'])

    def test_scenario_analysis(self):
        """Test scenario analysis with different market conditions"""
        np.random.seed(42)
        trade_returns = np.random.normal(0.015, 0.06, 50).tolist()

        scenarios = {
            'Bull': {'mean_adj': 0.02, 'vol_mult': 0.8},
            'Bear': {'mean_adj': -0.03, 'vol_mult': 1.3}
        }

        results = self.mc.scenario_analysis(trade_returns, scenarios)

        self.assertIn('Bull', results)
        self.assertIn('Bear', results)
        # Bull scenario should generally have better returns
        self.assertGreater(
            results['Bull']['return_mean'],
            results['Bear']['return_mean']
        )


# ============================================================================
# TEST: Telegram Notifier (Mock)
# ============================================================================

class TestTelegramNotifier(unittest.TestCase):
    """Test Telegram notification methods (mocked)"""

    def setUp(self):
        # Import here to avoid import errors if module unavailable
        from telegram_notifier import TelegramNotifier, TelegramConfig

        self.config = TelegramConfig(
            bot_token="test_token",
            channel_id="test_channel"
        )
        self.notifier = TelegramNotifier(self.config)

    @patch('requests.post')
    def test_send_message(self, mock_post):
        """Test message sending with mocked API"""
        mock_post.return_value.json.return_value = {
            "ok": True,
            "result": {"message_id": 123}
        }

        msg_id = self.notifier.send_message("Test message")

        self.assertEqual(msg_id, 123)
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_rate_limiting(self, mock_post):
        """Test rate limiting prevents rapid fire messages"""
        mock_post.return_value.json.return_value = {
            "ok": True,
            "result": {"message_id": 1}
        }

        import time
        start = time.time()

        self.notifier.send_message("Message 1")
        self.notifier.send_message("Message 2")

        elapsed = time.time() - start

        # Should have waited at least min_message_interval
        self.assertGreaterEqual(elapsed, self.notifier.min_message_interval * 0.9)

    def test_config_not_configured(self):
        """Test behavior when not configured"""
        from telegram_notifier import TelegramNotifier, TelegramConfig

        empty_config = TelegramConfig(bot_token="", channel_id="")
        notifier = TelegramNotifier(empty_config)

        self.assertFalse(notifier.config.is_configured)
        self.assertIsNone(notifier.send_message("Test"))


# ============================================================================
# TEST: MongoDB Manager (Mock)
# ============================================================================

class TestMongoDBManager(unittest.TestCase):
    """Test MongoDB operations (mocked)"""

    def setUp(self):
        from mongodb_manager import MongoDBManager, MongoDBConfig

        self.config = MongoDBConfig(
            uri="",  # Empty URI = not configured
            database="test_db"
        )
        self.manager = MongoDBManager(self.config)

    def test_not_configured(self):
        """Test manager handles unconfigured state"""
        self.assertFalse(self.manager.is_connected)

    def test_save_state_when_disconnected(self):
        """Test save_state returns False when not connected"""
        result = self.manager.save_state("test_key", {"value": 123})
        self.assertFalse(result)

    def test_get_state_default_when_disconnected(self):
        """Test get_state returns default when not connected"""
        result = self.manager.get_state("test_key", default="default_value")
        self.assertEqual(result, "default_value")

    def test_save_trade_when_disconnected(self):
        """Test save_trade returns None when not connected"""
        trade = {"id": 1, "pnl": 100}
        result = self.manager.save_trade(trade)
        self.assertIsNone(result)


# ============================================================================
# TEST: Config Validation
# ============================================================================

class TestConfigValidation(unittest.TestCase):
    """Test configuration parameters"""

    def setUp(self):
        from config import (
            QSCI_CONFIG, ENTRY_CRITERIA, EXIT_RULES,
            POSITION_CONFIG, TIMEFRAMES
        )
        self.qsci_config = QSCI_CONFIG
        self.entry_criteria = ENTRY_CRITERIA
        self.exit_rules = EXIT_RULES
        self.position_config = POSITION_CONFIG
        self.timeframes = TIMEFRAMES

    def test_timeframe_weights_sum_to_one(self):
        """Test timeframe weights approximately sum to 1"""
        weights = self.qsci_config.get('timeframe_weights', {})
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, delta=0.05)

    def test_signal_weights_sum_to_one(self):
        """Test indicator category weights sum to 1"""
        keys = ['momentum_weight', 'trend_weight', 'volume_weight',
                'volatility_weight', 'pattern_weight']
        total = sum(self.qsci_config.get(k, 0) for k in keys)
        self.assertAlmostEqual(total, 1.0, delta=0.05)

    def test_entry_criteria_valid_ranges(self):
        """Test entry criteria are in valid ranges"""
        self.assertGreaterEqual(self.entry_criteria['min_qsci_signal'], 0)
        self.assertLessEqual(self.entry_criteria['min_qsci_signal'], 1)
        self.assertGreater(self.entry_criteria['min_dte'], 0)
        self.assertGreater(self.entry_criteria['max_dte'], self.entry_criteria['min_dte'])

    def test_exit_rules_logical(self):
        """Test exit rules are logically ordered"""
        self.assertGreater(self.exit_rules['tp2_target'], self.exit_rules['tp1_target'])
        self.assertGreater(self.exit_rules['tp3_target'], self.exit_rules['tp2_target'])

    def test_position_config_valid(self):
        """Test position config parameters are valid"""
        self.assertGreater(self.position_config['account_balance'], 0)
        self.assertGreater(self.position_config['risk_per_trade'], 0)
        self.assertLess(self.position_config['risk_per_trade'], 0.1)  # Max 10% risk
        self.assertGreater(self.position_config['max_concurrent_positions'], 0)


# ============================================================================
# INTEGRATION TEST: Full Signal Generation Pipeline
# ============================================================================

class TestIntegrationSignalPipeline(unittest.TestCase):
    """Integration test for full signal generation"""

    def setUp(self):
        """Create realistic BTC price data"""
        np.random.seed(42)
        n = 1000
        dates = pd.date_range(start='2024-01-01', periods=n, freq='1h')

        # Generate trending price data
        trend = np.linspace(0, 0.3, n)
        noise = np.random.randn(n) * 0.01
        returns = trend/n + noise
        close = 50000 * np.cumprod(1 + returns)

        self.df = pd.DataFrame({
            'Open Time': dates,
            'Open': close * (1 + np.random.randn(n) * 0.001),
            'High': close * (1 + np.abs(np.random.randn(n)) * 0.005),
            'Low': close * (1 - np.abs(np.random.randn(n)) * 0.005),
            'Close': close,
            'Volume': np.random.uniform(500, 2000, n)
        })

    def test_full_pipeline(self):
        """Test full indicator → signal → trade decision pipeline"""
        # Calculate indicators
        df = VectorizedTechnicalAnalysis.calculate_all_indicators_vectorized(self.df)

        # Generate signals
        df = VectorizedTechnicalAnalysis.calculate_signals_vectorized(df)

        # Get latest signal
        latest = df.iloc[-1]
        qsci = latest['QSCI']
        adx = latest['ADX']

        # Verify signal is generated
        self.assertFalse(np.isnan(qsci))
        self.assertFalse(np.isnan(adx))

        # Check if signal meets entry criteria
        from config import ENTRY_CRITERIA

        signal_strength = abs(qsci)
        meets_signal = signal_strength >= ENTRY_CRITERIA['min_qsci_signal']
        meets_adx = adx >= ENTRY_CRITERIA.get('min_adx', 0)

        # Log the decision
        decision = "TRADE" if meets_signal and meets_adx else "NO_TRADE"
        direction = "CALL" if qsci > 0 else "PUT"

        # This test verifies the pipeline works, not specific trade decisions
        self.assertIn(decision, ["TRADE", "NO_TRADE"])
        self.assertIn(direction, ["CALL", "PUT"])


# ============================================================================
# TEST: Position Sizing with Risk Management
# ============================================================================

class TestPositionSizing(unittest.TestCase):
    """Test improved position sizing logic using risk_per_trade"""

    def setUp(self):
        """Mock a backtester with minimal dependencies"""
        from qsci_backtester_v3 import QSCIBacktesterV3
        from config import POSITION_CONFIG
        
        # Create a minimal backtester instance
        self.backtester = QSCIBacktesterV3()
        self.backtester.account_balance = POSITION_CONFIG['account_balance']
        self.backtester.drawdown_tracker = DrawdownTracker()
        self.backtester.drawdown_tracker.peak_equity = self.backtester.account_balance

    def test_position_size_respects_risk_per_trade(self):
        """Position size should respect risk_per_trade limit"""
        from config import POSITION_CONFIG
        
        qsci = 0.5
        delta = 0.45
        option_price = 100.0
        spot_price = 50000.0
        volatility_pct = 0.02
        
        qty = self.backtester.calculate_position_size(
            qsci, delta, option_price, spot_price, volatility_pct
        )
        
        # Total premium paid should not exceed risk_per_trade * account_balance
        total_premium = qty * option_price
        max_allowed = self.backtester.account_balance * POSITION_CONFIG['risk_per_trade'] * 2  # 2x for scaling factors
        
        self.assertGreater(qty, 0, "Quantity should be positive")
        self.assertLessEqual(total_premium, max_allowed, 
                             f"Total premium {total_premium} exceeds max allowed {max_allowed}")

    def test_position_size_respects_max_position_size_pct(self):
        """Position size should not exceed max_position_size_pct"""
        from config import POSITION_CONFIG
        
        qsci = 0.8  # Strong signal
        delta = 0.50
        option_price = 50.0  # Cheap option
        spot_price = 50000.0
        volatility_pct = 0.01  # Low vol
        
        qty = self.backtester.calculate_position_size(
            qsci, delta, option_price, spot_price, volatility_pct
        )
        
        # Total value should not exceed max_position_size_pct
        total_value = qty * option_price
        max_allowed = self.backtester.account_balance * POSITION_CONFIG['max_position_size_pct']
        
        self.assertLessEqual(total_value, max_allowed,
                             f"Total value {total_value} exceeds max allowed {max_allowed}")

    def test_position_size_scales_with_conviction(self):
        """Stronger QSCI signals should result in larger positions"""
        delta = 0.45
        option_price = 100.0
        spot_price = 50000.0
        volatility_pct = 0.02
        
        # Weak signal
        qty_weak = self.backtester.calculate_position_size(
            0.1, delta, option_price, spot_price, volatility_pct
        )
        
        # Strong signal
        qty_strong = self.backtester.calculate_position_size(
            0.7, delta, option_price, spot_price, volatility_pct
        )
        
        self.assertGreater(qty_strong, qty_weak,
                          "Strong signals should have larger position sizes")

    def test_position_size_minimum_one(self):
        """Position size should always be at least 1"""
        qsci = 0.05  # Very weak
        delta = 0.20
        option_price = 5000.0  # Very expensive
        spot_price = 50000.0
        volatility_pct = 0.05
        
        qty = self.backtester.calculate_position_size(
            qsci, delta, option_price, spot_price, volatility_pct
        )
        
        self.assertGreaterEqual(qty, 1, "Quantity should be at least 1")


# ============================================================================
# TEST: IV Rank Filter
# ============================================================================

class TestIVRankFilter(unittest.TestCase):
    """Test IV Rank computation and filtering"""

    def setUp(self):
        """Create mock data with varying volatility"""
        from qsci_backtester_v3 import QSCIBacktesterV3
        
        self.backtester = QSCIBacktesterV3()
        
        # Create data with changing volatility
        np.random.seed(42)
        n = 2000
        dates = pd.date_range(start='2024-01-01', periods=n, freq='1h')
        
        # Simulate varying volatility regime
        close = 50000 + np.cumsum(np.random.randn(n) * 100)
        
        # ATR starts low, increases mid-period, then decreases
        atr_multiplier = np.concatenate([
            np.ones(700) * 0.5,      # Low vol
            np.linspace(0.5, 2.0, 600),  # Rising vol
            np.linspace(2.0, 0.8, 700)   # Declining vol
        ])
        
        atr = close * 0.02 * atr_multiplier
        
        self.df = pd.DataFrame({
            'Open Time': dates,
            'Close': close,
            'ATR': atr,
            'High': close * 1.01,
            'Low': close * 0.99,
            'Volume': np.random.uniform(500, 2000, n)
        })

    def test_iv_rank_computation(self):
        """Test IV rank is computed correctly"""
        iv_rank = self.backtester._compute_iv_rank(self.df, lookback_days=90)
        
        # IV rank should be between 0 and 1
        self.assertGreaterEqual(iv_rank, 0.0, "IV rank should be >= 0")
        self.assertLessEqual(iv_rank, 1.0, "IV rank should be <= 1")

    def test_iv_rank_at_low_volatility(self):
        """Test IV rank is low when volatility is low"""
        # Use first part of data (low vol period)
        low_vol_df = self.df.iloc[:800].copy()
        iv_rank = self.backtester._compute_iv_rank(low_vol_df, lookback_days=30)
        
        # At low vol, IV rank should be relatively low
        self.assertLess(iv_rank, 0.7, "IV rank should be low during low volatility")

    def test_iv_rank_at_high_volatility(self):
        """Test IV rank is high when volatility is high"""
        # Use middle part of data (high vol period)
        high_vol_df = self.df.iloc[700:1400].copy()
        iv_rank = self.backtester._compute_iv_rank(high_vol_df, lookback_days=30)
        
        # At high vol, IV rank should be relatively high
        self.assertGreater(iv_rank, 0.3, "IV rank should be higher during high volatility")

    def test_iv_rank_handles_missing_data(self):
        """Test IV rank handles missing data gracefully"""
        # Create minimal dataframe
        minimal_df = pd.DataFrame({
            'Close': [50000],
            'ATR': [1000]
        })
        
        iv_rank = self.backtester._compute_iv_rank(minimal_df, lookback_days=90)
        
        # Should return neutral value
        self.assertEqual(iv_rank, 0.5, "Should return neutral 0.5 for insufficient data")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Run with verbosity
    unittest.main(verbosity=2)
