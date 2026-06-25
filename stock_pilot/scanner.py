"""Market candidate scanning from scored stocks."""

from __future__ import annotations

import logging

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    ScanCandidate,
    ScannerResult,
    ScannerSettings,
    ScoreCalculationResult,
)

logger = logging.getLogger(__name__)


class MarketScanner:
    """Rank scored stocks into an explainable candidate list."""

    def __init__(self, settings: ScannerSettings) -> None:
        """Create a scanner with immutable filtering settings."""
        self._settings = settings

    def scan(
        self,
        score_results: tuple[ScoreCalculationResult, ...],
        analysis_results: tuple[AnalysisCalculationResult, ...] = (),
    ) -> ScannerResult:
        """Filter and rank score results into market candidates."""
        candidates: list[ScanCandidate] = []
        skipped_count = 0
        analysis_by_code = _analysis_by_code(analysis_results)

        for result in score_results:
            if result.score is None:
                skipped_count += 1
                continue
            if result.score.score < self._settings.min_score:
                skipped_count += 1
                continue
            if result.score.risk not in self._settings.allowed_risk_levels:
                skipped_count += 1
                continue
            analysis = analysis_by_code.get(result.score.code)
            if analysis is not None and not self._passes_analysis_rules(analysis):
                skipped_count += 1
                continue
            if (
                result.score.relative_strength_score
                < self._settings.min_relative_strength_score
            ):
                skipped_count += 1
                continue

            candidates.append(
                ScanCandidate(
                    code=result.score.code,
                    name=result.score.name,
                    score=result.score.score,
                    rating=result.score.rating,
                    risk=result.score.risk,
                    confidence=result.score.confidence,
                    reasons=result.score.reasons,
                )
            )

        ranked_candidates = sorted(
            candidates,
            key=lambda candidate: (candidate.score, candidate.confidence),
            reverse=True,
        )
        return ScannerResult(
            candidates=tuple(ranked_candidates[: self._settings.candidate_limit]),
            skipped_count=skipped_count,
        )

    def _passes_analysis_rules(self, analysis: AnalysisResult) -> bool:
        if analysis.trend != self._settings.required_trend:
            return False
        return analysis.volume_status in self._settings.min_volume_statuses


def _analysis_by_code(
    analysis_results: tuple[AnalysisCalculationResult, ...],
) -> dict[str, AnalysisResult]:
    return {
        result.analysis.code: result.analysis
        for result in analysis_results
        if result.analysis is not None
    }
