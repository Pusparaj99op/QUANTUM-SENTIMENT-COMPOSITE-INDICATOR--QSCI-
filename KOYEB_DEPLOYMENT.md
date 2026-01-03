# QSCI Trading Bot - Koyeb Deployment Guide

## Prerequisites

1. **Koyeb Account**: Sign up at [koyeb.com](https://www.koyeb.com)
2. **GitHub Repository**: Push your code to GitHub
3. **Environment Variables Ready**:
   - `BINANCE_API_KEY`
   - `BINANCE_API_SECRET`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

---

## Deployment Steps

### Option 1: Deploy from GitHub (Recommended)

1. **Go to Koyeb Dashboard** → Create Service → GitHub

2. **Connect Repository**:
   - Select your GitHub repository
   - Branch: `main`
   - Dockerfile: `Dockerfile`

3. **Configure Instance**:
   - **Instance Type**: `micro` (1GB RAM, 0.5 vCPU) - $5.36/month
   - **Region**: `fra` (Frankfurt) for lowest latency to Binance
   - **Scaling**: Min 1, Max 1

4. **Set Environment Variables** (in Koyeb dashboard):
   ```
   PORT=8080
   PYTHONUNBUFFERED=1
   TZ=UTC
   BINANCE_API_KEY=your_key_here
   BINANCE_API_SECRET=your_secret_here
   TELEGRAM_BOT_TOKEN=your_token_here
   TELEGRAM_CHAT_ID=your_chat_id
   TRADING_MODE=paper
   ```

5. **Configure Health Check**:
   - Path: `/health/live`
   - Port: 8080
   - Interval: 30s
   - Timeout: 10s
   - Grace Period: 60s

6. **Deploy** → Click "Deploy"

### Option 2: Deploy from Docker Registry

1. **Build and push Docker image**:
   ```bash
   # Build
   docker build -t your-registry/qsci-trading-bot:latest .

   # Push
   docker push your-registry/qsci-trading-bot:latest
   ```

2. **In Koyeb**: Create Service → Docker → Enter image URL

---

## Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Full health report (JSON) |
| `GET /health/live` | Kubernetes-style liveness probe |
| `GET /health/ready` | Kubernetes-style readiness probe |
| `GET /metrics` | Prometheus-compatible metrics |

---

## Local Testing

```bash
# Build locally
docker build -t qsci-bot .

# Run with environment file
docker run -d \
  --name qsci-bot \
  -p 8080:8080 \
  --env-file .env \
  qsci-bot

# Check logs
docker logs -f qsci-bot

# Test health endpoint
curl http://localhost:8080/health
```

---

## Koyeb CLI Deployment

```bash
# Install Koyeb CLI
curl -fsSL https://koyeb.com/install.sh | sh

# Login
koyeb login

# Deploy
koyeb service create qsci-trading-bot \
  --git github.com/YOUR_USERNAME/QUANTUM-SENTIMENT-COMPOSITE-INDICATOR--QSCI- \
  --git-branch main \
  --git-docker-command "python qsci_live_trader.py" \
  --instance-type micro \
  --regions fra \
  --port 8080:http \
  --env PORT=8080 \
  --env BINANCE_API_KEY=@binance-api-key \
  --env BINANCE_API_SECRET=@binance-api-secret \
  --env TELEGRAM_BOT_TOKEN=@telegram-bot-token \
  --env TELEGRAM_CHAT_ID=@telegram-chat-id
```

---

## Monitoring

### Via Telegram
- `/health` - Get system health report
- `/status` - Trading status
- `/balance` - Account balance
- `/positions` - Open positions

### Via HTTP
```bash
curl https://your-app.koyeb.app/health
```

---

## Cost Optimization

| Instance | RAM | CPU | Monthly Cost |
|----------|-----|-----|--------------|
| free | 512MB | shared | $0 (may sleep) |
| nano | 512MB | 0.1 vCPU | $2.68 |
| micro | 1GB | 0.5 vCPU | $5.36 |
| small | 2GB | 1 vCPU | $10.72 |

**Recommendation**: Start with `micro` for reliable operation.

---

## Troubleshooting

### Bot keeps restarting
- Check health endpoint: `curl your-app.koyeb.app/health/live`
- Increase grace period to 120s
- Check logs in Koyeb dashboard

### Connection to Binance fails
- Verify API keys are correct
- Check if testnet mode is enabled/disabled correctly
- Ensure IP whitelist includes Koyeb IPs (or disable IP restriction)

### Telegram not responding
- Verify bot token and chat ID
- Check if bot has admin rights in the chat
- Look for rate limiting errors in logs

---

## Security Best Practices

1. ✅ Never commit API keys to Git
2. ✅ Use Koyeb secrets for sensitive variables
3. ✅ Enable 2FA on Binance and Koyeb
4. ✅ Use IP whitelist on Binance API
5. ✅ Start with paper trading mode
6. ✅ Set up Telegram alerts for trade notifications
