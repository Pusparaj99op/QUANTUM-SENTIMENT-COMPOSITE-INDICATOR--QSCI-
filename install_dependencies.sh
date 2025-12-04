#!/bin/bash

################################################################################
# QSCI BTC Options Backtester - Automated Installation Script
# For Ubuntu 22.04 LTS
# Usage: chmod +x install_dependencies.sh && ./install_dependencies.sh
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                 QSCI BTC Options Backtester                        ║"
echo "║          Automated Installation for Ubuntu 22.04 LTS              ║"
echo "║                      Version 2.0                                   ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running on Ubuntu
if ! grep -q "Ubuntu" /etc/os-release; then
    echo -e "${RED}✗ This script is designed for Ubuntu. Please install manually.${NC}"
    exit 1
fi

echo -e "${YELLOW}→ Starting installation...${NC}\n"

# Step 1: Update system packages
echo -e "${BLUE}[1/7] Updating system packages...${NC}"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
echo -e "${GREEN}✓ System packages updated${NC}\n"

# Step 2: Install system dependencies
echo -e "${BLUE}[2/7] Installing system dependencies...${NC}"
sudo apt-get install -y -qq \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    wget \
    curl

echo -e "${GREEN}✓ System dependencies installed${NC}\n"

# Step 3: Install TA-Lib system library (compile from source)
echo -e "${BLUE}[3/7] Installing TA-Lib system library...${NC}"

# Check if TA-Lib is already installed
if [ -f "/usr/local/lib/libta_lib.so" ] || [ -f "/usr/lib/libta_lib.so" ]; then
    echo -e "${YELLOW}→ TA-Lib already installed, skipping...${NC}"
else
    echo "  → Downloading TA-Lib source..."
    cd /tmp
    wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
    tar -xzf ta-lib-0.4.0-src.tar.gz
    cd ta-lib/
    
    echo "  → Configuring TA-Lib..."
    ./configure --prefix=/usr/local > /dev/null 2>&1
    
    echo "  → Compiling TA-Lib (this may take a few minutes)..."
    make -j$(nproc) > /dev/null 2>&1
    
    echo "  → Installing TA-Lib..."
    sudo make install > /dev/null 2>&1
    
    # Update library cache
    sudo ldconfig
    
    # Cleanup
    cd /tmp
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz
    
    cd - > /dev/null
fi

echo -e "${GREEN}✓ TA-Lib system library installed${NC}\n"

# Step 4: Create virtual environment
echo -e "${BLUE}[4/7] Creating Python virtual environment...${NC}"
if [ -d "qsci_venv" ] && [ -f "qsci_venv/bin/activate" ]; then
    echo -e "${YELLOW}→ Virtual environment already exists, skipping...${NC}"
else
    # Remove broken venv if it exists
    if [ -d "qsci_venv" ]; then
        echo -e "${YELLOW}→ Removing broken virtual environment...${NC}"
        rm -rf qsci_venv
    fi
    python3 -m venv qsci_venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
source qsci_venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}\n"

# Step 5: Upgrade pip, setuptools, wheel
echo -e "${BLUE}[5/7] Upgrading pip, setuptools, and wheel...${NC}"
pip install --quiet --upgrade pip setuptools wheel
echo -e "${GREEN}✓ pip upgraded${NC}\n"

# Step 6: Install Python packages
echo -e "${BLUE}[6/7] Installing Python packages...${NC}"

# Core packages
echo "  → Installing pandas, numpy, scipy..."
pip install --quiet pandas==2.0.3 numpy==1.24.3 scipy==1.11.1

# Binance API
echo "  → Installing Binance API client..."
pip install --quiet python-binance==1.0.17

# Technical Indicators
echo "  → Installing TA-Lib and technical analysis tools..."
pip install --quiet TA-Lib ta

# Visualization
echo "  → Installing matplotlib and seaborn..."
pip install --quiet matplotlib==3.7.2 seaborn==0.12.2

# Utilities
echo "  → Installing python-dotenv and colorama..."
pip install --quiet python-dotenv==1.0.0 colorama==0.4.6

# Optional: Numba for performance
echo "  → Installing numba for performance optimization..."
pip install --quiet numba==0.57.0

echo -e "${GREEN}✓ All Python packages installed${NC}\n"

# Step 7: Verify installation
echo -e "${BLUE}[7/7] Verifying installation...${NC}"

# Test imports
python3 << EOF
try:
    import pandas
    import numpy
    import talib
    from binance.client import Client
    import matplotlib
    import colorama
    print("✓ All packages verified successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Installation verification passed${NC}\n"
else
    echo -e "${RED}✗ Installation verification failed${NC}\n"
    exit 1
fi

# Summary
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                  INSTALLATION COMPLETED ✓                          ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}→ Next Steps:${NC}\n"

echo "1. Edit config.py and add your Binance Testnet API keys:"
echo -e "   ${BLUE}nano config.py${NC}"
echo "   → Replace BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET\n"

echo "2. Activate virtual environment (if needed):"
echo -e "   ${BLUE}source qsci_venv/bin/activate${NC}\n"

echo "3. Run the backtester:"
echo -e "   ${BLUE}python3 qsci_backtester.py${NC}\n"

echo "4. Check results:"
echo -e "   ${BLUE}cat backtest_results.csv${NC}"
echo -e "   ${BLUE}tail -f qsci_backtest.log${NC}\n"

echo -e "${YELLOW}→ Virtual Environment Info:${NC}"
echo "Activate:   ${BLUE}source qsci_venv/bin/activate${NC}"
echo "Deactivate: ${BLUE}deactivate${NC}\n"

echo -e "${YELLOW}→ Documentation:${NC}"
echo "README:     ${BLUE}cat README.md${NC}"
echo "Config:     ${BLUE}cat config.py${NC}\n"

echo -e "${GREEN}Happy backtesting! 🚀${NC}\n"
