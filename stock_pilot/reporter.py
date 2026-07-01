"""Console, Markdown, and CSV reporting for StockPilot."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from math import isnan
from pathlib import Path

from rich.console import Console
from rich.table import Table

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisDataSnapshot,
    DailySummary,
    DecisionCalculationResult,
    FetchResult,
    IndicatorCalculationResult,
    NotificationDispatchResult,
    PortfolioAnalysis,
    PortfolioDecisionPlan,
    PortfolioValuationResult,
    PositionRecommendation,
    ScannerResult,
    ScoreCalculationResult,
)


@dataclass(frozen=True)
class DailyReportPayload:
    """All computed daily results needed by reporters."""

    report_date: date
    analysis_snapshot: AnalysisDataSnapshot
    fetch_results: tuple[FetchResult, ...]
    portfolio_valuation: PortfolioValuationResult
    portfolio_analysis: PortfolioAnalysis
    portfolio_decision_plan: PortfolioDecisionPlan
    position_recommendations: tuple[PositionRecommendation, ...]
    indicator_results: tuple[IndicatorCalculationResult, ...]
    analysis_results: tuple[AnalysisCalculationResult, ...]
    score_results: tuple[ScoreCalculationResult, ...]
    decision_results: tuple[DecisionCalculationResult, ...]
    summary: DailySummary
    scanner_result: ScannerResult


class ConsoleReporter:
    """Render report results to the console."""

    def __init__(self, console: Console | None = None) -> None:
        """Create a console reporter."""
        self._console = console or Console()

    def render_fetch_results(self, results: tuple[FetchResult, ...]) -> None:
        """Print a basic fetch summary for portfolio positions."""
        table = Table(title="StockPilot 数据下载概览")
        table.add_column("代码", style="cyan")
        table.add_column("名称")
        table.add_column("行数", justify="right")
        table.add_column("最新日期")
        table.add_column("状态")

        for result in results:
            if result.market_data is None:
                table.add_row(
                    result.position.code,
                    result.position.name,
                    "0",
                    "-",
                    f"失败：{result.error}",
                )
                continue

            frame = result.market_data.frame
            latest_date = "-"
            if not frame.empty and "date" in frame.columns:
                latest_date = str(frame.iloc[-1]["date"].date())

            table.add_row(
                result.position.code,
                result.position.name,
                str(len(frame)),
                latest_date,
                "成功",
            )

        self._console.print(table)

    def render_analysis_snapshot(self, snapshot: AnalysisDataSnapshot) -> None:
        """Print the market data snapshot used for analysis."""
        table = Table(title="StockPilot 分析口径")
        table.add_column("项目", style="cyan")
        table.add_column("内容")
        table.add_row("分析数据日期", snapshot.data_date or "-")
        table.add_row(
            "分析模式",
            "上一完整收盘日" if snapshot.is_using_previous_close else "最新日线",
        )
        table.add_row("建议对象", _translate_advice_horizon(snapshot.advice_horizon))
        table.add_row("原因", _translate_reason(snapshot.reason))
        self._console.print(table)

    def render_summary(self, summary: DailySummary) -> None:
        """Print the daily natural-language summary."""
        table = Table(title="StockPilot 今日总结")
        table.add_column("项目", style="cyan")
        table.add_column("内容")
        table.add_row("最强个股", summary.strongest_stock or "-")
        table.add_row("最弱个股", summary.weakest_stock or "-")
        table.add_row("今日风险", summary.today_risk)
        table.add_row("明日观察", "；".join(summary.tomorrow_watchlist) or "-")
        table.add_row("操作建议", summary.operation_advice)
        table.add_row("结论", summary.conclusion)
        table.add_row("依据", "；".join(summary.reasons))
        self._console.print(table)

    def render_scanner_result(self, result: ScannerResult) -> None:
        """Print ranked scanner candidates."""
        table = Table(title="StockPilot 候选扫描")
        table.add_column("排名", justify="right")
        table.add_column("代码", style="cyan")
        table.add_column("名称")
        table.add_column("分数", justify="right")
        table.add_column("评级")
        table.add_column("风险")
        table.add_column("置信度", justify="right")
        table.add_column("入选原因")

        if not result.candidates:
            table.add_row("-", "-", "-", "-", "-", "-", "-", "暂无满足条件的候选")
            self._console.print(table)
            return

        for index, candidate in enumerate(result.candidates, start=1):
            table.add_row(
                str(index),
                candidate.code,
                candidate.name,
                str(candidate.score),
                candidate.rating,
                _translate_risk(candidate.risk),
                _format_percent(candidate.confidence),
                "；".join(_translate_reason(reason) for reason in candidate.reasons),
            )

        self._console.print(table)

    def render_decision_results(
        self, results: tuple[DecisionCalculationResult, ...]
    ) -> None:
        """Print actionable decision support results."""
        table = Table(title="StockPilot 决策建议")
        table.add_column("代码", style="cyan")
        table.add_column("名称")
        table.add_column("行动")
        table.add_column("风险")
        table.add_column("置信度", justify="right")
        table.add_column("原因")

        for result in results:
            if result.decision is None:
                table.add_row(
                    result.position.code,
                    result.position.name,
                    "-",
                    "-",
                    "-",
                    f"失败：{result.error}",
                )
                continue
            table.add_row(
                result.position.code,
                result.position.name,
                _translate_action(result.decision.action),
                _translate_risk(result.decision.risk),
                _format_percent(result.decision.confidence),
                "；".join(
                    _translate_reason(reason) for reason in result.decision.reasons
                ),
            )

        self._console.print(table)

    def render_score_results(
        self, results: tuple[ScoreCalculationResult, ...]
    ) -> None:
        """Print explainable score output for portfolio positions."""
        table = Table(title="StockPilot 评分")
        table.add_column("代码", style="cyan")
        table.add_column("名称")
        table.add_column("分数", justify="right")
        table.add_column("评级")
        table.add_column("风险")
        table.add_column("置信度", justify="right")
        table.add_column("评分原因")

        for result in results:
            if result.score is None:
                table.add_row(
                    result.position.code,
                    result.position.name,
                    "-",
                    "-",
                    "-",
                    "-",
                    f"失败：{result.error}",
                )
                continue

            table.add_row(
                result.position.code,
                result.position.name,
                str(result.score.score),
                result.score.rating,
                _translate_risk(result.score.risk),
                _format_percent(result.score.confidence),
                "；".join(_translate_reason(reason) for reason in result.score.reasons),
            )

        self._console.print(table)

    def render_position_recommendations(
        self, recommendations: tuple[PositionRecommendation, ...]
    ) -> None:
        """Print portfolio-aware position-size recommendations."""
        table = Table(title="StockPilot 组合仓位建议")
        table.add_column("代码", style="cyan")
        table.add_column("名称")
        table.add_column("当前股数", justify="right")
        table.add_column("建议股数", justify="right")
        table.add_column("建议仓位", justify="right")
        table.add_column("趋势阶段")
        table.add_column("动作")
        table.add_column("风险")
        table.add_column("置信度", justify="right")
        table.add_column("止损", justify="right")
        table.add_column("跟踪止损", justify="right")
        table.add_column("止盈参考", justify="right")
        table.add_column("原因")

        if not recommendations:
            table.add_row(
                "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"
            )
            self._console.print(table)
            return

        for recommendation in recommendations:
            table.add_row(
                recommendation.code,
                recommendation.name,
                str(recommendation.current_shares),
                str(recommendation.recommended_shares),
                _format_percent(recommendation.recommended_position_pct),
                _translate_trend_stage(recommendation.trend_stage),
                _translate_action(recommendation.action),
                _translate_risk(recommendation.risk),
                _format_percent(recommendation.confidence),
                _format_number(recommendation.suggested_stop_loss),
                _format_number(recommendation.suggested_trailing_stop),
                _format_number(recommendation.suggested_take_profit),
                "；".join(
                    _translate_reason(reason) for reason in recommendation.reasons
                ),
            )

        self._console.print(table)

    def render_analysis_results(
        self, results: tuple[AnalysisCalculationResult, ...]
    ) -> None:
        """Print explainable analyzer output for portfolio positions."""
        table = Table(title="StockPilot 分析")
        table.add_column("代码", style="cyan")
        table.add_column("名称")
        table.add_column("趋势")
        table.add_column("动量")
        table.add_column("风险")
        table.add_column("支撑位", justify="right")
        table.add_column("压力位", justify="right")
        table.add_column("原因")

        for result in results:
            if result.analysis is None:
                table.add_row(
                    result.position.code,
                    result.position.name,
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    f"失败：{result.error}",
                )
                continue

            table.add_row(
                result.position.code,
                result.position.name,
                _translate_trend(result.analysis.trend),
                _translate_momentum(result.analysis.momentum),
                _translate_risk(result.analysis.risk),
                _format_number(result.analysis.support),
                _format_number(result.analysis.resistance),
                "；".join(
                    _translate_reason(reason) for reason in result.analysis.reasons
                ),
            )

        self._console.print(table)

    def render_portfolio_valuation(self, result: PortfolioValuationResult) -> None:
        """Print portfolio valuation and profit/loss metrics."""
        table = Table(title="StockPilot 持仓估值")
        table.add_column("代码", style="cyan")
        table.add_column("名称")
        table.add_column("股数", justify="right")
        table.add_column("成本价", justify="right")
        table.add_column("现价", justify="right")
        table.add_column("市值", justify="right")
        table.add_column("浮动盈亏", justify="right")
        table.add_column("盈亏比例", justify="right")
        table.add_column("日内盈亏", justify="right")

        if result.valuation is None:
            table.add_row(
                "-", "-", "-", "-", "-", "-", "-", "-", f"失败：{result.error}"
            )
            self._console.print(table)
            return

        for position in result.valuation.positions:
            table.add_row(
                position.code,
                position.name,
                str(position.shares),
                _format_number(position.cost_price),
                _format_number(position.current_price),
                _format_number(position.market_value),
                _format_number(position.unrealized_pnl),
                _format_percent(position.unrealized_pnl_pct),
                _format_number(position.daily_pnl),
            )

        table.add_section()
        table.add_row(
            "合计",
            "-",
            "-",
            "-",
            "-",
            _format_number(result.valuation.total_market_value),
            _format_number(result.valuation.total_unrealized_pnl),
            _format_percent(result.valuation.total_unrealized_pnl_pct),
            _format_number(result.valuation.total_daily_pnl),
        )

        self._console.print(table)

    def render_portfolio_analysis(self, analysis: PortfolioAnalysis) -> None:
        """Print portfolio-level analysis."""
        table = Table(title="StockPilot 组合分析")
        table.add_column("项目", style="cyan")
        table.add_column("内容")
        table.add_row("行业暴露", _format_sector_exposures(analysis.sector_exposures))
        table.add_row(
            "最大持仓集中度",
            _format_percent(analysis.concentration_top_position_pct),
        )
        table.add_row("最大盈利", analysis.largest_winner or "-")
        table.add_row("最大亏损", analysis.largest_loser or "-")
        table.add_row("最高风险持仓", analysis.highest_risk_position or "-")
        table.add_row("最弱相对强弱", analysis.weakest_relative_position or "-")
        table.add_row("组合趋势分", _format_number(analysis.portfolio_trend_score))
        table.add_row(
            "组合风险",
            (
                f"{_format_number(analysis.portfolio_risk_score)}"
                f"（{_translate_risk(analysis.portfolio_risk_level)}）"
            ),
        )
        table.add_row(
            "风险原因",
            "；".join(
                _translate_reason(reason) for reason in analysis.portfolio_risk_reasons
            ),
        )
        table.add_row(
            "盈利集中度",
            (
                f"{_format_percent(analysis.profit_concentration_pct)}"
                f"（{_format_number(analysis.profit_concentration_score)}）"
            ),
        )
        table.add_row(
            "盈利集中原因",
            "；".join(
                _translate_reason(reason)
                for reason in analysis.profit_concentration_reasons
            ),
        )
        self._console.print(table)

    def render_portfolio_decision_plan(self, plan: PortfolioDecisionPlan) -> None:
        """Print the portfolio-level action plan."""
        table = Table(title="StockPilot 明日组合计划")
        table.add_column("综合排名", justify="right")
        table.add_column("相对排名", justify="right")
        table.add_column("风险排名", justify="right")
        table.add_column("趋势排名", justify="right")
        table.add_column("代码", style="cyan")
        table.add_column("名称")
        table.add_column("动作")
        table.add_column("分数", justify="right")
        table.add_column("风险")
        table.add_column("优先级")
        table.add_column("置信度", justify="right")
        table.add_column("替换候选")
        table.add_column("原因")

        if not plan.actions:
            table.add_row(
                "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", plan.summary
            )
            self._console.print(table)
            return

        for action in plan.actions:
            replacement = "-"
            if action.replacement is not None:
                replacement = (
                    f"{action.replacement.suggested_name}"
                    f"（{action.replacement.suggested_code}）"
                )
            table.add_row(
                str(action.rank),
                str(action.relative_rank),
                str(action.risk_rank),
                str(action.trend_rank),
                action.code,
                action.name,
                _translate_action(action.action),
                str(action.score),
                _translate_risk(action.risk),
                _translate_priority(action.execution_priority),
                _format_percent(action.confidence),
                replacement,
                "；".join(_translate_reason(reason) for reason in action.reasons),
            )

        self._console.print(table)

    def render_indicator_results(
        self, results: tuple[IndicatorCalculationResult, ...]
    ) -> None:
        """Print the latest raw indicator values for portfolio positions."""
        table = Table(title="StockPilot 最新指标")
        table.add_column("代码", style="cyan")
        table.add_column("名称")
        table.add_column("收盘价", justify="right")
        table.add_column("MA5", justify="right")
        table.add_column("MA20", justify="right")
        table.add_column("MACD", justify="right")
        table.add_column("RSI14", justify="right")
        table.add_column("ATR14", justify="right")
        table.add_column("量比", justify="right")
        table.add_column("状态")

        for result in results:
            if result.indicators is None:
                table.add_row(
                    result.position.code,
                    result.position.name,
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    f"失败：{result.error}",
                )
                continue

            latest = result.indicators.frame.iloc[-1]
            table.add_row(
                result.position.code,
                result.position.name,
                _format_number(latest.get("close")),
                _format_number(latest.get("ma5")),
                _format_number(latest.get("ma20")),
                _format_number(latest.get("macd")),
                _format_number(latest.get("rsi14")),
                _format_number(latest.get("atr14")),
                _format_number(latest.get("volume_ratio")),
                "成功",
            )

        self._console.print(table)

    def render_notification_results(self, result: NotificationDispatchResult) -> None:
        """Print notification delivery results."""
        table = Table(title="StockPilot 通知状态")
        table.add_column("渠道", style="cyan")
        table.add_column("状态")
        table.add_column("说明")

        for item in result.results:
            table.add_row(
                _translate_channel(item.channel),
                "已发送" if item.sent else "未发送",
                _translate_notification_message(item.message),
            )

        self._console.print(table)


class MarkdownReporter:
    """Write daily report output as a Markdown file."""

    def __init__(self, output_dir: Path) -> None:
        """Create a Markdown reporter with an output directory."""
        self._output_dir = output_dir

    def write(self, payload: DailyReportPayload) -> Path:
        """Write a daily Markdown report and return its path."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / f"{payload.report_date.isoformat()}.md"
        path.write_text(_build_markdown(payload), encoding="utf-8")
        return path


class CsvReporter:
    """Append score history rows to a CSV file."""

    def __init__(self, path: Path) -> None:
        """Create a CSV reporter for score history."""
        self._path = path

    def append(self, payload: DailyReportPayload) -> Path:
        """Append one row per scored stock and return the CSV path."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self._path.exists()

        with self._path.open("a", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=_csv_fieldnames())
            if not file_exists:
                writer.writeheader()
            for result in payload.score_results:
                if result.score is None:
                    continue
                writer.writerow(
                    {
                        "date": payload.report_date.isoformat(),
                        "code": result.position.code,
                        "name": result.position.name,
                        "score": result.score.score,
                        "rating": result.score.rating,
                        "risk": _translate_risk(result.score.risk),
                        "confidence": f"{result.score.confidence:.4f}",
                        "reasons": "；".join(
                            _translate_reason(reason) for reason in result.score.reasons
                        ),
                    }
                )

        return self._path


def _build_markdown(payload: DailyReportPayload) -> str:
    lines = [
        f"# StockPilot 日报 {payload.report_date.isoformat()}",
        "",
        "## 分析口径",
        "",
        *_analysis_snapshot_markdown_lines(payload.analysis_snapshot),
        "",
        "## 组合概览",
        "",
        *_portfolio_markdown_lines(payload.portfolio_valuation),
        "",
        "## 组合分析",
        "",
        *_portfolio_analysis_markdown_lines(payload.portfolio_analysis),
        "",
        "## 明日组合计划",
        "",
        *_portfolio_decision_markdown_lines(payload.portfolio_decision_plan),
        "",
        "## 今日总结",
        "",
        *_summary_markdown_lines(payload.summary),
        "",
        "## 候选扫描",
        "",
        *_scanner_markdown_lines(payload.scanner_result),
        "",
        "## 决策建议",
        "",
        *_decision_markdown_lines(payload.decision_results),
        "",
        "## 个股评分",
        "",
    ]

    for result in payload.score_results:
        lines.extend(_score_markdown_lines(result))
        lines.append("")

    lines.extend(["## 组合仓位建议", ""])
    lines.extend(_position_recommendation_markdown_lines(payload.position_recommendations))
    lines.append("")

    lines.extend(["## 个股分析", ""])
    for result in payload.analysis_results:
        lines.extend(_analysis_markdown_lines(result))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _portfolio_markdown_lines(result: PortfolioValuationResult) -> list[str]:
    if result.valuation is None:
        return [f"- 组合估值失败：{result.error}"]
    return [
        f"- 总市值：{_format_number(result.valuation.total_market_value)}",
        f"- 总浮动盈亏：{_format_number(result.valuation.total_unrealized_pnl)}",
        f"- 总盈亏比例：{_format_percent(result.valuation.total_unrealized_pnl_pct)}",
        f"- 总日内盈亏：{_format_number(result.valuation.total_daily_pnl)}",
    ]


def _analysis_snapshot_markdown_lines(snapshot: AnalysisDataSnapshot) -> list[str]:
    mode = "上一完整收盘日" if snapshot.is_using_previous_close else "最新日线"
    return [
        f"- 分析数据日期：{snapshot.data_date or '-'}",
        f"- 分析模式：{mode}",
        f"- 建议对象：{_translate_advice_horizon(snapshot.advice_horizon)}",
        f"- 原因：{_translate_reason(snapshot.reason)}",
    ]


def _portfolio_analysis_markdown_lines(analysis: PortfolioAnalysis) -> list[str]:
    return [
        f"- 行业暴露：{_format_sector_exposures(analysis.sector_exposures)}",
        f"- 最大持仓集中度：{_format_percent(analysis.concentration_top_position_pct)}",
        f"- 最大盈利：{analysis.largest_winner or '-'}",
        f"- 最大亏损：{analysis.largest_loser or '-'}",
        f"- 最高风险持仓：{analysis.highest_risk_position or '-'}",
        f"- 最弱相对强弱：{analysis.weakest_relative_position or '-'}",
        f"- 组合趋势分：{_format_number(analysis.portfolio_trend_score)}",
        (
            f"- 组合风险：{_format_number(analysis.portfolio_risk_score)}"
            f"（{_translate_risk(analysis.portfolio_risk_level)}）"
        ),
        f"- 盈利集中度：{_format_percent(analysis.profit_concentration_pct)}",
        "- 风险原因：",
        *[
            f"  - {_translate_reason(reason)}"
            for reason in analysis.portfolio_risk_reasons
        ],
        "- 盈利集中原因：",
        *[
            f"  - {_translate_reason(reason)}"
            for reason in analysis.profit_concentration_reasons
        ],
    ]


def _portfolio_decision_markdown_lines(plan: PortfolioDecisionPlan) -> list[str]:
    lines = [
        f"- 组合分：{_format_number(plan.portfolio_score)}",
        f"- 风险分：{_format_number(plan.portfolio_risk_score)}",
        f"- 结论：{plan.summary}",
        "- 依据：",
        *[f"  - {_translate_reason(reason)}" for reason in plan.reasons],
    ]
    if not plan.actions:
        return lines

    lines.append("- 持仓动作：")
    for action in plan.actions:
        lines.extend(
            [
                f"  - {action.name}（{action.code}）",
                f"    - 动作：{_translate_action(action.action)}",
                f"    - 综合排名：{action.rank}/{action.total_positions}",
                f"    - 相对强弱排名：{action.relative_rank}/{action.total_positions}",
                f"    - 风险排名：{action.risk_rank}/{action.total_positions}",
                f"    - 趋势排名：{action.trend_rank}/{action.total_positions}",
                f"    - 分数：{action.score}",
                f"    - 风险：{_translate_risk(action.risk)}",
                f"    - 执行优先级：{_translate_priority(action.execution_priority)}",
                (
                    "    - 风险拆分："
                    f"波动 {_translate_risk(action.risk_breakdown.volatility_risk)}，"
                    f"趋势 {_translate_risk(action.risk_breakdown.trend_risk)}，"
                    "集中度 "
                    f"{_translate_risk(action.risk_breakdown.concentration_risk)}，"
                    f"组合 {_translate_risk(action.risk_breakdown.portfolio_risk)}"
                ),
                f"    - 置信度：{_format_percent(action.confidence)}",
                "    - 原因：",
                *[
                    f"      - {_translate_reason(reason)}"
                    for reason in action.reasons
                ],
            ]
        )
        if action.replacement is not None:
            lines.extend(
                [
                    "    - 替换候选：",
                    (
                        f"      - {action.replacement.suggested_name}"
                        f"（{action.replacement.suggested_code}），"
                        f"分差 {action.replacement.score_gap}，"
                        "预期组合分改善 "
                        f"{action.replacement.expected_portfolio_score_delta}"
                    ),
                    f"      - 趋势改善：+{action.replacement.trend_improvement}",
                    (
                        "      - 相对强弱改善：+"
                        f"{action.replacement.relative_strength_improvement}"
                    ),
                    f"      - 风险改善：{action.replacement.risk_improvement}",
                    (
                        "      - 替换置信度："
                        f"{_format_percent(action.replacement.replacement_confidence)}"
                    ),
                    *[
                        f"      - {_translate_reason(reason)}"
                        for reason in action.replacement.reasons
                    ],
                ]
            )
    return lines


def _summary_markdown_lines(summary: DailySummary) -> list[str]:
    lines = [
        f"- 最强个股：{summary.strongest_stock or '-'}",
        f"- 最弱个股：{summary.weakest_stock or '-'}",
        f"- 今日风险：{summary.today_risk}",
        f"- 操作建议：{summary.operation_advice}",
        "- 明日观察：",
    ]
    if summary.tomorrow_watchlist:
        lines.extend(f"  - {item}" for item in summary.tomorrow_watchlist)
    else:
        lines.append("  - -")
    lines.extend(
        [
            f"- 结论：{summary.conclusion}",
            "- 依据：",
            *[f"  - {reason}" for reason in summary.reasons],
        ]
    )
    return lines


def _scanner_markdown_lines(result: ScannerResult) -> list[str]:
    if not result.candidates:
        return [f"- 暂无满足条件的候选；跳过 {result.skipped_count} 只。"]

    lines = [
        f"- 候选数量：{len(result.candidates)}",
        f"- 未入选数量：{result.skipped_count}",
    ]
    for index, candidate in enumerate(result.candidates, start=1):
        lines.extend(
            [
                f"- 第 {index} 名：{candidate.name}（{candidate.code}）",
                f"  - 分数：{candidate.score}",
                f"  - 评级：{candidate.rating}",
                f"  - 风险：{_translate_risk(candidate.risk)}",
                f"  - 置信度：{_format_percent(candidate.confidence)}",
                "  - 入选原因：",
                *[
                    f"    - {_translate_reason(reason)}"
                    for reason in candidate.reasons
                ],
            ]
        )
    return lines


def _decision_markdown_lines(
    results: tuple[DecisionCalculationResult, ...]
) -> list[str]:
    lines: list[str] = []
    for result in results:
        if result.decision is None:
            lines.append(
                f"- {result.position.name}（{result.position.code}）："
                f"失败：{result.error}"
            )
            continue
        lines.extend(
            [
                f"- {result.position.name}（{result.position.code}）",
                f"  - 行动：{_translate_action(result.decision.action)}",
                f"  - 风险：{_translate_risk(result.decision.risk)}",
                f"  - 置信度：{_format_percent(result.decision.confidence)}",
                "  - 原因：",
                *[
                    f"    - {_translate_reason(reason)}"
                    for reason in result.decision.reasons
                ],
            ]
        )
    return lines


def _position_recommendation_markdown_lines(
    recommendations: tuple[PositionRecommendation, ...]
) -> list[str]:
    if not recommendations:
        return ["- 暂无仓位建议。"]

    lines: list[str] = []
    for recommendation in recommendations:
        risk_breakdown = recommendation.risk_breakdown
        lines.extend(
            [
                f"- {recommendation.name}（{recommendation.code}）",
                f"  - 当前股数：{recommendation.current_shares}",
                f"  - 建议股数：{recommendation.recommended_shares}",
                (
                    "  - 建议仓位："
                    f"{_format_percent(recommendation.recommended_position_pct)}"
                    f"（{_translate_position_state(recommendation.state)}）"
                ),
                f"  - 趋势阶段：{_translate_trend_stage(recommendation.trend_stage)}",
                f"  - 动作：{_translate_action(recommendation.action)}",
                f"  - 风险：{_translate_risk(recommendation.risk)}",
                (
                    "  - 风险拆分："
                    f"波动 {_translate_risk(risk_breakdown.volatility_risk)}，"
                    f"趋势 {_translate_risk(risk_breakdown.trend_risk)}，"
                    "集中度 "
                    f"{_translate_risk(risk_breakdown.concentration_risk)}，"
                    f"组合 {_translate_risk(risk_breakdown.portfolio_risk)}"
                ),
                f"  - 置信度：{_format_percent(recommendation.confidence)}",
                f"  - 成本价：{_format_number(recommendation.cost_price)}",
                f"  - 现价：{_format_number(recommendation.current_price)}",
                f"  - 浮盈亏：{_format_percent(recommendation.unrealized_pnl_pct)}",
                f"  - 当前回撤：{_format_percent(recommendation.current_drawdown_pct)}",
                f"  - 建议止损：{_format_number(recommendation.suggested_stop_loss)}",
                (
                    "  - 建议跟踪止损："
                    f"{_format_number(recommendation.suggested_trailing_stop)}"
                ),
                f"  - 止盈参考：{_format_number(recommendation.suggested_take_profit)}",
                "  - 原因：",
                *[
                    f"    - {_translate_reason(reason)}"
                    for reason in recommendation.reasons
                ],
            ]
        )
    return lines


def _score_markdown_lines(result: ScoreCalculationResult) -> list[str]:
    if result.score is None:
        return [
            f"### {result.position.name}（{result.position.code}）",
            "",
            f"- 评分失败：{result.error}",
        ]
    return [
        f"### {result.position.name}（{result.position.code}）",
        "",
        f"- 分数：{result.score.score}",
        f"- 评级：{result.score.rating}",
        f"- 风险：{_translate_risk(result.score.risk)}",
        f"- 置信度：{_format_percent(result.score.confidence)}",
        "- 评分原因：",
        *[f"  - {_translate_reason(reason)}" for reason in result.score.reasons],
    ]


def _analysis_markdown_lines(result: AnalysisCalculationResult) -> list[str]:
    if result.analysis is None:
        return [
            f"### {result.position.name}（{result.position.code}）",
            "",
            f"- 分析失败：{result.error}",
        ]
    return [
        f"### {result.position.name}（{result.position.code}）",
        "",
        f"- 趋势：{_translate_trend(result.analysis.trend)}",
        f"- 动量：{_translate_momentum(result.analysis.momentum)}",
        f"- 风险：{_translate_risk(result.analysis.risk)}",
        f"- 支撑位：{_format_number(result.analysis.support)}",
        f"- 压力位：{_format_number(result.analysis.resistance)}",
        "- 分析原因：",
        *[f"  - {_translate_reason(reason)}" for reason in result.analysis.reasons],
    ]


def _csv_fieldnames() -> list[str]:
    return [
        "date",
        "code",
        "name",
        "score",
        "rating",
        "risk",
        "confidence",
        "reasons",
    ]


def _format_number(value: object) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
        if isnan(number):
            return "-"
        return f"{number:.2f}"
    except (TypeError, ValueError):
        return "-"


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
        if isnan(number):
            return "-"
        return f"{number:.2%}"
    except (TypeError, ValueError):
        return "-"


def _format_sector_exposures(exposures: tuple[tuple[str, float], ...]) -> str:
    if not exposures:
        return "-"
    return "；".join(
        f"{sector} {_format_percent(weight)}" for sector, weight in exposures
    )


def _translate_trend(value: str) -> str:
    return {"Bullish": "偏多", "Neutral": "中性", "Bearish": "偏空"}.get(value, value)


def _translate_momentum(value: str) -> str:
    return {"Strong": "强", "Medium": "中", "Weak": "弱"}.get(value, value)


def _translate_risk(value: str) -> str:
    return {"Low": "低", "Medium": "中", "High": "高"}.get(value, value)


def _translate_action(value: str) -> str:
    return {
        "Strong Hold": "强势持有",
        "Continue Hold": "继续持有",
        "Hold": "持有",
        "Watch": "观察",
        "Replace Candidate": "替换观察",
        "Reduce Position": "降低仓位",
        "Take Partial Profit": "部分止盈",
        "Take Profit": "止盈",
        "Exit Position": "退出持仓",
        "Exit": "退出",
        "Avoid Buying": "避免买入",
    }.get(value, value)


def _translate_position_state(value: str) -> str:
    return {
        "FULL": "满仓保留",
        "OVERWEIGHT": "超配",
        "ACCUMULATE": "保留核心仓",
        "NORMAL": "标准仓",
        "LIGHTEN": "轻仓",
        "EXIT": "清仓",
    }.get(value, value)


def _translate_trend_stage(value: str) -> str:
    return {
        "EARLY_UPTREND": "上升初期",
        "MID_UPTREND": "上升中段",
        "LATE_UPTREND": "上升后段",
        "PULLBACK": "趋势内回调",
        "BREAKDOWN": "趋势破位",
        "UNKNOWN": "阶段不明",
    }.get(value, value)


def _translate_priority(value: str) -> str:
    return {
        "Immediate": "立即",
        "Today": "今日",
        "This Week": "本周",
        "Observe": "观察",
        "Future": "未来",
    }.get(value, value)


def _translate_channel(value: str) -> str:
    return {
        "notification": "通知",
        "telegram": "Telegram",
        "email": "邮件",
    }.get(value, value)


def _translate_advice_horizon(value: str) -> str:
    return {"today": "今天", "tomorrow": "明天"}.get(value, value)


def _translate_notification_message(value: str) -> str:
    translations = {
        "notification is disabled": "通知未启用",
        "no notification channel is enabled": "没有启用任何通知渠道",
        "missing Telegram token or chat id environment variable": (
            "缺少 Telegram token 或 chat id 环境变量"
        ),
        "email recipients are not configured": "未配置邮件收件人",
        "missing email account environment variable": "缺少邮件账号环境变量",
        "sent": "发送成功",
    }
    if value.startswith("dry-run: would send "):
        return f"演练模式，未实际发送：{value.removeprefix('dry-run: would send ')}"
    return translations.get(value, value)


def _translate_reason(reason: str) -> str:
    translations = {
        "Close above MA20": "收盘价位于 MA20 上方",
        "Close below MA20": "收盘价位于 MA20 下方",
        "MA20 rising": "MA20 上行",
        "MA20 falling": "MA20 下行",
        "Close above MA60": "收盘价位于 MA60 上方",
        "Close below MA60": "收盘价位于 MA60 下方",
        "MACD above signal": "MACD 位于信号线上方",
        "MACD below signal": "MACD 位于信号线下方",
        "RSI in strong momentum range": "RSI 处于强动量区间",
        "RSI below momentum range": "RSI 低于动量区间",
        "Volume breakout": "成交量突破",
        "Volume below rolling average": "成交量低于滚动均量",
        "MACD histogram positive": "MACD 柱线为正",
        "MACD histogram negative": "MACD 柱线为负",
        "RSI risk threshold exceeded": "RSI 超过风险阈值",
        "ATR volatility threshold exceeded": "ATR 波动率超过阈值",
        "Support from lowest20": "支撑位来自 20 日低点",
        "Resistance from highest20": "压力位来自 20 日高点",
        "Trend is Bullish": "趋势偏多",
        "Trend is Neutral": "趋势中性",
        "Trend is Bearish": "趋势偏空",
        "Volume breakout confirmed": "成交量突破确认",
        "Volume signal is neutral": "成交量信号中性",
        "Momentum is Strong": "动量较强",
        "Momentum is Medium": "动量中等",
        "Momentum is Weak": "动量较弱",
        "Risk is Low": "风险较低",
        "Risk is Medium": "风险中等",
        "Risk is High": "风险较高",
        "Primary support from MA20/recent low/ATR stop": (
            "主支撑来自 MA20、近期低点或 ATR 止损位"
        ),
        "Primary resistance from recent high/ATR target": (
            "主压力来自近期高点或 ATR 目标位"
        ),
        "Abnormal volume risk": "异常放量风险",
        "Abnormal drawdown risk": "异常下跌风险",
        "Long upper shadow risk": "长上影线风险",
        "Downside breakout risk": "向下跌破风险",
        "Volume status unavailable": "量能状态不可用",
        "No valid stock scores are available": "没有可用个股评分",
        "No portfolio actions are available": "没有可用组合动作",
        "Portfolio valuation is unavailable": "组合估值不可用",
        "Portfolio risk is balanced across current holdings": "当前持仓风险分布较均衡",
        "Candidate risk is Low": "候选风险较低",
        "Candidate risk is Medium": "候选风险中等",
        "Candidate risk is High": "候选风险较高",
        "Candidate passed scanner filters": "候选通过扫描过滤条件",
        "Volume status is Strong": "量能状态较强",
        "Volume status is Breakout": "量能突破",
        "Volume status is Normal": "量能正常",
        "Volume status is Shrink": "量能收缩",
        "Volume status is Unknown": "量能状态未知",
        "Relative strength benchmark is not available in v0.5": (
            "v0.5 暂无相对强弱基准，按中性处理"
        ),
        "Relative strength data is unavailable": "相对强弱数据不可用，按中性处理",
        "Market close cutoff has passed; using latest daily bar": (
            "已过收盘判断时间，使用最新日线数据"
        ),
        "Before market close cutoff; using previous completed close": (
            "尚未到收盘判断时间，使用上一完整收盘日数据"
        ),
        "Analysis or score is unavailable": "分析或评分不可用",
        "Keep current position until signal quality improves": (
            "先保持当前仓位，等待信号质量改善"
        ),
        "Position is deeply underwater": "持仓浮亏较深",
        "No averaging down before right-side confirmation": (
            "没有右侧确认前不建议补仓"
        ),
        "Bearish trend with weak momentum and high risk": (
            "趋势偏空、动量较弱且风险较高"
        ),
        "Neutral trend with weak momentum": "趋势中性且动量较弱",
        "Close is near resistance": "价格接近压力位",
        "Protect existing profits while trend remains healthy": (
            "趋势仍健康，但需要保护已有利润"
        ),
        "Keep core position because trend remains bullish": (
            "趋势仍偏多，保留核心仓位"
        ),
        "Resistance has enough room": "距离压力位仍有空间",
        "High risk limits position size": "高风险限制仓位规模",
        "Signal mix supports keeping current exposure": "信号组合支持维持当前仓位",
        "No extra buying before cash management is implemented": (
            "现金管理实现前不建议额外加仓"
        ),
        "Long-term trend penalty: below MA60": "长期趋势惩罚：价格仍在 MA60 下方",
        "Switch cost is included in confidence": "替换置信度已计入换仓成本",
        "Trend remains intact": "趋势结构仍保持完整",
        "Trend is consolidating": "趋势处于整理阶段",
        "Trend has weakened": "趋势已经转弱",
        "Momentum and volume confirm the move": "动量与量能共同确认当前走势",
        "Momentum is improving but volume confirmation is limited": (
            "动量改善，但量能确认不足"
        ),
        "Momentum is weak, wait for confirmation": "动量偏弱，等待新的确认信号",
        "Relative strength remains competitive": "相对强弱仍具备竞争力",
        "Relative strength is lagging the portfolio": "相对强弱落后于组合",
        "Risk is elevated, avoid emotional averaging down": (
            "风险抬升，避免情绪化补仓"
        ),
        "Risk remains controlled": "风险仍处于可控状态",
        "Trend breakdown is confirmed": "趋势破位已经确认",
        "Current move is a pullback inside the broader trend": (
            "当前更像大趋势内回调"
        ),
        "Hold first and monitor MA20 confirmation": "先持有观察，重点跟踪 MA20 确认",
        "Uptrend is mature and close to resistance": "上升趋势进入后段并接近压力位",
        "Protect part of the profit while keeping core exposure": (
            "保护部分利润，同时保留核心仓位"
        ),
        "Risk is elevated but trend is not broken": "风险抬升，但趋势尚未破坏",
        "No profitable positions are available": "当前没有盈利持仓可用于集中度分析",
    }
    return translations.get(reason, _translate_prefixed_reason(reason))


def _translate_prefixed_reason(reason: str) -> str:
    prefix_translations = (
        ("Score is ", "分数 "),
        ("Relative strength score is ", "相对强弱分 "),
        ("Candidate score is higher by ", "候选分数高出 "),
        ("Portfolio trend score is ", "组合趋势分 "),
        ("Portfolio risk score is ", "组合风险分 "),
        ("Strongest holding is ", "最强持仓 "),
        ("Weakest holding is ", "最弱持仓 "),
        ("Largest position concentration is ", "最大持仓集中度 "),
        ("Expected portfolio score improves by ", "预期组合分改善 "),
        ("Trend improvement is ", "趋势改善 "),
        ("Relative strength improvement is ", "相对强弱改善 "),
        ("Risk improvement is ", "风险改善 "),
        ("Unrealized profit reached ", "浮动盈利达到 "),
        ("Position concentration is high at ", "单一持仓集中度较高，当前占比 "),
        ("Replacement confidence is ", "替换置信度 "),
        ("Trend stage is ", "趋势阶段 "),
        ("Profit concentration is high at ", "盈利集中度较高，当前占比 "),
        ("Profit concentration is medium at ", "盈利集中度中等，当前占比 "),
        ("Profit concentration is balanced at ", "盈利集中度均衡，当前占比 "),
        ("Most portfolio profit comes from ", "组合大部分盈利来自 "),
        ("Main profit contributors are ", "主要盈利贡献来自 "),
    )
    for prefix, translated_prefix in prefix_translations:
        if reason.startswith(prefix):
            return reason.replace(prefix, translated_prefix, 1)

    dynamic_translations = (
        _translate_rank_reason,
        _translate_holding_list_reason,
        _translate_sector_exposure_reason,
        _translate_position_sector_exposure_reason,
        _translate_volume_reason_if_match,
        _translate_relative_strength_reason_if_match,
        _translate_multi_period_relative_strength_reason,
        _translate_replacement_reason,
    )
    for translator in dynamic_translations:
        translated = translator(reason)
        if translated is not None:
            return translated
    return reason


def _translate_rank_reason(reason: str) -> str | None:
    rank_prefixes = (
        ("Portfolio rank ", "组合内排名 "),
        ("Relative rank ", "相对强弱排名 "),
        ("Risk rank ", "风险排名 "),
        ("Trend rank ", "趋势排名 "),
    )
    for prefix, translated_prefix in rank_prefixes:
        if reason.startswith(prefix):
            return reason.replace(prefix, translated_prefix).replace(" of ", "/")
    return None


def _translate_holding_list_reason(reason: str) -> str | None:
    list_prefixes = (
        ("High-risk holdings: ", "高风险持仓："),
        ("Drawdown positions: ", "浮亏持仓："),
    )
    for prefix, translated_prefix in list_prefixes:
        if reason.startswith(prefix):
            return reason.replace(prefix, translated_prefix, 1)
    return None


def _translate_sector_exposure_reason(reason: str) -> str | None:
    marker = " exposure is relatively high at "
    if marker not in reason:
        return None
    sector, weight = reason.split(marker, maxsplit=1)
    return f"{sector} 暴露较高，当前占比 {weight}"


def _translate_position_sector_exposure_reason(reason: str) -> str | None:
    marker = " sector exposure is high at "
    if marker not in reason:
        return None
    sector, weight = reason.split(marker, maxsplit=1)
    return f"{sector} 板块暴露较高，当前占比 {weight}"


def _translate_volume_reason_if_match(reason: str) -> str | None:
    if not reason.startswith("Today's volume is "):
        return None
    return _translate_volume_reason(reason)


def _translate_relative_strength_reason_if_match(reason: str) -> str | None:
    if not reason.startswith("Relative strength rank "):
        return None
    return _translate_relative_strength_reason(reason)


def _translate_multi_period_relative_strength_reason(reason: str) -> str | None:
    if not reason.startswith("Relative strength multi-period rank "):
        return None
    translated = reason.replace(
        "Relative strength multi-period rank ",
        "多周期相对强弱组合内排名 ",
    )
    translated = translated.replace(" of ", "/")
    translated = translated.replace("; sector rank ", "；行业内排名 ")
    translated = translated.replace("; weighted return ", "；加权收益 ")
    return translated


def _translate_replacement_reason(reason: str) -> str | None:
    if not (
        reason.startswith("Replacement candidate ")
        and reason.endswith(" has higher score")
    ):
        return None
    candidate = reason.removeprefix("Replacement candidate ").removesuffix(
        " has higher score"
    )
    return f"替换候选 {candidate} 分数更高"


def _translate_volume_reason(reason: str) -> str:
    translated = reason.replace("Today's volume is ", "今日成交量为滚动均量的 ")
    translated = translated.replace(" of rolling average: shrink volume", "，量能收缩")
    translated = translated.replace(
        " of rolling average: breakout volume", "，量能突破"
    )
    translated = translated.replace(" of rolling average: strong volume", "，量能较强")
    translated = translated.replace(" of rolling average: normal volume", "，量能正常")
    return translated


def _translate_relative_strength_reason(reason: str) -> str:
    translated = reason.replace("Relative strength rank ", "相对强弱组合内排名 ")
    translated = translated.replace(" of ", "/")
    translated = translated.replace("; sector rank ", "；行业内排名 ")
    return translated
