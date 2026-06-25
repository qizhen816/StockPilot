"""Tests for explainable stock scoring."""

from __future__ import annotations

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    Position,
    ScorerSettings,
)
from stock_pilot.scorer import ScoreEngine


def _settings() -> ScorerSettings:
    return ScorerSettings(
        trend_weight=40,
        volume_weight=20,
        momentum_weight=15,
        risk_weight=15,
        relative_strength_weight=10,
        reason_confidence_step=0.04,
        minimum_confidence=0.50,
        maximum_confidence=0.95,
    )


def test_score_engine_scores_bullish_low_risk_analysis() -> None:
    """ScoreEngine should produce a high explainable score for strong analysis."""
    analysis = AnalysisResult(
        code="002436",
        name="兴森科技",
        trend="Bullish",
        momentum="Strong",
        risk="Low",
        support=10.0,
        resistance=15.0,
        reasons=(
            "Close above MA20",
            "Volume breakout",
            "MACD histogram positive",
            "Support from lowest20",
        ),
    )

    score = ScoreEngine(_settings()).score(analysis)

    assert score.score == 95
    assert score.rating == "★★★★★"
    assert score.risk == "Low"
    assert score.confidence == 0.66
    assert len(score.components) == 5
    assert "Trend is Bullish" in score.reasons
    assert "Volume breakout confirmed" in score.reasons


def test_score_engine_scores_bearish_high_risk_analysis() -> None:
    """ScoreEngine should penalize bearish, weak, high-risk analysis."""
    analysis = AnalysisResult(
        code="002156",
        name="通富微电",
        trend="Bearish",
        momentum="Weak",
        risk="High",
        support=8.0,
        resistance=12.0,
        reasons=(
            "Close below MA20",
            "Volume below rolling average",
            "RSI risk threshold exceeded",
        ),
    )

    score = ScoreEngine(_settings()).score(analysis)

    assert score.score == 22
    assert score.rating == "★☆☆☆☆"
    assert score.risk == "High"
    assert "Risk is High" in score.reasons


def test_score_all_preserves_analysis_failures() -> None:
    """ScoreEngine should pass upstream analysis errors through as score failures."""
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    results = (
        AnalysisCalculationResult(
            position=position,
            analysis=None,
            error="analysis failed",
        ),
    )

    scored = ScoreEngine(_settings()).score_all(results)

    assert scored[0].position == position
    assert scored[0].score is None
    assert scored[0].error == "analysis failed"
