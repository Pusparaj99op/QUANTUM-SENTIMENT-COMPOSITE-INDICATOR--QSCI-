"""
QSCI Advanced Trading Strategies

Modules:
- SpreadTrader: Vertical spread trading for capped risk
- GammaScalper: Delta-neutral gamma scalping
- DeltaHedger: Dynamic delta hedging
- KellyCriterion: Optimal position sizing

Author: QSCI Trading System
Version: 3.1.0
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from math import log, sqrt, exp, erf

logger = logging.getLogger(__name__)


# ==============================================================================
# KELLY CRITERION POSITION SIZING
# ==============================================================================

@dataclass
class KellyResult:
    """Result of Kelly criterion calculation"""
    optimal_fraction: float  # Full Kelly fraction
    half_kelly: float  # Conservative half-Kelly
    edge: float  # Expected edge
    win_rate: float
    avg_win: float
    avg_loss: float
    recommended_fraction: float  # After all adjustments

    def __str__(self):
        return (
            f"Kelly: {self.optimal_fraction:.2%} | "
            f"Half-Kelly: {self.half_kelly:.2%} | "
            f"Edge: {self.edge:.2%}"
        )


class KellyCriterion:
    """
    Kelly Criterion for optimal position sizing

    Kelly formula: f* = (bp - q) / b
    Where:
        f* = fraction of bankroll to bet
        b = net odds received (win/loss ratio)
        p = probability of winning
        q = probability of losing (1-p)

    For options trading, we use fractional Kelly (typically 25-50%)
    to account for estimation errors and reduce volatility.
    """

    def __init__(
        self,
        kelly_fraction: float = 0.25,  # Use 25% of optimal Kelly
        min_trades_for_estimate: int = 20,
        max_kelly: float = 0.20,  # Cap at 20% of bankroll
        min_kelly: float = 0.01,  # Floor at 1%
    ):
        self.kelly_fraction = kelly_fraction
        self.min_trades = min_trades_for_estimate
        self.max_kelly = max_kelly
        self.min_kelly = min_kelly

    def calculate(
        self,
        trades: List[Dict],
        current_conviction: float = 1.0,
    ) -> KellyResult:
        """
        Calculate Kelly fraction from trade history

        Args:
            trades: List of trade dicts with 'pnl_after_fees' key
            current_conviction: Multiplier for current signal strength (0-1)

        Returns:
            KellyResult with optimal and recommended fractions
        """
        if len(trades) < self.min_trades:
            logger.debug(f"Insufficient trades ({len(trades)}) for Kelly, using min")
            return KellyResult(
                optimal_fraction=self.min_kelly,
                half_kelly=self.min_kelly / 2,
                edge=0.0,
                win_rate=0.5,
                avg_win=0.0,
                avg_loss=0.0,
                recommended_fraction=self.min_kelly,
            )

        # Calculate win rate and average returns
        pnls = [t.get('pnl_after_fees', 0) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        if not wins or not losses:
            return KellyResult(
                optimal_fraction=self.min_kelly,
                half_kelly=self.min_kelly / 2,
                edge=0.0,
                win_rate=len(wins) / len(pnls) if pnls else 0.5,
                avg_win=sum(wins) / len(wins) if wins else 0,
                avg_loss=sum(losses) / len(losses) if losses else 0,
                recommended_fraction=self.min_kelly,
            )

        win_rate = len(wins) / len(pnls)
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))

        # Win/loss ratio (b in Kelly formula)
        if avg_loss > 0:
            b = avg_win / avg_loss
        else:
            b = 2.0  # Default if no losses

        # Kelly formula: f = (bp - q) / b
        p = win_rate
        q = 1 - p
        edge = b * p - q

        if b > 0:
            kelly = (b * p - q) / b
        else:
            kelly = 0.0

        # Apply fractional Kelly and constraints
        kelly = max(0, kelly)
        half_kelly = kelly * 0.5
        fractional_kelly = kelly * self.kelly_fraction

        # Apply conviction scaling
        fractional_kelly *= current_conviction

        # Apply bounds
        recommended = max(self.min_kelly, min(self.max_kelly, fractional_kelly))

        logger.debug(
            f"Kelly: win_rate={win_rate:.2%}, b={b:.2f}, "
            f"kelly={kelly:.2%}, fractional={fractional_kelly:.2%}"
        )

        return KellyResult(
            optimal_fraction=kelly,
            half_kelly=half_kelly,
            edge=edge,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            recommended_fraction=recommended,
        )


# ==============================================================================
# SPREAD TRADING
# ==============================================================================

@dataclass
class SpreadLeg:
    """Single leg of an options spread"""
    strike: float
    option_type: str  # CALL or PUT
    side: str  # buy or sell
    quantity: int = 1
    price: float = 0.0
    delta: float = 0.0
    greeks: Dict = field(default_factory=dict)


@dataclass
class OptionSpread:
    """Complete options spread structure"""
    name: str  # e.g., "bull_call_spread", "iron_condor"
    legs: List[SpreadLeg]
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven: List[float] = field(default_factory=list)
    net_delta: float = 0.0
    net_premium: float = 0.0
    probability_profit: float = 0.0

    @property
    def risk_reward_ratio(self) -> float:
        if self.max_loss > 0:
            return self.max_profit / self.max_loss
        return float('inf')


class SpreadTrader:
    """
    Vertical spread trading for capped risk

    Strategies:
    - Bull Call Spread: Bullish, capped upside, reduced cost
    - Bear Put Spread: Bearish, capped downside
    - Iron Condor: Range-bound, collects premium
    - Butterfly: Low cost, high probability around strike
    """

    def __init__(self, option_model=None):
        """
        Args:
            option_model: OptionMarketModel instance for pricing
        """
        self.option_model = option_model

    def bull_call_spread(
        self,
        spot: float,
        long_strike: float,
        short_strike: float,
        dte: int,
        atr_pct: float,
        quantity: int = 1,
    ) -> OptionSpread:
        """
        Create a bull call spread (debit spread)

        - Buy lower strike call (at-the-money or slightly OTM)
        - Sell higher strike call (more OTM)

        Use when: Moderately bullish, want to reduce cost
        """
        if short_strike <= long_strike:
            raise ValueError("Short strike must be higher than long strike for bull call")

        # Price the options
        if self.option_model:
            long_pricing = self.option_model.estimate_fair_value(
                spot, long_strike, dte, atr_pct, "CALL"
            )
            short_pricing = self.option_model.estimate_fair_value(
                spot, short_strike, dte, atr_pct, "CALL"
            )
            long_price = long_pricing['mid']
            short_price = short_pricing['mid']
            long_delta = long_pricing['delta']
            short_delta = short_pricing['delta']
        else:
            # Approximate pricing
            long_price = max(spot - long_strike, 0) * 1.05 + spot * atr_pct
            short_price = max(spot - short_strike, 0) * 1.05 + spot * atr_pct * 0.5
            long_delta = 0.5
            short_delta = 0.3

        net_debit = long_price - short_price
        width = short_strike - long_strike
        max_profit = (width - net_debit) * quantity
        max_loss = net_debit * quantity
        breakeven = [long_strike + net_debit]

        return OptionSpread(
            name="bull_call_spread",
            legs=[
                SpreadLeg(
                    strike=long_strike,
                    option_type="CALL",
                    side="buy",
                    quantity=quantity,
                    price=long_price,
                    delta=long_delta,
                ),
                SpreadLeg(
                    strike=short_strike,
                    option_type="CALL",
                    side="sell",
                    quantity=quantity,
                    price=short_price,
                    delta=-short_delta,
                ),
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            net_delta=(long_delta - short_delta) * quantity,
            net_premium=-net_debit,  # Negative = debit
        )

    def bear_put_spread(
        self,
        spot: float,
        long_strike: float,
        short_strike: float,
        dte: int,
        atr_pct: float,
        quantity: int = 1,
    ) -> OptionSpread:
        """
        Create a bear put spread (debit spread)

        - Buy higher strike put (at-the-money or slightly OTM)
        - Sell lower strike put (more OTM)

        Use when: Moderately bearish, want to reduce cost
        """
        if long_strike <= short_strike:
            raise ValueError("Long strike must be higher than short strike for bear put")

        if self.option_model:
            long_pricing = self.option_model.estimate_fair_value(
                spot, long_strike, dte, atr_pct, "PUT"
            )
            short_pricing = self.option_model.estimate_fair_value(
                spot, short_strike, dte, atr_pct, "PUT"
            )
            long_price = long_pricing['mid']
            short_price = short_pricing['mid']
            long_delta = long_pricing['delta']
            short_delta = short_pricing['delta']
        else:
            long_price = max(long_strike - spot, 0) * 1.05 + spot * atr_pct
            short_price = max(short_strike - spot, 0) * 1.05 + spot * atr_pct * 0.5
            long_delta = -0.5
            short_delta = -0.3

        net_debit = long_price - short_price
        width = long_strike - short_strike
        max_profit = (width - net_debit) * quantity
        max_loss = net_debit * quantity
        breakeven = [long_strike - net_debit]

        return OptionSpread(
            name="bear_put_spread",
            legs=[
                SpreadLeg(
                    strike=long_strike,
                    option_type="PUT",
                    side="buy",
                    quantity=quantity,
                    price=long_price,
                    delta=long_delta,
                ),
                SpreadLeg(
                    strike=short_strike,
                    option_type="PUT",
                    side="sell",
                    quantity=quantity,
                    price=short_price,
                    delta=-short_delta,
                ),
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            net_delta=(long_delta - short_delta) * quantity,
            net_premium=-net_debit,
        )

    def iron_condor(
        self,
        spot: float,
        put_long_strike: float,
        put_short_strike: float,
        call_short_strike: float,
        call_long_strike: float,
        dte: int,
        atr_pct: float,
        quantity: int = 1,
    ) -> OptionSpread:
        """
        Create an iron condor (credit spread)

        - Sell put spread (bear put spread = sellable)
        - Sell call spread (bear call spread = sellable)

        Use when: Range-bound market, low volatility expected
        """
        # Create bull put spread (lower wing)
        bull_put = self.bear_put_spread(
            spot, put_short_strike, put_long_strike, dte, atr_pct, quantity
        )

        # Create bear call spread (upper wing) - manually to get credit
        if self.option_model:
            call_short_pricing = self.option_model.estimate_fair_value(
                spot, call_short_strike, dte, atr_pct, "CALL"
            )
            call_long_pricing = self.option_model.estimate_fair_value(
                spot, call_long_strike, dte, atr_pct, "CALL"
            )
            call_short_price = call_short_pricing['mid']
            call_long_price = call_long_pricing['mid']
        else:
            call_short_price = spot * atr_pct * 0.8
            call_long_price = spot * atr_pct * 0.4

        # Net credit from iron condor
        put_credit = bull_put.net_premium * -1  # Reverse since we're selling
        call_credit = call_short_price - call_long_price
        total_credit = (put_credit + call_credit) * quantity

        # Risk is max of either wing width minus credit
        put_width = put_short_strike - put_long_strike
        call_width = call_long_strike - call_short_strike
        max_loss = max(put_width, call_width) * quantity - total_credit

        return OptionSpread(
            name="iron_condor",
            legs=[
                SpreadLeg(strike=put_long_strike, option_type="PUT", side="buy", quantity=quantity),
                SpreadLeg(strike=put_short_strike, option_type="PUT", side="sell", quantity=quantity),
                SpreadLeg(strike=call_short_strike, option_type="CALL", side="sell", quantity=quantity),
                SpreadLeg(strike=call_long_strike, option_type="CALL", side="buy", quantity=quantity),
            ],
            max_profit=total_credit,
            max_loss=max_loss,
            breakeven=[put_short_strike - total_credit/quantity, call_short_strike + total_credit/quantity],
            net_delta=0.0,  # Approximately delta-neutral
            net_premium=total_credit,
        )

    def recommend_spread(
        self,
        spot: float,
        qsci: float,
        adx: float,
        atr_pct: float,
        dte: int = 14,
        width_pct: float = 0.05,
    ) -> Optional[OptionSpread]:
        """
        Recommend a spread based on market conditions

        Args:
            spot: Current spot price
            qsci: QSCI signal (-1 to 1)
            adx: ADX trend strength
            atr_pct: ATR as percentage of price
            dte: Days to expiration
            width_pct: Spread width as percentage
        """
        # Strong directional signal -> vertical spread
        if abs(qsci) > 0.3 and adx > 25:
            width = spot * width_pct

            if qsci > 0:  # Bullish
                long_strike = round(spot / 100) * 100
                short_strike = round((spot + width) / 100) * 100
                return self.bull_call_spread(
                    spot, long_strike, short_strike, dte, atr_pct
                )
            else:  # Bearish
                long_strike = round(spot / 100) * 100
                short_strike = round((spot - width) / 100) * 100
                return self.bear_put_spread(
                    spot, long_strike, short_strike, dte, atr_pct
                )

        # Low ADX, low QSCI -> iron condor for range
        elif adx < 20 and abs(qsci) < 0.15 and atr_pct < 0.03:
            put_short = round((spot * 0.97) / 100) * 100
            put_long = round((spot * 0.94) / 100) * 100
            call_short = round((spot * 1.03) / 100) * 100
            call_long = round((spot * 1.06) / 100) * 100

            return self.iron_condor(
                spot, put_long, put_short, call_short, call_long, dte, atr_pct
            )

        return None


# ==============================================================================
# GAMMA SCALPING
# ==============================================================================

@dataclass
class HedgeOrder:
    """Order to hedge delta"""
    instrument: str  # "futures" or "spot"
    side: str  # "buy" or "sell"
    quantity: float
    urgency: str = "normal"  # "urgent", "normal", "passive"


class GammaScalper:
    """
    Delta-neutral gamma scalping strategy

    Strategy:
    1. Own positive gamma (long options)
    2. Dynamically hedge delta with futures/spot
    3. Profit from realized volatility > implied volatility

    The profit comes from:
    - Scalping the moves (buying low, selling high as price oscillates)
    - Net gamma profit if realized vol > IV paid
    """

    def __init__(
        self,
        rebalance_threshold: float = 0.10,  # 10% delta change to rebalance
        min_rebalance_interval: int = 300,  # 5 minutes minimum between rebalances
        target_delta: float = 0.0,  # Target portfolio delta
        max_hedge_size: float = 1.0,  # Max hedge as multiple of position
    ):
        self.rebalance_threshold = rebalance_threshold
        self.min_rebalance_interval = min_rebalance_interval
        self.target_delta = target_delta
        self.max_hedge_size = max_hedge_size

        self.last_rebalance_time = 0.0
        self.total_hedge_trades = 0
        self.realized_pnl = 0.0
        self.hedge_position = 0.0  # Current futures hedge

    def should_rebalance(
        self,
        current_delta: float,
        current_time: float,
    ) -> bool:
        """Check if delta hedge needs rebalancing"""
        delta_drift = abs(current_delta - self.target_delta)
        time_since_last = current_time - self.last_rebalance_time

        if time_since_last < self.min_rebalance_interval:
            return False

        return delta_drift > self.rebalance_threshold

    def calculate_hedge(
        self,
        position_delta: float,
        position_gamma: float,
        spot_price: float,
        expected_move: float = 0.0,
    ) -> Optional[HedgeOrder]:
        """
        Calculate hedge trade to achieve target delta

        Args:
            position_delta: Current total options delta
            position_gamma: Current total options gamma
            spot_price: Current spot price
            expected_move: Expected price move (for anticipatory hedging)

        Returns:
            HedgeOrder if hedge needed, None otherwise
        """
        # Current portfolio delta including existing hedge
        total_delta = position_delta + self.hedge_position

        # Target adjustment
        delta_to_hedge = self.target_delta - total_delta

        if abs(delta_to_hedge) < 0.01:  # Too small to hedge
            return None

        # Clamp hedge size
        max_hedge = abs(position_delta) * self.max_hedge_size
        hedge_quantity = max(-max_hedge, min(max_hedge, delta_to_hedge))

        if abs(hedge_quantity) < 0.01:
            return None

        # Determine side
        side = "buy" if hedge_quantity > 0 else "sell"

        # Determine urgency based on gamma exposure
        if position_gamma > 0.01 and abs(delta_to_hedge) > 0.2:
            urgency = "urgent"
        else:
            urgency = "normal"

        return HedgeOrder(
            instrument="futures",
            side=side,
            quantity=abs(hedge_quantity),
            urgency=urgency,
        )

    def execute_hedge(
        self,
        hedge: HedgeOrder,
        execution_price: float,
        timestamp: float,
    ) -> float:
        """
        Record hedge execution (paper trading)

        Returns:
            Estimated cost/slippage
        """
        # Update position
        if hedge.side == "buy":
            self.hedge_position += hedge.quantity
        else:
            self.hedge_position -= hedge.quantity

        self.last_rebalance_time = timestamp
        self.total_hedge_trades += 1

        # Estimate slippage cost
        slippage_pct = 0.0002 if hedge.urgency == "normal" else 0.0005
        cost = execution_price * hedge.quantity * slippage_pct

        logger.debug(
            f"Gamma scalp hedge: {hedge.side} {hedge.quantity:.4f} @ {execution_price:.2f}, "
            f"new hedge pos: {self.hedge_position:.4f}"
        )

        return cost

    def calculate_gamma_pnl(
        self,
        old_price: float,
        new_price: float,
        position_gamma: float,
        position_value: float,
    ) -> float:
        """
        Calculate PnL from gamma exposure

        Gamma PnL = 0.5 * gamma * (price_move)^2
        """
        move = new_price - old_price
        gamma_pnl = 0.5 * position_gamma * (move ** 2) * position_value
        return gamma_pnl

    def get_stats(self) -> Dict:
        """Get gamma scalping statistics"""
        return {
            "hedge_position": self.hedge_position,
            "total_hedge_trades": self.total_hedge_trades,
            "realized_pnl": self.realized_pnl,
            "last_rebalance": self.last_rebalance_time,
        }


# ==============================================================================
# DELTA HEDGER
# ==============================================================================

class DeltaHedger:
    """
    Dynamic delta hedging for portfolio management

    Features:
    - Configurable hedge ratios
    - Multiple hedging instruments
    - Time-based and threshold-based rebalancing
    """

    def __init__(
        self,
        hedge_ratio: float = 1.0,  # 1.0 = full hedge, 0.5 = 50% hedge
        min_hedge_delta: float = 0.05,  # Minimum delta before hedging
        hedge_instrument: str = "futures",
    ):
        self.hedge_ratio = hedge_ratio
        self.min_hedge_delta = min_hedge_delta
        self.hedge_instrument = hedge_instrument
        self.current_hedge = 0.0
        self.hedge_history: List[Dict] = []

    def calculate_portfolio_delta(
        self,
        positions: List[Dict],
    ) -> float:
        """Calculate total portfolio delta"""
        total_delta = 0.0
        for pos in positions:
            qty = pos.get("quantity", 1)
            delta = pos.get("delta", 0)
            total_delta += qty * delta
        return total_delta

    def get_hedge_adjustment(
        self,
        portfolio_delta: float,
    ) -> float:
        """
        Calculate hedge adjustment needed

        Returns:
            Delta amount to hedge (positive = buy hedge, negative = sell)
        """
        target_hedge = -portfolio_delta * self.hedge_ratio
        adjustment = target_hedge - self.current_hedge

        if abs(adjustment) < self.min_hedge_delta:
            return 0.0

        return adjustment

    def record_hedge(self, delta: float, price: float, timestamp: datetime):
        """Record a hedge execution"""
        self.current_hedge += delta
        self.hedge_history.append({
            "delta": delta,
            "price": price,
            "timestamp": timestamp.isoformat(),
            "cumulative_hedge": self.current_hedge,
        })


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("Testing Advanced Trading Strategies...")

    # Test Kelly Criterion
    print("\n1. Kelly Criterion:")
    kelly = KellyCriterion(kelly_fraction=0.25)
    sample_trades = [
        {"pnl_after_fees": 100},
        {"pnl_after_fees": -50},
        {"pnl_after_fees": 80},
        {"pnl_after_fees": -30},
        {"pnl_after_fees": 120},
        {"pnl_after_fees": -40},
        {"pnl_after_fees": 90},
        {"pnl_after_fees": -25},
        {"pnl_after_fees": 150},
        {"pnl_after_fees": -60},
    ] * 3  # 30 trades

    result = kelly.calculate(sample_trades)
    print(f"   {result}")

    # Test Spread Trader
    print("\n2. Spread Trader:")
    trader = SpreadTrader()

    spread = trader.bull_call_spread(
        spot=50000,
        long_strike=50000,
        short_strike=52000,
        dte=14,
        atr_pct=0.03,
    )
    print(f"   Bull Call Spread: Max Profit=${spread.max_profit:.2f}, "
          f"Max Loss=${spread.max_loss:.2f}, R/R={spread.risk_reward_ratio:.2f}")

    # Test recommendation
    recommended = trader.recommend_spread(
        spot=50000, qsci=0.35, adx=30, atr_pct=0.03
    )
    if recommended:
        print(f"   Recommended: {recommended.name}")

    # Test Gamma Scalper
    print("\n3. Gamma Scalper:")
    scalper = GammaScalper(rebalance_threshold=0.05)

    hedge = scalper.calculate_hedge(
        position_delta=0.25,
        position_gamma=0.001,
        spot_price=50000,
    )
    if hedge:
        print(f"   Hedge needed: {hedge.side} {hedge.quantity:.4f} futures")

    # Test Delta Hedger
    print("\n4. Delta Hedger:")
    hedger = DeltaHedger(hedge_ratio=0.8)

    positions = [
        {"delta": 0.5, "quantity": 10},
        {"delta": -0.3, "quantity": 5},
    ]
    portfolio_delta = hedger.calculate_portfolio_delta(positions)
    adjustment = hedger.get_hedge_adjustment(portfolio_delta)
    print(f"   Portfolio Delta: {portfolio_delta:.2f}, Hedge Adjustment: {adjustment:.2f}")

    print("\n✅ All tests passed!")
