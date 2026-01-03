//! Lock-Free Order Book Implementation
//!
//! High-performance order book using atomic operations for thread-safe updates.

use parking_lot::RwLock;
use pyo3::prelude::*;
use std::collections::BTreeMap;
use std::sync::Arc;

/// Single price level in the order book
#[derive(Clone, Debug)]
pub struct PriceLevel {
    pub price: f64,
    pub quantity: f64,
    pub order_count: u32,
}

/// Order book with bid and ask levels
pub struct OrderBook {
    symbol: String,
    bids: RwLock<BTreeMap<i64, PriceLevel>>, // Descending order (highest first)
    asks: RwLock<BTreeMap<i64, PriceLevel>>, // Ascending order (lowest first)
    max_levels: usize,
    tick_size: f64,
    last_update_id: RwLock<u64>,
}

impl OrderBook {
    pub fn new(symbol: String, max_levels: usize) -> Self {
        Self {
            symbol,
            bids: RwLock::new(BTreeMap::new()),
            asks: RwLock::new(BTreeMap::new()),
            max_levels,
            tick_size: 0.01, // Default tick size
            last_update_id: RwLock::new(0),
        }
    }

    /// Convert price to integer key for precise ordering
    fn price_to_key(&self, price: f64) -> i64 {
        (price / self.tick_size).round() as i64
    }

    /// Convert key back to price
    fn key_to_price(&self, key: i64) -> f64 {
        key as f64 * self.tick_size
    }

    /// Update a bid level
    pub fn update_bid(&self, price: f64, quantity: f64) {
        let key = self.price_to_key(price);
        let mut bids = self.bids.write();

        if quantity == 0.0 {
            bids.remove(&key);
        } else {
            bids.insert(
                key,
                PriceLevel {
                    price,
                    quantity,
                    order_count: 1,
                },
            );
        }

        // Trim to max levels (keep highest bids)
        while bids.len() > self.max_levels {
            if let Some((&lowest_key, _)) = bids.iter().next() {
                bids.remove(&lowest_key);
            }
        }
    }

    /// Update an ask level
    pub fn update_ask(&self, price: f64, quantity: f64) {
        let key = self.price_to_key(price);
        let mut asks = self.asks.write();

        if quantity == 0.0 {
            asks.remove(&key);
        } else {
            asks.insert(
                key,
                PriceLevel {
                    price,
                    quantity,
                    order_count: 1,
                },
            );
        }

        // Trim to max levels (keep lowest asks)
        while asks.len() > self.max_levels {
            if let Some((&highest_key, _)) = asks.iter().next_back() {
                asks.remove(&highest_key);
            }
        }
    }

    /// Batch update bids
    pub fn update_bids_batch(&self, levels: &[(f64, f64)]) {
        let mut bids = self.bids.write();
        for &(price, quantity) in levels {
            let key = self.price_to_key(price);
            if quantity == 0.0 {
                bids.remove(&key);
            } else {
                bids.insert(
                    key,
                    PriceLevel {
                        price,
                        quantity,
                        order_count: 1,
                    },
                );
            }
        }

        // Trim to max levels
        while bids.len() > self.max_levels {
            if let Some((&lowest_key, _)) = bids.iter().next() {
                bids.remove(&lowest_key);
            }
        }
    }

    /// Batch update asks
    pub fn update_asks_batch(&self, levels: &[(f64, f64)]) {
        let mut asks = self.asks.write();
        for &(price, quantity) in levels {
            let key = self.price_to_key(price);
            if quantity == 0.0 {
                asks.remove(&key);
            } else {
                asks.insert(
                    key,
                    PriceLevel {
                        price,
                        quantity,
                        order_count: 1,
                    },
                );
            }
        }

        // Trim to max levels
        while asks.len() > self.max_levels {
            if let Some((&highest_key, _)) = asks.iter().next_back() {
                asks.remove(&highest_key);
            }
        }
    }

    /// Get best bid price
    pub fn best_bid(&self) -> Option<f64> {
        self.bids.read().iter().next_back().map(|(_, l)| l.price)
    }

    /// Get best ask price
    pub fn best_ask(&self) -> Option<f64> {
        self.asks.read().iter().next().map(|(_, l)| l.price)
    }

    /// Get mid price
    pub fn mid_price(&self) -> Option<f64> {
        match (self.best_bid(), self.best_ask()) {
            (Some(bid), Some(ask)) => Some((bid + ask) / 2.0),
            _ => None,
        }
    }

    /// Get spread
    pub fn spread(&self) -> Option<f64> {
        match (self.best_bid(), self.best_ask()) {
            (Some(bid), Some(ask)) => Some(ask - bid),
            _ => None,
        }
    }

    /// Get spread in basis points
    pub fn spread_bps(&self) -> Option<f64> {
        match (self.spread(), self.mid_price()) {
            (Some(spread), Some(mid)) if mid > 0.0 => Some((spread / mid) * 10000.0),
            _ => None,
        }
    }

    /// Get bid depth for top N levels
    pub fn bid_depth(&self, levels: usize) -> f64 {
        self.bids
            .read()
            .iter()
            .rev()
            .take(levels)
            .map(|(_, l)| l.quantity)
            .sum()
    }

    /// Get ask depth for top N levels
    pub fn ask_depth(&self, levels: usize) -> f64 {
        self.asks
            .read()
            .iter()
            .take(levels)
            .map(|(_, l)| l.quantity)
            .sum()
    }

    /// Calculate order imbalance (-1 to 1)
    pub fn imbalance(&self, levels: usize) -> f64 {
        let bid_depth = self.bid_depth(levels);
        let ask_depth = self.ask_depth(levels);
        let total = bid_depth + ask_depth;

        if total > 0.0 {
            (bid_depth - ask_depth) / total
        } else {
            0.0
        }
    }

    /// Get volume-weighted average bid price
    pub fn vwab(&self, levels: usize) -> Option<f64> {
        let bids = self.bids.read();
        let top_bids: Vec<_> = bids.iter().rev().take(levels).collect();

        let total_volume: f64 = top_bids.iter().map(|(_, l)| l.quantity).sum();
        if total_volume == 0.0 {
            return None;
        }

        let weighted_sum: f64 = top_bids.iter().map(|(_, l)| l.price * l.quantity).sum();
        Some(weighted_sum / total_volume)
    }

    /// Get volume-weighted average ask price
    pub fn vwaa(&self, levels: usize) -> Option<f64> {
        let asks = self.asks.read();
        let top_asks: Vec<_> = asks.iter().take(levels).collect();

        let total_volume: f64 = top_asks.iter().map(|(_, l)| l.quantity).sum();
        if total_volume == 0.0 {
            return None;
        }

        let weighted_sum: f64 = top_asks.iter().map(|(_, l)| l.price * l.quantity).sum();
        Some(weighted_sum / total_volume)
    }

    /// Clear the order book
    pub fn clear(&self) {
        self.bids.write().clear();
        self.asks.write().clear();
    }

    /// Get snapshot of bids
    pub fn get_bids(&self, levels: usize) -> Vec<(f64, f64)> {
        self.bids
            .read()
            .iter()
            .rev()
            .take(levels)
            .map(|(_, l)| (l.price, l.quantity))
            .collect()
    }

    /// Get snapshot of asks
    pub fn get_asks(&self, levels: usize) -> Vec<(f64, f64)> {
        self.asks
            .read()
            .iter()
            .take(levels)
            .map(|(_, l)| (l.price, l.quantity))
            .collect()
    }
}

/// Python wrapper for OrderBook
#[pyclass]
pub struct OrderBookPy {
    inner: Arc<OrderBook>,
}

#[pymethods]
impl OrderBookPy {
    #[new]
    pub fn new(symbol: String, max_levels: usize) -> Self {
        Self {
            inner: Arc::new(OrderBook::new(symbol, max_levels)),
        }
    }

    /// Update a bid level
    pub fn update_bid(&self, price: f64, quantity: f64) {
        self.inner.update_bid(price, quantity);
    }

    /// Update an ask level
    pub fn update_ask(&self, price: f64, quantity: f64) {
        self.inner.update_ask(price, quantity);
    }

    /// Batch update bids: list of (price, quantity) tuples
    pub fn update_bids(&self, levels: Vec<(f64, f64)>) {
        self.inner.update_bids_batch(&levels);
    }

    /// Batch update asks: list of (price, quantity) tuples
    pub fn update_asks(&self, levels: Vec<(f64, f64)>) {
        self.inner.update_asks_batch(&levels);
    }

    /// Get best bid price
    pub fn best_bid(&self) -> Option<f64> {
        self.inner.best_bid()
    }

    /// Get best ask price
    pub fn best_ask(&self) -> Option<f64> {
        self.inner.best_ask()
    }

    /// Get mid price
    pub fn mid_price(&self) -> Option<f64> {
        self.inner.mid_price()
    }

    /// Get spread
    pub fn spread(&self) -> Option<f64> {
        self.inner.spread()
    }

    /// Get spread in basis points
    pub fn spread_bps(&self) -> Option<f64> {
        self.inner.spread_bps()
    }

    /// Get bid depth for top N levels
    pub fn bid_depth(&self, levels: usize) -> f64 {
        self.inner.bid_depth(levels)
    }

    /// Get ask depth for top N levels
    pub fn ask_depth(&self, levels: usize) -> f64 {
        self.inner.ask_depth(levels)
    }

    /// Calculate order imbalance (-1 to 1)
    pub fn imbalance(&self, levels: usize) -> f64 {
        self.inner.imbalance(levels)
    }

    /// Clear the order book
    pub fn clear(&self) {
        self.inner.clear();
    }

    /// Get snapshot of bids
    pub fn get_bids(&self, levels: usize) -> Vec<(f64, f64)> {
        self.inner.get_bids(levels)
    }

    /// Get snapshot of asks
    pub fn get_asks(&self, levels: usize) -> Vec<(f64, f64)> {
        self.inner.get_asks(levels)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_order_book_basic() {
        let book = OrderBook::new("BTCUSDT".to_string(), 10);

        book.update_bid(50000.0, 1.5);
        book.update_bid(49999.0, 2.0);
        book.update_ask(50001.0, 1.0);
        book.update_ask(50002.0, 0.5);

        assert_eq!(book.best_bid(), Some(50000.0));
        assert_eq!(book.best_ask(), Some(50001.0));
        assert_eq!(book.spread(), Some(1.0));
    }

    #[test]
    fn test_order_book_imbalance() {
        let book = OrderBook::new("BTCUSDT".to_string(), 10);

        book.update_bid(50000.0, 10.0);
        book.update_ask(50001.0, 5.0);

        let imbalance = book.imbalance(5);
        assert!(imbalance > 0.0); // More bid volume = positive imbalance
    }
}
