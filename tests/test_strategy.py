"""Tests for trading decision support."""

from __future__ import annotations

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    DecisionSettings,
    Position,
    ScoreCalculationResult,
)
from stock_pilot.strategy import DecisionEngine
from tests.test_ai_summary import _score


def test_decision_engine_generates_continue_hold_for_strong_bullish_stock() -> None:
    """DecisionEngine should continue holding high-score bullish stocks."""
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    score = _score("002436", "兴森科技", 88, "Low")
    analysis = AnalysisResult(
        code="002436",
        name="兴森科技",
        trend="Bullish",
        momentum="Strong",
        risk="Low",
        support=10.0,
        resistance=12.0,
        reasons=("Close above MA20",),
    )

    result = DecisionEngine(_settings()).decide_all(
        score_results=(ScoreCalculationResult(position=position, score=score),),
        analysis_results=(
            AnalysisCalculationResult(position=position, analysis=analysis),
        ),
    )

    assert result[0].decision is not None
    assert result[0].decision.action == "Continue Hold"
    assert result[0].decision.risk == "Low"


def test_decision_engine_reduces_high_risk_stock() -> None:
    """DecisionEngine should reduce high-risk stocks regardless of score."""
    score = _score("002201", "九鼎新材", 82, "High")

    decision = DecisionEngine(_settings()).decide(score, analysis=None)

    assert decision.action == "Reduce Position"
    assert "Risk is High" in decision.reasons


def _settings() -> DecisionSettings:
    return DecisionSettings(
        high_score_threshold=80,
        low_score_threshold=55,
        high_confidence_threshold=0.75,
    )
