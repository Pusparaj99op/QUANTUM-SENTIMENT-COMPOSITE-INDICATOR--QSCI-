//! QSCI Signal Generation
//!
//! High-performance signal generation combining all indicators.

use crate::indicators::*;
use rayon::prelude::*;

/// Calculate QSCI signal for a single bar
fn calculate_qsci_single(
    rsi: f64,
    macd: f64,
    macd_signal: f64,
    adx: f64,
    plus_di: f64,
    minus_di: f64,
    close: f64,
    ema_fast: f64,
    ema_slow: f64,
    momentum_weight: f64,
    trend_weight: f64,
    volatility_weight: f64,
    volume_weight: f64,
) -> f64 {
    // Momentum signal from RSI
    let momentum_sig = if rsi.is_nan() {
        0.0
    } else {
        (rsi - 50.0) / 50.0 // -1 to 1
    };

    // MACD signal
    let macd_sig = if macd.is_nan() || macd_signal.is_nan() || close == 0.0 {
        0.0
    } else {
        ((macd - macd_signal) / close * 100.0).tanh()
    };

    // Trend signal from DI
    let trend_sig = if plus_di.is_nan() || minus_di.is_nan() {
        0.0
    } else {
        ((plus_di - minus_di) / 20.0).tanh()
    };

    // EMA trend
    let ema_sig = if ema_fast.is_nan() || ema_slow.is_nan() || close == 0.0 {
        0.0
    } else {
        let raw = (ema_fast - ema_slow) / close * 10.0;
        raw.max(-1.0).min(1.0)
    };

    // ADX multiplier
    let adx_mult = if adx.is_nan() || adx < 20.0 {
        0.5
    } else if adx > 40.0 {
        1.2
    } else {
        0.5 + (adx - 20.0) * 0.035
    };

    // Combine signals
    let raw_signal = momentum_weight * momentum_sig
        + trend_weight * (trend_sig + macd_sig) / 2.0
        + volatility_weight * ema_sig
        + volume_weight * 0.0; // Placeholder for volume signal

    // Apply ADX multiplier and clip
    (raw_signal * adx_mult).max(-1.0).min(1.0)
}

/// Calculate QSCI signals for entire dataset using parallel processing
pub fn calculate_qsci_signal_batch(
    high: &[f64],
    low: &[f64],
    close: &[f64],
    volume: &[f64],
    momentum_weight: f64,
    trend_weight: f64,
    volatility_weight: f64,
    volume_weight: f64,
) -> Vec<f64> {
    let n = close.len();
    if n == 0 {
        return vec![];
    }

    // Calculate all indicators
    let rsi = calculate_rsi(close, 14);
    let (macd_line, macd_signal, _) = calculate_macd(close, 12, 26, 9);
    let (adx, plus_di, minus_di) = calculate_adx(high, low, close, 14);
    let ema_fast = calculate_ema(close, 12);
    let ema_slow = calculate_ema(close, 26);

    // Calculate QSCI in parallel
    (0..n)
        .into_par_iter()
        .map(|i| {
            calculate_qsci_single(
                rsi[i],
                macd_line[i],
                macd_signal[i],
                adx[i],
                plus_di[i],
                minus_di[i],
                close[i],
                ema_fast[i],
                ema_slow[i],
                momentum_weight,
                trend_weight,
                volatility_weight,
                volume_weight,
            )
        })
        .collect()
}

/// Signal classification
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum SignalType {
    StrongBuy,
    Buy,
    Neutral,
    Sell,
    StrongSell,
}

impl SignalType {
    pub fn from_qsci(qsci: f64, threshold: f64) -> Self {
        if qsci > threshold * 2.0 {
            SignalType::StrongBuy
        } else if qsci > threshold {
            SignalType::Buy
        } else if qsci < -threshold * 2.0 {
            SignalType::StrongSell
        } else if qsci < -threshold {
            SignalType::Sell
        } else {
            SignalType::Neutral
        }
    }
}

/// Trade signal with all relevant information
#[derive(Debug, Clone)]
pub struct TradeSignal {
    pub signal_type: SignalType,
    pub qsci_value: f64,
    pub rsi: f64,
    pub adx: f64,
    pub trend_direction: i8, // 1 = up, -1 = down, 0 = neutral
    pub confidence: f64,     // 0 to 1
}

/// Generate trade signals from price data
pub fn generate_trade_signals(
    high: &[f64],
    low: &[f64],
    close: &[f64],
    volume: &[f64],
    qsci_threshold: f64,
    adx_threshold: f64,
) -> Vec<TradeSignal> {
    let n = close.len();
    if n == 0 {
        return vec![];
    }

    // Calculate indicators
    let rsi = calculate_rsi(close, 14);
    let (adx, plus_di, minus_di) = calculate_adx(high, low, close, 14);
    let qsci = calculate_qsci_signal_batch(high, low, close, volume, 0.35, 0.30, 0.15, 0.10);

    // Generate signals
    (0..n)
        .into_par_iter()
        .map(|i| {
            let signal_type = SignalType::from_qsci(qsci[i], qsci_threshold);

            let trend_direction = if !plus_di[i].is_nan() && !minus_di[i].is_nan() {
                if plus_di[i] > minus_di[i] {
                    1
                } else if minus_di[i] > plus_di[i] {
                    -1
                } else {
                    0
                }
            } else {
                0
            };

            // Confidence based on ADX and signal strength
            let confidence = if !adx[i].is_nan() && adx[i] >= adx_threshold {
                let adx_factor = (adx[i] - adx_threshold) / (50.0 - adx_threshold);
                let signal_factor = qsci[i].abs();
                (adx_factor * signal_factor).min(1.0)
            } else {
                0.0
            };

            TradeSignal {
                signal_type,
                qsci_value: qsci[i],
                rsi: rsi[i],
                adx: adx[i],
                trend_direction,
                confidence,
            }
        })
        .collect()
}

/// Filter signals based on entry criteria
pub fn filter_valid_signals(
    signals: &[TradeSignal],
    min_qsci: f64,
    min_adx: f64,
    min_confidence: f64,
) -> Vec<(usize, &TradeSignal)> {
    signals
        .iter()
        .enumerate()
        .filter(|(_, s)| {
            s.qsci_value.abs() >= min_qsci
                && !s.adx.is_nan()
                && s.adx >= min_adx
                && s.confidence >= min_confidence
                && s.signal_type != SignalType::Neutral
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_qsci_batch() {
        let n = 1000;
        let close: Vec<f64> = (0..n).map(|i| 50000.0 + (i as f64 * 0.01).sin() * 1000.0).collect();
        let high: Vec<f64> = close.iter().map(|c| c + 50.0).collect();
        let low: Vec<f64> = close.iter().map(|c| c - 50.0).collect();
        let volume: Vec<f64> = vec![1000.0; n];

        let qsci = calculate_qsci_signal_batch(&high, &low, &close, &volume, 0.35, 0.30, 0.15, 0.10);

        assert_eq!(qsci.len(), n);

        // QSCI should be in range [-1, 1]
        for &val in qsci.iter().skip(50) {
            // Skip warmup period
            assert!(val >= -1.0 && val <= 1.0, "QSCI out of range: {}", val);
        }
    }

    #[test]
    fn test_signal_classification() {
        assert_eq!(SignalType::from_qsci(0.5, 0.12), SignalType::StrongBuy);
        assert_eq!(SignalType::from_qsci(0.15, 0.12), SignalType::Buy);
        assert_eq!(SignalType::from_qsci(0.05, 0.12), SignalType::Neutral);
        assert_eq!(SignalType::from_qsci(-0.15, 0.12), SignalType::Sell);
        assert_eq!(SignalType::from_qsci(-0.5, 0.12), SignalType::StrongSell);
    }
}
