#!/bin/bash
# Quick Setup Script for QSCI Keep-Alive System
# Run this after deploying to Koyeb

echo "=================================="
echo "QSCI Keep-Alive Setup"
echo "=================================="
echo ""

# Get Koyeb service URL
echo "📍 Step 1: Get your Koyeb service URL"
echo "   Go to: https://app.koyeb.com/services"
echo "   Copy your service URL (e.g., https://your-app-abc123.koyeb.app)"
echo ""
read -p "   Enter your Koyeb service URL: " KOYEB_URL

# Validate URL
if [[ ! $KOYEB_URL =~ ^https:// ]]; then
    echo "   ⚠ Adding https:// prefix"
    KOYEB_URL="https://$KOYEB_URL"
fi

# Remove trailing slash
KOYEB_URL="${KOYEB_URL%/}"

HEALTH_URL="${KOYEB_URL}/health"

echo ""
echo "✓ Health check URL: $HEALTH_URL"
echo ""

# Test health endpoint
echo "📊 Step 2: Testing health endpoint..."
if command -v curl &> /dev/null; then
    response=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" --max-time 10)
    if [ "$response" == "200" ]; then
        echo "   ✓ Health endpoint is accessible!"
        curl -s "$HEALTH_URL" | python3 -m json.tool 2>/dev/null || echo "   Response received"
    else
        echo "   ⚠ Warning: Got HTTP $response"
        echo "   Make sure your service is deployed and running"
    fi
else
    echo "   ⚠ curl not found, skipping test"
fi

echo ""
echo "=================================="
echo "Next Steps:"
echo "=================================="
echo ""
echo "1. ✅ Configure Koyeb Health Checks:"
echo "   - Go to: https://app.koyeb.com/services"
echo "   - Edit your service → Health Checks"
echo "   - Path: /health"
echo "   - Port: 8000"
echo "   - Interval: 60 seconds"
echo ""
echo "2. ✅ Set up UptimeRobot:"
echo "   - Go to: https://dashboard.uptimerobot.com/dashboard?addMonitor=1"
echo "   - Monitor Type: HTTP(s)"
echo "   - URL: $HEALTH_URL"
echo "   - Interval: 5 minutes"
echo ""
echo "3. ✅ (Optional) Deploy pinger service:"
echo "   - Create new Koyeb service"
echo "   - Use Dockerfile.pinger"
echo "   - Set TARGET_URL=$HEALTH_URL"
echo ""
echo "=================================="
echo "Your URLs for reference:"
echo "=================================="
echo "Service URL: $KOYEB_URL"
echo "Health URL:  $HEALTH_URL"
echo ""
echo "Copy these URLs for UptimeRobot and pinger configuration!"
echo "=================================="
