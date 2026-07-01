"""Tests for portfolio-aware position management."""

from __future__ import annotations

import pandas as pd

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    IndicatorCalculationResult,
    IndicatorResult,
    Portfolio,
    PortfolioAnalysis,
    PortfolioValuation,
    PortfolioValuationResult,
    Position,
    PositionManagerSettings,
    PositionValuation,
    ScoreCalculationResult,
    ScoreComponent,
    StockScore,
)
from stock_pilot.position_manager import PositionManagementInput, PositionManager


def test_position_manager_takes_partial_profit_near_resistance() -> None:
    """Bullish holdings near resistance should protect part of the profit."""
    recommendation = _recommend(
        analysis=_analysis(
            trend="Bullish", momentum="Strong", risk="Low", resistance=12.2
        ),
        score=_score(score=88, risk="Low"),
        valuation=_valuation(current_price=12.0, unrealized_pnl_pct=0.18),
    )[0]

    assert recommendation.action == "Take Partial Profit"
    assert recommendation.state == "ACCUMULATE"
    assert recommendation.recommended_position_pct == 0.75
    assert recommendation.recommended_shares == 75
    assert recommendation.suggested_stop_loss == 10.8
    assert recommendation.suggested_trailing_stop == 10.8
    assert recommendation.trend_stage == "LATE_UPTREND"
    assert "Uptrend is mature and close to resistance" in recommendation.reasons


def test_position_manager_reduces_aggressively_only_after_breakdown() -> None:
    """Bearish weak high-risk holdings need breakdown confirmation first."""
    recommendation = _recommend(
        analysis=_analysis(
            trend="Bearish",
            momentum="Weak",
            risk="High",
            resistance=11.0,
            long_term_distance_pct=-0.08,
        ),
        score=_score(score=35, risk="High"),
        valuation=_valuation(current_price=9.0, unrealized_pnl_pct=-0.05),
    )[0]

    assert recommendation.action == "Reduce Position"
    assert recommendation.state == "LIGHTEN"
    assert recommendation.trend_stage == "BREAKDOWN"
    assert recommendation.recommended_shares == 25
    assert "Trend breakdown is confirmed" in recommendation.reasons


def test_position_manager_does_not_average_down_without_confirmation() -> None:
    """Deep underwater positions without bullish confirmation should be watched."""
    recommendation = _recommend(
        analysis=_analysis(
            trend="Neutral", momentum="Weak", risk="Medium", resistance=11.0
        ),
        score=_score(score=58, risk="Medium"),
        valuation=_valuation(current_price=8.0, unrealized_pnl_pct=-0.20),
    )[0]

    assert recommendation.action == "Watch"
    assert recommendation.recommended_shares == 100
    assert "Position is deeply underwater" in recommendation.reasons
    assert "No averaging down before right-side confirmation" in recommendation.reasons


def _recommend(
    analysis: AnalysisResult,
    score: StockScore,
    valuation: PositionValuation,
) -> tuple:
    position = Position(
        code="002436",
        name="兴森科技",
        cost=10.0,
        shares=100,
        sector="PCB",
    )
    return PositionManager(_settings()).recommend_all(
        PositionManagementInput(
            portfolio=Portfolio(positions=(position,)),
            analysis_results=(
                AnalysisCalculationResult(position=position, analysis=analysis),
            ),
            score_results=(ScoreCalculationResult(position=position, score=score),),
            portfolio_valuation=PortfolioValuationResult(
                valuation=PortfolioValuation(
                    positions=(valuation,),
                    total_cost=1000.0,
                    total_market_value=valuation.market_value,
                    total_unrealized_pnl=valuation.unrealized_pnl,
                    total_unrealized_pnl_pct=valuation.unrealized_pnl_pct,
                    total_daily_pnl=0.0,
                )
            ),
            portfolio_analysis=_portfolio_analysis(),
            indicator_results=(
                IndicatorCalculationResult(
                    position=position,
                    indicators=IndicatorResult(
                        code=position.code,
                        name=position.name,
                        frame=_indicator_frame(valuation.current_price),
                    ),
                ),
            ),
        )
    )


def _settings() -> PositionManagerSettings:
    return PositionManagerSettings(
        full_position_pct=1.0,
        overweight_position_pct=1.25,
        accumulate_position_pct=0.75,
        normal_position_pct=0.5,
        lighten_position_pct=0.25,
        exit_position_pct=0.0,
        near_resistance_pct=0.03,
        wide_resistance_pct=0.08,
        profit_protection_levels=(0.05, 0.10, 0.15, 0.20),
        atr_stop_multiplier=2.0,
        sector_concentration_threshold=0.60,
        position_concentration_threshold=0.25,
        minimum_confidence=0.55,
        maximum_confidence=0.90,
        pullback_position_pct=1.0,
        late_uptrend_position_pct=0.75,
        breakdown_position_pct=0.25,
    )


def _analysis(
    trend: str,
    momentum: str,
    risk: str,
    resistance: float,
    long_term_distance_pct: float = 0.05,
) -> AnalysisResult:
    return AnalysisResult(
        code="002436",
        name="兴森科技",
        trend=trend,
        momentum=momentum,
        risk=risk,
        support=8.8,
        resistance=resistance,
        reasons=(f"Trend is {trend}", f"Momentum is {momentum}"),
        sector="PCB",
        return_20d=0.08,
        long_term_distance_pct=long_term_distance_pct,
    )


def _score(score: int, risk: str) -> StockScore:
    return StockScore(
        code="002436",
        name="兴森科技",
        score=score,
        rating="★★★★",
        risk=risk,
        confidence=0.75,
        components=(ScoreComponent(name="Trend", score=35, weight=35, reason="Trend"),),
        reasons=("Trend is Bullish",),
        relative_strength_score=80,
    )


def _valuation(
    current_price: float,
    unrealized_pnl_pct: float,
) -> PositionValuation:
    market_value = current_price * 100
    cost_amount = market_value / (1 + unrealized_pnl_pct)
    return PositionValuation(
        code="002436",
        name="兴森科技",
        shares=100,
        cost_price=cost_amount / 100,
        cost_amount=cost_amount,
        current_price=current_price,
        previous_close=current_price - 0.2,
        market_value=market_value,
        unrealized_pnl=market_value - cost_amount,
        unrealized_pnl_pct=unrealized_pnl_pct,
        daily_pnl=20.0,
        daily_pnl_pct=0.02,
        sector="PCB",
    )


def _portfolio_analysis() -> PortfolioAnalysis:
    return PortfolioAnalysis(
        sector_exposures=(("PCB", 0.50),),
        concentration_top_position_pct=0.20,
        largest_winner="兴森科技（002436）",
        largest_loser=None,
        highest_risk_position=None,
        weakest_relative_position=None,
        portfolio_trend_score=80.0,
        portfolio_risk_score=35.0,
        portfolio_risk_level="Medium",
        portfolio_risk_reasons=("Portfolio risk is balanced across current holdings",),
        profit_concentration_pct=1.0,
        profit_concentration_score=100.0,
        profit_concentration_reasons=("Profit concentration is high at 100%",),
    )


def _indicator_frame(current_price: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": [current_price - 0.3, current_price - 0.1, current_price],
            "atr14": [0.6, 0.6, 0.6],
        }
    )
