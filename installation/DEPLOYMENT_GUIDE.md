# QSCI Trading Bot - Complete Deployment Guide

<div align="center">

## 🚀 Deploy to Koyeb with MongoDB Atlas & Telegram

**Free Tier Deployment | Paper Trading | Real-time Binance Data**

</div>

---

## Table of Contents

1. [Prerequisites](#-prerequisites)
2. [MongoDB Atlas Setup](#-step-1-mongodb-atlas-setup)
3. [Telegram Bot Setup](#-step-2-telegram-bot-setup)
4. [Koyeb Deployment](#-step-3-koyeb-deployment)
5. [Environment Variables](#-step-4-environment-variables)
6. [Verification](#-step-5-verification)
7. [Monitoring & Maintenance](#-monitoring--maintenance)
8. [Troubleshooting](#-troubleshooting)

---

## 📋 Prerequisites

Before starting, ensure you have:

| Requirement | Sign Up | Free Tier |
|:---|:---|:---:|
| **Koyeb Account** | [koyeb.com](https://app.koyeb.com) | 512MB RAM + 2 vCPU |
| **MongoDB Atlas** | [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) | 512MB Storage |
| **Telegram Account** | Already have one | ✅ Free |
| **GitHub Account** | [github.com](https://github.com) | ✅ Free |
| **Binance Account** | [binance.com](https://www.binance.com) | API Keys (no trading required) |

---

## 🗄️ Step 1: MongoDB Atlas Setup

### 1.1 Create Account & Cluster

1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) and sign up
2. Click **"Build a Database"**
3. Select **"M0 FREE"** tier (Shared)

   ![MongoDB Tier Selection](https://i.imgur.com/placeholder.png)

4. Choose a cloud provider:
   - **AWS** → `eu-west-1` (Ireland) or `us-east-1` (Virginia)
   - Matches well with Koyeb's European servers

5. Name your cluster: `qsci-cluster`
6. Click **"Create"** (takes 1-3 minutes)

### 1.2 Configure Database Access

1. Navigate to **Security** → **Database Access**
2. Click **"Add New Database User"**
3. Set credentials:
   - Username: `qsci_bot`
   - Password: **Generate a strong password** (save it!)
   - Privileges: **"Read and write to any database"**
4. Click **"Add User"**

### 1.3 Configure Network Access

1. Navigate to **Security** → **Network Access**
2. Click **"Add IP Address"**
3. Select **"Allow Access from Anywhere"** (required for Koyeb)
   - This adds `0.0.0.0/0`
   - ⚠️ Security note: This is necessary for cloud deployment
4. Click **"Confirm"**

### 1.4 Get Connection String

1. Navigate to **Deployment** → **Database**
2. Click **"Connect"** on your cluster
3. Select **"Connect your application"**
4. Choose **Driver: Python** and **Version: 3.12 or later**
5. Copy the connection string:
   ```
   mongodb+srv://qsci_bot:<password>@qsci-cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
6. **Replace `<password>`** with your actual password

> [!IMPORTANT]
> Save this connection string securely. You'll need it for Koyeb deployment:
> ```
> MONGODB_URI=mongodb+srv://qsci_bot:YOUR_PASSWORD@qsci-cluster.xxxxx.mongodb.net/qsci_trading?retryWrites=true&w=majority
> ```

---

## 📱 Step 2: Telegram Bot Setup

### 2.1 Create a Bot with BotFather

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow prompts:
   - Bot name: `QSCI Trading Bot` (display name)
   - Bot username: `qsci_yourname_bot` (must end with `_bot`, be unique)
4. BotFather will give you a **token** like:
   ```
   1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789
   ```
5. **Save this token!**

### 2.2 Create a Channel for Logs

1. In Telegram, create a **new channel**:
   - Click hamburger menu → "New Channel"
   - Name: `QSCI Trading Logs`
   - Type: **Private** (recommended) or Public
   - Create the channel

2. Add your bot as **Admin**:
   - Open channel settings → Administrators
   - Add Administrator → Search your bot name
   - Grant permission: **"Post Messages"**

3. Get the **Channel ID**:

   **Method 1: Using @getidsbot**
   - Add @getidsbot to your channel temporarily
   - Forward any message from your channel to @getidsbot
   - It will reply with the channel ID (starts with `-100`)

   **Method 2: Via API**
   - Post a test message in your channel
   - Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Look for `"chat":{"id":-100xxxxxxxxxx}`

4. Your channel ID will look like: `-1001234567890`

> [!TIP]
> **Test your bot token works:**
> ```bash
> curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
> ```
> Should return your bot's info.

---

## ☁️ Step 3: Koyeb Deployment

### 3.1 Prepare Your Repository

1. Fork or push the QSCI project to your GitHub
2. Ensure these files exist in your repo:
   - `Dockerfile`
   - `requirements.txt`
   - `qsci_live_trader.py` (main entry point)

### 3.2 Create Koyeb Service

1. Go to [Koyeb Dashboard](https://app.koyeb.com)
2. Click **"Create Service"**
3. **Important: Select "Worker"**

   ```
   ┌─────────────────────────────────────────────┐
   │ Create service                              │
   ├─────────────────────────────────────────────┤
   │ ○ Web service      ← HTTP endpoints         │
   │ ○ Private service  ← Internal only          │
   │ ○ Sandbox          ← Development IDE        │
   │ ● Worker           ← ✅ SELECT THIS ONE     │
   │ ○ Database         ← Managed DB             │
   └─────────────────────────────────────────────┘
   ```

4. Why **Worker**?
   - No HTTP endpoint needed
   - Runs continuously in background
   - Perfect for trading bots

### 3.3 Configure Build Settings

1. **Source**: Select **GitHub**
2. **Repository**: Choose your QSCI repository
3. **Branch**: `main` or `master`
4. **Build method**: **Dockerfile**
5. **Dockerfile path**: `./Dockerfile`

### 3.4 Configure Service Settings

| Setting | Value |
|:---|:---|
| **Service name** | `qsci-trading-bot` |
| **Region** | `fra` (Frankfurt) - low latency to Binance |
| **Instance type** | `nano` (Free tier: 512MB RAM) |
| **Scale** | 1 instance |
| **Command** | Leave empty (uses Dockerfile CMD) |

### 3.5 Add Environment Variables

Click **"Add variable"** for each:

| Variable | Value | Description |
|:---|:---|:---|
| `TELEGRAM_BOT_TOKEN` | `1234567890:ABC...` | From BotFather |
| `TELEGRAM_CHANNEL_ID` | `-1001234567890` | Your channel ID |
| `MONGODB_URI` | `mongodb+srv://...` | Full connection string |
| `BINANCE_API_KEY` | Your API key | From Binance |
| `BINANCE_API_SECRET` | Your API secret | From Binance |
| `INITIAL_BALANCE` | `10000` | Paper trading balance |
| `TRADING_MODE` | `paper` | Keep as paper trading |

### 3.6 Deploy

1. Click **"Deploy"**
2. Wait for build (first build: ~5-10 minutes due to TA-Lib)
3. Check status turns to **"Running"**

---

## 🔐 Step 4: Environment Variables

### Full List of Environment Variables

Create a `.env` file locally for testing (never commit this!):

```bash
# === TELEGRAM ===
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789
TELEGRAM_CHANNEL_ID=-1001234567890

# === MONGODB ===
MONGODB_URI=mongodb+srv://qsci_bot:YOUR_PASSWORD@qsci-cluster.xxxxx.mongodb.net/qsci_trading?retryWrites=true&w=majority

# === BINANCE (read-only keys are sufficient) ===
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret

# === TRADING (Paper) ===
TRADING_MODE=paper
INITIAL_BALANCE=10000

# === OPTIONAL: News API ===
CRYPTOPANIC_API_KEY=your_cryptopanic_key

# === OPTIONAL: Advanced ===
LOG_LEVEL=INFO
TIMEZONE=UTC
CHECK_INTERVAL_MINUTES=5
```

### Getting Binance API Keys

1. Log in to [Binance](https://www.binance.com)
2. Go to **Profile** → **API Management**
3. Create a new API key
4. **Important**: Only enable **"Read"** permission
5. Copy both the API Key and Secret Key

> [!CAUTION]
> Never enable "Enable Spot & Margin Trading" for a paper trading bot. Read-only access is sufficient and much safer.

---

## ✅ Step 5: Verification

### 5.1 Check Koyeb Logs

1. Go to your Koyeb service dashboard
2. Click **"Logs"** tab
3. Look for these startup messages:
   ```
   ✓ Connected to MongoDB Atlas
   ✓ Telegram bot authenticated
   ✓ Connected to Binance API
   ✓ QSCI Trading Bot started
   ```

### 5.2 Verify Telegram Notifications

Within 5 minutes of deployment, you should receive a startup message in your Telegram channel:

```
🤖 QSCI Trading Bot Started
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Status: Running
💰 Initial Balance: $10,000.00
⏰ Started: 2024-12-07 14:30 UTC
🔄 Checking every: 5 minutes
━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 5.3 Verify MongoDB Data

1. Go to MongoDB Atlas dashboard
2. Click **"Browse Collections"**
3. You should see:
   - `qsci_trading.btc_ohlcv` - Price data
   - `qsci_trading.system_state` - Bot status

---

## 📊 Monitoring & Maintenance

### Daily Summary (Automated)

Every 24 hours, the bot sends a summary to Telegram:

```
📊 DAILY TRADING SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Date: 2024-12-07

💹 Performance:
   • Trades Today: 3
   • Wins: 2 | Losses: 1
   • Win Rate: 66.7%
   • Daily P&L: +$234.50

📈 Cumulative:
   • Total Trades: 142
   • Overall Win Rate: 58.3%
   • Total P&L: +$1,845.32
   • Current Balance: $11,845.32

📉 Risk:
   • Max Drawdown Today: 2.1%
   • Open Positions: 2

🔄 Next Update: In 24 hours
━━━━━━━━━━━━━━━━━━━━━━━━━
```

### MongoDB Storage Monitoring

Check your storage usage in Atlas dashboard:
- **Goal**: Stay under 480MB (leave buffer)
- **Auto-cleanup**: Old data automatically deleted after:
  - OHLCV data: 365 days
  - Trade logs: 180 days

### Koyeb Health Checks

Koyeb automatically restarts your worker if it crashes. Check the **Events** tab for any restart history.

---

## 🔧 Troubleshooting

### Issue: Bot Not Starting

**Check Koyeb Logs for:**

| Error | Solution |
|:---|:---|
| `ModuleNotFoundError: talib` | Dockerfile issue - TA-Lib not building |
| `MongoDB connection failed` | Check `MONGODB_URI` and network access |
| `Telegram API error 401` | Invalid bot token |
| `Telegram API error 400` | Invalid channel ID format |

### Issue: No Telegram Messages

1. Verify bot is admin in channel
2. Check channel ID starts with `-100`
3. Test token: `curl "https://api.telegram.org/bot<TOKEN>/getMe"`

### Issue: MongoDB Connection Timeout

1. Check Network Access in Atlas (should be `0.0.0.0/0`)
2. Verify password doesn't have special characters that need URL encoding
3. Check cluster is not paused (free tier pauses after 60 days of inactivity)

### Issue: Koyeb Build Failing

Check the build logs for:
- Missing Dockerfile
- TA-Lib compilation errors (common - see Dockerfile for fix)
- Memory limit exceeded during build

### Issue: Instance Stops After 1 Hour ("Deep Sleep")

**Symptoms:**
- Logs show: `No traffic detected in the past hour. Transitioning to deep sleep.`
- Instance status changes to "Stopped"
- Bot stops trading after ~1 hour of running

**Cause:**
Koyeb's autoscaling feature puts instances to sleep when no **external HTTP traffic** is detected for 1 hour, even if the container is actively running internal processes.

**Solution (Automatic):**
The bot now **automatically prevents this** by pinging its own health endpoint every 30 minutes, generating the HTTP traffic Koyeb needs to keep the instance active.

You'll see this in the logs periodically:
```
Health endpoint pinged to prevent autoscaling sleep
```

**Manual Alternative - Disable Autoscaling:**

If you want to disable autoscaling entirely in Koyeb:

1. Go to your service in Koyeb dashboard
2. Navigate to **Settings** → **Scaling**
3. Set **Autoscaling** to:
   - Minimum instances: `1`
   - Maximum instances: `1`
4. **Important**: Enable **"Never sleep instances"** if available in your plan

> [!NOTE]
> The automatic self-ping solution is already implemented in the code, so no manual action is needed unless you prefer to configure Koyeb directly.

---

## 📁 Required Files in Repository

Ensure your repo has these files:

```
QUANTUM-SENTIMENT-COMPOSITE-INDICATOR--QSCI-/
├── Dockerfile                 # Container build
├── requirements.txt           # Python dependencies
├── config.py                  # Configuration (updated)
├── qsci_live_trader.py        # Main entry point
├── qsci_backtester_v3.py      # Core trading logic
├── telegram_notifier.py       # Telegram integration
├── mongodb_manager.py         # MongoDB integration
├── .env.example               # Environment template
└── DEPLOYMENT_GUIDE.md        # This file
```

---

## 📝 Quick Reference

### Koyeb CLI Commands (Optional)

```bash
# Install Koyeb CLI
curl -s https://koyeb.com/install-cli.sh | sh

# Login
koyeb login

# View logs
koyeb logs qsci-trading-bot

# Restart service
koyeb redeploy qsci-trading-bot

# View environment
koyeb env list --service qsci-trading-bot
```

### Useful Links

| Resource | URL |
|:---|:---|
| Koyeb Dashboard | https://app.koyeb.com |
| MongoDB Atlas | https://cloud.mongodb.com |
| Binance API Docs | https://binance-docs.github.io/apidocs |
| Telegram Bot API | https://core.telegram.org/bots/api |

---

<div align="center">

**Questions?** Open an issue on GitHub or check the Koyeb community.

**Happy Trading! 📈🤖**

</div>
