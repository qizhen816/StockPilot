"""Tests for report persistence."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisDataSnapshot,
    AnalysisResult,
    DailySummary,
    DecisionCalculationResult,
    DecisionResult,
    PortfolioAction,
    PortfolioAnalysis,
    PortfolioDecisionPlan,
    PortfolioValuation,
    PortfolioValuationResult,
    Position,
    PositionValuation,
    ScanCandidate,
    ScannerResult,
    ScoreCalculationResult,
    ScoreComponent,
    StockScore,
)
from stock_pilot.reporter import CsvReporter, DailyReportPayload, MarkdownReporter


def test_markdown_reporter_writes_chinese_daily_report(tmp_path: Path) -> None:
    """MarkdownReporter should persist a Chinese report with scores and reasons."""
    payload = _payload()

    path = MarkdownReporter(tmp_path).write(payload)

    content = path.read_text(encoding="utf-8")
    assert path.name == "2026-06-25.md"
    assert "# StockPilot 日报 2026-06-25" in content
    assert "## 分析口径" in content
    assert "## 明日组合计划" in content
    assert "强势持有" in content
    assert "兴森科技（002436）" in content
    assert "趋势偏多" in content
    assert "收盘价位于 MA20 上方" in content


def test_csv_reporter_appends_score_history(tmp_path: Path) -> None:
    """CsvReporter should append one row per stock score."""
    path = tmp_path / "history.csv"

    CsvReporter(path).append(_payload())

    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["date"] == "2026-06-25"
    assert rows[0]["code"] == "002436"
    assert rows[0]["risk"] == "低"
    assert "趋势偏多" in rows[0]["reasons"]


def _payload() -> DailyReportPayload:
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    analysis = AnalysisResult(
        code="002436",
        name="兴森科技",
        trend="Bullish",
        momentum="Strong",
        risk="Low",
        support=9.5,
        resistance=12.5,
        reasons=("Close above MA20", "Volume breakout"),
    )
    stock_score = StockScore(
        code="002436",
        name="兴森科技",
        score=95,
        rating="★★★★★",
        risk="Low",
        confidence=0.7,
        components=(
            ScoreComponent(
                name="Trend",
                score=40,
                weight=40,
                reason="Trend is Bullish",
            ),
        ),
        reasons=("Trend is Bullish", "Volume breakout confirmed"),
    )
    valuation = PortfolioValuation(
        positions=(
            PositionValuation(
                code="002436",
                name="兴森科技",
                shares=100,
                cost_price=10.0,
                cost_amount=1000.0,
                current_price=12.0,
                previous_close=11.0,
                market_value=1200.0,
                unrealized_pnl=200.0,
                unrealized_pnl_pct=0.2,
                daily_pnl=100.0,
                daily_pnl_pct=1 / 11,
            ),
        ),
        total_cost=1000.0,
        total_market_value=1200.0,
        total_unrealized_pnl=200.0,
        total_unrealized_pnl_pct=0.2,
        total_daily_pnl=100.0,
    )

    return DailyReportPayload(
        report_date=date(2026, 6, 25),
        analysis_snapshot=AnalysisDataSnapshot(
            data_date="2026-06-25",
            is_using_previous_close=False,
            advice_horizon="tomorrow",
            reason="Market close cutoff has passed; using latest daily bar",
        ),
        fetch_results=(),
        portfolio_valuation=PortfolioValuationResult(valuation=valuation),
        portfolio_analysis=PortfolioAnalysis(
            sector_exposures=(("科技", 1.0),),
            concentration_top_position_pct=1.0,
            largest_winner="兴森科技（002436）",
            largest_loser="兴森科技（002436）",
            highest_risk_position="兴森科技（002436）",
            weakest_relative_position="兴森科技（002436）",
            portfolio_trend_score=95.0,
            portfolio_risk_score=25.0,
            portfolio_risk_level="Low",
            portfolio_risk_reasons=(
                "Portfolio risk is balanced across current holdings",
            ),
        ),
        portfolio_decision_plan=PortfolioDecisionPlan(
            actions=(
                PortfolioAction(
                    code="002436",
                    name="兴森科技",
                    action="Strong Hold",
                    confidence=0.88,
                    risk="Low",
                    score=95,
                    rank=1,
                    relative_rank=1,
                    risk_rank=1,
                    trend_rank=1,
                    total_positions=1,
                    relative_strength_score=50,
                    replacement=None,
                    reasons=(
                        "Portfolio rank 1 of 1",
                        "Score is 95",
                        "Trend is Bullish",
                    ),
                ),
            ),
            replacements=(),
            portfolio_score=95.0,
            portfolio_risk_score=25.0,
            summary="明日组合重点是继续跟踪 兴森科技，重点防守 兴森科技。",
            reasons=(
                "Portfolio trend score is 95.00",
                "Portfolio risk score is 25.00",
            ),
        ),
        indicator_results=(),
        analysis_results=(
            AnalysisCalculationResult(position=position, analysis=analysis),
        ),
        score_results=(
            ScoreCalculationResult(position=position, score=stock_score),
        ),
        decision_results=(
            DecisionCalculationResult(
                position=position,
                decision=DecisionResult(
                    code="002436",
                    name="兴森科技",
                    action="Strong Hold",
                    confidence=0.8,
                    risk="Low",
                    reasons=("Score 95 with rating ★★★★★",),
                ),
            ),
        ),
        summary=DailySummary(
            strongest_stock="兴森科技（002436）",
            weakest_stock="兴森科技（002436）",
            today_risk="今日组合未出现高风险个股。",
            tomorrow_watchlist=("兴森科技（002436）：95 分，风险低",),
            operation_advice="明日操作建议：继续跟踪强势品种 兴森科技。",
            conclusion="今日组合最强的是 兴森科技。",
            reasons=("最强个股来自最高评分：兴森科技 95 分。",),
        ),
        scanner_result=ScannerResult(
            candidates=(
                ScanCandidate(
                    code="002436",
                    name="兴森科技",
                    score=95,
                    rating="★★★★★",
                    risk="Low",
                    confidence=0.7,
                    reasons=("Trend is Bullish",),
                ),
            ),
            skipped_count=0,
        ),
    )
