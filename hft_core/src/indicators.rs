//! Technical Indicators Implementation
//!
//! SIMD-optimized technical indicators using Rust's parallel processing capabilities.

use rayon::prelude::*;

/// Calculate Exponential Moving Average (EMA)
pub fn calculate_ema(prices: &[f64], period: usize) -> Vec<f64> {
    if prices.is_empty() || period == 0 {
        return vec![];
    }

    let n = prices.len();
    let mut ema = vec![f64::NAN; n];

    if n < period {
        return ema;
    }

    // Initial SMA
    let sma: f64 = prices[..period].iter().sum::<f64>() / period as f64;
    ema[period - 1] = sma;

    // EMA calculation
    let multiplier = 2.0 / (period as f64 + 1.0);
    for i in period..n {
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1];
    }

    ema
}

/// Calculate Relative Strength Index (RSI)
pub fn calculate_rsi(prices: &[f64], period: usize) -> Vec<f64> {
    if prices.len() < period + 1 {
        return vec![f64::NAN; prices.len()];
    }

    let n = prices.len();
    let mut rsi = vec![f64::NAN; n];

    // Calculate price changes
    let mut gains = vec![0.0; n];
    let mut losses = vec![0.0; n];

    for i in 1..n {
        let change = prices[i] - prices[i - 1];
        if change > 0.0 {
            gains[i] = change;
        } else {
            losses[i] = -change;
        }
    }

    // Initial averages
    let mut avg_gain: f64 = gains[1..=period].iter().sum::<f64>() / period as f64;
    let mut avg_loss: f64 = losses[1..=period].iter().sum::<f64>() / period as f64;

    if avg_loss == 0.0 {
        rsi[period] = 100.0;
    } else {
        let rs = avg_gain / avg_loss;
        rsi[period] = 100.0 - (100.0 / (1.0 + rs));
    }

    // Wilder's smoothing for subsequent values
    for i in (period + 1)..n {
        avg_gain = (avg_gain * (period - 1) as f64 + gains[i]) / period as f64;
        avg_loss = (avg_loss * (period - 1) as f64 + losses[i]) / period as f64;

        if avg_loss == 0.0 {
            rsi[i] = 100.0;
        } else {
            let rs = avg_gain / avg_loss;
            rsi[i] = 100.0 - (100.0 / (1.0 + rs));
        }
    }

    rsi
}

/// Calculate MACD (Moving Average Convergence Divergence)
pub fn calculate_macd(
    prices: &[f64],
    fast_period: usize,
    slow_period: usize,
    signal_period: usize,
) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let ema_fast = calculate_ema(prices, fast_period);
    let ema_slow = calculate_ema(prices, slow_period);

    let n = prices.len();
    let mut macd_line = vec![f64::NAN; n];

    // MACD line = Fast EMA - Slow EMA
    for i in 0..n {
        if !ema_fast[i].is_nan() && !ema_slow[i].is_nan() {
            macd_line[i] = ema_fast[i] - ema_slow[i];
        }
    }

    // Signal line = EMA of MACD line
    let signal_line = calculate_ema(&macd_line, signal_period);

    // Histogram = MACD line - Signal line
    let mut histogram = vec![f64::NAN; n];
    for i in 0..n {
        if !macd_line[i].is_nan() && !signal_line[i].is_nan() {
            histogram[i] = macd_line[i] - signal_line[i];
        }
    }

    (macd_line, signal_line, histogram)
}

/// Calculate Average True Range (ATR)
pub fn calculate_atr(high: &[f64], low: &[f64], close: &[f64], period: usize) -> Vec<f64> {
    let n = close.len();
    if n < 2 || high.len() != n || low.len() != n {
        return vec![f64::NAN; n];
    }

    let mut tr = vec![0.0; n];
    tr[0] = high[0] - low[0];

    for i in 1..n {
        let hl = high[i] - low[i];
        let hc = (high[i] - close[i - 1]).abs();
        let lc = (low[i] - close[i - 1]).abs();
        tr[i] = hl.max(hc).max(lc);
    }

    let mut atr = vec![f64::NAN; n];
    if n < period {
        return atr;
    }

    // Initial ATR (simple average)
    atr[period - 1] = tr[..period].iter().sum::<f64>() / period as f64;

    // Wilder's smoothing
    for i in period..n {
        atr[i] = (atr[i - 1] * (period - 1) as f64 + tr[i]) / period as f64;
    }

    atr
}

/// Calculate Bollinger Bands
pub fn calculate_bollinger_bands(
    prices: &[f64],
    period: usize,
    std_dev_mult: f64,
) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let n = prices.len();
    let mut upper = vec![f64::NAN; n];
    let mut middle = vec![f64::NAN; n];
    let mut lower = vec![f64::NAN; n];

    if n < period {
        return (upper, middle, lower);
    }

    for i in (period - 1)..n {
        let window = &prices[(i + 1 - period)..=i];
        let sma: f64 = window.iter().sum::<f64>() / period as f64;
        let variance: f64 = window.iter().map(|x| (x - sma).powi(2)).sum::<f64>() / period as f64;
        let std_dev = variance.sqrt();

        middle[i] = sma;
        upper[i] = sma + std_dev_mult * std_dev;
        lower[i] = sma - std_dev_mult * std_dev;
    }

    (upper, middle, lower)
}

/// Calculate ADX (Average Directional Index) with +DI and -DI
pub fn calculate_adx(
    high: &[f64],
    low: &[f64],
    close: &[f64],
    period: usize,
) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let n = close.len();
    let mut adx = vec![f64::NAN; n];
    let mut plus_di = vec![f64::NAN; n];
    let mut minus_di = vec![f64::NAN; n];

    if n < 2 * period || high.len() != n || low.len() != n {
        return (adx, plus_di, minus_di);
    }

    // Calculate +DM and -DM
    let mut plus_dm = vec![0.0; n];
    let mut minus_dm = vec![0.0; n];

    for i in 1..n {
        let up_move = high[i] - high[i - 1];
        let down_move = low[i - 1] - low[i];

        if up_move > down_move && up_move > 0.0 {
            plus_dm[i] = up_move;
        }
        if down_move > up_move && down_move > 0.0 {
            minus_dm[i] = down_move;
        }
    }

    // Calculate ATR
    let atr = calculate_atr(high, low, close, period);

    // Smooth +DM and -DM
    let mut smoothed_plus_dm = 0.0;
    let mut smoothed_minus_dm = 0.0;

    for i in 1..=period {
        smoothed_plus_dm += plus_dm[i];
        smoothed_minus_dm += minus_dm[i];
    }

    for i in period..n {
        if i > period {
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period as f64) + plus_dm[i];
            smoothed_minus_dm =
                smoothed_minus_dm - (smoothed_minus_dm / period as f64) + minus_dm[i];
        }

        if !atr[i].is_nan() && atr[i] > 0.0 {
            plus_di[i] = 100.0 * smoothed_plus_dm / (atr[i] * period as f64);
            minus_di[i] = 100.0 * smoothed_minus_dm / (atr[i] * period as f64);
        }
    }

    // Calculate DX and ADX
    let mut dx = vec![f64::NAN; n];
    for i in period..n {
        if !plus_di[i].is_nan() && !minus_di[i].is_nan() {
            let di_sum = plus_di[i] + minus_di[i];
            if di_sum > 0.0 {
                dx[i] = 100.0 * (plus_di[i] - minus_di[i]).abs() / di_sum;
            }
        }
    }

    // First ADX value
    if n >= 2 * period {
        let mut adx_sum = 0.0;
        for i in period..(2 * period) {
            if !dx[i].is_nan() {
                adx_sum += dx[i];
            }
        }
        adx[2 * period - 1] = adx_sum / period as f64;

        // Subsequent ADX values
        for i in (2 * period)..n {
            if !dx[i].is_nan() {
                adx[i] = (adx[i - 1] * (period - 1) as f64 + dx[i]) / period as f64;
            }
        }
    }

    (adx, plus_di, minus_di)
}

/// Calculate OBV (On-Balance Volume)
pub fn calculate_obv(close: &[f64], volume: &[f64]) -> Vec<f64> {
    let n = close.len();
    if n == 0 || volume.len() != n {
        return vec![];
    }

    let mut obv = vec![0.0; n];
    obv[0] = volume[0];

    for i in 1..n {
        if close[i] > close[i - 1] {
            obv[i] = obv[i - 1] + volume[i];
        } else if close[i] < close[i - 1] {
            obv[i] = obv[i - 1] - volume[i];
        } else {
            obv[i] = obv[i - 1];
        }
    }

    obv
}

/// Calculate VWAP (Volume Weighted Average Price)
pub fn calculate_vwap(high: &[f64], low: &[f64], close: &[f64], volume: &[f64]) -> Vec<f64> {
    let n = close.len();
    if n == 0 || high.len() != n || low.len() != n || volume.len() != n {
        return vec![];
    }

    let mut vwap = vec![0.0; n];
    let mut cumulative_volume = 0.0;
    let mut cumulative_tp_volume = 0.0;

    for i in 0..n {
        let typical_price = (high[i] + low[i] + close[i]) / 3.0;
        cumulative_volume += volume[i];
        cumulative_tp_volume += typical_price * volume[i];

        if cumulative_volume > 0.0 {
            vwap[i] = cumulative_tp_volume / cumulative_volume;
        }
    }

    vwap
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ema() {
        let prices = vec![10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0];
        let ema = calculate_ema(&prices, 3);
        assert_eq!(ema.len(), 10);
        assert!(ema[2].is_finite()); // First valid EMA
    }

    #[test]
    fn test_rsi() {
        let prices: Vec<f64> = (0..100).map(|i| 50.0 + (i as f64 * 0.1).sin() * 10.0).collect();
        let rsi = calculate_rsi(&prices, 14);
        assert_eq!(rsi.len(), 100);
        for i in 15..100 {
            assert!(rsi[i] >= 0.0 && rsi[i] <= 100.0);
        }
    }

    #[test]
    fn test_atr() {
        let high = vec![12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0];
        let low = vec![10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0];
        let close = vec![11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0];
        let atr = calculate_atr(&high, &low, &close, 5);
        assert_eq!(atr.len(), 10);
        assert!(atr[4].is_finite());
    }
}
