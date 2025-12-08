# Complete Keep-Alive Deployment Guide

This guide walks you through ALL methods to prevent Koyeb auto-sleep for your QSCI trading bot.

## 🎯 Multi-Layer Protection Strategy

We'll implement **3 layers** of protection:
1. ✅ Koyeb health check configuration
2. ✅ External monitoring with UptimeRobot
3. ✅ Backup pinger service

---

## Layer 1: Koyeb Health Check Configuration

### Option A: Using koyeb.yaml (Recommended)

The `koyeb.yaml` file is already configured. Deploy using Koyeb CLI:

```bash
# Install Koyeb CLI
curl -fsSL https://cli.koyeb.com/install.sh | sh

# Login
koyeb login

# Deploy with configuration file
koyeb service create --config koyeb.yaml
```

### Option B: Manual Configuration in Koyeb Dashboard

1. Go to [Koyeb Dashboard](https://app.koyeb.com)
2. Select your QSCI service
3. Click **"Settings"** → **"Edit Service"**
4. Configure:

**Health Checks:**
```
Protocol: HTTP
Path: /health
Port: 8000
Initial Delay: 30 seconds
Interval: 60 seconds
Timeout: 10 seconds
Grace Period: 30 seconds
Restart Limit: 3
```

**Ports:**
```
Port: 8000
Protocol: HTTP
Public: Yes (expose the health endpoint)
```

5. Click **"Deploy"**

---

## Layer 2: External Monitoring (UptimeRobot)

### Step 1: Get Your Koyeb Service URL

```bash
# Find your service URL in Koyeb dashboard
# It will look like: https://your-app-abc123.koyeb.app
```

### Step 2: Set Up UptimeRobot

1. Go to [https://uptimerobot.com](https://uptimerobot.com)
2. Click **"Sign Up"** (free account)
3. After login, click **"Add New Monitor"**
4. Configure:

```
Monitor Type: HTTP(s)
Friendly Name: QSCI Trading Bot
URL: https://your-app-abc123.koyeb.app/health
Monitoring Interval: 5 minutes
Alert Contacts: Your email
```

5. Click **"Create Monitor"**

**Done!** UptimeRobot will now ping your service every 5 minutes.

### Bonus: Email Alerts

UptimeRobot will email you if your service goes down, giving you double monitoring!

---

## Layer 3: Backup Pinger Service

Deploy the included `keep_alive_pinger.py` as a separate Koyeb service.

### Step 1: Create New Koyeb Service

1. In Koyeb dashboard, click **"Create Service"**
2. Choose **"GitHub"** (or upload code)
3. Select your repository
4. Configure:

```
Service Name: qsci-pinger
Type: Worker
Builder: Dockerfile
Dockerfile: Dockerfile.pinger
Instance Type: Nano (smallest)
```

### Step 2: Set Environment Variables

```bash
TARGET_URL=https://your-main-qsci-bot.koyeb.app/health
PING_INTERVAL_SECONDS=300
PING_TIMEOUT_SECONDS=10

# Optional: Telegram alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Step 3: Deploy

Click **"Deploy"** and the pinger will start automatically.

### Running Pinger Locally (Alternative)

If you prefer to run the pinger on your local machine:

```bash
# Install dependencies
pip install requests

# Set environment variables
export TARGET_URL=https://your-app.koyeb.app/health
export PING_INTERVAL_SECONDS=300

# Run the pinger
python keep_alive_pinger.py
```

Keep this running 24/7 on your computer or a VPS.

---

## 🔍 Verification

### 1. Check Health Endpoint

```bash
curl https://your-app.koyeb.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "QSCI Trading Bot",
  "timestamp": "2025-12-08T20:16:10",
  "version": "1.0.0",
  "balance": "$10,000.00",
  "running": true,
  "open_positions": 0
}
```

### 2. Monitor Koyeb Logs

```bash
# In Koyeb dashboard, view logs
# You should see:
📊 Loaded 7/7 timeframes
BTC Price: $90,346.70
📊 Multi-TF QSCI: 0.076 (blend of 7 timeframes)

# You should NOT see:
❌ "No traffic detected in the past hour. Transitioning to deep sleep."
```

### 3. Check UptimeRobot Status

In UptimeRobot dashboard, your monitor should show:
- ✅ **Status**: Up
- ✅ **Uptime**: 100%
- 📊 **Response Time**: ~200-500ms

---

## 📊 Keep-Alive Status Summary

After implementing all layers:

| Layer | Status | Ping Interval | Cost |
|-------|--------|---------------|------|
| Koyeb Health Checks | ✅ Active | 60 seconds | Free |
| UptimeRobot | ✅ Active | 5 minutes | Free |
| Pinger Service | ✅ Active | 5 minutes | Free* |

*Uses free tier resources

---

## 🚨 Troubleshooting

### Issue: Still seeing "deep sleep" message

**Solution:**
1. Verify health endpoint is accessible externally
2. Check Koyeb port 8000 is exposed publicly
3. Ensure UptimeRobot monitor is active (check your email for confirmation)

### Issue: Health endpoint returns 404

**Solution:**
```bash
# Check if service is running
# Verify PORT environment variable is set to 8000 in Koyeb
# Redeploy the service
```

### Issue: UptimeRobot shows "Down"

**Solution:**
1. Check Koyeb service is running
2. Verify URL is correct (include https://)
3. Test endpoint manually: `curl https://your-app.koyeb.app/health`

---

## 💡 Best Practices

### For Free Tier Users
✅ Use Koyeb health checks + UptimeRobot
✅ Set UptimeRobot to 5-minute intervals
✅ Enable email alerts in UptimeRobot

### For Serious Trading
✅ Upgrade to Koyeb Starter plan ($5.40/month)
✅ No auto-sleep guarantees 24/7 uptime
✅ Better performance and resources

### For Maximum Reliability
✅ All 3 layers (health checks + UptimeRobot + pinger)
✅ Multiple monitoring services (UptimeRobot + Cron-job.org)
✅ Telegram alerts enabled

---

## 📝 Files Created

- ✅ `koyeb.yaml` - Koyeb service configuration
- ✅ `keep_alive_pinger.py` - Standalone pinger service
- ✅ `Dockerfile.pinger` - Docker image for pinger
- ✅ `KOYEB_KEEP_ALIVE_GUIDE.md` - Detailed explanation
- ✅ `DEPLOYMENT_KEEP_ALIVE.md` - This deployment guide

---

## 🎉 Success!

Once all layers are active, your QSCI trading bot will run 24/7 without interruption.

Verify by checking logs after 1-2 hours - you should see continuous trading activity without any "deep sleep" messages.

Happy trading! 📈
