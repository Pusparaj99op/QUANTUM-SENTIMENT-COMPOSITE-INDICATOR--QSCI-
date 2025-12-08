# Koyeb Keep-Alive Guide: Preventing Deep Sleep

Your QSCI trading bot is entering "deep sleep" on Koyeb due to lack of external traffic. Here's how to fix it.

## Understanding the Problem

Koyeb's free tier auto-sleeps services after **1 hour of no external HTTP traffic**, even if:
- ✅ Your app is running correctly
- ✅ Internal health checks are working
- ✅ The trading bot is processing data every 5 minutes

The issue: **Koyeb only counts EXTERNAL traffic, not internal health pings.**

---

## Solution 1: Configure Koyeb Health Checks (Recommended)

### Step 1: Update Koyeb Service Settings

1. Go to your Koyeb dashboard
2. Select your QSCI service
3. Click **"Settings"** or **"Edit Service"**
4. Under **"Health Checks"** section, configure:

```yaml
Health Check Settings:
  Protocol: HTTP
  Path: /health
  Port: 8000
  Initial Delay: 30 seconds
  Period: 60 seconds
  Timeout: 10 seconds
  Success Threshold: 1
  Failure Threshold: 3
```

### Step 2: Ensure Port is Exposed

In the same settings, make sure:
- **Ports**: `8000` is exposed
- **Type**: HTTP

### Step 3: Redeploy
Click **"Deploy"** to apply changes.

> **Note**: Koyeb's health checks count as external traffic and will prevent auto-sleep.

---

## Solution 2: External Monitoring Service (Free)

Use a free uptime monitoring service to ping your bot every 5-10 minutes.

### Option A: UptimeRobot (Recommended)

1. Sign up at [uptimerobot.com](https://uptimerobot.com) (free)
2. Click **"Add New Monitor"**
3. Configure:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: QSCI Trading Bot
   - **URL**: `https://your-koyeb-app-url.koyeb.app/health`
   - **Monitoring Interval**: 5 minutes

UptimeRobot will ping your service every 5 minutes, preventing auto-sleep.

### Option B: Cron-Job.org

1. Sign up at [cron-job.org](https://cron-job.org) (free)
2. Create new cron job:
   - **Title**: QSCI Keep-Alive
   - **URL**: `https://your-koyeb-app-url.koyeb.app/health`
   - **Schedule**: Every 5 minutes (`*/5 * * * *`)

### Option C: Another Koyeb Service

Create a tiny "pinger" service that calls your main service:

```python
# pinger.py
import time
import requests
import os

TARGET_URL = os.getenv("TARGET_URL", "https://your-app.koyeb.app/health")

while True:
    try:
        response = requests.get(TARGET_URL, timeout=10)
        print(f"Pinged: {response.status_code}")
    except Exception as e:
        print(f"Ping failed: {e}")
    time.sleep(300)  # 5 minutes
```

---

## Solution 3: Upgrade to Koyeb Paid Plan

Koyeb's **Starter plan** ($5.40/month) removes the auto-sleep limitation.

Benefits:
- No auto-sleep
- Better resources
- 24/7 uptime guaranteed

[View Pricing](https://www.koyeb.com/pricing)

---

## Verification

After implementing a solution, check the logs:

```bash
# You should NOT see this message anymore:
"No traffic detected in the past hour. Transitioning to deep sleep."
```

Instead, you'll see continuous operation:
```
2025-12-08 07:31:18,856 - INFO - 📊 Loaded 7/7 timeframes
2025-12-08 07:36:13,458 - INFO - 📊 Loaded 7/7 timeframes
# ... continues running
```

---

## Recommended Approach

**For Free Tier**: Use **Solution 1 + Solution 2A** together
1. Configure Koyeb health checks properly
2. Add UptimeRobot monitoring

**For Production Trading**: Upgrade to paid plan (Solution 3)

---

## Current Health Check Server

Your bot already has a health check server running at:
- **Port**: 8000
- **Endpoints**: `/`, `/health`, `/healthz`
- **Response**: JSON with status, balance, and open positions

Example response:
```json
{
  "status": "healthy",
  "service": "QSCI Trading Bot",
  "timestamp": "2025-12-08T12:00:00",
  "version": "1.0.0",
  "balance": "$10,000.00",
  "running": true,
  "open_positions": 0
}
```

This is perfect for both Koyeb health checks and external monitoring!

---

## Need Help?

If you're still having issues:
1. Check Koyeb service logs for errors
2. Verify the health endpoint works: `curl https://your-app.koyeb.app/health`
3. Ensure PORT environment variable is set to 8000 in Koyeb
