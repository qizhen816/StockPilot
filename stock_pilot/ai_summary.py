"""Deterministic natural-language summaries for daily portfolio results."""

from __future__ import annotations

import logging

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisDataSnapshot,
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
        analysis_snapshot: AnalysisDataSnapshot | None = None,
    ) -> DailySummary:
        """Generate a natural-language summary from existing pipeline results."""
        snapshot = analysis_snapshot or AnalysisDataSnapshot(
            data_date=None,
            is_using_previous_close=False,
            advice_horizon="tomorrow",
            reason="Market close cutoff has passed; using latest daily bar",
        )
        successful_scores = [
            result.score for result in score_results if result.score is not None
        ]
        if not successful_scores:
            return DailySummary(
                strongest_stock=None,
                weakest_stock=None,
                today_risk="无法生成风险结论：没有可用评分。",
                tomorrow_watchlist=(),
                operation_advice="没有可用评分，今天不建议依据系统输出做主动操作。",
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

        operation_advice = _operation_advice(
            score_results=score_results,
            snapshot=snapshot,
            strongest_name=strongest.name,
            weakest_name=weakest.name,
        )
        sector_line = _sector_strength_line(score_results)
        weakest_sector_line = _weakest_in_strongest_sector_line(score_results)
        conclusion = (
            f"当前最强持仓是 {strongest.name}，评分 {strongest.score}；"
            f"当前最弱持仓是 {weakest.name}，评分 {weakest.score}。"
            f"{sector_line}{weakest_sector_line}{pnl_line}{today_risk}"
            f"{operation_advice}"
        )

        reasons = (
            f"最强个股来自最高评分：{strongest.name} {strongest.score} 分。",
            f"最弱个股来自最低评分：{weakest.name} {weakest.score} 分。",
            f"观察清单按评分从高到低选取前 {self._settings.watchlist_limit} 只。",
            "风险结论来自 StockScore.risk，不使用未解释的外部判断。",
            f"分析数据日期：{snapshot.data_date or '未知'}。",
        )

        return DailySummary(
            strongest_stock=f"{strongest.name}（{strongest.code}）",
            weakest_stock=f"{weakest.name}（{weakest.code}）",
            today_risk=today_risk,
            tomorrow_watchlist=watchlist,
            operation_advice=operation_advice,
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


def _sector_strength_line(
    score_results: tuple[ScoreCalculationResult, ...],
) -> str:
    sector_scores: dict[str, list[int]] = {}
    for result in score_results:
        if result.score is None:
            continue
        sector_scores.setdefault(result.position.sector, []).append(result.score.score)
    if not sector_scores:
        return ""
    sector, scores = max(
        sector_scores.items(),
        key=lambda item: sum(item[1]) / len(item[1]),
    )
    average = sum(scores) / len(scores)
    return f"{sector} 是当前组合中相对最强的部分，平均评分 {average:.1f}。"


def _weakest_in_strongest_sector_line(
    score_results: tuple[ScoreCalculationResult, ...],
) -> str:
    successful = [result for result in score_results if result.score is not None]
    if not successful:
        return ""
    sector_scores: dict[str, list[ScoreCalculationResult]] = {}
    for result in successful:
        sector_scores.setdefault(result.position.sector, []).append(result)
    strongest_sector, results = max(
        sector_scores.items(),
        key=lambda item: sum(result.score.score for result in item[1] if result.score)
        / len(item[1]),
    )
    if len(results) <= 1:
        return ""
    weakest = min(results, key=lambda result: result.score.score if result.score else 0)
    if weakest.score is None:
        return ""
    return (
        f"{weakest.score.name} 是 {strongest_sector} 中相对偏弱的持仓，"
        "需要继续观察是否拖累组合。"
    )


def _operation_advice(
    score_results: tuple[ScoreCalculationResult, ...],
    snapshot: AnalysisDataSnapshot,
    strongest_name: str,
    weakest_name: str,
) -> str:
    risky_scores = [
        result.score
        for result in score_results
        if result.score is not None and result.score.risk == "High"
    ]
    if snapshot.advice_horizon == "today":
        if risky_scores:
            names = "、".join(score.name for score in risky_scores)
            return (
                "今天操作建议：盘中分析基于上一完整收盘日，"
                f"优先控制 {names} 的风险，不做激进加仓。"
            )
        return (
            "今天操作建议：盘中分析基于上一完整收盘日，"
            f"优先持有强势品种 {strongest_name}，观察 {weakest_name} 是否继续走弱。"
        )
    if risky_scores:
        names = "、".join(score.name for score in risky_scores)
        return f"明日操作建议：优先处理高风险持仓 {names}，控制组合回撤。"
    return (
        f"明日操作建议：继续跟踪强势品种 {strongest_name}，"
        f"弱势品种 {weakest_name} 暂不主动加仓。"
    )


def _translate_risk(value: str) -> str:
    return {"Low": "低", "Medium": "中", "High": "高"}.get(value, value)
