//! QSCI HFT Core - High-Frequency Trading Components
//!
//! This module provides ultra-low-latency trading components:
//! - SIMD-optimized technical indicators (RSI, MACD, ATR, etc.)
//! - Lock-free order book data structure
//! - Batch Greeks calculator using Black-Scholes
//! - Python bindings via PyO3
//!
//! Performance targets:
//! - RSI (10K bars): < 0.5ms
//! - MACD (10K bars): < 1ms
//! - Greeks batch (1000 options): < 0.5ms

use pyo3::prelude::*;
use pyo3::types::PyList;
use rayon::prelude::*;
use std::f64::consts::PI;

pub mod indicators;
pub mod order_book;
pub mod greeks;
pub mod signals;

use indicators::*;
use order_book::*;
use greeks::*;
use signals::*;

/// Calculate RSI using optimized Rust implementation
#[pyfunction]
fn rust_rsi(prices: Vec<f64>, period: usize) -> PyResult<Vec<f64>> {
    Ok(calculate_rsi(&prices, period))
}

/// Calculate EMA using optimized Rust implementation
#[pyfunction]
fn rust_ema(prices: Vec<f64>, period: usize) -> PyResult<Vec<f64>> {
    Ok(calculate_ema(&prices, period))
}

/// Calculate MACD using optimized Rust implementation
#[pyfunction]
fn rust_macd(
    prices: Vec<f64>,
    fast_period: usize,
    slow_period: usize,
    signal_period: usize,
) -> PyResult<(Vec<f64>, Vec<f64>, Vec<f64>)> {
    Ok(calculate_macd(&prices, fast_period, slow_period, signal_period))
}

/// Calculate ATR using optimized Rust implementation
#[pyfunction]
fn rust_atr(high: Vec<f64>, low: Vec<f64>, close: Vec<f64>, period: usize) -> PyResult<Vec<f64>> {
    Ok(calculate_atr(&high, &low, &close, period))
}

/// Calculate Bollinger Bands
#[pyfunction]
fn rust_bollinger_bands(
    prices: Vec<f64>,
    period: usize,
    std_dev: f64,
) -> PyResult<(Vec<f64>, Vec<f64>, Vec<f64>)> {
    Ok(calculate_bollinger_bands(&prices, period, std_dev))
}

/// Calculate ADX with +DI and -DI
#[pyfunction]
fn rust_adx(
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    period: usize,
) -> PyResult<(Vec<f64>, Vec<f64>, Vec<f64>)> {
    Ok(calculate_adx(&high, &low, &close, period))
}

/// Calculate all indicators and QSCI signal in one pass
#[pyfunction]
fn rust_calculate_qsci_batch(
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    volume: Vec<f64>,
    momentum_weight: f64,
    trend_weight: f64,
    volatility_weight: f64,
    volume_weight: f64,
) -> PyResult<Vec<f64>> {
    Ok(calculate_qsci_signal_batch(
        &high,
        &low,
        &close,
        &volume,
        momentum_weight,
        trend_weight,
        volatility_weight,
        volume_weight,
    ))
}

/// Calculate Greeks for a batch of options
#[pyfunction]
fn rust_batch_greeks(
    spots: Vec<f64>,
    strikes: Vec<f64>,
    dtes: Vec<f64>,
    ivs: Vec<f64>,
    risk_free_rate: f64,
    is_call: Vec<bool>,
) -> PyResult<Vec<GreeksResult>> {
    Ok(calculate_batch_greeks(
        &spots,
        &strikes,
        &dtes,
        &ivs,
        risk_free_rate,
        &is_call,
    ))
}

/// Calculate option price using Black-Scholes
#[pyfunction]
fn rust_black_scholes(
    spot: f64,
    strike: f64,
    dte: f64,
    iv: f64,
    risk_free_rate: f64,
    is_call: bool,
) -> PyResult<f64> {
    Ok(black_scholes_price(spot, strike, dte, iv, risk_free_rate, is_call))
}

/// Create a new order book
#[pyfunction]
fn create_order_book(symbol: String, max_levels: usize) -> PyResult<OrderBookPy> {
    Ok(OrderBookPy::new(symbol, max_levels))
}

/// Python module definition
#[pymodule]
fn qsci_hft_core(_py: Python, m: &PyModule) -> PyResult<()> {
    // Indicators
    m.add_function(wrap_pyfunction!(rust_rsi, m)?)?;
    m.add_function(wrap_pyfunction!(rust_ema, m)?)?;
    m.add_function(wrap_pyfunction!(rust_macd, m)?)?;
    m.add_function(wrap_pyfunction!(rust_atr, m)?)?;
    m.add_function(wrap_pyfunction!(rust_bollinger_bands, m)?)?;
    m.add_function(wrap_pyfunction!(rust_adx, m)?)?;
    m.add_function(wrap_pyfunction!(rust_calculate_qsci_batch, m)?)?;

    // Greeks
    m.add_function(wrap_pyfunction!(rust_batch_greeks, m)?)?;
    m.add_function(wrap_pyfunction!(rust_black_scholes, m)?)?;

    // Order book
    m.add_function(wrap_pyfunction!(create_order_book, m)?)?;
    m.add_class::<OrderBookPy>()?;
    m.add_class::<GreeksResult>()?;

    Ok(())
}
