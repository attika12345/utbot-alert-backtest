UT Bot Trading Strategy Backtester
This repository contains a Python-based backtesting engine designed to evaluate the viability of the UT Bot trading strategy using historical market data. The script specifically targets the XRP/USDC pair but can be adapted for other assets.

Features
Automated Data Retrieval: Downloads historical kline data directly from the Binance API.

Technical Indicators: Utilizes TA-Lib for high-performance ATR calculations and VectorBT for portfolio analysis.

Strategy Validation: Implements a trailing stop mechanism based on volatility to generate buy and sell signals.

Performance Comparison: Compares algorithmic returns against a standard "Buy & Hold" benchmark.

Requirements
To run this script, you will need the following Python libraries:

vectorbt

pandas

numpy

talib

requests

How to Use
Clone the repository.

Adjust SENSITIVITY and ATR_PERIOD in the script to fine-tune strategy signals.

Run the script to see a full statistical breakdown of the trade performance.
