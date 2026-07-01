ARCHITECTURE.md

StockPilot Architecture

Purpose

This document defines the software architecture of StockPilot.

Unlike README.md, this file is intended for developers and AI coding assistants (Codex, Cursor, Claude Code).

Every module must follow the architecture described here.

⸻

Philosophy

StockPilot is NOT a quantitative trading engine.

It is a decision support system.

Its purpose is

Market Data
      │
      ▼
Indicators
      │
      ▼
Analysis
      │
      ▼
Score
      │
      ▼
Suggestion
      │
      ▼
Human Decision

The system never performs automatic trading.

All conclusions must be explainable.

⸻

Design Principles

1. Single Responsibility

Every module should have exactly one responsibility.

Examples

fetcher.py
ONLY downloads market data.
indicators.py
ONLY calculates indicators.
analyzer.py
ONLY analyzes indicators.

Never mix responsibilities.

⸻

2. Stateless

Modules should be stateless whenever possible.

Avoid

global variables

Avoid

module-level cache

Input

↓

Output

Only.

⸻

3. Immutable Data

Prefer dataclass(frozen=True)

instead of mutable dict.

Example

@dataclass(frozen=True)
class Position:
    code: str
    name: str
    shares: int
    cost: float

⸻

4. Explainability

Every score

Every suggestion

Every warning

must include reasons.

Bad

Score
89

Good

Score
89
Reasons
✓ MA20 Up
✓ MACD Bullish
✓ Volume Breakout

⸻

System Overview

              portfolio.yaml
                     │
                     ▼
             PortfolioLoader
                     │
                     ▼
               Fetcher (AKShare)
                     │
                     ▼
          Market Session Selector
                     │
                     ▼
               OHLCV DataFrame
                     │
                     ▼
             Indicator Calculator
                     │
                     ▼
              IndicatorResult
                     │
                     ▼
                 Analyzer
                     │
                     ▼
              AnalysisResult
                     │
                     ▼
                 Scorer
                     │
                     ▼
                StockScore
                    │
                    ▼
          Portfolio Decision Engine
                     │
                     ▼
          Position Management Engine
                     │
                     ▼
                 Reporter
                     │
                     ▼
        Console / Markdown / CSV
                     │
                     ▼
              Notification
                     │
                     ▼
              Telegram / Email

⸻

Module Responsibilities

fetcher.py

Responsibility

Download market data.

Input

Stock code

Output

OHLCV DataFrame

Must NOT

* calculate indicators
* generate reports

⸻

market_session.py

Responsibility

Select the correct market data snapshot for analysis.

Before the configured cutoff time, analysis should use the previous completed
daily close. Valuation may still use the latest available data.

Must NOT

* download data
* calculate indicators
* generate scores
* render reports

⸻

indicators.py

Input

OHLCV

Output

IndicatorResult

Contains

MA5
MA10
MA20
MA60
EMA12
EMA26
MACD
Signal
Histogram
RSI14
ATR14
Volume Ratio
Highest20
Lowest20

No analysis should happen here.

Only mathematics.

⸻

analyzer.py

Input

IndicatorResult

Output

AnalysisResult

Responsibilities

Determine

Trend

Bullish
Neutral
Bearish

Momentum

Strong
Medium
Weak

Risk

Low
Medium
High

Support

Resistance

Reasons

No score here.

⸻

scorer.py

Input

AnalysisResult

Output

StockScore

Range

0~95

The score should never reach 100 because markets do not offer perfect certainty.

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

Relative Strength must measure sustainable leadership.

Use configurable 5-day, 20-day, and 60-day weighted performance plus sector
and portfolio comparison.

Scorer may apply configurable long-term trend penalties when price remains
below MA60 or long-term trend context is weak.

Never hardcode random values.

All weights should be configurable.

⸻

portfolio_decision.py

Input

StockScore

AnalysisResult

PortfolioAnalysis

ScannerResult

Output

PortfolioDecisionPlan

Responsibilities

Generate portfolio-aware actions.

Generate execution priority.

Separate volatility, trend, concentration, and portfolio risk.

Examples

Strong Hold
Hold
Reduce Position
Replace Candidate
Exit
Watch

Execution Priority

Immediate
Today
This Week
Observe
Future

Must include

Reason

Confidence

Risk

RiskBreakdown

Execution Priority

Must NOT

* download data
* calculate indicators
* generate raw scores
* mutate portfolio configuration

⸻

position_manager.py

Input

Position
AnalysisResult
StockScore
PortfolioValuation
PortfolioAnalysis
IndicatorResult

Output

PositionRecommendation

Responsibilities

Recommend how much of each existing holding to keep.

Use Trend Stage before sizing.

Trend Stage

EARLY_UPTREND
MID_UPTREND
LATE_UPTREND
PULLBACK
BREAKDOWN

Examples

Continue Hold
Take Partial Profit
Reduce Position
Exit Position
Watch

Must include

Recommended shares
Recommended position percentage
Reason
Confidence
Risk
RiskBreakdown
Trend Stage
Suggested ATR stop
Suggested trailing stop
Suggested take-profit reference

Must NOT

* download data
* calculate indicators
* calculate raw stock scores
* generate replacement candidates
* mutate portfolio configuration

⸻

strategy.py

Generate trading suggestions.

Example

Strong Hold
Reduce Position
Watch
Potential Breakout
Potential Reversal

This module contains trading rules.

No UI.

⸻

reporter.py

Convert results into

Console

Markdown

CSV

Future

HTML

No calculations here.

⸻

notification.py

Deliver generated reports through external channels.

Input

DailyReportPayload

Markdown report path

Output

NotificationDispatchResult

Must NOT

* calculate indicators
* score stocks
* alter decisions
* fetch market data

⸻

Data Models

Use dataclasses.

Never return dict from public APIs.

Example

Position
↓
MarketData
↓
IndicatorResult
↓
AnalysisResult
↓
StockScore
↓
ReportItem

⸻

Class Diagram

Position
    │
    ▼
MarketData
    │
    ▼
IndicatorResult
    │
    ▼
AnalysisResult
    │
    ▼
StockScore
    │
    ▼
ReportItem

⸻

Indicator Layer

The indicator layer should NEVER perform interpretation.

Example

Correct

RSI = 72.4

Wrong

RSI is overbought.

Interpretation belongs to Analyzer.

⸻

Analyzer Rules

Trend

Bullish

Example

Close > MA20
MA20 rising
MACD > Signal

Bearish

Close < MA20
MA20 falling
MACD < Signal

Momentum

Strong

MACD expanding
RSI between 55~75
Volume > 1.3x Average

Risk

High

RSI > 80
Long upper shadow
ATR expanding rapidly

⸻

Strategy Rules

The strategy module converts analysis into actions.

Possible actions

Strong Buy
Buy
Accumulate
Hold
Watch
Reduce
Sell

Every action must include

Reason

Confidence

Example

Suggestion
Hold
Confidence
86%
Reasons
✓ Trend Bullish
✓ MACD Bullish
✓ Above MA20

⸻

Scoring Philosophy

Score should represent

Probability
×
Trend Quality
×
Risk

NOT

Expected Profit.

⸻

Relative Strength

Future versions should compare

Stock

vs

Industry

vs

CSI300

vs

ChiNext

Generate

Relative Strength Score

⸻

Portfolio Layer

Portfolio should be independent.

Portfolio only knows

Cost
Shares
Cash
PnL

Portfolio should NOT calculate indicators.

⸻

Persistence

Current version

CSV

Future

SQLite

No ORM.

⸻

Configuration

Everything configurable.

Avoid magic numbers.

Example

trend:
  ma_short: 5
  ma_mid: 20
  ma_long: 60
score:
  trend: 40
  volume: 20
  momentum: 15
  risk: 15
  relative: 10

⸻

Logging

Every module should use logging.

No print() except reporter.

⸻

Testing

Each module should have unit tests.

Target coverage

>90%

Indicator calculations must be deterministic.

⸻

Future Modules

scanner.py

Scan all A-share stocks.

sector.py

Industry strength analysis.

news.py

News aggregation.

ai_summary.py

LLM-generated natural language report.

dashboard.py

Streamlit dashboard.

⸻

Development Rules

Every public function

must have

* type hints
* docstring
* unit tests

Avoid

* duplicated code
* hidden state
* circular imports

Prefer

composition

over inheritance.

⸻

Mission

Build an explainable, maintainable, modular trading assistant.

Every recommendation should be transparent.

Every score should be reproducible.

The human always makes the final investment decision.
