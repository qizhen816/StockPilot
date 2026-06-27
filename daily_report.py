"""CLI entry point for the StockPilot daily report."""

from __future__ import annotations

from pathlib import Path

from stock_pilot.logging_config import configure_logging
from stock_pilot.notification import NotificationDispatcher
from stock_pilot.pipeline import run_daily_pipeline
from stock_pilot.portfolio import PortfolioLoader
from stock_pilot.reporter import (
    ConsoleReporter,
    CsvReporter,
    MarkdownReporter,
)
from stock_pilot.settings import SettingsLoader

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"
DEFAULT_PORTFOLIO_PATH = PROJECT_ROOT / "config" / "portfolio.yaml"


def main() -> None:
    """Run the daily report pipeline and deliver configured outputs."""
    settings = SettingsLoader(DEFAULT_SETTINGS_PATH).load()
    configure_logging(settings.log_level)

    portfolio = PortfolioLoader(DEFAULT_PORTFOLIO_PATH).load()
    payload = run_daily_pipeline(settings=settings, portfolio=portfolio)

    reporter = ConsoleReporter()
    reporter.render_fetch_results(payload.fetch_results)
    reporter.render_analysis_snapshot(payload.analysis_snapshot)
    reporter.render_portfolio_valuation(payload.portfolio_valuation)
    reporter.render_portfolio_analysis(payload.portfolio_analysis)
    reporter.render_portfolio_decision_plan(payload.portfolio_decision_plan)
    reporter.render_indicator_results(payload.indicator_results)
    reporter.render_analysis_results(payload.analysis_results)
    reporter.render_score_results(payload.score_results)
    reporter.render_scanner_result(payload.scanner_result)
    reporter.render_decision_results(payload.decision_results)
    reporter.render_summary(payload.summary)

    markdown_path = MarkdownReporter(settings.report.output_dir).write(payload)
    CsvReporter(settings.report.history_csv).append(payload)
    notification_result = NotificationDispatcher(settings.notification).dispatch(
        payload=payload,
        markdown_path=markdown_path,
    )
    reporter.render_notification_results(notification_result)


if __name__ == "__main__":
    main()
