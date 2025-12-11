# QSCI Trading System - Architecture & Future Improvements

This document outlines the current architecture and suggests improvements for the QSCI Trading System.

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    QSCI Trading System v3.0                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐       │
│  │   Binance     │    │     QSCI      │    │   Telegram    │       │
│  │   Data Feed   │───▶│   Backtester  │───▶│   Notifier    │       │
│  │   (REST/WS)   │    │   Engine      │    │   (Polling)   │       │
│  └───────────────┘    └───────────────┘    └───────────────┘       │
│          │                    │                    │                │
│          │                    ▼                    │                │
│          │           ┌───────────────┐             │                │
│          │           │   MongoDB     │             │                │
│          │           │   Manager     │◀────────────┘                │
│          │           │  (Persistence)│                              │
│          │           └───────────────┘                              │
│          │                                                          │
│          ▼                                                          │
│  ┌───────────────────────────────────────────────────────┐         │
│  │              Multi-Timeframe Data Manager             │         │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌────┐ ┌───┐ │         │
│  │  │ 4h  │ │ 2h  │ │ 1h  │ │30m  │ │15m  │ │5m  │ │1m │ │         │
│  │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └────┘ └───┘ │         │
│  └───────────────────────────────────────────────────────┘         │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────┐         │
│  │           Vectorized Technical Analysis               │         │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │         │
│  │  │ Momentum │ │  Trend   │ │  Volume  │ │Volatility│  │         │
│  │  │ Signals  │ │ Signals  │ │ Signals  │ │ Signals  │  │         │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │         │
│  └───────────────────────────────────────────────────────┘         │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────┐         │
│  │              QSCI Signal Generation                   │         │
│  │         (Weighted Multi-TF Blending + NLP)            │         │
│  └───────────────────────────────────────────────────────┘         │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────┐         │
│  │           Black-Scholes Options Pricing               │         │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌────────────┐   │         │
│  │  │Delta │ │Gamma │ │ Vega │ │Theta │ │Fair Value  │   │         │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └────────────┘   │         │
│  └───────────────────────────────────────────────────────┘         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Telegram Notification Architecture

### Current: Long Polling (v2.1)

```
┌────────────────┐         ┌────────────────┐
│   QSCI Bot     │         │   Telegram     │
│   (Client)     │         │   Servers      │
├────────────────┤         ├────────────────┤
│                │         │                │
│  Every 5s:     │         │                │
│  GET /updates  │────────▶│  Return new    │
│                │◀────────│  messages      │
│                │         │                │
│  Process       │         │                │
│  commands      │         │                │
│                │         │                │
│  Send response │────────▶│  Deliver to    │
│                │         │  user          │
└────────────────┘         └────────────────┘

Pros:
✓ Simple to implement
✓ Works behind NAT/firewalls
✓ No public IP required
✓ Easy to debug

Cons:
✗ 5+ second latency for commands
✗ Constant polling = wasted resources
✗ Not real-time
```

### Recommended Future: Webhooks

```
┌────────────────┐         ┌────────────────┐
│   QSCI Bot     │         │   Telegram     │
│   (Server)     │         │   Servers      │
├────────────────┤         ├────────────────┤
│                │         │                │
│  /webhook      │◀────────│  POST message  │
│  endpoint      │         │  instantly     │
│                │         │                │
│  Process       │         │                │
│  immediately   │         │                │
│                │         │                │
│  Send response │────────▶│  Deliver to    │
│                │         │  user          │
└────────────────┘         └────────────────┘

Pros:
✓ <100ms latency
✓ Real-time responses
✓ No polling overhead
✓ Scalable

Cons:
✗ Requires public IP/domain
✗ Requires HTTPS certificate
✗ More complex setup
```

## Implementing Webhooks

### Prerequisites
1. Public domain or IP address
2. HTTPS certificate (Let's Encrypt or similar)
3. Open port 443, 80, 88, or 8443

### Example Implementation

```python
# telegram_webhook.py
from flask import Flask, request
import ssl

app = Flask(__name__)

@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    """Receive Telegram updates via webhook"""
    if token != BOT_TOKEN:
        return 'Unauthorized', 403

    update = request.get_json()
    process_update(update)
    return 'OK', 200

def setup_webhook(bot_token: str, webhook_url: str):
    """Register webhook with Telegram"""
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    data = {
        "url": webhook_url,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True
    }
    response = requests.post(url, json=data)
    return response.json()

if __name__ == '__main__':
    # Setup webhook on startup
    setup_webhook(BOT_TOKEN, f"https://yourdomain.com/webhook/{BOT_TOKEN}")

    # Run with HTTPS
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_cert_chain('cert.pem', 'key.pem')
    app.run(host='0.0.0.0', port=8443, ssl_context=context)
```

### Koyeb Deployment with Webhooks

Since Koyeb provides HTTPS by default, webhooks are straightforward:

```yaml
# koyeb.yaml
name: qsci-trading-bot
type: web

# This enables the webhook endpoint
ports:
  - port: 8000
    protocol: http

env:
  - name: TELEGRAM_WEBHOOK_URL
    value: "https://qsci-bot.koyeb.app/webhook"
```

## Additional Suggestions

### 1. Message Priority Queue

```python
class PriorityNotifier:
    """Send critical messages first"""

    PRIORITY_LEVELS = {
        'error': 0,      # Immediate
        'trade_close': 1, # High
        'trade_open': 2,  # Medium
        'signal': 3,      # Low
        'info': 4         # Batch-able
    }

    def send(self, message: str, priority: str = 'info'):
        level = self.PRIORITY_LEVELS.get(priority, 4)
        heapq.heappush(self.queue, (level, time.time(), message))
```

### 2. Telegram Inline Keyboards

```python
def send_trade_with_actions(trade: Dict):
    """Send trade notification with action buttons"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approve_{trade['id']}"},
                {"text": "❌ Reject", "callback_data": f"reject_{trade['id']}"}
            ],
            [
                {"text": "📊 Details", "callback_data": f"details_{trade['id']}"}
            ]
        ]
    }
    return send_message(text, reply_markup=keyboard)
```

### 3. Notification Channels

```python
class NotificationRouter:
    """Route notifications to appropriate channels"""

    CHANNELS = {
        'trades': '@qsci_trades',      # Public trade alerts
        'signals': '@qsci_signals',    # Public signals
        'errors': -100123456,          # Private error channel
        'admin': 123456789             # Admin DM
    }

    def route(self, notification_type: str, message: str):
        channel = self.CHANNELS.get(notification_type, self.CHANNELS['admin'])
        self.send(channel, message)
```

### 4. Message Templates

```python
from jinja2 import Template

TEMPLATES = {
    'trade_open': Template("""
🟢 <b>{{ option_type }} OPENED</b> #{{ id }}
━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Strike: ${{ strike|round(0) }}
📈 Entry: ${{ entry_price|round(2) }}
🎯 QSCI: {{ qsci|round(3) }}
━━━━━━━━━━━━━━━━━━━━━━━━━
    """),
}

def render_notification(template_name: str, **kwargs) -> str:
    return TEMPLATES[template_name].render(**kwargs)
```

## Performance Metrics

| Metric | Polling (Current) | Webhooks (Future) |
|--------|------------------|-------------------|
| Command Latency | 2-10 seconds | <100ms |
| API Calls/Hour | ~720 (polling) | ~0 (on-demand) |
| Server Load | Constant | Event-driven |
| Scalability | Limited | High |

## Migration Path

1. **Phase 1 (Current)**: Polling with rate limiting ✅
2. **Phase 2**: Add webhook endpoint alongside polling
3. **Phase 3**: Switch to webhooks when deployed on public URL
4. **Phase 4**: Remove polling code, webhook-only

## Environment Variables for Webhooks

```bash
# Add to .env or Koyeb secrets
TELEGRAM_WEBHOOK_MODE=true
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook
TELEGRAM_WEBHOOK_SECRET=your-random-secret-for-validation
```

## Conclusion

The current polling implementation (v2.1) is suitable for development and private deployments. When deploying to production with a public URL (e.g., Koyeb, Railway, Render), migrating to webhooks will provide:

- **10-100x faster** response times
- **Lower server load** (no constant polling)
- **Better user experience** with real-time interactions
- **Improved scalability** for multiple users

The migration is non-breaking and can be done incrementally.
