"""
QSCI Trading Bot - Telegram Notification Module
Sends trade alerts, P&L updates, and daily summaries to Telegram channel

Author: QSCI Trading System
Version: 1.0.0
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig:
    """Telegram configuration from environment variables"""
    bot_token: str = ""
    channel_id: str = ""
    log_retention_days: int = 180
    notification_level: str = "ALL"  # ALL, TRADES_ONLY, SUMMARY_ONLY

    def __post_init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", self.bot_token)
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", self.channel_id)

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.channel_id)


class TelegramNotifier:
    """
    Telegram notification handler for QSCI Trading Bot

    Features:
    - Trade entry/exit notifications
    - Daily P&L summaries
    - Support/Resistance level alerts
    - Error notifications
    - Rate limiting to avoid spam
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

        if self.config.is_configured:
            logger.info("✓ Telegram notifier initialized")
        else:
            logger.warning("⚠️ Telegram not configured - notifications disabled")

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
                     disable_notification: bool = False) -> Optional[int]:
        """
        Send message to configured Telegram channel

        Args:
            text: Message text (HTML or Markdown)
            parse_mode: "HTML" or "Markdown"
            disable_notification: Send silently

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
                asyncio.get_event_loop().run_until_complete(
                    asyncio.sleep(self.min_message_interval - elapsed)
                )

        data = {
            "chat_id": self.config.channel_id,
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

    def send_startup_message(self, balance: float, check_interval: int = 5):
        """Send bot startup notification"""
        text = f"""
🤖 <b>QSCI Trading Bot Started</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Status:</b> Running
💰 <b>Initial Balance:</b> ${balance:,.2f}
⏰ <b>Started:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
🔄 <b>Checking every:</b> {check_interval} minutes
━━━━━━━━━━━━━━━━━━━━━━━━━
        """.strip()

        return self.send_message(text)

    def send_trade_opened(self, trade: Dict, account_balance: float,
                          total_trades: int) -> Optional[int]:
        """
        Send trade opened notification

        Expected trade dict keys:
        - id, option_type, strike, entry_price, quantity, qsci,
        - delta, support, resistance, sentiment_score, adx
        """
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
        """
        Send trade closed notification

        Expected trade dict keys:
        - id, option_type, entry_price, exit_price, quantity,
        - pnl_after_fees, trade_return, status
        """
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
        """
        Send daily trading summary

        Expected stats dict keys:
        - date, trades_today, wins, losses, daily_pnl,
        - total_trades, total_pnl, win_rate, balance,
        - max_drawdown_pct, open_positions
        """
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
                "🧪 <b>Test Message</b>\nQSCI Trading Bot is configured correctly!",
                parse_mode="HTML"
            )

            if msg_id:
                print(f"✓ Test message sent (ID: {msg_id})")
            else:
                print("✗ Failed to send test message")
        else:
            print("✗ Bot connection failed")
            sys.exit(1)
    else:
        print("Usage: python telegram_notifier.py --test")
        print("\nRequired environment variables:")
        print("  TELEGRAM_BOT_TOKEN - Your bot token from @BotFather")
        print("  TELEGRAM_CHANNEL_ID - Your channel ID (e.g., -1001234567890)")
