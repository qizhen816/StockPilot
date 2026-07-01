"""Tests for portfolio-level decision support."""

from __future__ import annotations

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    PortfolioAnalysis,
    PortfolioDecisionSettings,
    Position,
    ScanCandidate,
    ScannerResult,
    ScoreCalculationResult,
)
from stock_pilot.portfolio_decision import PortfolioDecisionEngine
from tests.test_ai_summary import _score


def test_portfolio_decision_strong_holds_top_holding() -> None:
    """Strong low-risk leaders should become strong-hold candidates."""
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    score = _score("002436", "兴森科技", 90, "Low")
    analysis = _analysis("002436", "兴森科技", "Bullish", "Strong", "Breakout")

    plan = PortfolioDecisionEngine(_settings()).build_plan(
        score_results=(ScoreCalculationResult(position=position, score=score),),
        analysis_results=(
            AnalysisCalculationResult(position=position, analysis=analysis),
        ),
        portfolio_analysis=_portfolio_analysis(),
        scanner_result=ScannerResult(candidates=(), skipped_count=0),
    )

    assert plan.actions[0].action == "Strong Hold"
    assert plan.actions[0].confidence > score.confidence
    assert "Portfolio rank 1 of 1" in plan.actions[0].reasons
    assert plan.actions[0].relative_rank == 1
    assert plan.actions[0].risk_rank == 1
    assert plan.actions[0].trend_rank == 1
    assert plan.actions[0].execution_priority == "This Week"
    assert plan.actions[0].risk_breakdown.trend_risk == "Low"


def test_portfolio_decision_recommends_replacement_for_weak_holding() -> None:
    """Weak holdings should pair with stronger scanner candidates."""
    position = Position(code="002201", name="九鼎新材", cost=10.0, shares=100)
    score = _score("002201", "九鼎新材", 58, "Medium")
    candidate = ScanCandidate(
        code="300088",
        name="长信科技",
        score=78,
        rating="★★★★☆",
        risk="Low",
        confidence=0.82,
        reasons=("Trend is Bullish",),
    )

    plan = PortfolioDecisionEngine(_settings()).build_plan(
        score_results=(ScoreCalculationResult(position=position, score=score),),
        analysis_results=(
            AnalysisCalculationResult(
                position=position,
                analysis=_analysis("002201", "九鼎新材", "Neutral", "Weak", "Shrink"),
            ),
        ),
        portfolio_analysis=_portfolio_analysis(),
        scanner_result=ScannerResult(candidates=(candidate,), skipped_count=0),
    )

    assert plan.actions[0].action == "Replace Candidate"
    assert plan.actions[0].replacement is not None
    assert plan.actions[0].replacement.suggested_code == "300088"
    assert plan.replacements[0].score_gap == 20
    assert plan.replacements[0].expected_portfolio_score_delta == 20
    assert plan.replacements[0].replacement_confidence >= 0.68


def _settings() -> PortfolioDecisionSettings:
    return PortfolioDecisionSettings(
        strong_hold_score_threshold=85,
        hold_score_threshold=70,
        reduce_score_threshold=55,
        exit_score_threshold=40,
        replace_score_threshold=60,
        replacement_min_score_gap=12,
        minimum_confidence=0.55,
        maximum_confidence=0.90,
        replacement_min_confidence=0.68,
        replacement_switch_cost_penalty=0.08,
    )


def _analysis(
    code: str,
    name: str,
    trend: str,
    momentum: str,
    volume_status: str,
) -> AnalysisResult:
    return AnalysisResult(
        code=code,
        name=name,
        trend=trend,
        momentum=momentum,
        risk="Low",
        support=10.0,
        resistance=12.0,
        reasons=("Close above MA20",),
        volume_status=volume_status,
    )


def _portfolio_analysis() -> PortfolioAnalysis:
    return PortfolioAnalysis(
        sector_exposures=(("科技", 1.0),),
        concentration_top_position_pct=1.0,
        largest_winner="兴森科技（002436）",
        largest_loser="九鼎新材（002201）",
        highest_risk_position="九鼎新材（002201）",
        weakest_relative_position="九鼎新材（002201）",
        portfolio_trend_score=76.0,
        portfolio_risk_score=40.0,
        portfolio_risk_level="Medium",
        portfolio_risk_reasons=("Largest position concentration is 100%",),
        profit_concentration_pct=1.0,
        profit_concentration_score=100.0,
        profit_concentration_reasons=("Profit concentration is high at 100%",),
    )
