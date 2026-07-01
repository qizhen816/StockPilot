"""Tests for explainable stock scoring."""

from __future__ import annotations

import pytest

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
        minimum_confidence=0.55,
        maximum_confidence=0.90,
        maximum_score=95,
        relative_strength_5d_weight=0.30,
        relative_strength_20d_weight=0.40,
        relative_strength_60d_weight=0.30,
        long_term_trend_penalty=10,
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
    assert score.confidence == pytest.approx(0.68)
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


def test_score_all_uses_portfolio_relative_strength_ranking() -> None:
    """ScoreEngine should rank relative strength across analyzed holdings."""
    position_a = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    position_b = Position(code="002156", name="通富微电", cost=20.0, shares=100)
    analysis_a = _analysis("002436", "兴森科技", 0.04)
    analysis_b = _analysis("002156", "通富微电", -0.02)

    scored = ScoreEngine(_settings()).score_all(
        (
            AnalysisCalculationResult(position=position_a, analysis=analysis_a),
            AnalysisCalculationResult(position=position_b, analysis=analysis_b),
        )
    )

    assert scored[0].score is not None
    assert scored[1].score is not None
    assert scored[0].score.relative_strength_score > (
        scored[1].score.relative_strength_score
    )
    assert any(
        "Relative strength multi-period rank 1 of 2" in reason
        for reason in scored[0].score.reasons
    )


def _analysis(code: str, name: str, stock_return: float) -> AnalysisResult:
    return AnalysisResult(
        code=code,
        name=name,
        trend="Bullish",
        momentum="Strong",
        risk="Low",
        support=10.0,
        resistance=15.0,
        reasons=("Close above MA20", "Volume breakout"),
        sector="科技",
        stock_return=stock_return,
        return_5d=stock_return,
        return_20d=stock_return * 2,
        return_60d=stock_return * 3,
        long_term_distance_pct=0.05,
    )
