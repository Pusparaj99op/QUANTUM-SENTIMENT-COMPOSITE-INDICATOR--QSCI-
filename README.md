<div align="center">

# 🔮 QSCI: Quantum-Sentiment Composite Indicator
### Advanced Bitcoin Options Backtester v3.0

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Binance](https://img.shields.io/badge/Binance-API-yellow?style=for-the-badge&logo=binance&logoColor=black)](https://binance.com)
[![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)](https://github.com/)
[![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](LICENSE)

*A sophisticated algorithmic trading engine merging **Technical Analysis** with **NLP Sentiment**.*

[Features](#-key-features) • [Installation](#-installation) • [Configuration](#-configuration) • [Usage](#-usage) • [Results](#-outputs--results)

---
</div>

## 📖 Overview

The **Quantum-Sentiment Composite Indicator (QSCI)** is a high-performance backtesting framework designed for Bitcoin (BTC) options. It goes beyond traditional technical analysis by integrating **Natural Language Processing (NLP)** to gauge market sentiment from real-time news and social media.

Built for **quant traders** and **researchers**, QSCI simulates a realistic execution environment, complete with Greeks modeling, dynamic transaction costs, and a Monte Carlo robustness engine.

## 🚀 Key Features

| Feature | Description |
|:---:|---|
| 🧠 **Composite Signal Engine** | Fuses **Momentum, Trend, Volume, Volatility, and Pattern** into a single, high-conviction `QSCI` score. |
| 📰 **Sentiment Intelligence** | Uses **VADER & TextBlob** to quantify sentiment from major financial outlets (Bloomberg, Reuters) and crypto-social spheres. |
| ⏱️ **Multi-Timeframe Analysis** | Concurrently monitors 7 distinct timeframes (`1m` to `4h`) to spot fractal alignment and trend shifting. |
| 📈 **Realistic Simulation** | Full **Black-Scholes** pricing, Greeks (Δ, Γ, ν, Θ) tracking, and realistic fee/slippage modeling. |
| 🛡️ **Advanced Risk Management** | Features **Auto-Rolling**, dynamic position sizing (Kelly Criterion option), and tiered Take-Profit/Stop-Loss systems. |
| 🎲 **Monte Carlo Validator** | Automatically runs thousands of simulations to stress-test your strategy's expected returns and drawdown risks. |

## 📋 Prerequisites

*   **Python 3.8+**
*   **TA-Lib** (Technical Analysis Library)

### System Setup (Ubuntu/Linux)
```bash
sudo apt-get update
sudo apt-get install -y build-essential libta-lib0 libta-lib-dev
```

## 🛠️ Installation

1.  **Clone the Project**
    ```bash
    git clone https://github.com/yourusername/QSCI-Backtester.git
    cd QSCI-Backtester
    ```

2.  **Set Up Virtual Environment**
    ```bash
    python3 -m venv qsci_venv
    source qsci_venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r installation/DEPENDENCIES.txt
    # OR manually:
    pip install pandas numpy scipy python-binance binance-connector TA-Lib pandas-ta matplotlib seaborn colorama numba textblob vaderSentiment
    ```

## ⚙️ Configuration

Control every aspect of the engine via `config.py`.

> [!TIP]
> **Quick Start**: Set `USE_TESTNET = True` to run safely without real capital risks during live forward-testing (if enabled).

| Section | Key Settings |
|:---|---|
| **API** | `BINANCE_TESTNET_API_KEY`, `BINANCE_MAINNET_API_KEY` |
| **Strategy** | `QSCI_CONFIG` (Indicator Weights), `ENTRY_CRITERIA` |
| **Sentiment** | `NEWS_SENTIMENT_CONFIG` (Source weights, standard decay) |
| **Risk** | `POSITION_CONFIG` (Max position size, account balance) |

## 🏃 Usage

Execute the main engine to start the backtest:

```bash
python3 qsci_backtester_v3.py
```

You will see real-time logging in the console:

```text
2023-10-27 10:00:00 - INFO - Loading historical data...
2023-10-27 10:00:05 - INFO - [SIGNAL] QSCI Score: 0.85 | Sentiment: Bullish (0.42)
2023-10-27 10:00:05 - INFO - 🟢 OPEN LONG | Call Option | Strike: 35000 | DTE: 7
```

## 📊 Outputs & Results

The system generates detailed artifacts for analysis:

*   **`backtest_results.csv`**: Comprehensive trade log (Entry/Exit, ROI, Fees).
*   **`drawdown_curve.csv`**: Equity curve data points for visualization.
*   **`plots/`**: (If enabled) High-res charts of Performance vs. Drawdown.
*   **`qsci_backtest.log`**: Full execution trace.

#### Monte Carlo Analysis
At the end of a run, the system outputs a robustness report:
> "95% Confidence Level: Strategy expects a return between **15%** and **45%**."

## 📂 Project Architecture

```
📦 QUANTUM-SENTIMENT-COMPOSITE-INDICATOR
 ┣ 📂 BTC_DATA           # 🗄️ Historical Cache
 ┣ 📂 demonstration      # 💡 Strategy Examples
 ┣ 📂 installation       # 🔧 Setup Scripts
 ┣ 📜 config.py          # ⚙️ Configuration Core
 ┣ 📜 qsci_backtester_v3.py  # 🧠 Main Engine
 ┣ 📜 backtest_results.csv   # 📊 Results
 ┗ 📜 README.md          # 📖 Documentation
```

## 🤝 Contributing

Contributions are welcome! Please feel free to verify the `TODO.md` or submit a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---
<div align="center">
  <sub>Built with ❤️ by the Quantum Trading Team</sub>
</div>
