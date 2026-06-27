"""Trading decision support rules."""

from __future__ import annotations

import logging

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    DecisionCalculationResult,
    DecisionResult,
    DecisionSettings,
    ScoreCalculationResult,
    StockScore,
)

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Generate explainable trading decisions from scores and analysis."""

    def __init__(self, settings: DecisionSettings) -> None:
        """Create a decision engine with immutable thresholds."""
        self._settings = settings

    def decide_all(
        self,
        score_results: tuple[ScoreCalculationResult, ...],
        analysis_results: tuple[AnalysisCalculationResult, ...],
    ) -> tuple[DecisionCalculationResult, ...]:
        """Generate decisions for all successful score results."""
        analysis_by_code = {
            result.analysis.code: result.analysis
            for result in analysis_results
            if result.analysis is not None
        }
        decisions: list[DecisionCalculationResult] = []
        for score_result in score_results:
            if score_result.score is None:
                decisions.append(
                    DecisionCalculationResult(
                        position=score_result.position,
                        decision=None,
                        error=score_result.error,
                    )
                )
                continue
            analysis = analysis_by_code.get(score_result.score.code)
            decisions.append(
                DecisionCalculationResult(
                    position=score_result.position,
                    decision=self.decide(score_result.score, analysis),
                )
            )
        return tuple(decisions)

    def decide(
        self,
        score: StockScore,
        analysis: AnalysisResult | None,
    ) -> DecisionResult:
        """Generate one explainable trading decision."""
        reasons = [
        ]
        if analysis is not None:
            reasons.append(f"Trend is {analysis.trend}")
        reasons.extend(
            (
                f"Relative strength score is {score.relative_strength_score}",
                f"Risk is {score.risk}",
            )
        )
        if analysis is not None:
            reasons.append(f"Volume status is {analysis.volume_status}")
            reasons.append(f"Momentum is {analysis.momentum}")
        reasons.append(f"Score {score.score} with rating {score.rating}")

        action = self._action(score, analysis)
        confidence = min(0.90, max(score.confidence, 0.55))
        return DecisionResult(
            code=score.code,
            name=score.name,
            action=action,
            confidence=confidence,
            risk=score.risk,
            reasons=tuple(reasons),
        )

    def _action(self, score: StockScore, analysis: AnalysisResult | None) -> str:
        action = "Hold"
        if score.risk == "High" and score.score <= 40:
            action = "Exit"
        elif score.risk == "High":
            action = "Reduce Position"
        elif score.score >= self._settings.high_score_threshold:
            if analysis is not None and analysis.trend == "Bullish":
                action = "Strong Hold"
        elif score.score < self._settings.low_score_threshold:
            action = "Watch"
        elif analysis is not None and analysis.trend == "Bullish":
            action = "Hold"
        elif analysis is not None and analysis.risk == "Medium":
            action = "Watch"
        return action
