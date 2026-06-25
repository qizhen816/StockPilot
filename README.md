# StockPilot

> AI-powered personal A-share trading assistant.

StockPilot 是一个基于 Python 的个人股票分析工具。

它不会自动交易，也不会预测未来。

它的目标只有一个：

> **每天收盘后 5 秒钟告诉我：哪些股票继续持有、哪些股票危险、哪些股票值得关注。**

整个系统面向个人投资者设计，重点分析自己的持仓，而不是全市场量化交易。

---

# Design Philosophy

StockPilot 不追求：

- 高频交易
- 自动下单
- 复杂机器学习模型

而追求：

- 可解释
- 稳定
- 工程化
- 可维护
- 每天收盘分析一次

所有分析必须能够解释：

例如：

```
兴森科技

Score: 89

Reason

✓ Above MA20

✓ MACD Bullish

✓ Volume Breakout

✓ Relative Strength
```

而不是输出一个无法理解的分数。

---

# Tech Stack

Python 3.12+

Libraries

- akshare
- pandas
- numpy
- pyyaml
- rich
- matplotlib

Future versions may add charting and statistical dependencies when the feature
requires them.

不要使用 TA-Lib。

所有技术指标必须自己实现。

原因：

- Windows 安装困难
- Linux 环境兼容性差
- Pandas 足够实现所有指标

---

# Project Structure

```
stock-pilot/

│
├── config/
│   ├── portfolio.yaml
│   └── settings.yaml
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RULES.md
│   ├── ROADMAP.md
│   └── TASKS.md
│
├── stock_pilot/
│   ├── ai_summary.py
│   ├── analyzer.py
│   ├── fetcher.py
│   ├── indicators.py
│   ├── portfolio.py
│   ├── reporter.py
│   ├── scanner.py
│   ├── scorer.py
│   ├── strategy.py
│   ├── models.py
│   ├── settings.py
│   └── logging_config.py
│
├── reports/
│
├── tests/
│
├── daily_report.py
│
├── requirements.txt
│
└── README.md
```

---

# Development Roadmap

## Current Status

v0.8 Market Scanner is implemented.

Run:

```bash
python daily_report.py
```

The command loads `config/settings.yaml` and `config/portfolio.yaml`, downloads
daily OHLCV data for configured positions through AKShare, calculates raw
technical indicators, calculates portfolio valuation metrics, and prints basic
console summaries with explainable trend, momentum, risk, support, and
resistance analysis, plus explainable 0-100 scores and star ratings. It does
not generate trading suggestions. Reports are written to `reports/daily/`, and
score history is appended to `reports/history.csv`. A deterministic Chinese
daily summary highlights the strongest stock, weakest stock, current risk, and
tomorrow watchlist. The scanner produces an explainable candidate ranking, and
market data fetching retries Eastmoney before falling back to Tencent.

## v0.1

Project initialization

Support

- Portfolio loading
- AKShare download
- Daily OHLCV
- Console output

Status: Completed

---

## v0.2

Indicators

Implement

- MA5
- MA10
- MA20
- MA60

- EMA

- MACD

- RSI14

- ATR14

- Volume Ratio

- Highest20

- Lowest20

Do NOT use external indicator libraries.

Status: Completed

---

## v0.3

Portfolio

Support

- cost
- shares
- market value
- pnl
- pnl percentage

Status: Completed

---

## v0.4

Analyzer

Each stock should output

- trend
- momentum
- risk
- support
- resistance
- reasons

Status: Completed

---

## v0.5

Score Engine

Score should be between

0~100

Weight

Trend

40

Volume

20

Momentum

15

Risk

15

Relative Strength

10

Total

100

Output

★★★★★

★★★★☆

★★★☆☆

★★☆☆☆

★☆☆☆☆

Status: Completed

---

## v0.6

Reporter

Generate

Console Report

Markdown Report

CSV History

Status: Completed

Markdown example

```
# 2026-06-25

## 兴森科技

分数

89

趋势

偏多

原因

- 收盘价位于 MA20 上方

- MACD 位于信号线上方
```

---

## v0.7

AI Summary

Output

- strongest stock
- weakest stock
- today’s risk
- tomorrow’s watchlist

Status: Completed

---

## v0.8

Market Scanner

Output

- candidate ranking
- watch candidates
- scanner result

Status: Completed

---

## v0.9

Dashboard

Output

- Streamlit UI
- charts
- portfolio page

Status: Next

---

# portfolio.yaml

Example

```yaml
stocks:

  "002436":
    name: 兴森科技
    cost: 50.411
    shares: 100

  "002156":
    name: 通富微电
    cost: 74.041
    shares: 100

  "600062":
    name: 华润双鹤
    cost: 17.855
    shares: 600

  "002262":
    name: 恩华药业
    cost: 29.631
    shares: 400

  "600483":
    name: 福能股份
    cost: 12.074
    shares: 200

  "002201":
    name: 九鼎新材
    cost: 13.366
    shares: 200
```

---

# Coding Style

Use

- dataclass
- typing
- pathlib
- logging

Avoid

- global variables
- magic numbers
- duplicated code

Every public function should include

- type hints
- docstring

---

# Future Features

## Scanner

Scan all A-shares.

Find

- MA20 breakout
- Volume breakout
- MACD bullish
- Strong relative strength

Generate today's candidate list.

---

## Sector Analysis

Support

- PCB

- Semiconductor

- AI

- Robotics

- Medicine

Calculate

Sector Score

Sector Ranking

---

## Visualization

Generate

- K-line
- MA
- Volume
- MACD
- RSI

Save PNG automatically.

---

## Notifications

Support

Telegram

Email

Enterprise WeChat

Daily 16:05 report.

---

# Non Goals

The project will NOT

- predict stock prices
- perform automatic trading
- recommend guaranteed profitable stocks
- use black-box AI for scoring

Every recommendation must be explainable.

---

# Mission

Build a lightweight, explainable, maintainable personal trading assistant that helps make better decisions after market close every day.
