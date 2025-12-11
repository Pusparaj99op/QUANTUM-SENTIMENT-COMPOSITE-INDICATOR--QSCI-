"""
QSCI Trading Bot - Enhanced Telegram Notification Module
Sends trade alerts, P&L updates, and daily summaries to Telegram channel
Now with INTERACTIVE COMMANDS support!

Author: QSCI Trading System
Version: 2.1.0 - Enhanced Rate Limiting & Message Batching
"""

import os
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Callable, Tuple
from collections import deque
import json
import requests
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig:
    """Telegram configuration from environment variables"""
    bot_token: str = ""
    channel_id: str = ""
    log_retention_days: int = 180
    notification_level: str = "ALL"  # ALL, TRADES_ONLY, SUMMARY_ONLY
    polling_interval: int = 5  # seconds between polling for commands

    # Rate limiting settings
    rate_limit_messages: int = 30  # Max messages per minute
    rate_limit_window: int = 60  # Window in seconds
    batch_delay: float = 2.0  # Seconds to wait before batching similar messages
    max_batch_size: int = 5  # Max messages to batch together

    def __post_init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", self.bot_token)
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", self.channel_id)

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.channel_id)


class RateLimiter:
    """
    Token bucket rate limiter for Telegram API calls

    Prevents hitting Telegram's rate limits:
    - 30 messages per second to the same group
    - 20 messages per minute to the same group for bots
    """

    def __init__(self, max_calls: int = 20, period: int = 60):
        self.max_calls = max_calls
        self.period = period
        self.calls: deque = deque()
        self._lock = threading.Lock()

    def acquire(self) -> Tuple[bool, float]:
        """
        Try to acquire a rate limit token.

        Returns:
            Tuple of (allowed: bool, wait_time: float)
        """
        with self._lock:
            now = time.time()

            # Remove old calls outside the window
            while self.calls and self.calls[0] < now - self.period:
                self.calls.popleft()

            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True, 0.0

            # Calculate wait time until oldest call expires
            wait_time = self.calls[0] + self.period - now
            return False, wait_time

    def wait_if_needed(self) -> None:
        """Block until rate limit allows a call"""
        allowed, wait_time = self.acquire()
        if not allowed:
            logger.debug(f"Rate limited, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            self.acquire()


class MessageBatcher:
    """
    Batches similar messages to reduce notification spam

    Groups messages by type (trade, signal, error) and sends
    summaries instead of individual notifications for high-frequency events.
    """

    def __init__(self, batch_delay: float = 2.0, max_size: int = 5):
        self.batch_delay = batch_delay
        self.max_size = max_size
        self._pending: Dict[str, List[Dict]] = {}
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._flush_callback: Optional[Callable] = None

    def set_flush_callback(self, callback: Callable):
        """Set callback to be called when batch is flushed"""
        self._flush_callback = callback

    def add(self, message_type: str, message: Dict) -> bool:
        """
        Add a message to the batch.

        Returns:
            True if message was batched, False if should be sent immediately
        """
        # Some message types should never be batched
        never_batch = {'startup', 'shutdown', 'error', 'daily_summary', 'command_response'}
        if message_type in never_batch:
            return False

        with self._lock:
            if message_type not in self._pending:
                self._pending[message_type] = []

            self._pending[message_type].append(message)

            # Cancel existing timer
            if message_type in self._timers:
                self._timers[message_type].cancel()

            # Flush immediately if batch is full
            if len(self._pending[message_type]) >= self.max_size:
                self._flush_type(message_type)
                return True

            # Set timer for delayed flush
            timer = threading.Timer(self.batch_delay, self._flush_type, args=[message_type])
            timer.daemon = True
            timer.start()
            self._timers[message_type] = timer

            return True

    def _flush_type(self, message_type: str):
        """Flush all pending messages of a type"""
        with self._lock:
            messages = self._pending.pop(message_type, [])
            if message_type in self._timers:
                self._timers[message_type].cancel()
                del self._timers[message_type]

        if messages and self._flush_callback:
            self._flush_callback(message_type, messages)

    def flush_all(self):
        """Flush all pending batches"""
        with self._lock:
            types = list(self._pending.keys())

        for msg_type in types:
            self._flush_type(msg_type)


class TelegramNotifier:
    """
    Enhanced Telegram notification handler for QSCI Trading Bot

    Features:
    - Trade entry/exit notifications
    - Daily P&L summaries
    - Support/Resistance level alerts
    - Error notifications
    - Rate limiting to avoid spam (v2.1)
    - Message batching for high-frequency events (v2.1)
    - Per-chat rate limiting (v2.1)
    - INTERACTIVE COMMANDS
    - Custom message sending
    """

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, config: Optional[TelegramConfig] = None):
        self.config = config or TelegramConfig()
        self.last_message_time: Optional[datetime] = None
        self.min_message_interval = 1  # seconds between messages
        self.message_queue: List[str] = []
        self.daily_trade_count = 0
        self.daily_pnl = 0.0
        self._session = None

        # Rate limiting (v2.1)
        self.rate_limiter = RateLimiter(
            max_calls=self.config.rate_limit_messages,
            period=self.config.rate_limit_window
        )

        # Per-chat rate limiters for DM commands
        self._chat_rate_limiters: Dict[str, RateLimiter] = {}

        # Message batching (v2.1)
        self.batcher = MessageBatcher(
            batch_delay=self.config.batch_delay,
            max_size=self.config.max_batch_size
        )
        self.batcher.set_flush_callback(self._send_batched_messages)

        # Interactive bot state
        self.last_update_id = 0
        self.polling_active = False
        self.polling_thread: Optional[threading.Thread] = None
        self.command_handlers: Dict[str, Callable] = {}
        self.trader_reference = None  # Reference to live trader for status
        self.is_trading_paused = False
        
        # User settings per chat
        self.user_settings: Dict[str, Dict] = {}  # chat_id -> settings

        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_batched': 0,
            'rate_limited_waits': 0,
            'errors': 0
        }

        if self.config.is_configured:
            logger.info("✓ Telegram notifier initialized (Interactive Mode v2.1)")
        else:
            logger.warning("⚠️ Telegram not configured - notifications disabled")

    def _get_chat_rate_limiter(self, chat_id: str) -> RateLimiter:
        """Get or create rate limiter for a specific chat"""
        if chat_id not in self._chat_rate_limiters:
            # Stricter limits for individual chats (10 per minute)
            self._chat_rate_limiters[chat_id] = RateLimiter(max_calls=10, period=60)
        return self._chat_rate_limiters[chat_id]

    def set_trader_reference(self, trader):
        """Set reference to live trader for status commands"""
        self.trader_reference = trader

    def _make_request(self, method: str, data: Dict) -> Optional[Dict]:
        """Make API request to Telegram with rate limiting"""
        if not self.config.is_configured:
            return None

        # Apply rate limiting
        allowed, wait_time = self.rate_limiter.acquire()
        if not allowed:
            self.stats['rate_limited_waits'] += 1
            logger.debug(f"Rate limited, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            self.rate_limiter.acquire()

        url = self.BASE_URL.format(token=self.config.bot_token, method=method)

        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()

            if not result.get("ok"):
                error_code = result.get('error_code', 0)
                description = result.get('description', 'Unknown error')

                # Handle rate limit errors from Telegram
                if error_code == 429:
                    retry_after = result.get('parameters', {}).get('retry_after', 30)
                    logger.warning(f"Telegram rate limit hit, retry after {retry_after}s")
                    time.sleep(retry_after)
                    return self._make_request(method, data)  # Retry

                logger.error(f"Telegram API error: {description}")
                self.stats['errors'] += 1
                return None

            self.stats['messages_sent'] += 1
            return result

        except requests.exceptions.Timeout:
            logger.error("Telegram API timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram request failed: {e}")
            return None
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from Telegram")
            return None

    def send_message(self, text: str, parse_mode: str = "HTML",
                     disable_notification: bool = False,
                     chat_id: str = None,
                     reply_markup: Dict = None) -> Optional[int]:
        """
        Send message to configured Telegram channel or specific chat

        Args:
            text: Message text (HTML or Markdown)
            parse_mode: "HTML" or "Markdown"
            disable_notification: Send silently
            chat_id: Override channel_id for direct replies
            reply_markup: Inline keyboard or reply keyboard markup

        Returns:
            Message ID if successful, None otherwise
        """
        if not self.config.is_configured:
            logger.debug(f"Telegram not configured, would send: {text[:100]}...")
            return None

        # Rate limiting
        if self.last_message_time:
            elapsed = (datetime.now() - self.last_message_time).total_seconds()
            if elapsed < self.min_message_interval:
                time.sleep(self.min_message_interval - elapsed)

        data = {
            "chat_id": chat_id or self.config.channel_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification
        }
        
        if reply_markup:
            data["reply_markup"] = reply_markup

        result = self._make_request("sendMessage", data)
        self.last_message_time = datetime.now()

        if result:
            message_id = result.get("result", {}).get("message_id")
            logger.debug(f"Telegram message sent: ID {message_id}")
            return message_id
        return None

    def send_custom_message(self, message: str) -> Optional[int]:
        """
        Send any custom message to the bot channel

        Args:
            message: The message to send (HTML supported)

        Returns:
            Message ID if successful
        """
        text = f"""
📩 <b>Custom Message</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
{message}
━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
        """.strip()
        return self.send_message(text)

    # ============================================================
    # MESSAGE BATCHING (v2.1)
    # ============================================================

    def _send_batched_messages(self, message_type: str, messages: List[Dict]):
        """
        Send batched messages as a summary.

        Called by MessageBatcher when a batch is ready to send.
        Groups similar messages into a single summary notification.
        """
        if not messages:
            return

        count = len(messages)
        self.stats['messages_batched'] += count

        if message_type == 'signal':
            # Batch signal alerts
            bullish = sum(1 for m in messages if m.get('qsci', 0) > 0)
            bearish = count - bullish
            avg_qsci = sum(m.get('qsci', 0) for m in messages) / count

            text = f"""
📡 <b>SIGNAL SUMMARY</b> ({count} signals)
━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 Bullish: {bullish} | 🔴 Bearish: {bearish}
📊 Avg QSCI: {avg_qsci:.2f}
⏰ Last {self.config.batch_delay}s
━━━━━━━━━━━━━━━━━━━━━━━━━
            """.strip()
            self.send_message(text, disable_notification=True)

        elif message_type == 'position_update':
            # Batch position updates
            total_pnl = sum(m.get('pnl', 0) for m in messages)
            emoji = "🟢" if total_pnl >= 0 else "🔴"

            text = f"""
{emoji} <b>POSITION UPDATES</b> ({count} updates)
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Combined P&L: ${total_pnl:+,.2f}
⏰ Last {self.config.batch_delay}s
━━━━━━━━━━━━━━━━━━━━━━━━━
            """.strip()
            self.send_message(text, disable_notification=True)

        elif message_type == 'trade_opened':
            # Batch multiple trade opens
            calls = sum(1 for m in messages if m.get('option_type') == 'CALL')
            puts = count - calls

            text = f"""
📈 <b>TRADES OPENED</b> ({count} positions)
━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 CALLs: {calls} | 🔴 PUTs: {puts}
⏰ Last {self.config.batch_delay}s
━━━━━━━━━━━━━━━━━━━━━━━━━
            """.strip()
            self.send_message(text)

        else:
            # Generic batch summary
            text = f"""
📋 <b>{message_type.upper()}</b> ({count} events)
━━━━━━━━━━━━━━━━━━━━━━━━━
Batched {count} {message_type} notifications
⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
━━━━━━━━━━━━━━━━━━━━━━━━━
            """.strip()
            self.send_message(text, disable_notification=True)

    def get_stats(self) -> Dict:
        """Get notification statistics"""
        return {
            **self.stats,
            'rate_limiter_calls': len(self.rate_limiter.calls),
            'pending_batches': len(self.batcher._pending)
        }

    # ============================================================
    # INTERACTIVE COMMAND HANDLING
    # ============================================================

    def start_polling(self):
        """Start background polling for incoming commands"""
        if self.polling_active:
            logger.warning("Polling already active")
            return

        if not self.config.is_configured:
            logger.warning("Cannot start polling - Telegram not configured")
            return

        self.polling_active = True
        self.polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.polling_thread.start()
        logger.info("✓ Telegram command polling started")

    def stop_polling(self):
        """Stop the command polling"""
        self.polling_active = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
        logger.info("Telegram polling stopped")

    def _polling_loop(self):
        """Background loop to poll for new messages/commands"""
        while self.polling_active:
            try:
                self._fetch_and_process_updates()
            except Exception as e:
                logger.error(f"Polling error: {e}")
            time.sleep(self.config.polling_interval)

    def _fetch_and_process_updates(self):
        """Fetch new updates from Telegram and process commands"""
        url = self.BASE_URL.format(token=self.config.bot_token, method="getUpdates")

        try:
            params = {
                "offset": self.last_update_id + 1,
                "timeout": 10,
                "allowed_updates": ["message", "callback_query"]
            }
            response = requests.get(url, params=params, timeout=15)
            data = response.json()

            if not data.get("ok"):
                return

            for update in data.get("result", []):
                self.last_update_id = update["update_id"]
                
                # Handle callback queries (button presses)
                if "callback_query" in update:
                    callback = update["callback_query"]
                    chat_id = str(callback["message"]["chat"]["id"])
                    callback_data = callback["data"]
                    callback_id = callback["id"]
                    
                    # Answer the callback to remove loading state
                    self._make_request("answerCallbackQuery", {"callback_query_id": callback_id})
                    
                    # Handle the button press
                    self._handle_callback(callback_data, chat_id)
                
                # Handle text messages
                elif "message" in update:
                    message = update["message"]
                    text = message.get("text", "")
                    chat_id = str(message.get("chat", {}).get("id", ""))

                    if text.startswith("/"):
                        self._handle_command(text, chat_id)
                    elif text:
                        # Echo back non-command messages
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "📊 Status", "callback_data": "status"},
                                 {"text": "❓ Help", "callback_data": "help"}]
                            ]
                        }
                        self.send_message(
                            f"📝 Received: <i>{text[:100]}</i>\n\nUse buttons below or /help for commands.",
                            chat_id=chat_id,
                            reply_markup=keyboard
                        )

        except Exception as e:
            logger.debug(f"Update fetch failed: {e}")
    
    def _handle_callback(self, callback_data: str, chat_id: str):
        """Handle inline button callback"""
        logger.info(f"🔘 Button pressed: {callback_data} from {chat_id}")
        
        # Map callback data to commands
        if callback_data == "status":
            self._cmd_status(chat_id)
        elif callback_data == "stats":
            self._cmd_stats(chat_id)
        elif callback_data == "balance":
            self._cmd_balance(chat_id)
        elif callback_data == "trades":
            self._cmd_trades(chat_id)
        elif callback_data == "positions":
            self._cmd_positions(chat_id)
        elif callback_data == "settings":
            self._cmd_settings(chat_id)
        elif callback_data == "help":
            self._cmd_help(chat_id)
        elif callback_data.startswith("set_"):
            self._handle_setting_callback(callback_data, chat_id)
    
    def _handle_setting_callback(self, callback_data: str, chat_id: str):
        """Handle settings adjustment callbacks"""
        from config import POSITION_CONFIG, ENTRY_CRITERIA
        
        if callback_data == "set_pos_up":
            old = POSITION_CONFIG['max_concurrent_positions']
            new = min(old + 1, 10)
            POSITION_CONFIG['max_concurrent_positions'] = new
            msg = f"✅ Max positions: {old} → {new}"
        
        elif callback_data == "set_pos_down":
            old = POSITION_CONFIG['max_concurrent_positions']
            new = max(old - 1, 1)
            POSITION_CONFIG['max_concurrent_positions'] = new
            msg = f"✅ Max positions: {old} → {new}"
        
        elif callback_data == "set_risk_up":
            old = POSITION_CONFIG['risk_per_trade'] * 100
            new = min(old + 0.5, 10.0)
            POSITION_CONFIG['risk_per_trade'] = new / 100
            msg = f"✅ Risk per trade: {old:.1f}% → {new:.1f}%"
        
        elif callback_data == "set_risk_down":
            old = POSITION_CONFIG['risk_per_trade'] * 100
            new = max(old - 0.5, 0.5)
            POSITION_CONFIG['risk_per_trade'] = new / 100
            msg = f"✅ Risk per trade: {old:.1f}% → {new:.1f}%"
        
        elif callback_data == "set_entry_strict":
            ENTRY_CRITERIA['min_qsci_signal'] = min(ENTRY_CRITERIA.get('min_qsci_signal', 0.12) + 0.02, 0.30)
            ENTRY_CRITERIA['min_adx'] = min(ENTRY_CRITERIA.get('min_adx', 20) + 2, 30)
            msg = f"✅ Entry criteria made stricter\nQSCI: {ENTRY_CRITERIA['min_qsci_signal']:.2f}, ADX: {ENTRY_CRITERIA['min_adx']}"
        
        elif callback_data == "set_entry_relaxed":
            ENTRY_CRITERIA['min_qsci_signal'] = max(ENTRY_CRITERIA.get('min_qsci_signal', 0.12) - 0.02, 0.05)
            ENTRY_CRITERIA['min_adx'] = max(ENTRY_CRITERIA.get('min_adx', 20) - 2, 10)
            msg = f"✅ Entry criteria relaxed\nQSCI: {ENTRY_CRITERIA['min_qsci_signal']:.2f}, ADX: {ENTRY_CRITERIA['min_adx']}"
        
        elif callback_data == "set_reset":
            POSITION_CONFIG['max_concurrent_positions'] = 2
            POSITION_CONFIG['risk_per_trade'] = 0.025
            ENTRY_CRITERIA['min_qsci_signal'] = 0.12
            ENTRY_CRITERIA['min_adx'] = 20
            msg = "✅ Settings reset to defaults"
        
        else:
            msg = "❌ Unknown setting"
        
        self.send_message(msg, chat_id=chat_id)
        # Show updated settings
        time.sleep(0.5)
        self._cmd_settings(chat_id)

    def _handle_command(self, text: str, chat_id: str):
        """Process an incoming bot command"""
        parts = text.split()
        command = parts[0].lower().replace("@", "").split("@")[0]  # Handle @botname suffix
        args = parts[1:] if len(parts) > 1 else []

        logger.info(f"📥 Command received: {command} from {chat_id}")

        if command == "/status":
            self._cmd_status(chat_id)
        elif command == "/stats":
            self._cmd_stats(chat_id)
        elif command == "/balance":
            self._cmd_balance(chat_id)
        elif command == "/trades":
            self._cmd_trades(chat_id)
        elif command == "/positions":
            self._cmd_positions(chat_id)
        elif command == "/settings":
            self._cmd_settings(chat_id)
        elif command == "/stop":
            self._cmd_stop(chat_id)
        elif command == "/start":
            self._cmd_start(chat_id)
        elif command == "/help":
            self._cmd_help(chat_id)
        elif command == "/setbalance" and args:
            self._cmd_setbalance(chat_id, args[0])
        elif command == "/settrades" and args:
            self._cmd_settrades(chat_id, args[0])
        elif command == "/setrisk" and args:
            self._cmd_setrisk(chat_id, args[0])
        else:
            self.send_message(
                f"❓ Unknown command: <code>{command}</code>\n\nUse /help for available commands.",
                chat_id=chat_id
            )

    def _cmd_status(self, chat_id: str):
        """Handle /status command - show current trading status with quick actions"""
        if self.trader_reference:
            t = self.trader_reference
            open_pos = len([p for p in t.positions if p.status == "OPEN"])
            status_emoji = "🟢" if t.running and not self.is_trading_paused else "🔴"
            status_text = "Active" if t.running and not self.is_trading_paused else "Paused"

            text = f"""
{status_emoji} <b>QSCI Trading Bot Status</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Trading:</b> {status_text}
💰 <b>Balance:</b> ${t.account_balance:,.2f}
📈 <b>Total P&L:</b> ${t.total_pnl:+,.2f}
📂 <b>Open Positions:</b> {open_pos}
🕐 <b>Uptime:</b> Running
━━━━━━━━━━━━━━━━━━━━━━━━━
            """.strip()
            
            # Create inline keyboard with quick action buttons
            keyboard = {
                "inline_keyboard": [
                    [{"text": "📊 Stats", "callback_data": "stats"},
                     {"text": "💰 Balance", "callback_data": "balance"}],
                    [{"text": "📂 Positions", "callback_data": "positions"},
                     {"text": "📋 Trades", "callback_data": "trades"}],
                    [{"text": "⚙️ Settings", "callback_data": "settings"},
                     {"text": "🔄 Refresh", "callback_data": "status"}]
                ]
            }
        else:
            text = """
📊 <b>Bot Status</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ No trader connected
Use with qsci_live_trader.py
            """.strip()
            keyboard = None

        self.send_message(text, chat_id=chat_id, reply_markup=keyboard)

    def _cmd_balance(self, chat_id: str):
        """Handle /balance command - show detailed balance info"""
        if self.trader_reference:
            t = self.trader_reference
            initial = t.initial_balance
            current = t.account_balance
            pnl = t.total_pnl
            pnl_pct = (pnl / initial * 100) if initial > 0 else 0

            text = f"""
💰 <b>Balance Details</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
💵 <b>Initial:</b> ${initial:,.2f}
💎 <b>Current:</b> ${current:,.2f}
📈 <b>Total P&L:</b> ${pnl:+,.2f} ({pnl_pct:+.1f}%)

📅 <b>Today:</b>
   • Trades: {t.daily_trades}
   • P&L: ${t.daily_pnl:+,.2f}
   • Wins: {t.daily_wins} | Losses: {t.daily_losses}
━━━━━━━━━━━━━━━━━━━━━━━━━
            """.strip()
        else:
            text = "⚠️ No trader connected"

        self.send_message(text, chat_id=chat_id)

    def _cmd_trades(self, chat_id: str):
        """Handle /trades command - show recent trades"""
        if self.trader_reference and self.trader_reference.trades_log:
            t = self.trader_reference
            recent = t.trades_log[-5:]  # Last 5 trades

            trades_text = ""
            for trade in reversed(recent):
                pnl = trade.get('pnl_after_fees', 0)
                emoji = "✅" if pnl > 0 else "❌"
                opt_type = trade.get('option_type', 'CALL')
                trades_text += f"{emoji} #{trade.get('id')}: {opt_type} ${pnl:+.2f}\n"

            text = f"""
📋 <b>Recent Trades</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
{trades_text}
━━━━━━━━━━━━━━━━━━━━━━━━━
Total closed: {len(t.trades_log)}
            """.strip()
        else:
            text = "📋 No trades yet"

        self.send_message(text, chat_id=chat_id)

    def _cmd_positions(self, chat_id: str):
        """Handle /positions command - show open positions"""
        if self.trader_reference:
            t = self.trader_reference
            open_pos = [p for p in t.positions if p.status == "OPEN"]

            if open_pos:
                pos_text = ""
                for p in open_pos:
                    pnl = p.pnl
                    emoji = "🟢" if pnl >= 0 else "🔴"
                    pos_text += f"{emoji} #{p.id}: {p.option_type} Strike=${p.strike:.0f} P&L=${pnl:+.2f}\n"

                text = f"""
📂 <b>Open Positions</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
{pos_text}
━━━━━━━━━━━━━━━━━━━━━━━━━
                """.strip()
            else:
                text = "📂 No open positions"
        else:
            text = "⚠️ No trader connected"

        self.send_message(text, chat_id=chat_id)

    def _cmd_stop(self, chat_id: str):
        """Handle /stop command - pause trading"""
        self.is_trading_paused = True
        self.send_message(
            "🛑 <b>Trading PAUSED</b>\n\nNo new trades will be opened.\nUse /start to resume.",
            chat_id=chat_id
        )
        logger.info("Trading paused via Telegram command")

    def _cmd_start(self, chat_id: str):
        """Handle /start command - resume trading"""
        self.is_trading_paused = False
        self.send_message(
            "🟢 <b>Trading RESUMED</b>\n\nBot will open new trades based on signals.",
            chat_id=chat_id
        )
        logger.info("Trading resumed via Telegram command")

    def _cmd_stats(self, chat_id: str):
        """Handle /stats command - show comprehensive statistics"""
        if self.trader_reference:
            t = self.trader_reference
            
            # Calculate statistics
            total_trades = len(t.trades_log)
            wins = sum(1 for trade in t.trades_log if trade.get('pnl_after_fees', 0) > 0)
            losses = total_trades - wins
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            
            avg_win = sum(trade.get('pnl_after_fees', 0) for trade in t.trades_log if trade.get('pnl_after_fees', 0) > 0) / wins if wins > 0 else 0
            avg_loss = sum(trade.get('pnl_after_fees', 0) for trade in t.trades_log if trade.get('pnl_after_fees', 0) < 0) / losses if losses > 0 else 0
            
            profit_factor = abs(avg_win * wins / (avg_loss * losses)) if losses > 0 and avg_loss != 0 else 0
            
            # Get max drawdown
            max_dd = getattr(t, 'max_drawdown_pct', 0)
            
            # Current positions
            open_positions = [p for p in t.positions if p.status == "OPEN"]
            open_pos_pnl = sum(p.pnl for p in open_positions)
            
            # Return calculations
            initial = t.initial_balance
            current = t.account_balance
            total_return = ((current - initial) / initial * 100) if initial > 0 else 0
            
            text = f"""
📊 <b>Trading Statistics Dashboard</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

💹 <b>Performance Summary</b>
• Total Trades: {total_trades}
• Wins: {wins} | Losses: {losses}
• Win Rate: {win_rate:.1f}%
• Profit Factor: {profit_factor:.2f}

💵 <b>Financial Metrics</b>
• Initial Balance: ${initial:,.2f}
• Current Balance: ${current:,.2f}
• Total P&L: ${t.total_pnl:+,.2f}
• Return: {total_return:+.2f}%

📈 <b>Trade Quality</b>
• Avg Win: ${avg_win:,.2f}
• Avg Loss: ${avg_loss:,.2f}
• Win/Loss Ratio: {abs(avg_win/avg_loss):.2f}x

📉 <b>Risk Metrics</b>
• Max Drawdown: {max_dd:.2f}%
• Open Positions: {len(open_positions)}
• Open P&L: ${open_pos_pnl:+,.2f}

📅 <b>Today's Activity</b>
• Trades: {getattr(t, 'daily_trades', 0)}
• P&L: ${getattr(t, 'daily_pnl', 0):+,.2f}
• Wins: {getattr(t, 'daily_wins', 0)} | Losses: {getattr(t, 'daily_losses', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 Updated: {datetime.now().strftime('%H:%M:%S')}
            """.strip()
            
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🔄 Refresh", "callback_data": "stats"},
                     {"text": "📋 Trades", "callback_data": "trades"}],
                    [{"text": "📂 Positions", "callback_data": "positions"},
                     {"text": "🏠 Home", "callback_data": "status"}]
                ]
            }
        else:
            text = "⚠️ No trader connected"
            keyboard = None

        self.send_message(text, chat_id=chat_id, reply_markup=keyboard)

    def _cmd_settings(self, chat_id: str):
        """Handle /settings command - show and adjust trading parameters"""
        from config import POSITION_CONFIG, ENTRY_CRITERIA
        
        # Get current settings
        max_positions = POSITION_CONFIG.get('max_concurrent_positions', 2)
        risk_per_trade = POSITION_CONFIG.get('risk_per_trade', 0.025) * 100
        min_qsci = ENTRY_CRITERIA.get('min_qsci_signal', 0.12)
        min_adx = ENTRY_CRITERIA.get('min_adx', 20)
        max_iv_rank = ENTRY_CRITERIA.get('max_iv_rank', 0.6) * 100
        
        text = f"""
⚙️ <b>Trading Settings</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Position Management</b>
• Max Concurrent: {max_positions} positions
• Risk per Trade: {risk_per_trade:.1f}%

📈 <b>Entry Criteria</b>
• Min QSCI: {min_qsci:.2f}
• Min ADX: {min_adx:.0f}
• Max IV Rank: {max_iv_rank:.0f}%

━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Click below to adjust settings
        """.strip()
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "➕ Increase Positions", "callback_data": "set_pos_up"},
                 {"text": "➖ Decrease Positions", "callback_data": "set_pos_down"}],
                [{"text": "⬆️ More Risk", "callback_data": "set_risk_up"},
                 {"text": "⬇️ Less Risk", "callback_data": "set_risk_down"}],
                [{"text": "📊 Stricter Entry", "callback_data": "set_entry_strict"},
                 {"text": "📉 Relaxed Entry", "callback_data": "set_entry_relaxed"}],
                [{"text": "🔄 Reset Defaults", "callback_data": "set_reset"},
                 {"text": "🏠 Home", "callback_data": "status"}]
            ]
        }
        
        self.send_message(text, chat_id=chat_id, reply_markup=keyboard)

    def _cmd_help(self, chat_id: str):
        """Handle /help command - show available commands"""
        text = """
🤖 <b>QSCI Bot Commands</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Information</b>
/status - Bot status + quick actions
/stats - Comprehensive statistics
/balance - Detailed balance info
/trades - Recent trades list
/positions - Open positions

⚙️ <b>Controls</b>
/settings - Adjust trading parameters
/stop - Pause trading
/start - Resume trading

🔧 <b>Advanced</b>
/setbalance &lt;amt&gt; - Set balance
/settrades &lt;num&gt; - Set max positions
/setrisk &lt;pct&gt; - Set risk per trade

━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Use interactive buttons for easier navigation!
        """.strip()
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "📊 Status", "callback_data": "status"},
                 {"text": "📈 Stats", "callback_data": "stats"}],
                [{"text": "⚙️ Settings", "callback_data": "settings"}]
            ]
        }
        
        self.send_message(text, chat_id=chat_id, reply_markup=keyboard)

    def _cmd_setbalance(self, chat_id: str, amount_str: str):
        """Handle /setbalance command - manually set balance"""
        try:
            amount = float(amount_str.replace(",", "").replace("$", ""))
            if self.trader_reference:
                old_balance = self.trader_reference.account_balance
                self.trader_reference.account_balance = amount
                self.trader_reference._save_state()

                self.send_message(
                    f"💰 <b>Balance Updated</b>\n\n"
                    f"Old: ${old_balance:,.2f}\n"
                    f"New: ${amount:,.2f}",
                    chat_id=chat_id
                )
                logger.info(f"Balance set to ${amount:.2f} via Telegram")
            else:
                self.send_message("⚠️ No trader connected", chat_id=chat_id)
        except ValueError:
            self.send_message(
                f"❌ Invalid amount: <code>{amount_str}</code>\n\nUse: /setbalance 10000",
                chat_id=chat_id
            )
    
    def _cmd_settrades(self, chat_id: str, num_str: str):
        """Handle /settrades command - set max concurrent positions"""
        try:
            num = int(num_str)
            if num < 1 or num > 10:
                self.send_message(
                    f"❌ Invalid number: {num}\n\nMust be between 1 and 10",
                    chat_id=chat_id
                )
                return
            
            from config import POSITION_CONFIG
            old_max = POSITION_CONFIG['max_concurrent_positions']
            POSITION_CONFIG['max_concurrent_positions'] = num
            
            self.send_message(
                f"📊 <b>Max Positions Updated</b>\n\n"
                f"Old: {old_max} positions\n"
                f"New: {num} positions\n\n"
                f"⚠️ Restart required for full effect",
                chat_id=chat_id
            )
            logger.info(f"Max positions set to {num} via Telegram")
        except ValueError:
            self.send_message(
                f"❌ Invalid number: <code>{num_str}</code>\n\nUse: /settrades 3",
                chat_id=chat_id
            )
    
    def _cmd_setrisk(self, chat_id: str, pct_str: str):
        """Handle /setrisk command - set risk per trade percentage"""
        try:
            pct = float(pct_str.replace("%", ""))
            if pct < 0.5 or pct > 10:
                self.send_message(
                    f"❌ Invalid percentage: {pct}%\n\nMust be between 0.5% and 10%",
                    chat_id=chat_id
                )
                return
            
            from config import POSITION_CONFIG
            old_risk = POSITION_CONFIG['risk_per_trade'] * 100
            POSITION_CONFIG['risk_per_trade'] = pct / 100
            
            risk_level = "🟢 Conservative" if pct < 2 else "🟡 Moderate" if pct < 3.5 else "🔴 Aggressive"
            
            self.send_message(
                f"⚠️ <b>Risk Per Trade Updated</b>\n\n"
                f"Old: {old_risk:.1f}%\n"
                f"New: {pct:.1f}%\n"
                f"Level: {risk_level}\n\n"
                f"⚠️ Higher risk = larger positions",
                chat_id=chat_id
            )
            logger.info(f"Risk per trade set to {pct}% via Telegram")
        except ValueError:
            self.send_message(
                f"❌ Invalid percentage: <code>{pct_str}</code>\n\nUse: /setrisk 2.5",
                chat_id=chat_id
            )

    # ============================================================
    # EXISTING NOTIFICATION METHODS
    # ============================================================

    def send_startup_message(self, balance: float, check_interval: int = 5):
        """Send bot startup notification"""
        text = f"""
🤖 <b>QSCI Trading Bot Started</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Status:</b> Running
💰 <b>Initial Balance:</b> ${balance:,.2f}
⏰ <b>Started:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
🔄 <b>Checking every:</b> {check_interval} minutes
💬 <b>Interactive:</b> Send /help for commands
━━━━━━━━━━━━━━━━━━━━━━━━━
        """.strip()

        return self.send_message(text)

    def send_trade_opened(self, trade: Dict, account_balance: float,
                          total_trades: int) -> Optional[int]:
        """Send trade opened notification"""
        if self.is_trading_paused:
            return None  # Don't open trades when paused

        option_type = trade.get("option_type", "CALL")
        emoji = "🟢" if option_type == "CALL" else "🔴"
        direction = "LONG" if option_type == "CALL" else "SHORT"
        predicted = "Bullish 📈" if option_type == "CALL" else "Bearish 📉"

        trade_value = trade.get("entry_price", 0) * trade.get("quantity", 1)

        # Sentiment display
        sentiment = trade.get("sentiment_score", 0)
        if sentiment > 0.1:
            sentiment_text = f"Bullish ({sentiment:.2f})"
        elif sentiment < -0.1:
            sentiment_text = f"Bearish ({sentiment:.2f})"
        else:
            sentiment_text = f"Neutral ({sentiment:.2f})"

        text = f"""
{emoji} <b>{direction} POSITION OPENED</b> (#{trade.get('id', 0)})
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Trade Details:</b>
   • Type: {option_type} Option
   • Strike: ${trade.get('strike', 0):,.0f}
   • Entry: ${trade.get('entry_price', 0):,.2f}
   • Quantity: {trade.get('quantity', 1)} contracts
   • Value: ${trade_value:,.2f}

📈 <b>Analysis:</b>
   • QSCI Score: {trade.get('qsci', 0):.2f}
   • Predicted: {predicted}
   • Support: ${trade.get('support', 0):,.0f}
   • Resistance: ${trade.get('resistance', 0):,.0f}
   • ADX: {trade.get('adx', 0):.1f}

📰 <b>News Sentiment:</b> {sentiment_text}
━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Account: ${account_balance:,.2f} | Total Trades: {total_trades}
        """.strip()

        self.daily_trade_count += 1
        return self.send_message(text)

    def send_trade_closed(self, trade: Dict, account_balance: float,
                          total_pnl: float) -> Optional[int]:
        """Send trade closed notification"""
        pnl = trade.get("pnl_after_fees", 0)
        trade_return = trade.get("trade_return", 0) * 100

        if pnl > 0:
            emoji = "✅"
            result = "PROFIT"
        else:
            emoji = "❌"
            result = "LOSS"

        entry = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        quantity = trade.get("quantity", 1)

        text = f"""
{emoji} <b>POSITION CLOSED - {result}</b> (#{trade.get('id', 0)})
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Trade Result:</b>
   • Type: {trade.get('option_type', 'CALL')}
   • Entry: ${entry:,.2f}
   • Exit: ${exit_price:,.2f}
   • Quantity: {quantity}

💵 <b>P&L:</b>
   • Trade P&L: ${pnl:+,.2f}
   • Return: {trade_return:+.2f}%
   • Status: {trade.get('status', 'CLOSED')}

━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Balance: ${account_balance:,.2f} | Total P&L: ${total_pnl:+,.2f}
        """.strip()

        self.daily_pnl += pnl
        return self.send_message(text)

    def send_daily_summary(self, stats: Dict) -> Optional[int]:
        """Send daily trading summary"""
        win_rate = stats.get("win_rate", 0)

        text = f"""
📊 <b>DAILY TRADING SUMMARY</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
📅 <b>Date:</b> {stats.get('date', datetime.utcnow().strftime('%Y-%m-%d'))}

💹 <b>Performance:</b>
   • Trades Today: {stats.get('trades_today', 0)}
   • Wins: {stats.get('wins', 0)} | Losses: {stats.get('losses', 0)}
   • Win Rate: {win_rate:.1f}%
   • Daily P&L: ${stats.get('daily_pnl', 0):+,.2f}

📈 <b>Cumulative:</b>
   • Total Trades: {stats.get('total_trades', 0)}
   • Overall Win Rate: {stats.get('overall_win_rate', win_rate):.1f}%
   • Total P&L: ${stats.get('total_pnl', 0):+,.2f}
   • Current Balance: ${stats.get('balance', 0):,.2f}

📉 <b>Risk:</b>
   • Max Drawdown Today: {stats.get('max_drawdown_pct', 0):.1f}%
   • Open Positions: {stats.get('open_positions', 0)}

🔄 <b>Next Update:</b> In 24 hours
━━━━━━━━━━━━━━━━━━━━━━━━━
        """.strip()

        # Reset daily counters
        self.daily_trade_count = 0
        self.daily_pnl = 0.0

        return self.send_message(text)

    def send_error_alert(self, error_type: str, message: str) -> Optional[int]:
        """Send error notification"""
        text = f"""
⚠️ <b>ERROR ALERT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
<b>Type:</b> {error_type}
<b>Message:</b> {message}
<b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
        """.strip()

        return self.send_message(text)

    def send_position_rolled(self, trade: Dict) -> Optional[int]:
        """Send position roll notification"""
        text = f"""
🔄 <b>POSITION ROLLED</b> (#{trade.get('id', 0)})
━━━━━━━━━━━━━━━━━━━━━━━━━
• New Strike: ${trade.get('strike', 0):,.0f}
• New DTE: {trade.get('dte', 0)} days
• Roll Count: {trade.get('rolled_count', 1)}
        """.strip()

        return self.send_message(text, disable_notification=True)

    def send_signal_alert(self, signal: Dict) -> Optional[int]:
        """Send strong signal alert (without trade)"""
        qsci = signal.get("qsci", 0)
        direction = "BULLISH 🟢" if qsci > 0 else "BEARISH 🔴"

        text = f"""
📡 <b>STRONG SIGNAL DETECTED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
• Direction: {direction}
• QSCI Score: {qsci:.2f}
• BTC Price: ${signal.get('price', 0):,.2f}
• Reason: Entry criteria not met
        """.strip()

        return self.send_message(text, disable_notification=True)

    def test_connection(self) -> bool:
        """Test Telegram bot connection"""
        if not self.config.is_configured:
            logger.error("Telegram not configured")
            return False

        result = self._make_request("getMe", {})
        if result:
            bot_info = result.get("result", {})
            logger.info(f"✓ Connected to Telegram as @{bot_info.get('username')}")
            return True
        return False


# Standalone test
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if "--test" in sys.argv:
        notifier = TelegramNotifier()

        if notifier.test_connection():
            print("✓ Bot connection successful!")

            # Send test message
            msg_id = notifier.send_message(
                "🧪 <b>Test Message</b>\nQSCI Trading Bot v2.0 - Interactive Mode!\n\nSend /help for commands.",
                parse_mode="HTML"
            )

            if msg_id:
                print(f"✓ Test message sent (ID: {msg_id})")

                # Start polling for 30 seconds
                print("Starting command polling for 30 seconds...")
                print("Send a command to your bot to test!")
                notifier.start_polling()
                time.sleep(30)
                notifier.stop_polling()
                print("Polling stopped")
            else:
                print("✗ Failed to send test message")
        else:
            print("✗ Bot connection failed")
            sys.exit(1)
    elif "--interactive" in sys.argv:
        notifier = TelegramNotifier()
        if notifier.test_connection():
            print("Starting interactive mode - Press Ctrl+C to stop")
            notifier.start_polling()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                notifier.stop_polling()
                print("\nStopped")
    else:
        print("Usage: python telegram_notifier.py --test")
        print("       python telegram_notifier.py --interactive")
        print("\nRequired environment variables:")
        print("  TELEGRAM_BOT_TOKEN - Your bot token from @BotFather")
        print("  TELEGRAM_CHANNEL_ID - Your channel ID (e.g., -1001234567890)")
