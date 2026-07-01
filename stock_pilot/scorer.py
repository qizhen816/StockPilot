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
        penalty, penalty_reason = self._long_term_trend_penalty(analysis)
        clamped_score = max(0, min(self._settings.maximum_score, total_score - penalty))
        reasons = [component.reason for component in components]
        if penalty:
            reasons.append(penalty_reason)

        return StockScore(
            code=analysis.code,
            name=analysis.name,
            score=clamped_score,
            rating=_rating_for_score(clamped_score),
            risk=analysis.risk,
            confidence=self._confidence(analysis, relative_strength_score),
            components=components,
            reasons=tuple(reasons),
            relative_strength_score=relative_strength_score,
        )

    def score_all(
        self, analysis_results: tuple[AnalysisCalculationResult, ...]
    ) -> tuple[ScoreCalculationResult, ...]:
        """Score all successful analysis results without stopping on failures."""
        results: list[ScoreCalculationResult] = []
        relative_metrics = self._relative_strength_metrics(analysis_results)
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
        return self._settings.minimum_confidence

    def _long_term_trend_penalty(self, analysis: AnalysisResult) -> tuple[int, str]:
        if analysis.long_term_distance_pct is None:
            return 0, ""
        if analysis.long_term_distance_pct >= 0:
            return 0, ""
        severity = min(1.0, abs(analysis.long_term_distance_pct) / 0.12)
        penalty = round(self._settings.long_term_trend_penalty * severity)
        return penalty, "Long-term trend penalty: below MA60"

    def _confidence(
        self,
        analysis: AnalysisResult,
        relative_strength_score: int,
    ) -> float:
        confidence = 0.62
        agreement = _signal_agreement(analysis, relative_strength_score)
        confidence += agreement * self._settings.reason_confidence_step
        if analysis.volume_status in {"Strong", "Breakout"}:
            confidence += 0.06
        elif analysis.volume_status in {"Shrink", "Unknown"}:
            confidence -= 0.06
        if analysis.risk == "High":
            confidence -= 0.10
        elif analysis.risk == "Low":
            confidence += 0.04
        if (
            analysis.long_term_distance_pct is not None
            and analysis.long_term_distance_pct < 0
        ):
            confidence -= 0.08
        return max(
            self._settings.minimum_confidence,
            min(self._settings.maximum_confidence, confidence),
        )

    def _relative_strength_metrics(
        self,
        analysis_results: tuple[AnalysisCalculationResult, ...],
    ) -> dict[str, _RelativeStrengthMetric]:
        analyses = [
            result.analysis
            for result in analysis_results
            if result.analysis is not None
        ]
        analyses = [
            analysis for analysis in analyses if _has_multi_period_return(analysis)
        ]
        if not analyses:
            return {}

        weighted_returns = {
            analysis.code: _weighted_return(
                analysis=analysis,
                weight_5d=self._settings.relative_strength_5d_weight,
                weight_20d=self._settings.relative_strength_20d_weight,
                weight_60d=self._settings.relative_strength_60d_weight,
            )
            for analysis in analyses
        }
        market_return = sum(weighted_returns.values()) / len(weighted_returns)
        sector_returns = _sector_weighted_returns(analyses, weighted_returns)
        portfolio_ranks = _portfolio_ranks(analyses, weighted_returns)
        sector_ranks = _sector_ranks(analyses, weighted_returns)
        metrics: dict[str, _RelativeStrengthMetric] = {}
        for analysis in analyses:
            stock_return = weighted_returns[analysis.code]
            sector_return = sector_returns.get(analysis.sector, market_return)
            sector_delta = stock_return - sector_return
            market_delta = stock_return - market_return
            rank_score = _rank_score(portfolio_ranks[analysis.code], len(analyses))
            raw_score = (rank_score * 0.55) + 50 + (sector_delta * 220) + (
                market_delta * 220
            )
            portfolio_rank = portfolio_ranks[analysis.code]
            sector_rank, sector_total = sector_ranks[analysis.code]
            metrics[analysis.code] = _RelativeStrengthMetric(
                score=round(max(0, min(100, raw_score))),
                reason=(
                    f"Relative strength multi-period rank {portfolio_rank} "
                    f"of {len(analyses)}; sector rank {sector_rank} "
                    f"of {sector_total}; weighted return {stock_return:.2%}"
                ),
            )
        return metrics


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


def _signal_agreement(analysis: AnalysisResult, relative_strength_score: int) -> int:
    bullish = 0
    bearish = 0
    if analysis.trend == "Bullish":
        bullish += 1
    elif analysis.trend == "Bearish":
        bearish += 1
    if analysis.momentum == "Strong":
        bullish += 1
    elif analysis.momentum == "Weak":
        bearish += 1
    if analysis.volume_status in {"Strong", "Breakout"}:
        bullish += 1
    elif analysis.volume_status == "Shrink":
        bearish += 1
    if relative_strength_score >= 70:
        bullish += 1
    elif relative_strength_score <= 40:
        bearish += 1
    if analysis.risk == "High":
        bearish += 1
    return bullish - bearish


def _has_multi_period_return(analysis: AnalysisResult) -> bool:
    return any(
        value is not None
        for value in (analysis.return_5d, analysis.return_20d, analysis.return_60d)
    )


def _weighted_return(
    analysis: AnalysisResult,
    weight_5d: float,
    weight_20d: float,
    weight_60d: float,
) -> float:
    return (
        (analysis.return_5d or 0.0) * weight_5d
        + (analysis.return_20d or 0.0) * weight_20d
        + (analysis.return_60d or 0.0) * weight_60d
    )


def _sector_weighted_returns(
    analyses: list[AnalysisResult],
    weighted_returns: dict[str, float],
) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for analysis in analyses:
        grouped.setdefault(analysis.sector, []).append(
            weighted_returns[analysis.code]
        )
    return {
        sector: sum(values) / len(values)
        for sector, values in grouped.items()
        if values
    }


def _portfolio_ranks(
    analyses: list[AnalysisResult],
    weighted_returns: dict[str, float],
) -> dict[str, int]:
    ranked = sorted(
        analyses,
        key=lambda analysis: weighted_returns[analysis.code],
        reverse=True,
    )
    return {analysis.code: index for index, analysis in enumerate(ranked, start=1)}


def _sector_ranks(
    analyses: list[AnalysisResult],
    weighted_returns: dict[str, float],
) -> dict[str, tuple[int, int]]:
    grouped: dict[str, list[AnalysisResult]] = {}
    for analysis in analyses:
        grouped.setdefault(analysis.sector, []).append(analysis)

    ranks: dict[str, tuple[int, int]] = {}
    for sector_analyses in grouped.values():
        ranked = sorted(
            sector_analyses,
            key=lambda analysis: weighted_returns[analysis.code],
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
