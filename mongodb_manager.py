"""
QSCI Trading Bot - MongoDB Manager Module
Handles data persistence with automatic cleanup for 512MB limit

Author: QSCI Trading System
Version: 1.0.0
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

# MongoDB imports with fallback
try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, OperationFailure
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False
    logger.warning("pymongo not installed - MongoDB features disabled")


@dataclass
class MongoDBConfig:
    """MongoDB configuration from environment variables"""
    uri: str = ""
    database: str = "qsci_trading"
    data_retention_days: int = 365
    log_retention_days: int = 180
    max_storage_mb: int = 480  # Leave buffer from 512MB

    def __post_init__(self):
        self.uri = os.getenv("MONGODB_URI", self.uri)

    @property
    def is_configured(self) -> bool:
        return bool(self.uri) and HAS_PYMONGO


class MongoDBManager:
    """
    MongoDB Atlas integration for QSCI Trading Bot

    Collections:
    - btc_ohlcv: Price data (365 day TTL)
    - trades: Trade history (180 day TTL)
    - telegram_logs: Message IDs for cleanup (180 day TTL)
    - system_state: Bot state and counters (no TTL)

    Features:
    - Automatic TTL-based cleanup
    - Storage monitoring
    - Connection pooling
    - Retry logic
    """

    COLLECTIONS = {
        "ohlcv": "btc_ohlcv",
        "trades": "trades",
        "telegram": "telegram_logs",
        "state": "system_state",
    }

    def __init__(self, config: Optional[MongoDBConfig] = None):
        self.config = config or MongoDBConfig()
        self.client: Optional[MongoClient] = None
        self.db = None
        self._connected = False

        if self.config.is_configured:
            self._connect()

    def _connect(self) -> bool:
        """Establish MongoDB connection"""
        if not self.config.is_configured:
            logger.error("MongoDB not configured")
            return False

        try:
            self.client = MongoClient(
                self.config.uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                retryWrites=True
            )

            # Test connection
            self.client.admin.command('ping')

            self.db = self.client[self.config.database]
            self._connected = True

            # Setup indexes and TTL
            self._setup_indexes()

            logger.info("✓ Connected to MongoDB Atlas")
            return True

        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"MongoDB error: {e}")
            return False

    def _setup_indexes(self):
        """Setup indexes and TTL for automatic cleanup"""
        if not self._connected:
            return

        try:
            # OHLCV collection - TTL on timestamp
            ohlcv_col = self.db[self.COLLECTIONS["ohlcv"]]
            ohlcv_col.create_index([("timestamp", ASCENDING)])
            ohlcv_col.create_index([("timeframe", ASCENDING)])
            ohlcv_col.create_index(
                [("created_at", ASCENDING)],
                expireAfterSeconds=self.config.data_retention_days * 86400,
                name="ohlcv_ttl"
            )

            # Trades collection - TTL on entry_time
            trades_col = self.db[self.COLLECTIONS["trades"]]
            trades_col.create_index([("entry_time", DESCENDING)])
            trades_col.create_index([("status", ASCENDING)])
            trades_col.create_index(
                [("created_at", ASCENDING)],
                expireAfterSeconds=self.config.log_retention_days * 86400,
                name="trades_ttl"
            )

            # Telegram logs - TTL
            tg_col = self.db[self.COLLECTIONS["telegram"]]
            tg_col.create_index(
                [("created_at", ASCENDING)],
                expireAfterSeconds=self.config.log_retention_days * 86400,
                name="telegram_ttl"
            )

            logger.debug("MongoDB indexes configured")

        except OperationFailure as e:
            logger.warning(f"Index setup warning: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to MongoDB"""
        if not self._connected or not self.client:
            return False
        try:
            self.client.admin.command('ping')
            return True
        except:
            self._connected = False
            return False

    # ========== OHLCV Data Methods ==========

    def save_ohlcv(self, data: List[Dict], timeframe: str = "1h") -> int:
        """
        Save OHLCV candles to MongoDB

        Args:
            data: List of candle dicts with keys: timestamp, open, high, low, close, volume
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, etc.)

        Returns:
            Number of documents inserted/updated
        """
        if not self.is_connected:
            return 0

        collection = self.db[self.COLLECTIONS["ohlcv"]]
        count = 0

        for candle in data:
            doc = {
                "timestamp": candle.get("timestamp") or candle.get("Open Time"),
                "open": float(candle.get("open") or candle.get("Open", 0)),
                "high": float(candle.get("high") or candle.get("High", 0)),
                "low": float(candle.get("low") or candle.get("Low", 0)),
                "close": float(candle.get("close") or candle.get("Close", 0)),
                "volume": float(candle.get("volume") or candle.get("Volume", 0)),
                "timeframe": timeframe,
                "created_at": datetime.utcnow()
            }

            # Upsert based on timestamp + timeframe
            result = collection.update_one(
                {"timestamp": doc["timestamp"], "timeframe": timeframe},
                {"$set": doc},
                upsert=True
            )

            if result.upserted_id or result.modified_count:
                count += 1

        logger.debug(f"Saved {count} OHLCV candles ({timeframe})")
        return count

    def get_ohlcv(self, timeframe: str = "1h",
                  start_time: Optional[datetime] = None,
                  end_time: Optional[datetime] = None,
                  limit: int = 1000) -> List[Dict]:
        """
        Retrieve OHLCV data from MongoDB

        Args:
            timeframe: Candle timeframe
            start_time: Start of range (optional)
            end_time: End of range (optional)
            limit: Maximum candles to return

        Returns:
            List of candle dicts
        """
        if not self.is_connected:
            return []

        collection = self.db[self.COLLECTIONS["ohlcv"]]

        query = {"timeframe": timeframe}

        if start_time:
            query["timestamp"] = {"$gte": start_time}
        if end_time:
            if "timestamp" in query:
                query["timestamp"]["$lte"] = end_time
            else:
                query["timestamp"] = {"$lte": end_time}

        cursor = collection.find(
            query,
            {"_id": 0}
        ).sort("timestamp", ASCENDING).limit(limit)

        return list(cursor)

    def get_latest_ohlcv(self, timeframe: str = "1h") -> Optional[Dict]:
        """Get the most recent candle"""
        if not self.is_connected:
            return None

        collection = self.db[self.COLLECTIONS["ohlcv"]]

        doc = collection.find_one(
            {"timeframe": timeframe},
            {"_id": 0},
            sort=[("timestamp", DESCENDING)]
        )

        return doc

    # ========== Trade Methods ==========

    def save_trade(self, trade: Dict) -> Optional[str]:
        """
        Save trade to MongoDB

        Args:
            trade: Trade dict with standard trade fields

        Returns:
            Inserted document ID as string, or None
        """
        if not self.is_connected:
            return None

        collection = self.db[self.COLLECTIONS["trades"]]

        doc = {
            **trade,
            "created_at": datetime.utcnow()
        }

        result = collection.insert_one(doc)

        logger.debug(f"Saved trade #{trade.get('id')}")
        return str(result.inserted_id)

    def update_trade(self, trade_id: int, updates: Dict) -> bool:
        """Update an existing trade"""
        if not self.is_connected:
            return False

        collection = self.db[self.COLLECTIONS["trades"]]

        result = collection.update_one(
            {"id": trade_id},
            {"$set": updates}
        )

        return result.modified_count > 0

    def get_trades(self, status: Optional[str] = None,
                   limit: int = 100) -> List[Dict]:
        """Get trades with optional status filter"""
        if not self.is_connected:
            return []

        collection = self.db[self.COLLECTIONS["trades"]]

        query = {}
        if status:
            query["status"] = status

        cursor = collection.find(
            query,
            {"_id": 0}
        ).sort("entry_time", DESCENDING).limit(limit)

        return list(cursor)

    def get_trade_stats(self) -> Dict:
        """Get aggregate trade statistics"""
        if not self.is_connected:
            return {}

        collection = self.db[self.COLLECTIONS["trades"]]

        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_trades": {"$sum": 1},
                    "total_pnl": {"$sum": "$pnl_after_fees"},
                    "wins": {
                        "$sum": {"$cond": [{"$gt": ["$pnl_after_fees", 0]}, 1, 0]}
                    },
                    "losses": {
                        "$sum": {"$cond": [{"$lte": ["$pnl_after_fees", 0]}, 1, 0]}
                    },
                    "avg_pnl": {"$avg": "$pnl_after_fees"},
                    "max_win": {"$max": "$pnl_after_fees"},
                    "max_loss": {"$min": "$pnl_after_fees"}
                }
            }
        ]

        result = list(collection.aggregate(pipeline))

        if result:
            stats = result[0]
            stats.pop("_id", None)
            total = stats.get("total_trades", 0)
            wins = stats.get("wins", 0)
            stats["win_rate"] = (wins / total * 100) if total > 0 else 0
            return stats

        return {
            "total_trades": 0,
            "total_pnl": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0
        }

    # ========== System State Methods ==========

    def save_state(self, key: str, value: Any) -> bool:
        """Save system state value"""
        if not self.is_connected:
            return False

        collection = self.db[self.COLLECTIONS["state"]]

        result = collection.update_one(
            {"key": key},
            {
                "$set": {
                    "key": key,
                    "value": value,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        return result.acknowledged

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get system state value"""
        if not self.is_connected:
            return default

        collection = self.db[self.COLLECTIONS["state"]]

        doc = collection.find_one({"key": key})

        if doc:
            return doc.get("value", default)
        return default

    # ========== Telegram Log Methods ==========

    def save_telegram_message(self, message_id: int,
                               message_type: str = "trade") -> bool:
        """Save Telegram message ID for potential cleanup"""
        if not self.is_connected:
            return False

        collection = self.db[self.COLLECTIONS["telegram"]]

        result = collection.insert_one({
            "message_id": message_id,
            "message_type": message_type,
            "created_at": datetime.utcnow()
        })

        return result.acknowledged

    def get_old_telegram_messages(self, days: int = 180) -> List[int]:
        """Get message IDs older than specified days"""
        if not self.is_connected:
            return []

        collection = self.db[self.COLLECTIONS["telegram"]]

        cutoff = datetime.utcnow() - timedelta(days=days)

        cursor = collection.find(
            {"created_at": {"$lt": cutoff}},
            {"message_id": 1, "_id": 0}
        )

        return [doc["message_id"] for doc in cursor]

    # ========== Storage Management ==========

    def get_storage_stats(self) -> Dict:
        """Get current storage usage"""
        if not self.is_connected:
            return {}

        try:
            stats = self.db.command("dbStats")

            return {
                "storage_size_mb": stats.get("storageSize", 0) / (1024 * 1024),
                "data_size_mb": stats.get("dataSize", 0) / (1024 * 1024),
                "index_size_mb": stats.get("indexSize", 0) / (1024 * 1024),
                "collections": stats.get("collections", 0),
                "objects": stats.get("objects", 0)
            }
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}

    def cleanup_old_data(self, force: bool = False) -> Dict:
        """
        Manually cleanup old data (TTL handles this automatically,
        but can force if approaching limit)

        Returns:
            Dict with deleted counts per collection
        """
        if not self.is_connected:
            return {}

        results = {}

        # Check if cleanup needed
        stats = self.get_storage_stats()
        current_mb = stats.get("storage_size_mb", 0)

        if current_mb < self.config.max_storage_mb and not force:
            logger.debug(f"Storage OK: {current_mb:.1f}MB / {self.config.max_storage_mb}MB")
            return {"status": "not_needed", "current_mb": current_mb}

        logger.info(f"Running cleanup: {current_mb:.1f}MB used")

        # Delete OHLCV older than retention
        ohlcv_cutoff = datetime.utcnow() - timedelta(days=self.config.data_retention_days)
        ohlcv_result = self.db[self.COLLECTIONS["ohlcv"]].delete_many(
            {"timestamp": {"$lt": ohlcv_cutoff}}
        )
        results["ohlcv_deleted"] = ohlcv_result.deleted_count

        # Delete trades older than retention
        trades_cutoff = datetime.utcnow() - timedelta(days=self.config.log_retention_days)
        trades_result = self.db[self.COLLECTIONS["trades"]].delete_many(
            {"created_at": {"$lt": trades_cutoff}}
        )
        results["trades_deleted"] = trades_result.deleted_count

        logger.info(f"Cleanup complete: {results}")
        return results

    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self._connected = False
            logger.debug("MongoDB connection closed")


# Standalone test
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if "--test" in sys.argv:
        if not HAS_PYMONGO:
            print("✗ pymongo not installed. Run: pip install pymongo")
            sys.exit(1)

        manager = MongoDBManager()

        if manager.is_connected:
            print("✓ MongoDB connection successful!")

            # Test storage stats
            stats = manager.get_storage_stats()
            print(f"✓ Storage: {stats.get('storage_size_mb', 0):.2f}MB used")

            # Test state save/get
            manager.save_state("test_key", {"tested_at": str(datetime.utcnow())})
            value = manager.get_state("test_key")
            print(f"✓ State test: {value}")

            manager.close()
        else:
            print("✗ MongoDB connection failed")
            print("\nRequired environment variables:")
            print("  MONGODB_URI - Your MongoDB Atlas connection string")
            sys.exit(1)
    else:
        print("Usage: python mongodb_manager.py --test")
        print("\nRequired environment variables:")
        print("  MONGODB_URI - mongodb+srv://user:pass@cluster.mongodb.net/db")
