"""Tests for market scanner candidate ranking."""

from __future__ import annotations

from stock_pilot.models import Position, ScannerSettings, ScoreCalculationResult
from stock_pilot.scanner import MarketScanner
from tests.test_ai_summary import _score


def test_market_scanner_filters_and_ranks_candidates() -> None:
    """MarketScanner should rank eligible stocks by score and confidence."""
    settings = ScannerSettings(
        candidate_limit=2,
        min_score=70,
        allowed_risk_levels=("Low", "Medium"),
        min_relative_strength_score=50,
    )
    score_results = (
        _score_result("002436", "兴森科技", 88, "Low", confidence=0.70),
        _score_result("002156", "通富微电", 88, "Low", confidence=0.85),
        _score_result("600062", "华润双鹤", 69, "Low", confidence=0.90),
        _score_result("002262", "恩华药业", 91, "High", confidence=0.95),
    )

    result = MarketScanner(settings).scan(score_results)

    assert [candidate.code for candidate in result.candidates] == ["002156", "002436"]
    assert result.skipped_count == 2


def test_market_scanner_skips_failed_scores() -> None:
    """MarketScanner should count failed scores as skipped items."""
    settings = ScannerSettings(
        candidate_limit=2,
        min_score=70,
        allowed_risk_levels=("Low",),
    )
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)

    result = MarketScanner(settings).scan(
        (ScoreCalculationResult(position=position, score=None, error="failed"),)
    )

    assert result.candidates == ()
    assert result.skipped_count == 1


def _score_result(
    code: str,
    name: str,
    score: int,
    risk: str,
    confidence: float,
) -> ScoreCalculationResult:
    position = Position(code=code, name=name, cost=10.0, shares=100)
    stock_score = _score(code=code, name=name, score=score, risk=risk)
    stock_score = type(stock_score)(
        code=stock_score.code,
        name=stock_score.name,
        score=stock_score.score,
        rating=stock_score.rating,
        risk=stock_score.risk,
        confidence=confidence,
        components=stock_score.components,
        reasons=stock_score.reasons,
    )
    return ScoreCalculationResult(position=position, score=stock_score)
