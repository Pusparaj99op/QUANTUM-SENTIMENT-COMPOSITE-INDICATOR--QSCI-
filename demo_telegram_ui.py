#!/usr/bin/env python3
"""
Enhanced Telegram Bot - Interactive Demo
Shows all the new features with mock data
"""

import os
import sys
from datetime import datetime
from telegram_notifier import TelegramNotifier

def demo_enhanced_features():
    """Demonstrate the enhanced Telegram bot features"""
    
    print("=" * 60)
    print("📱 ENHANCED TELEGRAM BOT DEMO")
    print("=" * 60)
    print()
    
    # Check if configured
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")
    
    if not token or not chat_id:
        print("⚠️  Telegram not configured!")
        print()
        print("To use the enhanced bot, set environment variables:")
        print("  export TELEGRAM_BOT_TOKEN='your_bot_token'")
        print("  export TELEGRAM_CHANNEL_ID='your_chat_id'")
        print()
        print("Get your bot token from: @BotFather on Telegram")
        print("Get your chat ID by sending /start to @userinfobot")
        print()
        return False
    
    print("✓ Telegram configured")
    print(f"  Token: {token[:10]}...{token[-4:]}")
    print(f"  Chat ID: {chat_id}")
    print()
    
    # Initialize bot
    notifier = TelegramNotifier()
    
    # Test connection
    print("Testing connection...")
    if notifier.test_connection():
        print("✓ Connected successfully!")
    else:
        print("✗ Connection failed")
        return False
    
    print()
    print("=" * 60)
    print("SENDING ENHANCED UI DEMOS")
    print("=" * 60)
    print()
    
    # Demo 1: Status with buttons
    print("1️⃣  Sending Status Dashboard with Interactive Buttons...")
    status_text = """
🟢 <b>QSCI Trading Bot Status</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>Trading:</b> Active (Demo Mode)
💰 <b>Balance:</b> $10,234.56
📈 <b>Total P&L:</b> +$1,234.56
📂 <b>Open Positions:</b> 2
🕐 <b>Started:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Use buttons below for navigation
    """.strip()
    
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
    
    notifier.send_message(status_text, reply_markup=keyboard)
    print("   ✓ Sent with 6 interactive buttons")
    print()
    
    import time
    time.sleep(2)
    
    # Demo 2: Stats Dashboard
    print("2️⃣  Sending Statistics Dashboard...")
    stats_text = """
📊 <b>Trading Statistics Dashboard</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

📹 <b>Performance Summary</b>
• Total Trades: 47
• Wins: 32 | Losses: 15
• Win Rate: 68.1%
• Profit Factor: 2.34

💵 <b>Financial Metrics</b>
• Initial Balance: $10,000.00
• Current Balance: $11,234.56
• Total P&L: +$1,234.56
• Return: +12.35%

📈 <b>Trade Quality</b>
• Avg Win: $125.50
• Avg Loss: -$85.20
• Win/Loss Ratio: 1.47x

📉 <b>Risk Metrics</b>
• Max Drawdown: -8.5%
• Open Positions: 2
• Open P&L: +$45.80

📅 <b>Today's Activity</b>
• Trades: 3
• P&L: +$156.00
• Wins: 2 | Losses: 1

━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 Updated: {datetime.now().strftime('%H:%M:%S')}
    """.strip()
    
    stats_keyboard = {
        "inline_keyboard": [
            [{"text": "🔄 Refresh", "callback_data": "stats"},
             {"text": "📋 Trades", "callback_data": "trades"}],
            [{"text": "📂 Positions", "callback_data": "positions"},
             {"text": "🏠 Home", "callback_data": "status"}]
        ]
    }
    
    notifier.send_message(stats_text, reply_markup=stats_keyboard)
    print("   ✓ Sent comprehensive statistics")
    print()
    
    time.sleep(2)
    
    # Demo 3: Settings Panel
    print("3️⃣  Sending Interactive Settings Panel...")
    settings_text = """
⚙️ <b>Trading Settings</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Position Management</b>
• Max Concurrent: 2 positions
• Risk per Trade: 2.5%

📈 <b>Entry Criteria</b>
• Min QSCI: 0.12
• Min ADX: 20
• Max IV Rank: 60%

━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Click below to adjust settings
    """.strip()
    
    settings_keyboard = {
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
    
    notifier.send_message(settings_text, reply_markup=settings_keyboard)
    print("   ✓ Sent with 8 adjustment buttons")
    print()
    
    time.sleep(2)
    
    # Demo 4: Trade Notification
    print("4️⃣  Sending Enhanced Trade Notification...")
    trade_text = """
🟢 <b>LONG POSITION OPENED</b> (#42)
━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Trade Details:</b>
   • Type: CALL Option
   • Strike: $98,500
   • Entry: $450.00
   • Quantity: 5 contracts
   • Value: $2,250.00

📈 <b>Analysis:</b>
   • QSCI Score: 0.18
   • Predicted: Bullish 📈
   • Support: $96,000
   • Resistance: $102,000
   • ADX: 28.5

📰 <b>News Sentiment:</b> Bullish (0.15)
━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Account: $10,234.56 | Total Trades: 47
    """.strip()
    
    notifier.send_message(trade_text)
    print("   ✓ Sent with enhanced formatting")
    print()
    
    time.sleep(2)
    
    # Demo 5: Help Menu
    print("5️⃣  Sending Interactive Help Menu...")
    help_text = """
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
/setbalance <amt> - Set balance
/settrades <num> - Set max positions
/setrisk <pct> - Set risk per trade

━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Use interactive buttons for easier navigation!
    """.strip()
    
    help_keyboard = {
        "inline_keyboard": [
            [{"text": "📊 Status", "callback_data": "status"},
             {"text": "📈 Stats", "callback_data": "stats"}],
            [{"text": "⚙️ Settings", "callback_data": "settings"}]
        ]
    }
    
    notifier.send_message(help_text, reply_markup=help_keyboard)
    print("   ✓ Sent with quick access buttons")
    print()
    
    print("=" * 60)
    print("✅ DEMO COMPLETE!")
    print("=" * 60)
    print()
    print("Check your Telegram for the enhanced UI!")
    print()
    print("Features demonstrated:")
    print("  ✓ Interactive button navigation")
    print("  ✓ Comprehensive statistics dashboard")
    print("  ✓ Easy parameter adjustment")
    print("  ✓ Rich text formatting")
    print("  ✓ Visual emoji indicators")
    print()
    print("To start interactive mode:")
    print("  python3 telegram_notifier.py --interactive")
    print()
    print("To use with live trading:")
    print("  python3 qsci_live_trader.py")
    print()
    
    return True

if __name__ == "__main__":
    success = demo_enhanced_features()
    sys.exit(0 if success else 1)
