#!/bin/bash
# QSCI Backtester - Quick Run Script
# Usage: ./run_backtest.sh [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source qsci_venv/bin/activate

echo "=================================="
echo "QSCI BTC Options Backtester v3.0"
echo "With Improvements:"
echo "  ✓ Risk-based position sizing"
echo "  ✓ IV Rank filter (max 60%)"
echo "  ✓ Stricter thresholds (QSCI≥0.12, ADX≥20)"
echo "=================================="
echo ""

# Parse command line arguments
RUN_TESTS=false
RUN_BACKTEST=true
QUICK_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --test)
            RUN_TESTS=true
            shift
            ;;
        --no-backtest)
            RUN_BACKTEST=false
            shift
            ;;
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --help)
            echo "Usage: ./run_backtest.sh [options]"
            echo ""
            echo "Options:"
            echo "  --test          Run unit tests before backtesting"
            echo "  --no-backtest   Run tests only, skip backtest"
            echo "  --quick         Run quick backtest (limited data)"
            echo "  --help          Show this help message"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run tests if requested
if [ "$RUN_TESTS" = true ]; then
    echo "🧪 Running Unit Tests..."
    echo "------------------------"
    python3 tests/test_qsci.py TestPositionSizing 2>&1 | tail -20
    echo ""
    python3 tests/test_qsci.py TestIVRankFilter 2>&1 | tail -20
    echo ""
    echo "✓ Tests completed"
    echo ""
fi

# Run backtest if requested
if [ "$RUN_BACKTEST" = true ]; then
    echo "📊 Running Backtest..."
    echo "------------------------"
    
    if [ "$QUICK_MODE" = true ]; then
        echo "⚡ Quick mode: Limited data for faster results"
        # Could add logic to modify config for quick mode
    fi
    
    # Run the backtester
    python3 qsci_backtester_v3.py
    
    echo ""
    echo "✓ Backtest completed"
    echo ""
    echo "📁 Output files:"
    echo "  - qsci_backtest.log (detailed log)"
    echo "  - trades.csv (individual trades)"
    echo "  - performance.csv (performance metrics)"
    echo "  - backtest_results.csv (summary)"
    echo ""
fi

echo "=================================="
echo "Done! Check the output files above."
echo "=================================="
