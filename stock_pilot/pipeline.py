"""Reusable daily analysis pipeline for CLI and dashboard entry points."""

from __future__ import annotations

from datetime import date, datetime

from stock_pilot.ai_summary import DailySummaryGenerator
from stock_pilot.analyzer import Analyzer
from stock_pilot.fetcher import MarketDataFetcher
from stock_pilot.indicators import IndicatorCalculator
from stock_pilot.market_session import AnalysisDataSelector
from stock_pilot.models import AppSettings
from stock_pilot.portfolio import (
    Portfolio,
    PortfolioAnalyzer,
    PortfolioValuationCalculator,
)
from stock_pilot.portfolio_decision import PortfolioDecisionEngine
from stock_pilot.reporter import DailyReportPayload
from stock_pilot.scanner import MarketScanner
from stock_pilot.scorer import ScoreEngine
from stock_pilot.strategy import DecisionEngine


def run_daily_pipeline(
    settings: AppSettings,
    portfolio: Portfolio,
    report_date: date | None = None,
    report_datetime: datetime | None = None,
) -> DailyReportPayload:
    """Run the full post-market decision-support pipeline."""
    current_datetime = report_datetime or datetime.now()
    fetcher = MarketDataFetcher(settings.fetcher)
    fetch_results = fetcher.fetch_all(portfolio.positions)
    analysis_fetch_results, analysis_snapshot = AnalysisDataSelector(
        settings.market_session
    ).select(
        fetch_results,
        current_time=current_datetime,
    )
    indicator_results = IndicatorCalculator(settings.indicators).calculate_all(
        analysis_fetch_results
    )
    analysis_results = Analyzer(settings.analyzer).analyze_all(indicator_results)
    score_results = ScoreEngine(settings.scorer).score_all(analysis_results)
    scanner_result = MarketScanner(settings.scanner).scan(
        score_results=score_results,
        analysis_results=analysis_results,
    )
    decision_results = DecisionEngine(settings.decision).decide_all(
        score_results=score_results,
        analysis_results=analysis_results,
    )
    portfolio_valuation = PortfolioValuationCalculator().calculate(
        portfolio=portfolio,
        fetch_results=fetch_results,
    )
    portfolio_analysis = PortfolioAnalyzer().analyze(
        valuation_result=portfolio_valuation,
        score_results=score_results,
    )
    portfolio_decision_plan = PortfolioDecisionEngine(
        settings.portfolio_decision
    ).build_plan(
        score_results=score_results,
        analysis_results=analysis_results,
        portfolio_analysis=portfolio_analysis,
        scanner_result=scanner_result,
    )
    summary = DailySummaryGenerator(settings.summary).generate(
        score_results=score_results,
        analysis_results=analysis_results,
        portfolio_valuation=portfolio_valuation,
        analysis_snapshot=analysis_snapshot,
    )

    return DailyReportPayload(
        report_date=report_date or current_datetime.date(),
        analysis_snapshot=analysis_snapshot,
        fetch_results=fetch_results,
        portfolio_valuation=portfolio_valuation,
        portfolio_analysis=portfolio_analysis,
        portfolio_decision_plan=portfolio_decision_plan,
        indicator_results=indicator_results,
        analysis_results=analysis_results,
        score_results=score_results,
        decision_results=decision_results,
        summary=summary,
        scanner_result=scanner_result,
    )
