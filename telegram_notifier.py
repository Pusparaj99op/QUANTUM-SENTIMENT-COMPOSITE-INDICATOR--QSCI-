"""
QSCI Trading Bot - Enhanced Telegram Notification Module
Sends trade alerts, P&L updates, and daily summaries to Telegram channel
Now with INTERACTIVE COMMANDS support!

Author: QSCI Trading System
Version: 2.0.0 - Interactive Bot
"""

import os
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Callable
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

    def __post_init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", self.bot_token)
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", self.channel_id)

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.channel_id)


class TelegramNotifier:
    """
    Enhanced Telegram notification handler for QSCI Trading Bot

    Features:
    - Trade entry/exit notifications
    - Daily P&L summaries
    - Support/Resistance level alerts
    - Error notifications
    - Rate limiting to avoid spam
    - INTERACTIVE COMMANDS (NEW)
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

        # Interactive bot state
        self.last_update_id = 0
        self.polling_active = False
        self.polling_thread: Optional[threading.Thread] = None
        self.command_handlers: Dict[str, Callable] = {}
        self.trader_reference = None  # Reference to live trader for status
        self.is_trading_paused = False

        if self.config.is_configured:
            logger.info("✓ Telegram notifier initialized (Interactive Mode)")
        else:
            logger.warning("⚠️ Telegram not configured - notifications disabled")

    def set_trader_reference(self, trader):
        """Set reference to live trader for status commands"""
        self.trader_reference = trader

    def _make_request(self, method: str, data: Dict) -> Optional[Dict]:
        """Make API request to Telegram"""
        if not self.config.is_configured:
            return None

        url = self.BASE_URL.format(token=self.config.bot_token, method=method)

        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()

            if not result.get("ok"):
                logger.error(f"Telegram API error: {result.get('description')}")
                return None

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
                     chat_id: str = None) -> Optional[int]:
        """
        Send message to configured Telegram channel or specific chat

        Args:
            text: Message text (HTML or Markdown)
            parse_mode: "HTML" or "Markdown"
            disable_notification: Send silently
            chat_id: Override channel_id for direct replies

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
                "allowed_updates": ["message"]
            }
            response = requests.get(url, params=params, timeout=15)
            data = response.json()

            if not data.get("ok"):
                return

            for update in data.get("result", []):
                self.last_update_id = update["update_id"]
                message = update.get("message", {})
                text = message.get("text", "")
                chat_id = str(message.get("chat", {}).get("id", ""))

                if text.startswith("/"):
                    self._handle_command(text, chat_id)
                elif text:
                    # Echo back non-command messages
                    self.send_message(
                        f"📝 Received: <i>{text[:100]}</i>\n\nUse /help for available commands.",
                        chat_id=chat_id
                    )

        except Exception as e:
            logger.debug(f"Update fetch failed: {e}")

    def _handle_command(self, text: str, chat_id: str):
        """Process an incoming bot command"""
        parts = text.split()
        command = parts[0].lower().replace("@", "").split("@")[0]  # Handle @botname suffix
        args = parts[1:] if len(parts) > 1 else []

        logger.info(f"📥 Command received: {command} from {chat_id}")

        if command == "/status":
            self._cmd_status(chat_id)
        elif command == "/balance":
            self._cmd_balance(chat_id)
        elif command == "/trades":
            self._cmd_trades(chat_id)
        elif command == "/positions":
            self._cmd_positions(chat_id)
        elif command == "/stop":
            self._cmd_stop(chat_id)
        elif command == "/start":
            self._cmd_start(chat_id)
        elif command == "/help":
            self._cmd_help(chat_id)
        elif command == "/setbalance" and args:
            self._cmd_setbalance(chat_id, args[0])
        else:
            self.send_message(
                f"❓ Unknown command: <code>{command}</code>\n\nUse /help for available commands.",
                chat_id=chat_id
            )

    def _cmd_status(self, chat_id: str):
        """Handle /status command - show current trading status"""
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
        else:
            text = """
📊 <b>Bot Status</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ No trader connected
Use with qsci_live_trader.py
            """.strip()

        self.send_message(text, chat_id=chat_id)

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

    def _cmd_help(self, chat_id: str):
        """Handle /help command - show available commands"""
        text = """
🤖 <b>QSCI Bot Commands</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
/status - Current bot status
/balance - Detailed balance info
/trades - Recent trades list
/positions - Open positions
/stop - Pause trading
/start - Resume trading
/setbalance &lt;amt&gt; - Set balance
/help - This message
━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Send any text for acknowledgement
        """.strip()
        self.send_message(text, chat_id=chat_id)

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

