"""
Python Wrapper for QSCI HFT Core

This module provides a fallback Python implementation when the Rust extension
is not available, and automatically uses the Rust version when compiled.

For building the Rust module:
    cd hft_core
    pip install maturin
    maturin develop --release

Author: QSCI Trading System
Version: 3.1.0
"""

import logging
import numpy as np
from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import Rust extension
try:
    import qsci_hft_core as rust_core
    HAS_RUST_CORE = True
    logger.info("✓ Rust HFT core loaded successfully")
except ImportError:
    HAS_RUST_CORE = False
    logger.warning("Rust HFT core not available, using Python fallback")

# Try to use Numba-optimized Python fallback
try:
    from performance_optimizations import NumbaOptimizedIndicators
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False


@dataclass
class GreeksResult:
    """Greeks calculation result"""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


class HFTCore:
    """
    High-Frequency Trading Core Interface

    Automatically uses Rust implementation if available,
    otherwise falls back to Numba-optimized Python or pure Python.
    """

    def __init__(self):
        self.backend = self._detect_backend()
        logger.info(f"HFT Core using backend: {self.backend}")

        if self.backend == "numba":
            self._numba = NumbaOptimizedIndicators()

    def _detect_backend(self) -> str:
        """Detect the best available backend"""
        if HAS_RUST_CORE:
            return "rust"
        elif HAS_NUMBA:
            return "numba"
        else:
            return "python"

    def rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI"""
        if self.backend == "rust":
            return np.array(rust_core.rust_rsi(prices.tolist(), period))
        elif self.backend == "numba":
            return self._numba.rsi(prices, period)
        else:
            return self._python_rsi(prices, period)

    def ema(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate EMA"""
        if self.backend == "rust":
            return np.array(rust_core.rust_ema(prices.tolist(), period))
        elif self.backend == "numba":
            return self._numba.ema(prices, period)
        else:
            return self._python_ema(prices, period)

    def macd(
        self,
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate MACD"""
        if self.backend == "rust":
            macd, sig, hist = rust_core.rust_macd(prices.tolist(), fast, slow, signal)
            return np.array(macd), np.array(sig), np.array(hist)
        elif self.backend == "numba":
            return self._numba.macd(prices, fast, slow, signal)
        else:
            return self._python_macd(prices, fast, slow, signal)

    def atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """Calculate ATR"""
        if self.backend == "rust":
            return np.array(rust_core.rust_atr(
                high.tolist(), low.tolist(), close.tolist(), period
            ))
        elif self.backend == "numba":
            return self._numba.atr(high, low, close, period)
        else:
            return self._python_atr(high, low, close, period)

    def bollinger_bands(
        self,
        prices: np.ndarray,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate Bollinger Bands"""
        if self.backend == "rust":
            upper, mid, lower = rust_core.rust_bollinger_bands(
                prices.tolist(), period, std_dev
            )
            return np.array(upper), np.array(mid), np.array(lower)
        elif self.backend == "numba":
            return self._numba.bollinger_bands(prices, period, std_dev)
        else:
            return self._python_bollinger_bands(prices, period, std_dev)

    def adx(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate ADX with +DI and -DI"""
        if self.backend == "rust":
            adx_val, plus_di, minus_di = rust_core.rust_adx(
                high.tolist(), low.tolist(), close.tolist(), period
            )
            return np.array(adx_val), np.array(plus_di), np.array(minus_di)
        elif self.backend == "numba":
            return self._numba.adx(high, low, close, period)
        else:
            return self._python_adx(high, low, close, period)

    def calculate_qsci_batch(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: Optional[np.ndarray] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> np.ndarray:
        """Calculate QSCI signals for entire dataset"""
        weights = weights or {
            'momentum': 0.35,
            'trend': 0.30,
            'volatility': 0.15,
            'volume': 0.10,
        }

        if volume is None:
            volume = np.ones_like(close)

        if self.backend == "rust":
            return np.array(rust_core.rust_calculate_qsci_batch(
                high.tolist(),
                low.tolist(),
                close.tolist(),
                volume.tolist(),
                weights['momentum'],
                weights['trend'],
                weights['volatility'],
                weights['volume'],
            ))
        elif self.backend == "numba":
            return self._numba.calculate_qsci_batch(high, low, close, weights)
        else:
            return self._python_qsci_batch(high, low, close, volume, weights)

    def batch_greeks(
        self,
        spots: np.ndarray,
        strikes: np.ndarray,
        dtes: np.ndarray,
        ivs: np.ndarray,
        risk_free_rate: float = 0.05,
        is_calls: Optional[List[bool]] = None
    ) -> List[GreeksResult]:
        """Calculate Greeks for a batch of options"""
        if is_calls is None:
            is_calls = [True] * len(spots)

        if self.backend == "rust":
            results = rust_core.rust_batch_greeks(
                spots.tolist(),
                strikes.tolist(),
                dtes.tolist(),
                ivs.tolist(),
                risk_free_rate,
                is_calls,
            )
            return [
                GreeksResult(
                    delta=r.delta,
                    gamma=r.gamma,
                    vega=r.vega,
                    theta=r.theta,
                    rho=r.rho
                )
                for r in results
            ]
        else:
            return self._python_batch_greeks(
                spots, strikes, dtes, ivs, risk_free_rate, is_calls
            )

    def black_scholes(
        self,
        spot: float,
        strike: float,
        dte: float,
        iv: float,
        risk_free_rate: float = 0.05,
        is_call: bool = True
    ) -> float:
        """Calculate Black-Scholes option price"""
        if self.backend == "rust":
            return rust_core.rust_black_scholes(
                spot, strike, dte, iv, risk_free_rate, is_call
            )
        else:
            return self._python_black_scholes(
                spot, strike, dte, iv, risk_free_rate, is_call
            )

    # ==========================================================================
    # Python Fallback Implementations
    # ==========================================================================

    def _python_rsi(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Pure Python RSI calculation"""
        n = len(prices)
        rsi = np.full(n, np.nan)

        if n < period + 1:
            return rsi

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        if avg_loss == 0:
            rsi[period] = 100
        else:
            rsi[period] = 100 - (100 / (1 + avg_gain / avg_loss))

        for i in range(period + 1, n):
            avg_gain = (avg_gain * (period - 1) + gains[i-1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i-1]) / period
            if avg_loss == 0:
                rsi[i] = 100
            else:
                rsi[i] = 100 - (100 / (1 + avg_gain / avg_loss))

        return rsi

    def _python_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Pure Python EMA calculation"""
        n = len(prices)
        ema = np.full(n, np.nan)

        if n < period:
            return ema

        ema[period-1] = np.mean(prices[:period])
        mult = 2 / (period + 1)

        for i in range(period, n):
            ema[i] = (prices[i] - ema[i-1]) * mult + ema[i-1]

        return ema

    def _python_macd(
        self,
        prices: np.ndarray,
        fast: int,
        slow: int,
        signal: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Pure Python MACD calculation"""
        ema_fast = self._python_ema(prices, fast)
        ema_slow = self._python_ema(prices, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._python_ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def _python_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int
    ) -> np.ndarray:
        """Pure Python ATR calculation"""
        n = len(close)
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]

        for i in range(1, n):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i-1])
            lc = abs(low[i] - close[i-1])
            tr[i] = max(hl, hc, lc)

        atr = np.full(n, np.nan)
        atr[period-1] = np.mean(tr[:period])

        for i in range(period, n):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period

        return atr

    def _python_bollinger_bands(
        self,
        prices: np.ndarray,
        period: int,
        std_dev: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Pure Python Bollinger Bands"""
        n = len(prices)
        upper = np.full(n, np.nan)
        middle = np.full(n, np.nan)
        lower = np.full(n, np.nan)

        for i in range(period-1, n):
            window = prices[i-period+1:i+1]
            sma = np.mean(window)
            std = np.std(window)
            middle[i] = sma
            upper[i] = sma + std_dev * std
            lower[i] = sma - std_dev * std

        return upper, middle, lower

    def _python_adx(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Pure Python ADX calculation"""
        n = len(close)
        adx = np.full(n, np.nan)
        plus_di = np.full(n, np.nan)
        minus_di = np.full(n, np.nan)

        # Simplified implementation
        atr = self._python_atr(high, low, close, period)

        # Calculate directional movement
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)

        for i in range(1, n):
            up = high[i] - high[i-1]
            down = low[i-1] - low[i]
            if up > down and up > 0:
                plus_dm[i] = up
            if down > up and down > 0:
                minus_dm[i] = down

        # Smooth and calculate DI
        for i in range(period, n):
            if atr[i] > 0:
                plus_di[i] = 100 * np.mean(plus_dm[i-period+1:i+1]) / atr[i]
                minus_di[i] = 100 * np.mean(minus_dm[i-period+1:i+1]) / atr[i]

        # Calculate ADX
        for i in range(2*period-1, n):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx = 100 * abs(plus_di[i] - minus_di[i]) / di_sum
                if i == 2*period-1:
                    adx[i] = dx
                else:
                    adx[i] = (adx[i-1] * (period-1) + dx) / period

        return adx, plus_di, minus_di

    def _python_qsci_batch(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
        weights: Dict[str, float]
    ) -> np.ndarray:
        """Pure Python QSCI batch calculation"""
        n = len(close)

        rsi = self._python_rsi(close, 14)
        macd, macd_sig, _ = self._python_macd(close, 12, 26, 9)
        adx, plus_di, minus_di = self._python_adx(high, low, close, 14)
        ema_fast = self._python_ema(close, 12)
        ema_slow = self._python_ema(close, 26)

        qsci = np.zeros(n)

        for i in range(n):
            # Momentum
            mom_sig = 0 if np.isnan(rsi[i]) else (rsi[i] - 50) / 50

            # MACD
            macd_s = 0 if np.isnan(macd[i]) or close[i] == 0 else np.tanh((macd[i] - macd_sig[i]) / close[i] * 100)

            # Trend
            trend_s = 0 if np.isnan(plus_di[i]) else np.tanh((plus_di[i] - minus_di[i]) / 20)

            # EMA
            ema_s = 0 if np.isnan(ema_fast[i]) or close[i] == 0 else (ema_fast[i] - ema_slow[i]) / close[i] * 10
            ema_s = max(-1, min(1, ema_s))

            # ADX multiplier
            adx_mult = 0.5 if np.isnan(adx[i]) or adx[i] < 20 else (1.2 if adx[i] > 40 else 0.5 + (adx[i] - 20) * 0.035)

            raw = (
                weights['momentum'] * mom_sig +
                weights['trend'] * (trend_s + macd_s) / 2 +
                weights['volatility'] * ema_s
            )

            qsci[i] = max(-1, min(1, raw * adx_mult))

        return qsci

    def _python_batch_greeks(
        self,
        spots: np.ndarray,
        strikes: np.ndarray,
        dtes: np.ndarray,
        ivs: np.ndarray,
        risk_free_rate: float,
        is_calls: List[bool]
    ) -> List[GreeksResult]:
        """Pure Python batch Greeks calculation"""
        import math

        def norm_cdf(x):
            return 0.5 * (1 + math.erf(x / math.sqrt(2)))

        def norm_pdf(x):
            return math.exp(-0.5 * x**2) / math.sqrt(2 * math.pi)

        results = []
        for i in range(len(spots)):
            spot, strike, dte, iv = spots[i], strikes[i], dtes[i], ivs[i]
            is_call = is_calls[i]

            if dte <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
                results.append(GreeksResult(0, 0, 0, 0, 0))
                continue

            T = dte / 365
            sqrt_T = math.sqrt(T)
            d1 = (math.log(spot/strike) + (risk_free_rate + 0.5*iv**2)*T) / (iv*sqrt_T)
            d2 = d1 - iv*sqrt_T

            pdf_d1 = norm_pdf(d1)
            disc = math.exp(-risk_free_rate * T)

            delta = norm_cdf(d1) if is_call else norm_cdf(d1) - 1
            gamma = pdf_d1 / (spot * iv * sqrt_T)
            vega = spot * pdf_d1 * sqrt_T / 100

            theta1 = -(spot * pdf_d1 * iv) / (2 * sqrt_T)
            if is_call:
                theta = (theta1 - risk_free_rate * strike * disc * norm_cdf(d2)) / 365
                rho = strike * T * disc * norm_cdf(d2) / 100
            else:
                theta = (theta1 + risk_free_rate * strike * disc * norm_cdf(-d2)) / 365
                rho = -strike * T * disc * norm_cdf(-d2) / 100

            results.append(GreeksResult(delta, gamma, vega, theta, rho))

        return results

    def _python_black_scholes(
        self,
        spot: float,
        strike: float,
        dte: float,
        iv: float,
        risk_free_rate: float,
        is_call: bool
    ) -> float:
        """Pure Python Black-Scholes"""
        import math

        if dte <= 0 or iv <= 0:
            return 0.0

        def norm_cdf(x):
            return 0.5 * (1 + math.erf(x / math.sqrt(2)))

        T = dte / 365
        d1 = (math.log(spot/strike) + (risk_free_rate + 0.5*iv**2)*T) / (iv*math.sqrt(T))
        d2 = d1 - iv*math.sqrt(T)

        disc = math.exp(-risk_free_rate * T)

        if is_call:
            return spot * norm_cdf(d1) - strike * disc * norm_cdf(d2)
        else:
            return strike * disc * norm_cdf(-d2) - spot * norm_cdf(-d1)

    def get_backend(self) -> str:
        """Get current backend being used"""
        return self.backend

    def benchmark(self, n: int = 10000) -> Dict[str, float]:
        """Benchmark current backend"""
        import time

        # Generate test data
        close = 50000 + np.cumsum(np.random.randn(n) * 100)
        high = close + np.abs(np.random.randn(n) * 50)
        low = close - np.abs(np.random.randn(n) * 50)

        results = {}

        # RSI
        start = time.perf_counter()
        self.rsi(close)
        results['rsi_ms'] = (time.perf_counter() - start) * 1000

        # MACD
        start = time.perf_counter()
        self.macd(close)
        results['macd_ms'] = (time.perf_counter() - start) * 1000

        # ATR
        start = time.perf_counter()
        self.atr(high, low, close)
        results['atr_ms'] = (time.perf_counter() - start) * 1000

        # Full QSCI
        start = time.perf_counter()
        self.calculate_qsci_batch(high, low, close)
        results['qsci_batch_ms'] = (time.perf_counter() - start) * 1000

        # Greeks batch
        spots = np.full(1000, 50000.0)
        strikes = np.full(1000, 51000.0)
        dtes = np.full(1000, 14.0)
        ivs = np.full(1000, 0.6)

        start = time.perf_counter()
        self.batch_greeks(spots, strikes, dtes, ivs)
        results['greeks_batch_1000_ms'] = (time.perf_counter() - start) * 1000

        results['backend'] = self.backend
        results['data_points'] = n

        return results


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("Testing HFT Core Interface...\n")

    core = HFTCore()
    print(f"Backend: {core.backend}")

    # Run benchmark
    print("\nBenchmark Results:")
    results = core.benchmark(10000)
    for key, value in results.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")

    # Test Black-Scholes
    price = core.black_scholes(50000, 51000, 14, 0.6)
    print(f"\nBS Price (50K call, 51K strike, 14 DTE, 60% IV): ${price:.2f}")

    # Test Greeks
    greeks = core.batch_greeks(
        np.array([50000.0]),
        np.array([51000.0]),
        np.array([14.0]),
        np.array([0.6])
    )[0]
    print(f"Greeks: delta={greeks.delta:.4f}, gamma={greeks.gamma:.6f}, vega={greeks.vega:.4f}")

    print("\n✅ HFT Core tests complete!")
