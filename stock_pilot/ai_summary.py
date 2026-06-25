"""Deterministic natural-language summaries for daily portfolio results."""

from __future__ import annotations

import logging

from stock_pilot.models import (
    AnalysisCalculationResult,
    DailySummary,
    PortfolioValuationResult,
    ScoreCalculationResult,
    SummarySettings,
)

logger = logging.getLogger(__name__)


class DailySummaryGenerator:
    """Generate explainable Chinese summaries from scored portfolio results."""

    def __init__(self, settings: SummarySettings) -> None:
        """Create a summary generator with immutable summary settings."""
        self._settings = settings

    def generate(
        self,
        score_results: tuple[ScoreCalculationResult, ...],
        analysis_results: tuple[AnalysisCalculationResult, ...],
        portfolio_valuation: PortfolioValuationResult,
    ) -> DailySummary:
        """Generate a natural-language summary from existing pipeline results."""
        successful_scores = [
            result.score for result in score_results if result.score is not None
        ]
        if not successful_scores:
            return DailySummary(
                strongest_stock=None,
                weakest_stock=None,
                today_risk="无法生成风险结论：没有可用评分。",
                tomorrow_watchlist=(),
                conclusion="今日没有可用评分结果，暂不生成组合摘要。",
                reasons=("没有成功生成任何 StockScore。",),
            )

        strongest = max(successful_scores, key=lambda item: item.score)
        weakest = min(successful_scores, key=lambda item: item.score)
        high_risk_names = _high_risk_names(
            score_results, self._settings.high_risk_levels
        )
        watchlist = _watchlist(score_results, self._settings.watchlist_limit)
        pnl_line = _portfolio_pnl_line(portfolio_valuation)

        if high_risk_names:
            today_risk = "今日需要重点关注风险：" + "、".join(high_risk_names)
        else:
            today_risk = "今日组合未出现高风险个股。"

        conclusion = (
            f"今日组合最强的是 {strongest.name}（{strongest.score} 分，"
            f"{strongest.rating}），最弱的是 {weakest.name}（{weakest.score} 分）。"
            f"{pnl_line}{today_risk}"
        )

        reasons = (
            f"最强个股来自最高评分：{strongest.name} {strongest.score} 分。",
            f"最弱个股来自最低评分：{weakest.name} {weakest.score} 分。",
            f"观察清单按评分从高到低选取前 {self._settings.watchlist_limit} 只。",
            "风险结论来自 StockScore.risk，不使用未解释的外部判断。",
        )

        return DailySummary(
            strongest_stock=f"{strongest.name}（{strongest.code}）",
            weakest_stock=f"{weakest.name}（{weakest.code}）",
            today_risk=today_risk,
            tomorrow_watchlist=watchlist,
            conclusion=conclusion,
            reasons=reasons,
        )


def _high_risk_names(
    score_results: tuple[ScoreCalculationResult, ...],
    high_risk_levels: tuple[str, ...],
) -> list[str]:
    names: list[str] = []
    for result in score_results:
        if result.score is None:
            continue
        if result.score.risk in high_risk_levels:
            names.append(
                f"{result.score.name}（{_translate_risk(result.score.risk)}）"
            )
    return names


def _watchlist(
    score_results: tuple[ScoreCalculationResult, ...],
    limit: int,
) -> tuple[str, ...]:
    ranked_scores = sorted(
        (result.score for result in score_results if result.score is not None),
        key=lambda item: item.score,
        reverse=True,
    )
    return tuple(
        (
            f"{score.name}（{score.code}）："
            f"{score.score} 分，风险{_translate_risk(score.risk)}"
        )
        for score in ranked_scores[:limit]
    )


def _portfolio_pnl_line(portfolio_valuation: PortfolioValuationResult) -> str:
    if portfolio_valuation.valuation is None:
        return "组合估值暂不可用。"
    pnl = portfolio_valuation.valuation.total_unrealized_pnl
    pnl_pct = portfolio_valuation.valuation.total_unrealized_pnl_pct
    direction = "盈利" if pnl >= 0 else "亏损"
    return f"当前组合浮动{direction} {pnl:.2f} 元（{pnl_pct:.2%}）。"


def _translate_risk(value: str) -> str:
    return {"Low": "低", "Medium": "中", "High": "高"}.get(value, value)
