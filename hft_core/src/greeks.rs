//! Greeks Calculator using Black-Scholes
//!
//! High-performance batch Greeks calculation using parallel processing.

use pyo3::prelude::*;
use rayon::prelude::*;
use std::f64::consts::PI;

/// Standard normal CDF using error function
fn norm_cdf(x: f64) -> f64 {
    0.5 * (1.0 + erf(x / std::f64::consts::SQRT_2))
}

/// Standard normal PDF
fn norm_pdf(x: f64) -> f64 {
    (-0.5 * x * x).exp() / (2.0 * PI).sqrt()
}

/// Error function approximation
fn erf(x: f64) -> f64 {
    // Approximation using Horner's method
    let a1 = 0.254829592;
    let a2 = -0.284496736;
    let a3 = 1.421413741;
    let a4 = -1.453152027;
    let a5 = 1.061405429;
    let p = 0.3275911;

    let sign = if x < 0.0 { -1.0 } else { 1.0 };
    let x = x.abs();

    let t = 1.0 / (1.0 + p * x);
    let y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * (-x * x).exp();

    sign * y
}

/// Greeks result structure
#[pyclass]
#[derive(Clone, Debug)]
pub struct GreeksResult {
    #[pyo3(get)]
    pub delta: f64,
    #[pyo3(get)]
    pub gamma: f64,
    #[pyo3(get)]
    pub vega: f64,
    #[pyo3(get)]
    pub theta: f64,
    #[pyo3(get)]
    pub rho: f64,
}

#[pymethods]
impl GreeksResult {
    fn __repr__(&self) -> String {
        format!(
            "GreeksResult(delta={:.4}, gamma={:.6}, vega={:.4}, theta={:.4}, rho={:.4})",
            self.delta, self.gamma, self.vega, self.theta, self.rho
        )
    }
}

/// Calculate Black-Scholes option price
pub fn black_scholes_price(
    spot: f64,
    strike: f64,
    dte: f64,
    iv: f64,
    risk_free_rate: f64,
    is_call: bool,
) -> f64 {
    if dte <= 0.0 || iv <= 0.0 || spot <= 0.0 || strike <= 0.0 {
        return 0.0;
    }

    let t = dte / 365.0;
    let d1 = ((spot / strike).ln() + (risk_free_rate + 0.5 * iv * iv) * t) / (iv * t.sqrt());
    let d2 = d1 - iv * t.sqrt();

    if is_call {
        spot * norm_cdf(d1) - strike * (-risk_free_rate * t).exp() * norm_cdf(d2)
    } else {
        strike * (-risk_free_rate * t).exp() * norm_cdf(-d2) - spot * norm_cdf(-d1)
    }
}

/// Calculate Greeks for a single option
pub fn calculate_greeks(
    spot: f64,
    strike: f64,
    dte: f64,
    iv: f64,
    risk_free_rate: f64,
    is_call: bool,
) -> GreeksResult {
    if dte <= 0.0 || iv <= 0.0 || spot <= 0.0 || strike <= 0.0 {
        return GreeksResult {
            delta: 0.0,
            gamma: 0.0,
            vega: 0.0,
            theta: 0.0,
            rho: 0.0,
        };
    }

    let t = dte / 365.0;
    let sqrt_t = t.sqrt();
    let d1 = ((spot / strike).ln() + (risk_free_rate + 0.5 * iv * iv) * t) / (iv * sqrt_t);
    let d2 = d1 - iv * sqrt_t;

    let pdf_d1 = norm_pdf(d1);
    let discount = (-risk_free_rate * t).exp();

    // Delta
    let delta = if is_call {
        norm_cdf(d1)
    } else {
        norm_cdf(d1) - 1.0
    };

    // Gamma (same for calls and puts)
    let gamma = pdf_d1 / (spot * iv * sqrt_t);

    // Vega (per 1% IV change)
    let vega = spot * pdf_d1 * sqrt_t / 100.0;

    // Theta (per day)
    let theta_first = -(spot * pdf_d1 * iv) / (2.0 * sqrt_t);
    let theta = if is_call {
        (theta_first - risk_free_rate * strike * discount * norm_cdf(d2)) / 365.0
    } else {
        (theta_first + risk_free_rate * strike * discount * norm_cdf(-d2)) / 365.0
    };

    // Rho (per 1% rate change)
    let rho = if is_call {
        strike * t * discount * norm_cdf(d2) / 100.0
    } else {
        -strike * t * discount * norm_cdf(-d2) / 100.0
    };

    GreeksResult {
        delta,
        gamma,
        vega,
        theta,
        rho,
    }
}

/// Calculate Greeks for a batch of options in parallel
pub fn calculate_batch_greeks(
    spots: &[f64],
    strikes: &[f64],
    dtes: &[f64],
    ivs: &[f64],
    risk_free_rate: f64,
    is_calls: &[bool],
) -> Vec<GreeksResult> {
    let n = spots.len();
    if n == 0
        || strikes.len() != n
        || dtes.len() != n
        || ivs.len() != n
        || is_calls.len() != n
    {
        return vec![];
    }

    (0..n)
        .into_par_iter()
        .map(|i| calculate_greeks(spots[i], strikes[i], dtes[i], ivs[i], risk_free_rate, is_calls[i]))
        .collect()
}

/// Calculate implied volatility using Newton-Raphson method
pub fn implied_volatility(
    option_price: f64,
    spot: f64,
    strike: f64,
    dte: f64,
    risk_free_rate: f64,
    is_call: bool,
    max_iterations: usize,
) -> Option<f64> {
    if option_price <= 0.0 || dte <= 0.0 {
        return None;
    }

    let mut iv = 0.3; // Initial guess

    for _ in 0..max_iterations {
        let price = black_scholes_price(spot, strike, dte, iv, risk_free_rate, is_call);
        let diff = price - option_price;

        if diff.abs() < 0.0001 {
            return Some(iv);
        }

        let greeks = calculate_greeks(spot, strike, dte, iv, risk_free_rate, is_call);
        let vega = greeks.vega * 100.0; // Convert back from per-1%-change

        if vega.abs() < 0.0001 {
            break;
        }

        iv -= diff / vega;
        iv = iv.max(0.01).min(5.0); // Clamp IV to reasonable range
    }

    Some(iv)
}

/// Calculate option delta for a strike at given moneyness
pub fn delta_at_moneyness(
    moneyness: f64, // strike / spot
    dte: f64,
    iv: f64,
    risk_free_rate: f64,
    is_call: bool,
) -> f64 {
    if dte <= 0.0 || iv <= 0.0 || moneyness <= 0.0 {
        return 0.0;
    }

    let t = dte / 365.0;
    let d1 = (-moneyness.ln() + (risk_free_rate + 0.5 * iv * iv) * t) / (iv * t.sqrt());

    if is_call {
        norm_cdf(d1)
    } else {
        norm_cdf(d1) - 1.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_black_scholes() {
        let price = black_scholes_price(100.0, 100.0, 30.0, 0.2, 0.05, true);
        assert!(price > 0.0);
        assert!(price < 100.0);
    }

    #[test]
    fn test_greeks() {
        let greeks = calculate_greeks(100.0, 100.0, 30.0, 0.2, 0.05, true);

        // ATM call delta should be around 0.5
        assert!(greeks.delta > 0.4 && greeks.delta < 0.6);

        // Gamma should be positive
        assert!(greeks.gamma > 0.0);

        // Vega should be positive
        assert!(greeks.vega > 0.0);
    }

    #[test]
    fn test_batch_greeks() {
        let spots = vec![100.0; 1000];
        let strikes = vec![100.0; 1000];
        let dtes = vec![30.0; 1000];
        let ivs = vec![0.2; 1000];
        let is_calls = vec![true; 1000];

        let results = calculate_batch_greeks(&spots, &strikes, &dtes, &ivs, 0.05, &is_calls);

        assert_eq!(results.len(), 1000);
    }

    #[test]
    fn test_implied_volatility() {
        // Calculate price at known IV
        let known_iv = 0.25;
        let price = black_scholes_price(100.0, 100.0, 30.0, known_iv, 0.05, true);

        // Recover IV from price
        let recovered_iv = implied_volatility(price, 100.0, 100.0, 30.0, 0.05, true, 100);

        assert!(recovered_iv.is_some());
        let iv = recovered_iv.unwrap();
        assert!((iv - known_iv).abs() < 0.001);
    }
}
