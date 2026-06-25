"""Explainable stock scoring based on analysis results."""

from __future__ import annotations

import logging

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    ScoreCalculationResult,
    ScoreComponent,
    ScorerSettings,
    StockScore,
)

logger = logging.getLogger(__name__)


class ScoreEngine:
    """Convert analysis output into explainable 0-100 stock scores."""

    def __init__(self, settings: ScorerSettings) -> None:
        """Create a score engine with immutable weight settings."""
        self._settings = settings

    def score(
        self,
        analysis: AnalysisResult,
        relative_strength_score: int = 50,
    ) -> StockScore:
        """Score one analysis result with component-level explanations."""
        components = (
            self._trend_component(analysis),
            self._momentum_component(analysis),
            self._volume_component(analysis),
            self._risk_component(analysis),
            self._relative_strength_component(relative_strength_score),
        )
        total_score = sum(component.score for component in components)
        clamped_score = max(0, min(100, total_score))

        return StockScore(
            code=analysis.code,
            name=analysis.name,
            score=clamped_score,
            rating=_rating_for_score(clamped_score),
            risk=analysis.risk,
            confidence=self._confidence(analysis),
            components=components,
            reasons=tuple(component.reason for component in components),
            relative_strength_score=relative_strength_score,
        )

    def score_all(
        self, analysis_results: tuple[AnalysisCalculationResult, ...]
    ) -> tuple[ScoreCalculationResult, ...]:
        """Score all successful analysis results without stopping on failures."""
        results: list[ScoreCalculationResult] = []
        relative_scores = _relative_strength_scores(analysis_results)
        for analysis_result in analysis_results:
            if analysis_result.analysis is None:
                results.append(
                    ScoreCalculationResult(
                        position=analysis_result.position,
                        score=None,
                        error=analysis_result.error,
                    )
                )
                continue

            try:
                results.append(
                    ScoreCalculationResult(
                        position=analysis_result.position,
                        score=self.score(
                            analysis_result.analysis,
                            relative_strength_score=relative_scores.get(
                                analysis_result.analysis.code, 50
                            ),
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Failed to score analysis for %s",
                    analysis_result.position.code,
                )
                results.append(
                    ScoreCalculationResult(
                        position=analysis_result.position,
                        score=None,
                        error=str(exc),
                    )
                )
        return tuple(results)

    def _trend_component(self, analysis: AnalysisResult) -> ScoreComponent:
        ratio_by_trend = {"Bullish": 1.0, "Neutral": 0.55, "Bearish": 0.2}
        ratio = ratio_by_trend.get(analysis.trend, 0.0)
        return _component(
            name="Trend",
            weight=self._settings.trend_weight,
            ratio=ratio,
            reason=f"Trend is {analysis.trend}",
        )

    def _volume_component(self, analysis: AnalysisResult) -> ScoreComponent:
        if _has_reason(analysis, "Volume breakout"):
            ratio = 1.0
            reason = "Volume breakout confirmed"
        elif _has_reason(analysis, "Volume below rolling average"):
            ratio = 0.2
            reason = "Volume below rolling average"
        else:
            ratio = 0.55
            reason = "Volume signal is neutral"

        return _component(
            name="Volume",
            weight=self._settings.volume_weight,
            ratio=ratio,
            reason=reason,
        )

    def _momentum_component(self, analysis: AnalysisResult) -> ScoreComponent:
        ratio_by_momentum = {"Strong": 1.0, "Medium": 0.55, "Weak": 0.2}
        ratio = ratio_by_momentum.get(analysis.momentum, 0.0)
        return _component(
            name="Momentum",
            weight=self._settings.momentum_weight,
            ratio=ratio,
            reason=f"Momentum is {analysis.momentum}",
        )

    def _risk_component(self, analysis: AnalysisResult) -> ScoreComponent:
        ratio_by_risk = {"Low": 1.0, "Medium": 0.55, "High": 0.1}
        ratio = ratio_by_risk.get(analysis.risk, 0.0)
        return _component(
            name="Risk",
            weight=self._settings.risk_weight,
            ratio=ratio,
            reason=f"Risk is {analysis.risk}",
        )

    def _relative_strength_component(
        self, relative_strength_score: int
    ) -> ScoreComponent:
        ratio = max(0.0, min(1.0, relative_strength_score / 100))
        return _component(
            name="Relative Strength",
            weight=self._settings.relative_strength_weight,
            ratio=ratio,
            reason=f"Relative strength score is {relative_strength_score}",
        )

    def _confidence(self, analysis: AnalysisResult) -> float:
        confidence = self._settings.minimum_confidence + (
            len(analysis.reasons) * self._settings.reason_confidence_step
        )
        return max(
            self._settings.minimum_confidence,
            min(self._settings.maximum_confidence, confidence),
        )


def _component(name: str, weight: int, ratio: float, reason: str) -> ScoreComponent:
    score = round(weight * ratio)
    return ScoreComponent(name=name, score=score, weight=weight, reason=reason)


def _has_reason(analysis: AnalysisResult, needle: str) -> bool:
    return any(needle in reason for reason in analysis.reasons)


def _rating_for_score(score: int) -> str:
    if score >= 85:
        return "★★★★★"
    if score >= 70:
        return "★★★★☆"
    if score >= 55:
        return "★★★☆☆"
    if score >= 40:
        return "★★☆☆☆"
    return "★☆☆☆☆"


def _relative_strength_scores(
    analysis_results: tuple[AnalysisCalculationResult, ...],
) -> dict[str, int]:
    analyses = [
        result.analysis
        for result in analysis_results
        if result.analysis is not None and result.analysis.stock_return is not None
    ]
    if not analyses:
        return {}

    market_return = sum(item.stock_return or 0 for item in analyses) / len(analyses)
    sector_returns = _sector_returns(analyses)
    scores: dict[str, int] = {}
    for analysis in analyses:
        stock_return = analysis.stock_return or 0
        sector_return = sector_returns.get(analysis.sector, market_return)
        sector_delta = stock_return - sector_return
        market_delta = stock_return - market_return
        raw_score = 50 + (sector_delta * 500) + (market_delta * 500)
        scores[analysis.code] = round(max(0, min(100, raw_score)))
    return scores


def _sector_returns(analyses: list[AnalysisResult]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for analysis in analyses:
        grouped.setdefault(analysis.sector, []).append(analysis.stock_return or 0)
    return {
        sector: sum(values) / len(values)
        for sector, values in grouped.items()
        if values
    }
