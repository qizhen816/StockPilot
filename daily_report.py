"""CLI entry point for the StockPilot daily report."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from stock_pilot.ai_summary import DailySummaryGenerator
from stock_pilot.analyzer import Analyzer
from stock_pilot.fetcher import MarketDataFetcher
from stock_pilot.indicators import IndicatorCalculator
from stock_pilot.logging_config import configure_logging
from stock_pilot.portfolio import (
    PortfolioAnalyzer,
    PortfolioLoader,
    PortfolioValuationCalculator,
)
from stock_pilot.reporter import (
    ConsoleReporter,
    CsvReporter,
    DailyReportPayload,
    MarkdownReporter,
)
from stock_pilot.scanner import MarketScanner
from stock_pilot.scorer import ScoreEngine
from stock_pilot.settings import SettingsLoader
from stock_pilot.strategy import DecisionEngine

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"
DEFAULT_PORTFOLIO_PATH = PROJECT_ROOT / "config" / "portfolio.yaml"


def main() -> None:
    """Run the v0.1 daily report fetch pipeline."""
    settings = SettingsLoader(DEFAULT_SETTINGS_PATH).load()
    configure_logging(settings.log_level)

    portfolio = PortfolioLoader(DEFAULT_PORTFOLIO_PATH).load()
    fetcher = MarketDataFetcher(settings.fetcher)
    fetch_results = fetcher.fetch_all(portfolio.positions)
    indicator_results = IndicatorCalculator(settings.indicators).calculate_all(
        fetch_results
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
    summary = DailySummaryGenerator(settings.summary).generate(
        score_results=score_results,
        analysis_results=analysis_results,
        portfolio_valuation=portfolio_valuation,
    )

    reporter = ConsoleReporter()
    reporter.render_fetch_results(fetch_results)
    reporter.render_portfolio_valuation(portfolio_valuation)
    reporter.render_portfolio_analysis(portfolio_analysis)
    reporter.render_indicator_results(indicator_results)
    reporter.render_analysis_results(analysis_results)
    reporter.render_score_results(score_results)
    reporter.render_scanner_result(scanner_result)
    reporter.render_decision_results(decision_results)
    reporter.render_summary(summary)

    payload = DailyReportPayload(
        report_date=date.today(),
        fetch_results=fetch_results,
        portfolio_valuation=portfolio_valuation,
        portfolio_analysis=portfolio_analysis,
        indicator_results=indicator_results,
        analysis_results=analysis_results,
        score_results=score_results,
        decision_results=decision_results,
        summary=summary,
        scanner_result=scanner_result,
    )
    MarkdownReporter(settings.report.output_dir).write(payload)
    CsvReporter(settings.report.history_csv).append(payload)


if __name__ == "__main__":
    main()
