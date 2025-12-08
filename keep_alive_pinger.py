"""
Keep-Alive Pinger Service
Pings the main QSCI trading bot to prevent Koyeb auto-sleep

This is a lightweight service that can be deployed separately
to ping your main trading bot service every few minutes.

Deploy this as a separate Koyeb service or run locally.
"""

import os
import time
import logging
import requests
from datetime import datetime
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
TARGET_URL = os.getenv("TARGET_URL", "http://localhost:8000/health")
PING_INTERVAL = int(os.getenv("PING_INTERVAL_SECONDS", "300"))  # 5 minutes
TIMEOUT = int(os.getenv("PING_TIMEOUT_SECONDS", "10"))

# Optional: Send alerts via Telegram if pinging fails
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_telegram_alert(message: str):
    """Send alert to Telegram if configured"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚨 Keep-Alive Pinger Alert\n\n{message}",
            "parse_mode": "HTML"
        }
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")


def ping_service(url: str) -> Optional[dict]:
    """
    Ping the target service and return response data

    Args:
        url: Target health check URL

    Returns:
        Response JSON if successful, None otherwise
    """
    try:
        response = requests.get(url, timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"✓ Ping successful: {data.get('status', 'unknown')}")

            # Log additional info if available
            if 'balance' in data:
                logger.info(f"  Balance: {data['balance']}")
            if 'open_positions' in data:
                logger.info(f"  Open Positions: {data['open_positions']}")

            return data
        else:
            logger.warning(f"⚠ Ping returned status {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"✗ Ping timeout after {TIMEOUT}s")
        send_telegram_alert(f"Ping timeout to {url}")
        return None

    except requests.exceptions.ConnectionError:
        logger.error(f"✗ Connection error to {url}")
        send_telegram_alert(f"Connection error to {url}")
        return None

    except Exception as e:
        logger.error(f"✗ Ping failed: {e}")
        send_telegram_alert(f"Ping failed: {str(e)}")
        return None


def main():
    """Main pinger loop"""
    logger.info("=" * 60)
    logger.info("QSCI Keep-Alive Pinger Started")
    logger.info("=" * 60)
    logger.info(f"Target URL: {TARGET_URL}")
    logger.info(f"Ping Interval: {PING_INTERVAL}s ({PING_INTERVAL/60:.1f} minutes)")
    logger.info(f"Timeout: {TIMEOUT}s")
    logger.info("=" * 60)

    consecutive_failures = 0
    max_failures = 5

    while True:
        try:
            logger.info(f"Pinging {TARGET_URL}...")
            result = ping_service(TARGET_URL)

            if result:
                consecutive_failures = 0
            else:
                consecutive_failures += 1

                if consecutive_failures >= max_failures:
                    alert_msg = (
                        f"Service has failed {consecutive_failures} consecutive pings!\n"
                        f"Target: {TARGET_URL}\n"
                        f"Time: {datetime.utcnow().isoformat()}"
                    )
                    logger.critical(alert_msg)
                    send_telegram_alert(alert_msg)
                    consecutive_failures = 0  # Reset to avoid spam

            # Wait for next ping
            logger.info(f"Waiting {PING_INTERVAL}s until next ping...")
            time.sleep(PING_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Pinger stopped by user")
            break

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(60)  # Wait 1 minute before retrying


if __name__ == "__main__":
    main()
