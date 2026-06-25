"""Tests for deterministic daily summaries."""

from __future__ import annotations

from stock_pilot.ai_summary import DailySummaryGenerator
from stock_pilot.models import (
    PortfolioValuation,
    PortfolioValuationResult,
    Position,
    PositionValuation,
    ScoreCalculationResult,
    StockScore,
    SummarySettings,
)


def test_daily_summary_identifies_strongest_weakest_and_watchlist() -> None:
    """DailySummaryGenerator should summarize ranked scores in Chinese."""
    settings = SummarySettings(watchlist_limit=2, high_risk_levels=("High",))
    position_a = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    position_b = Position(code="002156", name="通富微电", cost=20.0, shares=100)
    scores = (
        ScoreCalculationResult(
            position=position_a,
            score=_score("002436", "兴森科技", 88, "Low"),
        ),
        ScoreCalculationResult(
            position=position_b,
            score=_score("002156", "通富微电", 42, "High"),
        ),
    )

    summary = DailySummaryGenerator(settings).generate(
        score_results=scores,
        analysis_results=(),
        portfolio_valuation=_valuation(),
    )

    assert summary.strongest_stock == "兴森科技（002436）"
    assert summary.weakest_stock == "通富微电（002156）"
    assert summary.tomorrow_watchlist == (
        "兴森科技（002436）：88 分，风险低",
        "通富微电（002156）：42 分，风险高",
    )
    assert "通富微电" in summary.today_risk
    assert "最强的是 兴森科技" in summary.conclusion


def test_daily_summary_handles_missing_scores() -> None:
    """DailySummaryGenerator should return an explicit fallback without scores."""
    settings = SummarySettings(watchlist_limit=2, high_risk_levels=("High",))

    summary = DailySummaryGenerator(settings).generate(
        score_results=(),
        analysis_results=(),
        portfolio_valuation=PortfolioValuationResult(valuation=None),
    )

    assert summary.strongest_stock is None
    assert summary.weakest_stock is None
    assert summary.tomorrow_watchlist == ()
    assert "没有可用评分" in summary.conclusion


def _score(code: str, name: str, score: int, risk: str) -> StockScore:
    return StockScore(
        code=code,
        name=name,
        score=score,
        rating="★★★★☆",
        risk=risk,
        confidence=0.8,
        components=(),
        reasons=("Trend is Bullish",),
    )


def _valuation() -> PortfolioValuationResult:
    valuation = PortfolioValuation(
        positions=(
            PositionValuation(
                code="002436",
                name="兴森科技",
                shares=100,
                cost_price=10.0,
                cost_amount=1000.0,
                current_price=12.0,
                previous_close=11.0,
                market_value=1200.0,
                unrealized_pnl=200.0,
                unrealized_pnl_pct=0.2,
                daily_pnl=100.0,
                daily_pnl_pct=1 / 11,
            ),
        ),
        total_cost=1000.0,
        total_market_value=1200.0,
        total_unrealized_pnl=200.0,
        total_unrealized_pnl_pct=0.2,
        total_daily_pnl=100.0,
    )
    return PortfolioValuationResult(valuation=valuation)
