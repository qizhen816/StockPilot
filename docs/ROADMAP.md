ROADMAP.md

StockPilot Development Roadmap

⸻

Vision

Build a lightweight, explainable and modular personal trading assistant for the A-share market.

The system focuses on post-market decision support, not automated trading.

⸻

Milestone

v0.1 Foundation

Status

Completed

Goal

Project can run successfully.

Features

* Project structure
* Config loader
* Portfolio loader
* AKShare downloader
* Logging
* CLI entry

Output

python daily_report.py

Should download all portfolio stocks.

⸻

v0.2 Indicator Engine

Status

Completed

Implement

* SMA
* EMA
* MACD
* RSI
* ATR
* Volume Ratio
* Highest N
* Lowest N

No external TA library.

⸻

v0.3 Portfolio Engine

Status

Completed

Support

* Cost
* Shares
* Current Value
* Unrealized PnL
* Daily PnL

⸻

v0.4 Analyzer

Status

Completed

Generate

Trend

Momentum

Risk

Support

Resistance

Reasons

⸻

v0.5 Scoring Engine

Status

Completed

Generate

0~100 score.

Five-Star rating.

Risk level.

⸻

v0.6 Report Engine

Status

Completed

Generate

Console

Markdown

CSV

⸻

v0.7 AI Summary

Status

Completed

Generate natural language report.

Include

* strongest stock
* weakest stock
* today’s risk
* tomorrow’s watchlist

⸻

v0.8 Scanner

Status

Completed

Scan all A-shares.

Generate candidate list.

⸻

v0.9 Dashboard

Status

Completed

Streamlit UI.

Interactive charts.

Portfolio overview.

⸻

v1.0

Status

Completed

Daily trading assistant.

One-click report generation.

Markdown

HTML

PNG

Telegram

Email

Ready.

⸻

v1.1 Portfolio Decision Engine

Status

Completed

Shift focus from individual stock analysis to portfolio management.

Generate

* Portfolio-aware actions
* Increase / Hold / Reduce / Replace / Exit / Watch
* Dynamic decision confidence
* Replacement suggestions
* Tomorrow-focused portfolio plan
* Dashboard plan view

⸻

v1.2 Relative Strength & Market Session

Status

Completed

Improve decision quality with clearer relative-strength ranking and
market-session-aware analysis.

Generate

* Portfolio relative strength rank
* Sector relative strength rank
* Chinese analysis reasons
* Previous-close analysis before 15:00
* Today operation advice before market close

⸻

v1.2.1 Polish

Status

Completed

Improve consistency, readability, and professional decision quality.

Refine

* Score capped at 95
* Confidence capped at 90%
* Strong Hold replaces Increase Position
* Existing holdings avoid Avoid Buying actions
* Portfolio risk explanations
* Replacement improvement breakdown
* Portfolio relative / risk / trend ranks
* More natural rule-based summary

⸻

v1.3 Position Management Engine

Status

Completed

Add dedicated position-size recommendations for existing holdings.

Generate

* Current vs recommended shares
* Position state
* Continue Hold / Take Partial Profit / Reduce / Exit / Watch actions
* Cost-aware profit protection
* ATR stop, trailing stop, and take-profit reference
* Portfolio and sector concentration reasons
* Console, Markdown, and Dashboard rendering

⸻

v1.3.1 Decision Engine Refinement

Status

Completed

Improve swing-trading decision quality without changing module boundaries.

Refine

* Trend Stage based position sizing
* 5/20/60-day relative strength
* Long-term trend score penalty
* Profit concentration analysis
* Replacement confidence with switch cost
* Execution priority
* Risk breakdown
* Decision-oriented explanations

⸻

Future

Sector Rotation

Northbound Capital

ETF Analysis

Market Breadth

News Analysis

Fund Flow

AI Explanation

Backtesting

Pattern Recognition

Volume Profile

Support & Resistance Detection
