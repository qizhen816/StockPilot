"""Explainable stock scoring based on analysis results."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    ScoreCalculationResult,
    ScoreComponent,
    ScorerSettings,
    StockScore,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _RelativeStrengthMetric:
    score: int
    reason: str


class ScoreEngine:
    """Convert analysis output into explainable 0-100 stock scores."""

    def __init__(self, settings: ScorerSettings) -> None:
        """Create a score engine with immutable weight settings."""
        self._settings = settings

    def score(
        self,
        analysis: AnalysisResult,
        relative_strength_score: int = 50,
        relative_strength_reason: str | None = None,
    ) -> StockScore:
        """Score one analysis result with component-level explanations."""
        components = (
            self._trend_component(analysis),
            self._momentum_component(analysis),
            self._volume_component(analysis),
            self._risk_component(analysis),
            self._relative_strength_component(
                relative_strength_score,
                relative_strength_reason
                or f"Relative strength score is {relative_strength_score}",
            ),
        )
        total_score = sum(component.score for component in components)
        clamped_score = max(0, min(self._settings.maximum_score, total_score))

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
        relative_metrics = _relative_strength_metrics(analysis_results)
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
                relative_metric = relative_metrics.get(
                    analysis_result.analysis.code,
                    _RelativeStrengthMetric(
                        score=50,
                        reason="Relative strength data is unavailable",
                    ),
                )
                results.append(
                    ScoreCalculationResult(
                        position=analysis_result.position,
                        score=self.score(
                            analysis_result.analysis,
                            relative_strength_score=relative_metric.score,
                            relative_strength_reason=relative_metric.reason,
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
        self, relative_strength_score: int, reason: str
    ) -> ScoreComponent:
        ratio = max(0.0, min(1.0, relative_strength_score / 100))
        return _component(
            name="Relative Strength",
            weight=self._settings.relative_strength_weight,
            ratio=ratio,
            reason=reason,
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
    ratings = (
        (95, "★★★★★"),
        (90, "★★★★☆"),
        (80, "★★★★"),
        (70, "★★★★☆"),
        (60, "★★★☆☆"),
        (50, "★★☆☆☆"),
    )
    for threshold, rating in ratings:
        if score >= threshold:
            return rating
    return "★☆☆☆☆"


def _relative_strength_metrics(
    analysis_results: tuple[AnalysisCalculationResult, ...],
) -> dict[str, _RelativeStrengthMetric]:
    analyses = [
        result.analysis
        for result in analysis_results
        if result.analysis is not None and result.analysis.stock_return is not None
    ]
    if not analyses:
        return {}

    market_return = sum(item.stock_return or 0 for item in analyses) / len(analyses)
    sector_returns = _sector_returns(analyses)
    portfolio_ranks = _portfolio_ranks(analyses)
    sector_ranks = _sector_ranks(analyses)
    metrics: dict[str, _RelativeStrengthMetric] = {}
    for analysis in analyses:
        stock_return = analysis.stock_return or 0
        sector_return = sector_returns.get(analysis.sector, market_return)
        sector_delta = stock_return - sector_return
        market_delta = stock_return - market_return
        rank_score = _rank_score(portfolio_ranks[analysis.code], len(analyses))
        raw_score = (rank_score * 0.6) + 50 + (sector_delta * 300) + (
            market_delta * 300
        )
        portfolio_rank = portfolio_ranks[analysis.code]
        sector_rank, sector_total = sector_ranks[analysis.code]
        metrics[analysis.code] = _RelativeStrengthMetric(
            score=round(max(0, min(100, raw_score))),
            reason=(
                f"Relative strength rank {portfolio_rank} of {len(analyses)}; "
                f"sector rank {sector_rank} of {sector_total}"
            ),
        )
    return metrics


def _sector_returns(analyses: list[AnalysisResult]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for analysis in analyses:
        grouped.setdefault(analysis.sector, []).append(analysis.stock_return or 0)
    return {
        sector: sum(values) / len(values)
        for sector, values in grouped.items()
        if values
    }


def _portfolio_ranks(analyses: list[AnalysisResult]) -> dict[str, int]:
    ranked = sorted(
        analyses,
        key=lambda analysis: analysis.stock_return or 0,
        reverse=True,
    )
    return {analysis.code: index for index, analysis in enumerate(ranked, start=1)}


def _sector_ranks(analyses: list[AnalysisResult]) -> dict[str, tuple[int, int]]:
    grouped: dict[str, list[AnalysisResult]] = {}
    for analysis in analyses:
        grouped.setdefault(analysis.sector, []).append(analysis)

    ranks: dict[str, tuple[int, int]] = {}
    for sector_analyses in grouped.values():
        ranked = sorted(
            sector_analyses,
            key=lambda analysis: analysis.stock_return or 0,
            reverse=True,
        )
        total = len(ranked)
        for index, analysis in enumerate(ranked, start=1):
            ranks[analysis.code] = (index, total)
    return ranks


def _rank_score(rank: int, total: int) -> float:
    if total <= 1:
        return 50.0
    return 100.0 * (total - rank) / (total - 1)
