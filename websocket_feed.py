"""
QSCI WebSocket Real-Time Data Feed

Features:
- Binance WebSocket connections for trades and depth
- Async event-driven architecture
- Tick buffer with configurable size
- Order book maintenance
- Latency monitoring
- Automatic reconnection

Author: QSCI Trading System
Version: 3.1.0
"""

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
import threading

logger = logging.getLogger(__name__)

# Try to import websockets
try:
    import websockets
    from websockets.exceptions import ConnectionClosed, WebSocketException
    HAS_WEBSOCKETS = True
except ImportError:
    logger.warning("websockets not installed. Run: pip install websockets")
    HAS_WEBSOCKETS = False


@dataclass
class Tick:
    """Single tick/trade data point"""
    timestamp: int  # Unix timestamp in ms
    price: float
    quantity: float
    side: str  # "buy" or "sell"
    trade_id: int = 0

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp / 1000)


@dataclass
class OrderBookLevel:
    """Single price level in the order book"""
    price: float
    quantity: float


@dataclass
class OrderBook:
    """Order book with bid/ask levels"""
    symbol: str
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    last_update_id: int = 0
    last_update_time: float = 0.0

    @property
    def mid_price(self) -> float:
        if self.bids and self.asks:
            return (self.bids[0].price + self.asks[0].price) / 2
        return 0.0

    @property
    def spread(self) -> float:
        if self.bids and self.asks:
            return self.asks[0].price - self.bids[0].price
        return 0.0

    @property
    def spread_pct(self) -> float:
        mid = self.mid_price
        if mid > 0:
            return self.spread / mid
        return 0.0

    @property
    def imbalance(self) -> float:
        """Calculate order imbalance: positive = more bids, negative = more asks"""
        bid_vol = sum(level.quantity for level in self.bids[:5])
        ask_vol = sum(level.quantity for level in self.asks[:5])
        total = bid_vol + ask_vol
        if total > 0:
            return (bid_vol - ask_vol) / total
        return 0.0

    def get_bid_depth(self, levels: int = 5) -> float:
        """Get total bid volume for top N levels"""
        return sum(level.quantity for level in self.bids[:levels])

    def get_ask_depth(self, levels: int = 5) -> float:
        """Get total ask volume for top N levels"""
        return sum(level.quantity for level in self.asks[:levels])

    def get_vwap_bid(self, levels: int = 5) -> float:
        """Volume-weighted average bid price"""
        total_vol = 0.0
        total_value = 0.0
        for level in self.bids[:levels]:
            total_vol += level.quantity
            total_value += level.price * level.quantity
        return total_value / total_vol if total_vol > 0 else 0.0

    def get_vwap_ask(self, levels: int = 5) -> float:
        """Volume-weighted average ask price"""
        total_vol = 0.0
        total_value = 0.0
        for level in self.asks[:levels]:
            total_vol += level.quantity
            total_value += level.price * level.quantity
        return total_value / total_vol if total_vol > 0 else 0.0


@dataclass
class LatencyStats:
    """Track latency statistics"""
    samples: deque = field(default_factory=lambda: deque(maxlen=100))

    def add_sample(self, latency_ms: float):
        self.samples.append(latency_ms)

    @property
    def avg_latency(self) -> float:
        if self.samples:
            return sum(self.samples) / len(self.samples)
        return 0.0

    @property
    def max_latency(self) -> float:
        return max(self.samples) if self.samples else 0.0

    @property
    def min_latency(self) -> float:
        return min(self.samples) if self.samples else 0.0


class BinanceWebSocketFeed:
    """
    Real-time WebSocket feed from Binance

    Supports:
    - Aggregate trade streams (@aggTrade)
    - Order book depth streams (@depth)
    - Kline/candlestick streams (@kline)

    Usage:
        feed = BinanceWebSocketFeed(['BTCUSDT'])
        feed.on_trade = lambda tick: print(f"Trade: {tick.price}")
        feed.on_depth = lambda book: print(f"Mid: {book.mid_price}")
        await feed.start()
    """

    # Binance WebSocket endpoints
    ENDPOINTS = {
        "spot": "wss://stream.binance.com:9443/ws",
        "spot_combined": "wss://stream.binance.com:9443/stream",
        "futures": "wss://fstream.binance.com/ws",
        "futures_combined": "wss://fstream.binance.com/stream",
        "testnet_futures": "wss://stream.binancefuture.com/ws",
    }

    def __init__(
        self,
        symbols: List[str],
        use_futures: bool = False,
        use_testnet: bool = False,
        tick_buffer_size: int = 10000,
        depth_levels: int = 20,
        reconnect_delay: float = 5.0,
    ):
        self.symbols = [s.upper() for s in symbols]
        self.use_futures = use_futures
        self.use_testnet = use_testnet
        self.tick_buffer_size = tick_buffer_size
        self.depth_levels = depth_levels
        self.reconnect_delay = reconnect_delay

        # Data stores
        self.tick_buffers: Dict[str, deque] = {
            symbol: deque(maxlen=tick_buffer_size) for symbol in self.symbols
        }
        self.order_books: Dict[str, OrderBook] = {
            symbol: OrderBook(symbol=symbol) for symbol in self.symbols
        }
        self.latency_stats = LatencyStats()

        # Callbacks
        self.on_trade: Optional[Callable[[str, Tick], Any]] = None
        self.on_depth: Optional[Callable[[str, OrderBook], Any]] = None
        self.on_kline: Optional[Callable[[str, Dict], Any]] = None
        self.on_error: Optional[Callable[[Exception], Any]] = None

        # State
        self.running = False
        self._websocket = None
        self._reconnect_count = 0
        self._last_message_time = 0.0
        self._message_count = 0
        self._lock = threading.Lock()

    def _get_endpoint(self) -> str:
        """Get the appropriate WebSocket endpoint"""
        if self.use_testnet:
            return self.ENDPOINTS["testnet_futures"]
        if self.use_futures:
            return self.ENDPOINTS["futures_combined"]
        return self.ENDPOINTS["spot_combined"]

    def _get_streams(self) -> List[str]:
        """Build list of streams to subscribe"""
        streams = []
        for symbol in self.symbols:
            s = symbol.lower()
            streams.append(f"{s}@aggTrade")
            streams.append(f"{s}@depth{self.depth_levels}@100ms")
        return streams

    async def start(self):
        """Start the WebSocket connection"""
        if not HAS_WEBSOCKETS:
            logger.error("Cannot start: websockets module not installed")
            return

        self.running = True
        logger.info(f"Starting WebSocket feed for {self.symbols}")

        while self.running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                if self.on_error:
                    self.on_error(e)
                logger.error(f"WebSocket error: {e}")

                if self.running:
                    self._reconnect_count += 1
                    delay = min(self.reconnect_delay * (2 ** self._reconnect_count), 60)
                    logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_count})")
                    await asyncio.sleep(delay)

    async def _connect_and_listen(self):
        """Connect to WebSocket and listen for messages"""
        streams = self._get_streams()
        endpoint = self._get_endpoint()
        stream_param = "/".join(streams)
        url = f"{endpoint}?streams={stream_param}"

        logger.info(f"Connecting to {endpoint}")

        async with websockets.connect(
            url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            self._websocket = ws
            self._reconnect_count = 0
            logger.info(f"✓ Connected to Binance WebSocket ({len(streams)} streams)")

            async for message in ws:
                self._last_message_time = time.time()
                self._message_count += 1
                await self._process_message(message)

    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)

            # Combined stream format: {"stream": "...", "data": {...}}
            if "stream" in data:
                stream = data["stream"]
                payload = data["data"]
            else:
                # Direct stream format
                stream = data.get("e", "")
                payload = data

            # Calculate latency
            if "E" in payload:  # Event time
                event_time = payload["E"]
                receive_time = int(time.time() * 1000)
                latency = receive_time - event_time
                self.latency_stats.add_sample(latency)

            # Route to appropriate handler
            if "@aggTrade" in stream or payload.get("e") == "aggTrade":
                await self._handle_trade(payload)
            elif "@depth" in stream or payload.get("e") == "depthUpdate":
                await self._handle_depth(payload)
            elif "@kline" in stream or payload.get("e") == "kline":
                await self._handle_kline(payload)

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {message[:100]}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def _handle_trade(self, data: Dict):
        """Process aggregate trade message"""
        symbol = data.get("s", "").upper()
        if symbol not in self.symbols:
            return

        tick = Tick(
            timestamp=data.get("T", 0),
            price=float(data.get("p", 0)),
            quantity=float(data.get("q", 0)),
            side="sell" if data.get("m", False) else "buy",
            trade_id=data.get("a", 0),
        )

        with self._lock:
            self.tick_buffers[symbol].append(tick)

        if self.on_trade:
            try:
                result = self.on_trade(symbol, tick)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"on_trade callback error: {e}")

    async def _handle_depth(self, data: Dict):
        """Process order book depth message"""
        symbol = data.get("s", "").upper()
        if symbol not in self.symbols:
            return

        with self._lock:
            book = self.order_books[symbol]
            book.last_update_id = data.get("u", 0)
            book.last_update_time = time.time()

            # Update bids
            book.bids = [
                OrderBookLevel(price=float(p), quantity=float(q))
                for p, q in data.get("bids", data.get("b", []))
            ]

            # Update asks
            book.asks = [
                OrderBookLevel(price=float(p), quantity=float(q))
                for p, q in data.get("asks", data.get("a", []))
            ]

        if self.on_depth:
            try:
                result = self.on_depth(symbol, book)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"on_depth callback error: {e}")

    async def _handle_kline(self, data: Dict):
        """Process kline/candlestick message"""
        symbol = data.get("s", "").upper()
        kline = data.get("k", {})

        kline_data = {
            "symbol": symbol,
            "interval": kline.get("i", ""),
            "open_time": kline.get("t", 0),
            "close_time": kline.get("T", 0),
            "open": float(kline.get("o", 0)),
            "high": float(kline.get("h", 0)),
            "low": float(kline.get("l", 0)),
            "close": float(kline.get("c", 0)),
            "volume": float(kline.get("v", 0)),
            "is_closed": kline.get("x", False),
        }

        if self.on_kline:
            try:
                result = self.on_kline(symbol, kline_data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"on_kline callback error: {e}")

    def stop(self):
        """Stop the WebSocket connection"""
        self.running = False
        if self._websocket:
            asyncio.create_task(self._websocket.close())
        logger.info("WebSocket feed stopped")

    def get_last_price(self, symbol: str) -> Optional[float]:
        """Get the last traded price for a symbol"""
        symbol = symbol.upper()
        if symbol in self.tick_buffers and self.tick_buffers[symbol]:
            return self.tick_buffers[symbol][-1].price
        return None

    def get_order_book(self, symbol: str) -> Optional[OrderBook]:
        """Get the order book for a symbol"""
        symbol = symbol.upper()
        return self.order_books.get(symbol)

    def get_recent_ticks(self, symbol: str, count: int = 100) -> List[Tick]:
        """Get recent ticks for a symbol"""
        symbol = symbol.upper()
        if symbol in self.tick_buffers:
            return list(self.tick_buffers[symbol])[-count:]
        return []

    def get_tick_stats(self, symbol: str, window_seconds: float = 60.0) -> Dict:
        """Get statistics for recent ticks"""
        symbol = symbol.upper()
        if symbol not in self.tick_buffers:
            return {}

        now = time.time() * 1000
        cutoff = now - (window_seconds * 1000)

        recent = [t for t in self.tick_buffers[symbol] if t.timestamp > cutoff]

        if not recent:
            return {}

        prices = [t.price for t in recent]
        quantities = [t.quantity for t in recent]
        buys = [t for t in recent if t.side == "buy"]
        sells = [t for t in recent if t.side == "sell"]

        return {
            "count": len(recent),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "avg_price": sum(prices) / len(prices),
            "high": max(prices),
            "low": min(prices),
            "total_volume": sum(quantities),
            "buy_volume": sum(t.quantity for t in buys),
            "sell_volume": sum(t.quantity for t in sells),
            "vwap": sum(t.price * t.quantity for t in recent) / sum(quantities),
            "buy_sell_ratio": len(buys) / len(sells) if sells else float("inf"),
        }

    def get_stats(self) -> Dict:
        """Get feed statistics"""
        return {
            "running": self.running,
            "symbols": self.symbols,
            "message_count": self._message_count,
            "reconnect_count": self._reconnect_count,
            "last_message_age": time.time() - self._last_message_time if self._last_message_time else None,
            "avg_latency_ms": self.latency_stats.avg_latency,
            "max_latency_ms": self.latency_stats.max_latency,
            "tick_buffer_sizes": {s: len(b) for s, b in self.tick_buffers.items()},
        }


class WebSocketManager:
    """
    Manager for multiple WebSocket feeds with threading support

    Usage:
        manager = WebSocketManager()
        manager.add_symbol('BTCUSDT')
        manager.on_tick = lambda s, t: print(f"{s}: {t.price}")
        manager.start()
        # ... later
        manager.stop()
    """

    def __init__(self):
        self.feed: Optional[BinanceWebSocketFeed] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.symbols: List[str] = []

        # Callbacks
        self.on_tick: Optional[Callable[[str, Tick], Any]] = None
        self.on_book: Optional[Callable[[str, OrderBook], Any]] = None

    def add_symbol(self, symbol: str):
        """Add a symbol to track"""
        symbol = symbol.upper()
        if symbol not in self.symbols:
            self.symbols.append(symbol)

    def start(self):
        """Start the WebSocket feed in a background thread"""
        if not HAS_WEBSOCKETS:
            logger.error("Cannot start: websockets module not installed")
            return False

        if self._thread and self._thread.is_alive():
            logger.warning("WebSocket manager already running")
            return False

        if not self.symbols:
            logger.error("No symbols configured")
            return False

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"WebSocket manager started for {self.symbols}")
        return True

    def _run_loop(self):
        """Run the asyncio event loop in the background thread"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self.feed = BinanceWebSocketFeed(
            symbols=self.symbols,
            use_futures=False,
            tick_buffer_size=10000,
        )

        # Set up callbacks
        if self.on_tick:
            self.feed.on_trade = self.on_tick
        if self.on_book:
            self.feed.on_depth = self.on_book

        try:
            self._loop.run_until_complete(self.feed.start())
        except Exception as e:
            logger.error(f"WebSocket loop error: {e}")
        finally:
            self._loop.close()

    def stop(self):
        """Stop the WebSocket feed"""
        if self.feed:
            self.feed.stop()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("WebSocket manager stopped")

    def get_price(self, symbol: str) -> Optional[float]:
        """Get latest price for symbol"""
        if self.feed:
            return self.feed.get_last_price(symbol)
        return None

    def get_book(self, symbol: str) -> Optional[OrderBook]:
        """Get order book for symbol"""
        if self.feed:
            return self.feed.get_order_book(symbol)
        return None


# ==============================================================================
# DEMO / TEST
# ==============================================================================

async def demo():
    """Demo the WebSocket feed"""
    print("Starting WebSocket demo...")

    feed = BinanceWebSocketFeed(
        symbols=["BTCUSDT"],
        depth_levels=10,
    )

    tick_count = 0
    depth_count = 0

    def on_trade(symbol: str, tick: Tick):
        nonlocal tick_count
        tick_count += 1
        if tick_count % 10 == 0:  # Print every 10th tick
            print(f"  Trade: {symbol} ${tick.price:.2f} x {tick.quantity:.4f} ({tick.side})")

    def on_depth(symbol: str, book: OrderBook):
        nonlocal depth_count
        depth_count += 1
        if depth_count % 20 == 0:  # Print every 20th update
            print(
                f"  Depth: {symbol} mid=${book.mid_price:.2f} "
                f"spread={book.spread_pct*100:.4f}% imb={book.imbalance:+.2f}"
            )

    feed.on_trade = on_trade
    feed.on_depth = on_depth

    # Run for 30 seconds
    print("Listening for 30 seconds...")
    task = asyncio.create_task(feed.start())
    await asyncio.sleep(30)
    feed.stop()

    print(f"\nStats: {feed.get_stats()}")
    print(f"Tick stats: {feed.get_tick_stats('BTCUSDT', 30)}")


if __name__ == "__main__":
    if HAS_WEBSOCKETS:
        asyncio.run(demo())
    else:
        print("Install websockets first: pip install websockets")
