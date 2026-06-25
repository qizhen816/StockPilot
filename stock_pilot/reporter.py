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
    DailySummary,
    DecisionCalculationResult,
    FetchResult,
    IndicatorCalculationResult,
    PortfolioAnalysis,
    PortfolioValuationResult,
    ScannerResult,
    ScoreCalculationResult,
)


@dataclass(frozen=True)
class DailyReportPayload:
    """All computed daily results needed by reporters."""

    report_date: date
    fetch_results: tuple[FetchResult, ...]
    portfolio_valuation: PortfolioValuationResult
    portfolio_analysis: PortfolioAnalysis
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

    def render_summary(self, summary: DailySummary) -> None:
        """Print the daily natural-language summary."""
        table = Table(title="StockPilot 今日总结")
        table.add_column("项目", style="cyan")
        table.add_column("内容")
        table.add_row("最强个股", summary.strongest_stock or "-")
        table.add_row("最弱个股", summary.weakest_stock or "-")
        table.add_row("今日风险", summary.today_risk)
        table.add_row("明日观察", "；".join(summary.tomorrow_watchlist) or "-")
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
        table.add_row("组合风险分", _format_number(analysis.portfolio_risk_score))
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
        "## 组合概览",
        "",
        *_portfolio_markdown_lines(payload.portfolio_valuation),
        "",
        "## 组合分析",
        "",
        *_portfolio_analysis_markdown_lines(payload.portfolio_analysis),
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


def _portfolio_analysis_markdown_lines(analysis: PortfolioAnalysis) -> list[str]:
    return [
        f"- 行业暴露：{_format_sector_exposures(analysis.sector_exposures)}",
        f"- 最大持仓集中度：{_format_percent(analysis.concentration_top_position_pct)}",
        f"- 最大盈利：{analysis.largest_winner or '-'}",
        f"- 最大亏损：{analysis.largest_loser or '-'}",
        f"- 最高风险持仓：{analysis.highest_risk_position or '-'}",
        f"- 最弱相对强弱：{analysis.weakest_relative_position or '-'}",
        f"- 组合趋势分：{_format_number(analysis.portfolio_trend_score)}",
        f"- 组合风险分：{_format_number(analysis.portfolio_risk_score)}",
    ]


def _summary_markdown_lines(summary: DailySummary) -> list[str]:
    lines = [
        f"- 最强个股：{summary.strongest_stock or '-'}",
        f"- 最弱个股：{summary.weakest_stock or '-'}",
        f"- 今日风险：{summary.today_risk}",
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
        "Continue Hold": "继续持有",
        "Hold": "持有",
        "Accumulate": "加仓观察",
        "Watch": "观察",
        "Reduce Position": "降低仓位",
        "Take Profit": "止盈",
        "Avoid Buying": "避免买入",
    }.get(value, value)


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
        "Relative strength benchmark is not available in v0.5": (
            "v0.5 暂无相对强弱基准，按中性处理"
        ),
    }
    return translations.get(reason, reason)
