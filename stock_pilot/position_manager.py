"""Portfolio-aware position management recommendations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from math import isnan

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    IndicatorCalculationResult,
    Portfolio,
    PortfolioAnalysis,
    PortfolioValuationResult,
    Position,
    PositionManagerSettings,
    PositionRecommendation,
    PositionValuation,
    RiskBreakdown,
    ScoreCalculationResult,
    StockScore,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PositionManagementInput:
    """Input bundle for portfolio-aware position management."""

    portfolio: Portfolio
    analysis_results: tuple[AnalysisCalculationResult, ...]
    score_results: tuple[ScoreCalculationResult, ...]
    portfolio_valuation: PortfolioValuationResult
    portfolio_analysis: PortfolioAnalysis
    indicator_results: tuple[IndicatorCalculationResult, ...]


@dataclass(frozen=True)
class _IndicatorMetrics:
    atr: float | None
    highest_close: float


@dataclass(frozen=True)
class _RecommendationContext:
    position: Position
    analysis: AnalysisResult | None
    score: StockScore | None
    valuation: PositionValuation
    portfolio_value: float
    portfolio_analysis: PortfolioAnalysis
    indicator_metrics: _IndicatorMetrics | None


@dataclass(frozen=True)
class _TargetDecision:
    state: str
    action: str
    recommended_pct: float
    risk: str
    confidence: float
    reasons: tuple[str, ...]


class PositionManager:
    """Recommend how much of each existing position to keep."""

    def __init__(self, settings: PositionManagerSettings) -> None:
        """Create a position manager with configurable sizing rules."""
        self._settings = settings

    def recommend_all(
        self,
        input_data: PositionManagementInput,
    ) -> tuple[PositionRecommendation, ...]:
        """Build position-size recommendations for all valued holdings."""
        if input_data.portfolio_valuation.valuation is None:
            logger.warning("Skipping position management without portfolio valuation")
            return ()

        analyses = {
            result.position.code: result.analysis
            for result in input_data.analysis_results
            if result.analysis is not None
        }
        scores = {
            result.position.code: result.score
            for result in input_data.score_results
            if result.score is not None
        }
        valuations = {
            item.code: item
            for item in input_data.portfolio_valuation.valuation.positions
        }
        indicator_metrics = {
            result.position.code: _extract_indicator_metrics(result)
            for result in input_data.indicator_results
            if result.indicators is not None
        }

        recommendations: list[PositionRecommendation] = []
        for position in input_data.portfolio.positions:
            valuation = valuations.get(position.code)
            if valuation is None:
                logger.warning(
                    "Skipping position recommendation for %s without valuation",
                    position.code,
                )
                continue

            recommendation = self._recommend(
                _RecommendationContext(
                    position=position,
                    analysis=analyses.get(position.code),
                    score=scores.get(position.code),
                    valuation=valuation,
                    portfolio_value=(
                        input_data.portfolio_valuation.valuation.total_market_value
                    ),
                    portfolio_analysis=input_data.portfolio_analysis,
                    indicator_metrics=indicator_metrics.get(position.code),
                )
            )
            recommendations.append(recommendation)

        return tuple(recommendations)

    def _recommend(self, context: _RecommendationContext) -> PositionRecommendation:
        current_pct = 1.0
        trend_stage = _trend_stage(context, self._settings)
        decision = self._decide_target(context, trend_stage)
        recommended_shares = int(
            round(context.position.shares * decision.recommended_pct)
        )
        current_drawdown_pct = _current_drawdown_pct(
            context.valuation.current_price,
            context.indicator_metrics,
        )
        stop_loss, trailing_stop, take_profit = self._build_atr_levels(
            valuation=context.valuation,
            analysis=context.analysis,
            indicator_metrics=context.indicator_metrics,
        )

        return PositionRecommendation(
            code=context.position.code,
            name=context.position.name,
            current_shares=context.position.shares,
            recommended_shares=recommended_shares,
            current_position_pct=current_pct,
            recommended_position_pct=decision.recommended_pct,
            state=decision.state,
            trend_stage=trend_stage,
            action=decision.action,
            confidence=decision.confidence,
            risk=decision.risk,
            risk_breakdown=_risk_breakdown(context),
            cost_price=context.valuation.cost_price,
            current_price=context.valuation.current_price,
            unrealized_pnl_pct=context.valuation.unrealized_pnl_pct,
            current_drawdown_pct=current_drawdown_pct,
            suggested_stop_loss=stop_loss,
            suggested_trailing_stop=trailing_stop,
            suggested_take_profit=take_profit,
            reasons=tuple(decision.reasons),
        )

    def _decide_target(  # noqa: PLR0911
        self, context: _RecommendationContext, trend_stage: str
    ) -> _TargetDecision:
        settings = self._settings
        analysis = context.analysis
        score = context.score
        valuation = context.valuation
        reasons: list[str] = []

        trend = analysis.trend if analysis is not None else "Unknown"
        momentum = analysis.momentum if analysis is not None else "Unknown"
        risk = (
            analysis.risk
            if analysis is not None
            else score.risk
            if score
            else "Medium"
        )
        distance_to_resistance = _distance_to_resistance(valuation, analysis)

        if analysis is None or score is None:
            reasons.extend(
                (
                    "Analysis or score is unavailable",
                    "Keep current position until signal quality improves",
                )
            )
            return self._target(
                state="FULL",
                action="Watch",
                pct=settings.full_position_pct,
                risk=risk,
                confidence=settings.minimum_confidence,
                reasons=reasons,
            )

        reasons.append(f"Trend is {trend}")
        reasons.append(f"Momentum is {momentum}")
        reasons.append(f"Risk is {risk}")
        reasons.append(f"Score is {score.score}")
        reasons.append(f"Trend stage is {trend_stage}")

        if valuation.unrealized_pnl_pct <= -0.10 and trend != "Bullish":
            reasons.extend(
                (
                    "Position is deeply underwater",
                    "No averaging down before right-side confirmation",
                )
            )
            return self._target(
                state="FULL",
                action="Watch",
                pct=settings.full_position_pct,
                risk=risk,
                confidence=self._confidence(score, analysis, reasons, -0.02),
                reasons=self._append_portfolio_reasons(
                    context, reasons, allow_add=False
                ),
            )

        if trend_stage == "BREAKDOWN":
            reasons.append("Trend breakdown is confirmed")
            return self._target(
                state="LIGHTEN",
                action="Reduce Position",
                pct=settings.breakdown_position_pct,
                risk=risk,
                confidence=self._confidence(score, analysis, reasons, 0.06),
                reasons=self._append_portfolio_reasons(
                    context, reasons, allow_add=False
                ),
            )

        if trend_stage == "PULLBACK":
            reasons.extend(
                (
                    "Current move is a pullback inside the broader trend",
                    "Hold first and monitor MA20 confirmation",
                )
            )
            return self._target(
                state="FULL",
                action="Watch",
                pct=settings.pullback_position_pct,
                risk=risk,
                confidence=self._confidence(score, analysis, reasons, -0.01),
                reasons=self._append_portfolio_reasons(
                    context, reasons, allow_add=False
                ),
            )

        if trend_stage == "LATE_UPTREND":
            reasons.extend(
                (
                    "Uptrend is mature and close to resistance",
                    "Protect part of the profit while keeping core exposure",
                )
            )
            return self._target(
                state="ACCUMULATE",
                action="Take Partial Profit",
                pct=settings.late_uptrend_position_pct,
                risk=risk,
                confidence=self._confidence(score, analysis, reasons, 0.05),
                reasons=self._append_portfolio_reasons(
                    context, reasons, allow_add=False
                ),
            )

        profit_protection = self._profit_protection_reason(valuation)
        if profit_protection is not None and trend == "Bullish":
            reasons.extend(
                (
                    profit_protection,
                    "Keep core position because trend remains bullish",
                )
            )
            pct = (
                settings.accumulate_position_pct
                if valuation.unrealized_pnl_pct
                >= max(settings.profit_protection_levels)
                else settings.full_position_pct
            )
            action = (
                "Take Partial Profit"
                if pct < settings.full_position_pct
                else "Continue Hold"
            )
            return self._target(
                state="ACCUMULATE" if pct < settings.full_position_pct else "FULL",
                action=action,
                pct=pct,
                risk=risk,
                confidence=self._confidence(score, analysis, reasons, 0.03),
                reasons=self._append_portfolio_reasons(
                    context, reasons, allow_add=False
                ),
            )

        if (
            trend == "Bullish"
            and momentum == "Strong"
            and risk == "Low"
            and (
                distance_to_resistance is None
                or distance_to_resistance > settings.wide_resistance_pct
            )
        ):
            reasons.append("Resistance has enough room")
            return self._target(
                state="FULL",
                action="Continue Hold",
                pct=settings.full_position_pct,
                risk=risk,
                confidence=self._confidence(score, analysis, reasons, 0.04),
                reasons=self._append_portfolio_reasons(
                    context, reasons, allow_add=False
                ),
            )

        if risk == "High":
            reasons.append("Risk is elevated but trend is not broken")
            return self._target(
                state="ACCUMULATE",
                action="Watch",
                pct=settings.accumulate_position_pct,
                risk=risk,
                confidence=self._confidence(score, analysis, reasons, 0.03),
                reasons=self._append_portfolio_reasons(
                    context, reasons, allow_add=False
                ),
            )

        reasons.append("Signal mix supports keeping current exposure")
        return self._target(
            state="FULL",
            action="Continue Hold",
            pct=settings.full_position_pct,
            risk=risk,
            confidence=self._confidence(score, analysis, reasons, 0.0),
            reasons=self._append_portfolio_reasons(
                context, reasons, allow_add=False
            ),
        )

    def _target(  # noqa: PLR0913
        self,
        state: str,
        action: str,
        pct: float,
        risk: str,
        confidence: float,
        reasons: list[str],
    ) -> _TargetDecision:
        return _TargetDecision(
            state=state,
            action=action,
            recommended_pct=pct,
            risk=risk,
            confidence=_clamp(
                confidence,
                self._settings.minimum_confidence,
                self._settings.maximum_confidence,
            ),
            reasons=tuple(_deduplicate(reasons)),
        )

    def _confidence(
        self,
        score: StockScore,
        analysis: AnalysisResult,
        reasons: list[str],
        adjustment: float,
    ) -> float:
        base = 0.58 + (score.score / 100 * 0.18) + (score.confidence * 0.14)
        if analysis.trend == "Bullish":
            base += 0.03
        if analysis.momentum == "Strong":
            base += 0.03
        if analysis.risk == "High":
            base -= 0.05
        if len(reasons) >= 5:
            base += 0.02
        return _clamp(
            base + adjustment,
            self._settings.minimum_confidence,
            self._settings.maximum_confidence,
        )

    def _append_portfolio_reasons(
        self,
        context: _RecommendationContext,
        reasons: list[str],
        allow_add: bool,
    ) -> list[str]:
        sector_weight = _sector_weight(context)
        position_weight = _ratio(
            context.valuation.market_value,
            context.portfolio_value,
        )
        if sector_weight > self._settings.sector_concentration_threshold:
            reasons.append(
                f"{context.position.sector} sector exposure is high at "
                f"{sector_weight:.2%}"
            )
        if position_weight > self._settings.position_concentration_threshold:
            reasons.append(f"Position concentration is high at {position_weight:.2%}")
        if not allow_add:
            reasons.append("No extra buying before cash management is implemented")
        return reasons

    def _profit_protection_reason(
        self,
        valuation: PositionValuation,
    ) -> str | None:
        passed_levels = [
            level
            for level in self._settings.profit_protection_levels
            if valuation.unrealized_pnl_pct >= level
        ]
        if not passed_levels:
            return None
        return f"Unrealized profit reached {max(passed_levels):.0%}"

    def _build_atr_levels(
        self,
        valuation: PositionValuation,
        analysis: AnalysisResult | None,
        indicator_metrics: _IndicatorMetrics | None,
    ) -> tuple[float | None, float | None, float | None]:
        if indicator_metrics is None or indicator_metrics.atr is None:
            take_profit = analysis.resistance if analysis is not None else None
            return None, None, take_profit

        multiplier = self._settings.atr_stop_multiplier
        stop_loss = valuation.current_price - multiplier * indicator_metrics.atr
        trailing_stop = (
            indicator_metrics.highest_close - multiplier * indicator_metrics.atr
        )
        take_profit = analysis.resistance if analysis is not None else None
        if take_profit is None:
            take_profit = valuation.current_price + multiplier * indicator_metrics.atr
        return stop_loss, trailing_stop, take_profit

def _extract_indicator_metrics(
    result: IndicatorCalculationResult,
) -> _IndicatorMetrics | None:
    if result.indicators is None or result.indicators.frame.empty:
        return None
    frame = result.indicators.frame
    latest = frame.iloc[-1]
    atr = _safe_float(latest.get("atr14"))
    closes = frame["close"].tail(20) if "close" in frame.columns else frame.iloc[:, 0]
    highest_close = float(closes.max())
    return _IndicatorMetrics(atr=atr, highest_close=highest_close)


def _distance_to_resistance(
    valuation: PositionValuation,
    analysis: AnalysisResult | None,
) -> float | None:
    if (
        analysis is None
        or analysis.resistance is None
        or valuation.current_price <= 0
    ):
        return None
    return (analysis.resistance - valuation.current_price) / valuation.current_price


def _current_drawdown_pct(
    current_price: float,
    indicator_metrics: _IndicatorMetrics | None,
) -> float:
    if indicator_metrics is None or indicator_metrics.highest_close <= 0:
        return 0.0
    return (
        current_price - indicator_metrics.highest_close
    ) / indicator_metrics.highest_close


def _sector_weight(context: _RecommendationContext) -> float:
    for sector, weight in context.portfolio_analysis.sector_exposures:
        if sector == context.position.sector:
            return weight
    return 0.0


def _trend_stage(  # noqa: PLR0911
    context: _RecommendationContext,
    settings: PositionManagerSettings,
) -> str:
    analysis = context.analysis
    if analysis is None:
        return "UNKNOWN"

    distance_to_resistance = _distance_to_resistance(context.valuation, analysis)
    below_long_term = (
        analysis.long_term_distance_pct is not None
        and analysis.long_term_distance_pct < -0.03
    )
    if (
        analysis.trend == "Bearish"
        and analysis.momentum == "Weak"
        and below_long_term
    ):
        return "BREAKDOWN"
    if analysis.trend == "Bullish" and analysis.risk == "High":
        return "PULLBACK"
    if analysis.trend == "Neutral" and analysis.momentum == "Weak":
        return "PULLBACK"
    if (
        analysis.trend == "Bullish"
        and distance_to_resistance is not None
        and distance_to_resistance < settings.near_resistance_pct
    ):
        return "LATE_UPTREND"
    if (
        analysis.trend == "Bullish"
        and analysis.return_20d is not None
        and analysis.return_20d > 0
    ):
        return "MID_UPTREND"
    if analysis.trend == "Bullish":
        return "EARLY_UPTREND"
    return "PULLBACK" if analysis.trend == "Neutral" else "BREAKDOWN"


def _risk_breakdown(context: _RecommendationContext) -> RiskBreakdown:
    analysis = context.analysis
    volatility = analysis.risk if analysis is not None else "Medium"
    trend = "Medium"
    if analysis is not None:
        trend = {"Bullish": "Low", "Neutral": "Medium", "Bearish": "High"}.get(
            analysis.trend,
            "Medium",
        )
    position_weight = _ratio(context.valuation.market_value, context.portfolio_value)
    concentration = (
        "High"
        if position_weight >= 0.25
        else "Medium"
        if position_weight >= 0.18
        else "Low"
    )
    return RiskBreakdown(
        volatility_risk=volatility,
        trend_risk=trend,
        concentration_risk=concentration,
        portfolio_risk=context.portfolio_analysis.portfolio_risk_level,
    )


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if isnan(number):
        return None
    return number


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _deduplicate(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        unique.append(reason)
    return unique
