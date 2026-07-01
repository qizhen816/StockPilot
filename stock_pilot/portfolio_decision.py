"""Portfolio-level decision support for StockPilot."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    PortfolioAction,
    PortfolioAnalysis,
    PortfolioDecisionPlan,
    PortfolioDecisionSettings,
    ReplacementSuggestion,
    RiskBreakdown,
    ScanCandidate,
    ScannerResult,
    ScoreCalculationResult,
    StockScore,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _DecisionContext:
    score: StockScore
    analysis: AnalysisResult | None
    rank: int
    relative_rank: int
    risk_rank: int
    trend_rank: int
    total_positions: int
    candidates: tuple[ScanCandidate, ...]
    portfolio_analysis: PortfolioAnalysis


class PortfolioDecisionEngine:
    """Generate portfolio-aware actions for existing holdings."""

    def __init__(self, settings: PortfolioDecisionSettings) -> None:
        """Create an engine with immutable portfolio decision thresholds."""
        self._settings = settings

    def build_plan(
        self,
        score_results: tuple[ScoreCalculationResult, ...],
        analysis_results: tuple[AnalysisCalculationResult, ...],
        portfolio_analysis: PortfolioAnalysis,
        scanner_result: ScannerResult,
    ) -> PortfolioDecisionPlan:
        """Build a tomorrow-focused portfolio decision plan."""
        scored_positions = [
            result.score for result in score_results if result.score is not None
        ]
        if not scored_positions:
            return PortfolioDecisionPlan(
                actions=(),
                replacements=(),
                portfolio_score=0.0,
                portfolio_risk_score=portfolio_analysis.portfolio_risk_score,
                summary="当前没有可用评分，无法生成组合决策计划。",
                reasons=("No valid stock scores are available",),
            )

        ranked_scores = sorted(
            scored_positions,
            key=lambda score: score.score,
            reverse=True,
        )
        analysis_by_code = _analysis_by_code(analysis_results)
        candidates = tuple(scanner_result.candidates)
        relative_ranks = _relative_ranks(ranked_scores)
        risk_ranks = _risk_ranks(ranked_scores)
        trend_ranks = _trend_ranks(ranked_scores, analysis_by_code)
        actions = tuple(
            self._build_action(
                _DecisionContext(
                    score=score,
                    analysis=analysis_by_code.get(score.code),
                    rank=index,
                    relative_rank=relative_ranks[score.code],
                    risk_rank=risk_ranks[score.code],
                    trend_rank=trend_ranks[score.code],
                    total_positions=len(ranked_scores),
                    candidates=candidates,
                    portfolio_analysis=portfolio_analysis,
                )
            )
            for index, score in enumerate(ranked_scores, start=1)
        )
        replacements = tuple(
            action.replacement for action in actions if action.replacement is not None
        )
        return PortfolioDecisionPlan(
            actions=actions,
            replacements=replacements,
            portfolio_score=portfolio_analysis.portfolio_trend_score,
            portfolio_risk_score=portfolio_analysis.portfolio_risk_score,
            summary=_plan_summary(actions, replacements),
            reasons=_plan_reasons(portfolio_analysis, actions),
        )

    def _build_action(
        self,
        context: _DecisionContext,
    ) -> PortfolioAction:
        replacement = self._replacement_for(context)
        action = self._action(context, replacement)
        confidence = self._confidence(context, action)
        priority = _execution_priority(action, confidence, context.score.risk)
        return PortfolioAction(
            code=context.score.code,
            name=context.score.name,
            action=action,
            confidence=confidence,
            risk=context.score.risk,
            risk_breakdown=_risk_breakdown(context),
            score=context.score.score,
            rank=context.rank,
            relative_rank=context.relative_rank,
            risk_rank=context.risk_rank,
            trend_rank=context.trend_rank,
            total_positions=context.total_positions,
            relative_strength_score=context.score.relative_strength_score,
            execution_priority=priority,
            replacement=replacement if action == "Replace Candidate" else None,
            reasons=self._reasons(context, replacement),
        )

    def _action(
        self,
        context: _DecisionContext,
        replacement: ReplacementSuggestion | None,
    ) -> str:
        score = context.score
        analysis = context.analysis
        if score.risk == "High" and score.score <= self._settings.exit_score_threshold:
            return "Exit"
        if score.risk == "High" or score.score <= self._settings.reduce_score_threshold:
            return "Reduce Position"
        if score.score <= self._settings.replace_score_threshold and replacement:
            return "Replace Candidate"
        if (
            score.score >= self._settings.strong_hold_score_threshold
            and score.risk == "Low"
            and context.rank <= max(1, context.total_positions // 3)
            and analysis is not None
            and analysis.trend == "Bullish"
        ):
            return "Strong Hold"
        if score.score >= self._settings.hold_score_threshold:
            return "Hold"
        return "Watch"

    def _confidence(
        self,
        context: _DecisionContext,
        action: str,
    ) -> float:
        score = context.score
        confidence = score.confidence
        if context.rank <= max(1, context.total_positions // 3):
            confidence += 0.04
        if context.rank == context.total_positions and context.total_positions > 1:
            confidence -= 0.05
        if score.risk == "Low":
            confidence += 0.04
        elif score.risk == "High":
            confidence -= 0.08
        if action in {"Reduce Position", "Exit", "Replace Candidate", "Strong Hold"}:
            confidence += 0.03

        if context.analysis is not None:
            confidence += _analysis_confidence_adjustment(context.analysis)

        return min(
            self._settings.maximum_confidence,
            max(self._settings.minimum_confidence, confidence),
        )

    def _replacement_for(
        self, context: _DecisionContext
    ) -> ReplacementSuggestion | None:
        score = context.score
        for candidate in context.candidates:
            if candidate.code == score.code:
                continue
            score_gap = candidate.score - score.score
            if score_gap < self._settings.replacement_min_score_gap:
                continue
            risk_improvement = _risk_points(score.risk) - _risk_points(candidate.risk)
            expected_delta = round(score_gap / max(1, context.total_positions))
            trend_improvement = _trend_improvement(context.analysis, candidate)
            relative_improvement = max(
                0, candidate.score - score.relative_strength_score
            )
            replacement_confidence = _replacement_confidence(
                score_gap=score_gap,
                trend_improvement=trend_improvement,
                relative_improvement=relative_improvement,
                risk_improvement=risk_improvement,
                candidate_confidence=candidate.confidence,
                switch_cost_penalty=self._settings.replacement_switch_cost_penalty,
            )
            if replacement_confidence < self._settings.replacement_min_confidence:
                continue
            return ReplacementSuggestion(
                current_code=score.code,
                current_name=score.name,
                suggested_code=candidate.code,
                suggested_name=candidate.name,
                confidence=min(
                    self._settings.maximum_confidence,
                    max(self._settings.minimum_confidence, candidate.confidence),
                ),
                score_gap=score_gap,
                trend_improvement=trend_improvement,
                relative_strength_improvement=relative_improvement,
                risk_improvement=risk_improvement,
                expected_portfolio_score_delta=expected_delta,
                replacement_confidence=replacement_confidence,
                reasons=(
                    f"Replacement confidence is {replacement_confidence:.0%}",
                    f"Candidate score is higher by {score_gap}",
                    f"Expected portfolio score improves by {expected_delta}",
                    f"Trend improvement is {trend_improvement}",
                    f"Relative strength improvement is {relative_improvement}",
                    f"Risk improvement is {risk_improvement}",
                    "Switch cost is included in confidence",
                    f"Candidate risk is {candidate.risk}",
                    "Candidate passed scanner filters",
                ),
            )
        return None

    def _reasons(
        self,
        context: _DecisionContext,
        replacement: ReplacementSuggestion | None,
    ) -> tuple[str, ...]:
        score = context.score
        reasons: list[str] = []
        if context.analysis is not None:
            reasons.extend(_decision_explanation(context))
        else:
            reasons.extend(
                (
                    f"Relative strength score is {score.relative_strength_score}",
                    (
                        f"Relative rank {context.relative_rank} "
                        f"of {context.total_positions}"
                    ),
                    f"Risk is {score.risk}",
                    f"Risk rank {context.risk_rank} of {context.total_positions}",
                )
            )
        reasons.extend(
            (
                f"Portfolio rank {context.rank} of {context.total_positions}",
                f"Score is {score.score}",
            )
        )
        if replacement is not None:
            reasons.append(
                f"Replacement candidate {replacement.suggested_name} has higher score"
            )
            reasons.append(
                f"Replacement confidence is {replacement.replacement_confidence:.0%}"
            )
        return tuple(reasons)


def _analysis_by_code(
    analysis_results: tuple[AnalysisCalculationResult, ...],
) -> dict[str, AnalysisResult]:
    return {
        result.analysis.code: result.analysis
        for result in analysis_results
        if result.analysis is not None
    }


def _analysis_confidence_adjustment(analysis: AnalysisResult) -> float:
    adjustment = 0.0
    if analysis.trend == "Bullish":
        adjustment += 0.04
    elif analysis.trend == "Bearish":
        adjustment -= 0.04
    if analysis.momentum == "Strong":
        adjustment += 0.03
    elif analysis.momentum == "Weak":
        adjustment -= 0.03
    if analysis.volume_status in {"Strong", "Breakout"}:
        adjustment += 0.03
    elif analysis.volume_status == "Shrink":
        adjustment -= 0.02
    return adjustment


def _risk_breakdown(context: _DecisionContext) -> RiskBreakdown:
    analysis = context.analysis
    volatility_risk = "Medium"
    trend_risk = "Medium"
    if analysis is not None:
        volatility_risk = "High" if analysis.risk == "High" else analysis.risk
        trend_risk = {"Bullish": "Low", "Neutral": "Medium", "Bearish": "High"}.get(
            analysis.trend,
            "Medium",
        )
    concentration_risk = (
        "High"
        if context.portfolio_analysis.concentration_top_position_pct >= 0.25
        else "Medium"
        if context.portfolio_analysis.concentration_top_position_pct >= 0.18
        else "Low"
    )
    return RiskBreakdown(
        volatility_risk=volatility_risk,
        trend_risk=trend_risk,
        concentration_risk=concentration_risk,
        portfolio_risk=context.portfolio_analysis.portfolio_risk_level,
    )


def _execution_priority(action: str, confidence: float, risk: str) -> str:
    if action == "Exit" and confidence >= 0.78:
        return "Immediate"
    if action in {"Reduce Position", "Replace Candidate"} and confidence >= 0.78:
        return "Today"
    if action in {"Reduce Position", "Replace Candidate"}:
        return "Observe"
    if action in {"Strong Hold", "Hold"} and risk != "High":
        return "This Week"
    return "Future"


def _replacement_confidence(  # noqa: PLR0913
    score_gap: int,
    trend_improvement: int,
    relative_improvement: int,
    risk_improvement: int,
    candidate_confidence: float,
    switch_cost_penalty: float,
) -> float:
    confidence = 0.50 + min(0.16, score_gap / 100)
    confidence += min(0.10, trend_improvement / 180)
    confidence += min(0.10, relative_improvement / 300)
    confidence += max(-0.08, min(0.08, risk_improvement / 40))
    confidence += (candidate_confidence - 0.65) * 0.35
    confidence -= switch_cost_penalty
    return max(0.0, min(0.90, confidence))


def _decision_explanation(context: _DecisionContext) -> tuple[str, ...]:
    analysis = context.analysis
    if analysis is None:
        return ()
    explanations: list[str] = []
    if analysis.trend == "Bullish":
        explanations.append("Trend remains intact")
    elif analysis.trend == "Neutral":
        explanations.append("Trend is consolidating")
    else:
        explanations.append("Trend has weakened")

    if (
        analysis.momentum == "Strong"
        and analysis.volume_status in {"Strong", "Breakout"}
    ):
        explanations.append("Momentum and volume confirm the move")
    elif analysis.momentum == "Strong":
        explanations.append("Momentum is improving but volume confirmation is limited")
    elif analysis.momentum == "Weak":
        explanations.append("Momentum is weak, wait for confirmation")

    if context.score.relative_strength_score >= 70:
        explanations.append("Relative strength remains competitive")
    elif context.score.relative_strength_score <= 40:
        explanations.append("Relative strength is lagging the portfolio")

    if analysis.risk == "High":
        explanations.append("Risk is elevated, avoid emotional averaging down")
    elif analysis.risk == "Low":
        explanations.append("Risk remains controlled")

    explanations.extend(
        (
            f"Trend rank {context.trend_rank} of {context.total_positions}",
            f"Relative rank {context.relative_rank} of {context.total_positions}",
            f"Risk rank {context.risk_rank} of {context.total_positions}",
        )
    )
    return tuple(explanations)


def _relative_ranks(scores: list[StockScore]) -> dict[str, int]:
    ranked = sorted(
        scores,
        key=lambda score: score.relative_strength_score,
        reverse=True,
    )
    return {score.code: index for index, score in enumerate(ranked, start=1)}


def _risk_ranks(scores: list[StockScore]) -> dict[str, int]:
    ranked = sorted(scores, key=lambda score: _risk_points(score.risk))
    return {score.code: index for index, score in enumerate(ranked, start=1)}


def _trend_ranks(
    scores: list[StockScore], analysis_by_code: dict[str, AnalysisResult]
) -> dict[str, int]:
    ranked = sorted(
        scores,
        key=lambda score: _trend_points(analysis_by_code.get(score.code)),
        reverse=True,
    )
    return {score.code: index for index, score in enumerate(ranked, start=1)}


def _trend_points(analysis: AnalysisResult | None) -> int:
    if analysis is None:
        return 1
    return {"Bullish": 3, "Neutral": 2, "Bearish": 1}.get(analysis.trend, 1)


def _risk_points(risk: str) -> int:
    return {"Low": 1, "Medium": 2, "High": 3}.get(risk, 2)


def _trend_improvement(
    analysis: AnalysisResult | None, candidate: ScanCandidate
) -> int:
    current = _trend_points(analysis)
    candidate_points = (
        3 if any("Trend is Bullish" in reason for reason in candidate.reasons) else 2
    )
    return max(0, (candidate_points - current) * 18)


def _plan_summary(
    actions: tuple[PortfolioAction, ...],
    replacements: tuple[ReplacementSuggestion, ...],
) -> str:
    if not actions:
        return "当前没有可执行的组合动作。"
    strongest = actions[0]
    weakest = actions[-1]
    if replacements:
        replacement = replacements[0]
        return (
            f"明日组合重点是继续跟踪 {strongest.name}，同时观察是否用 "
            f"{replacement.suggested_name} 替换 {replacement.current_name}。"
        )
    return f"明日组合重点是继续跟踪 {strongest.name}，重点防守 {weakest.name}。"


def _plan_reasons(
    portfolio_analysis: PortfolioAnalysis,
    actions: tuple[PortfolioAction, ...],
) -> tuple[str, ...]:
    if not actions:
        return ("No portfolio actions are available",)
    return (
        f"Portfolio trend score is {portfolio_analysis.portfolio_trend_score:.2f}",
        f"Portfolio risk score is {portfolio_analysis.portfolio_risk_score:.2f}",
        f"Strongest holding is {actions[0].name}",
        f"Weakest holding is {actions[-1].name}",
    )
