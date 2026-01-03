"""
QSCI Expected Value (EV) Analyzer and Optimizer

This module provides tools to:
1. Calculate current system EV from historical trades
2. Identify EV-positive parameter combinations
3. Optimize parameters for maximum risk-adjusted returns
4. Monte Carlo simulation for robustness testing

Author: QSCI Trading System
Version: 3.1.0
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import json
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class EVMetrics:
    """Expected Value metrics for a trading system"""
    win_rate: float
    avg_win: float  # Average winning trade return
    avg_loss: float  # Average losing trade return (positive number)
    total_trades: int

    # Costs
    avg_entry_cost: float = 0.0
    avg_exit_cost: float = 0.0
    avg_slippage: float = 0.0

    # Calculated
    expectancy: float = 0.0  # EV per trade
    profit_factor: float = 0.0
    payoff_ratio: float = 0.0
    edge: float = 0.0  # Above break-even
    break_even_win_rate: float = 0.0

    # Risk metrics
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Trading frequency
    avg_trades_per_month: float = 0.0

    def __post_init__(self):
        """Calculate derived metrics"""
        total_cost = self.avg_entry_cost + self.avg_exit_cost + self.avg_slippage

        # Payoff ratio = avg win / avg loss
        if self.avg_loss > 0:
            self.payoff_ratio = self.avg_win / self.avg_loss
        else:
            self.payoff_ratio = float('inf')

        # Expectancy = (win_rate * avg_win) - (loss_rate * avg_loss) - costs
        self.expectancy = (
            (self.win_rate * self.avg_win) -
            ((1 - self.win_rate) * self.avg_loss) -
            total_cost
        )

        # Break-even win rate
        if self.avg_win + self.avg_loss > 0:
            self.break_even_win_rate = (self.avg_loss + total_cost) / (self.avg_win + self.avg_loss)
        else:
            self.break_even_win_rate = 0.5

        # Edge above break-even
        self.edge = self.win_rate - self.break_even_win_rate

        # Profit factor = gross profit / gross loss
        gross_profit = self.win_rate * self.avg_win * self.total_trades
        gross_loss = (1 - self.win_rate) * self.avg_loss * self.total_trades
        if gross_loss > 0:
            self.profit_factor = gross_profit / gross_loss
        else:
            self.profit_factor = float('inf')

    @property
    def is_positive_ev(self) -> bool:
        return self.expectancy > 0

    @property
    def ev_per_trade_pct(self) -> float:
        """EV as percentage"""
        return self.expectancy * 100

    def to_dict(self) -> Dict:
        return {
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'total_trades': self.total_trades,
            'expectancy': self.expectancy,
            'profit_factor': self.profit_factor,
            'payoff_ratio': self.payoff_ratio,
            'edge': self.edge,
            'break_even_win_rate': self.break_even_win_rate,
            'is_positive_ev': self.is_positive_ev,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
        }

    def __str__(self) -> str:
        ev_emoji = "✅" if self.is_positive_ev else "❌"
        return f"""
{ev_emoji} Expected Value Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Win Rate:           {self.win_rate*100:.1f}%
Avg Win:            +{self.avg_win*100:.1f}%
Avg Loss:           -{self.avg_loss*100:.1f}%
Payoff Ratio:       {self.payoff_ratio:.2f}

EV per Trade:       {self.expectancy*100:+.2f}%
Profit Factor:      {self.profit_factor:.2f}
Break-even WR:      {self.break_even_win_rate*100:.1f}%
Edge:               {self.edge*100:+.1f}%

Sharpe Ratio:       {self.sharpe_ratio:.2f}
Max Drawdown:       {self.max_drawdown*100:.1f}%
Total Trades:       {self.total_trades}
"""


class EVAnalyzer:
    """
    Analyze Expected Value from trade history
    """

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate  # Annual risk-free rate

    def calculate_from_trades(
        self,
        trades: List[Dict],
        initial_balance: float = 10000
    ) -> EVMetrics:
        """
        Calculate EV metrics from a list of trade dictionaries.

        Each trade should have:
        - 'pnl' or 'pnl_after_fees': P&L in dollars
        - 'entry_value': Entry position value
        - 'fees': Total fees (optional)
        - 'slippage': Slippage cost (optional)
        """
        if not trades:
            return EVMetrics(
                win_rate=0.5,
                avg_win=0,
                avg_loss=0,
                total_trades=0,
            )

        # Extract P&L values
        pnls = []
        returns = []
        fees_list = []

        for t in trades:
            pnl = t.get('pnl_after_fees', t.get('pnl', 0))
            entry_value = t.get('entry_value', t.get('position_size', 1))

            if entry_value > 0:
                ret = pnl / entry_value
            else:
                ret = 0

            pnls.append(pnl)
            returns.append(ret)
            fees_list.append(t.get('fees', 0))

        # Classify wins and losses
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]

        win_rate = len(wins) / len(returns) if returns else 0.5
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0

        # Calculate costs
        avg_fees = np.mean(fees_list) if fees_list else 0
        avg_entry_value = np.mean([t.get('entry_value', 0) for t in trades])
        avg_cost_pct = avg_fees / avg_entry_value if avg_entry_value > 0 else 0

        # Calculate equity curve for risk metrics
        equity = [initial_balance]
        for pnl in pnls:
            equity.append(equity[-1] + pnl)
        equity = np.array(equity)

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_drawdown = np.max(drawdown)

        # Calculate returns for Sharpe/Sortino
        daily_returns = np.diff(equity) / equity[:-1]

        # Sharpe ratio (annualized)
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            excess_returns = daily_returns - (self.risk_free_rate / 252)
            sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        else:
            sharpe = 0

        # Sortino ratio (using downside deviation)
        negative_returns = daily_returns[daily_returns < 0]
        if len(negative_returns) > 1:
            downside_std = np.std(negative_returns)
            if downside_std > 0:
                sortino = np.mean(daily_returns - self.risk_free_rate/252) / downside_std * np.sqrt(252)
            else:
                sortino = 0
        else:
            sortino = 0

        # Calmar ratio
        annual_return = np.mean(daily_returns) * 252
        calmar = annual_return / max_drawdown if max_drawdown > 0 else 0

        # Estimate monthly trade frequency
        if trades:
            first_trade_time = trades[0].get('entry_time', trades[0].get('timestamp', datetime.now()))
            last_trade_time = trades[-1].get('exit_time', trades[-1].get('timestamp', datetime.now()))

            if isinstance(first_trade_time, str):
                first_trade_time = datetime.fromisoformat(first_trade_time.replace('Z', '+00:00'))
            if isinstance(last_trade_time, str):
                last_trade_time = datetime.fromisoformat(last_trade_time.replace('Z', '+00:00'))

            if hasattr(first_trade_time, 'timestamp'):
                days = (last_trade_time - first_trade_time).days
            else:
                days = 30  # Default

            months = max(days / 30, 1)
            trades_per_month = len(trades) / months
        else:
            trades_per_month = 0

        return EVMetrics(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_trades=len(trades),
            avg_entry_cost=avg_cost_pct / 2,
            avg_exit_cost=avg_cost_pct / 2,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            avg_trades_per_month=trades_per_month,
        )

    def estimate_ev_from_parameters(
        self,
        win_rate: float = 0.42,
        avg_win_pct: float = 0.80,
        avg_loss_pct: float = 0.50,
        entry_fee_pct: float = 0.0004,
        exit_fee_pct: float = 0.0004,
        slippage_pct: float = 0.0003,
    ) -> EVMetrics:
        """
        Estimate EV from expected parameters
        """
        return EVMetrics(
            win_rate=win_rate,
            avg_win=avg_win_pct,
            avg_loss=avg_loss_pct,
            total_trades=100,  # Placeholder
            avg_entry_cost=entry_fee_pct,
            avg_exit_cost=exit_fee_pct,
            avg_slippage=slippage_pct,
        )

    def find_break_even_parameters(
        self,
        current_metrics: EVMetrics,
    ) -> Dict[str, float]:
        """
        Find parameter values that would bring EV to break-even
        """
        return {
            'min_win_rate_for_positive_ev': current_metrics.break_even_win_rate,
            'current_win_rate': current_metrics.win_rate,
            'win_rate_buffer': current_metrics.edge,
            'required_payoff_ratio_at_current_wr': (
                (1 - current_metrics.win_rate) / current_metrics.win_rate
                if current_metrics.win_rate > 0 else float('inf')
            ),
            'current_payoff_ratio': current_metrics.payoff_ratio,
        }


class EVOptimizer:
    """
    Optimize trading parameters for positive EV
    """

    def __init__(self, analyzer: EVAnalyzer = None):
        self.analyzer = analyzer or EVAnalyzer()
        self.optimization_history: List[Dict] = []

    def optimize_for_positive_ev(
        self,
        current_config: Dict,
        trades: List[Dict] = None,
        target_ev_pct: float = 0.05,  # 5% EV per trade
    ) -> Dict[str, Any]:
        """
        Suggest parameter changes to achieve positive EV

        Returns:
            Dict with recommended changes and expected impact
        """
        # Current EV
        if trades:
            current_ev = self.analyzer.calculate_from_trades(trades)
        else:
            current_ev = self.analyzer.estimate_ev_from_parameters()

        recommendations = []

        # 1. Improve Win Rate: Increase QSCI threshold
        if current_ev.win_rate < 0.45:
            recommendations.append({
                'parameter': 'min_qsci_signal',
                'current': current_config.get('min_qsci_signal', 0.12),
                'recommended': 0.15,
                'reason': 'Higher threshold = stronger signals = higher win rate',
                'expected_impact': '+3-5% win rate',
            })

        # 2. Improve Win Rate: Increase ADX filter
        if current_ev.win_rate < 0.45:
            recommendations.append({
                'parameter': 'min_adx',
                'current': current_config.get('min_adx', 20),
                'recommended': 25,
                'reason': 'Trade only in strong trends',
                'expected_impact': '+2-4% win rate',
            })

        # 3. Reduce losses: Tighter stop loss
        if current_ev.avg_loss > 0.50:
            recommendations.append({
                'parameter': 'sl_multiplier',
                'current': current_config.get('sl_multiplier', 1.2),
                'recommended': 1.0,
                'reason': 'Tighter stops reduce average loss size',
                'expected_impact': '-10% avg loss',
            })

        # 4. Improve win size: Better take profit
        if current_ev.avg_win < 0.70:
            recommendations.append({
                'parameter': 'tp1_target',
                'current': current_config.get('tp1_target', 1.5),
                'recommended': 2.0,
                'reason': 'Let winners run longer',
                'expected_impact': '+10-15% avg win',
            })

        # 5. Reduce costs: Lower trade frequency
        if current_ev.expectancy < target_ev_pct / 100:
            recommendations.append({
                'parameter': 'max_concurrent_positions',
                'current': current_config.get('max_concurrent_positions', 2),
                'recommended': 1,
                'reason': 'Fewer positions = more selective = better quality',
                'expected_impact': 'Higher avg trade quality',
            })

        # 6. IV filter
        if current_config.get('max_iv_rank', 0.6) > 0.5:
            recommendations.append({
                'parameter': 'max_iv_rank',
                'current': current_config.get('max_iv_rank', 0.6),
                'recommended': 0.50,
                'reason': 'Avoid expensive options in high IV environment',
                'expected_impact': 'Lower theta decay cost',
            })

        # 7. Delta selection
        if current_config.get('min_delta', 0.30) < 0.35:
            recommendations.append({
                'parameter': 'min_delta',
                'current': current_config.get('min_delta', 0.30),
                'recommended': 0.40,
                'reason': 'Higher delta = more directional exposure',
                'expected_impact': 'Better alignment with signal',
            })

        # Calculate expected new EV
        improved_wr = current_ev.win_rate + 0.05  # Assume 5% improvement
        improved_avg_win = current_ev.avg_win * 1.10  # 10% better wins
        improved_avg_loss = current_ev.avg_loss * 0.90  # 10% smaller losses

        new_ev = self.analyzer.estimate_ev_from_parameters(
            win_rate=improved_wr,
            avg_win_pct=improved_avg_win,
            avg_loss_pct=improved_avg_loss,
        )

        return {
            'current_ev': current_ev.to_dict(),
            'expected_ev': new_ev.to_dict(),
            'is_currently_positive': current_ev.is_positive_ev,
            'will_be_positive': new_ev.is_positive_ev,
            'recommendations': recommendations,
            'summary': f"""
Current EV: {current_ev.expectancy*100:+.2f}% per trade
Expected EV after optimization: {new_ev.expectancy*100:+.2f}% per trade
Improvement: {(new_ev.expectancy - current_ev.expectancy)*100:+.2f}%

Key Changes:
{chr(10).join(f"• {r['parameter']}: {r['current']} → {r['recommended']} ({r['expected_impact']})" for r in recommendations[:5])}
""".strip(),
        }

    def monte_carlo_simulation(
        self,
        ev_metrics: EVMetrics,
        initial_balance: float = 10000,
        num_trades: int = 100,
        num_simulations: int = 1000,
        risk_per_trade: float = 0.025,
    ) -> Dict[str, Any]:
        """
        Monte Carlo simulation to test robustness
        """
        results = []

        for _ in range(num_simulations):
            balance = initial_balance
            max_balance = balance
            max_dd = 0

            for _ in range(num_trades):
                position_size = balance * risk_per_trade * 10  # Leverage

                # Simulate trade outcome
                if np.random.random() < ev_metrics.win_rate:
                    pnl = position_size * ev_metrics.avg_win
                else:
                    pnl = -position_size * ev_metrics.avg_loss

                # Apply costs
                costs = position_size * (ev_metrics.avg_entry_cost + ev_metrics.avg_exit_cost)
                balance += pnl - costs

                # Track max balance and drawdown
                max_balance = max(max_balance, balance)
                dd = (max_balance - balance) / max_balance if max_balance > 0 else 0
                max_dd = max(max_dd, dd)

            results.append({
                'final_balance': balance,
                'total_return': (balance - initial_balance) / initial_balance,
                'max_drawdown': max_dd,
            })

        # Analyze results
        final_balances = [r['final_balance'] for r in results]
        returns = [r['total_return'] for r in results]
        drawdowns = [r['max_drawdown'] for r in results]

        return {
            'num_simulations': num_simulations,
            'num_trades': num_trades,
            'profit_probability': sum(1 for b in final_balances if b > initial_balance) / num_simulations,
            'avg_final_balance': np.mean(final_balances),
            'median_final_balance': np.median(final_balances),
            'worst_case_balance': np.percentile(final_balances, 5),
            'best_case_balance': np.percentile(final_balances, 95),
            'avg_return': np.mean(returns),
            'avg_max_drawdown': np.mean(drawdowns),
            'worst_drawdown': np.percentile(drawdowns, 95),
            'returns_distribution': {
                'p5': np.percentile(returns, 5),
                'p25': np.percentile(returns, 25),
                'p50': np.percentile(returns, 50),
                'p75': np.percentile(returns, 75),
                'p95': np.percentile(returns, 95),
            },
        }


def apply_positive_ev_config() -> Dict[str, Any]:
    """
    Return a configuration optimized for positive EV
    """
    return {
        # Entry criteria - Stricter for higher win rate
        'min_qsci_signal': 0.15,  # Raised from 0.12
        'min_adx': 25,  # Raised from 20
        'max_iv_rank': 0.50,  # Lowered from 0.60
        'min_delta': 0.40,  # Raised from 0.30
        'max_delta': 0.55,  # Lowered from 0.60

        # Exit rules - Better risk/reward
        'tp1_target': 2.0,  # Raised from 1.5
        'tp2_target': 3.5,  # Raised from 3.0
        'tp3_target': 5.5,  # Raised from 5.0
        'sl_multiplier': 1.0,  # Lowered from 1.2

        # Position sizing - Conservative
        'risk_per_trade': 0.02,  # Lowered from 0.025
        'max_concurrent_positions': 1,  # Lowered from 2
        'max_position_size_pct': 0.04,  # Lowered from 0.05

        # Filters - More selective
        'require_trend_alignment': True,
        'require_volume_confirmation': True,
        'use_sentiment_filter': True,

        # Timeframe weights - Focus on longer TFs
        'weight_4h': 0.25,  # Increased
        'weight_1h': 0.25,  # Increased
        'weight_15m': 0.20,
        'weight_5m': 0.15,
        'weight_1m': 0.10,
    }


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("Testing EV Analyzer and Optimizer...\n")

    # Create analyzer
    analyzer = EVAnalyzer()

    # Estimate EV from current config
    print("1. Current System EV Estimate:")
    ev = analyzer.estimate_ev_from_parameters(
        win_rate=0.42,
        avg_win_pct=0.80,
        avg_loss_pct=0.50,
        entry_fee_pct=0.0004,
        exit_fee_pct=0.0004,
        slippage_pct=0.0003,
    )
    print(ev)

    # Optimize
    print("\n2. Optimization Recommendations:")
    optimizer = EVOptimizer(analyzer)

    current_config = {
        'min_qsci_signal': 0.12,
        'min_adx': 20,
        'sl_multiplier': 1.2,
        'tp1_target': 1.5,
        'max_iv_rank': 0.60,
        'min_delta': 0.30,
        'max_concurrent_positions': 2,
    }

    result = optimizer.optimize_for_positive_ev(current_config)
    print(result['summary'])

    # Monte Carlo
    print("\n3. Monte Carlo Simulation (1000 runs, 100 trades each):")
    mc_result = optimizer.monte_carlo_simulation(
        ev,
        initial_balance=10000,
        num_trades=100,
        num_simulations=1000,
        risk_per_trade=0.025,
    )

    print(f"   Profit Probability: {mc_result['profit_probability']*100:.1f}%")
    print(f"   Average Final Balance: ${mc_result['avg_final_balance']:,.2f}")
    print(f"   Worst Case (5th pctl): ${mc_result['worst_case_balance']:,.2f}")
    print(f"   Best Case (95th pctl): ${mc_result['best_case_balance']:,.2f}")
    print(f"   Average Max Drawdown: {mc_result['avg_max_drawdown']*100:.1f}%")

    # Positive EV config
    print("\n4. Optimized Config for Positive EV:")
    positive_config = apply_positive_ev_config()
    for key, value in list(positive_config.items())[:10]:
        print(f"   {key}: {value}")

    print("\n✅ EV Analysis complete!")
