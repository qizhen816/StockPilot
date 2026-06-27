"""Tests for the reusable daily pipeline."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from stock_pilot.models import (
    AnalyzerSettings,
    AppSettings,
    DecisionSettings,
    EmailSettings,
    FetcherSettings,
    IndicatorSettings,
    MarketData,
    MarketSessionSettings,
    NotificationSettings,
    Portfolio,
    PortfolioDecisionSettings,
    Position,
    ReportSettings,
    ScannerSettings,
    ScorerSettings,
    SummarySettings,
    TelegramSettings,
)
from stock_pilot.pipeline import run_daily_pipeline


def test_run_daily_pipeline_returns_complete_payload(monkeypatch) -> None:
    """run_daily_pipeline should produce all report sections."""
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    portfolio = Portfolio(positions=(position,))
    settings = _settings()

    def fake_fetch(self, fetched_position: Position) -> MarketData:
        return MarketData(
            code=fetched_position.code,
            name=fetched_position.name,
            frame=_market_frame(),
        )

    monkeypatch.setattr("stock_pilot.fetcher.MarketDataFetcher.fetch", fake_fetch)

    payload = run_daily_pipeline(
        settings=settings,
        portfolio=portfolio,
        report_datetime=datetime(2026, 6, 25, 16, 0),
    )

    assert len(payload.fetch_results) == 1
    assert len(payload.score_results) == 1
    assert payload.summary.strongest_stock == "兴森科技（002436）"
    assert payload.analysis_snapshot.advice_horizon == "tomorrow"


def _market_frame() -> pd.DataFrame:
    periods = 80
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=periods),
            "open": [10.0 + index * 0.1 for index in range(periods)],
            "high": [10.8 + index * 0.1 for index in range(periods)],
            "low": [9.7 + index * 0.1 for index in range(periods)],
            "close": [10.2 + index * 0.1 for index in range(periods)],
            "volume": [1000.0 + index * 20 for index in range(periods)],
            "pct_change": [1.0 for _ in range(periods)],
        }
    )


def _settings() -> AppSettings:
    return AppSettings(
        fetcher=FetcherSettings(
            start_date="20200101",
            adjust="qfq",
            retry_attempts=1,
            fallback_sources=("eastmoney",),
        ),
        indicators=IndicatorSettings(
            sma_periods=(5, 10, 20, 60),
            ema_short_period=12,
            ema_long_period=26,
            macd_signal_period=9,
            rsi_period=14,
            atr_period=14,
            volume_ratio_period=20,
            highest_period=20,
            lowest_period=20,
        ),
        analyzer=AnalyzerSettings(
            trend_short_ma_period=5,
            trend_mid_ma_period=20,
            trend_long_ma_period=60,
            momentum_rsi_lower=55,
            momentum_rsi_upper=75,
            volume_breakout_ratio=1.3,
            risk_rsi_high=80,
            risk_atr_pct_high=0.08,
            support_resistance_period=20,
        ),
        scorer=ScorerSettings(
            trend_weight=35,
            momentum_weight=15,
            volume_weight=10,
            risk_weight=20,
            relative_strength_weight=20,
            reason_confidence_step=0.04,
            minimum_confidence=0.55,
            maximum_confidence=0.90,
            maximum_score=95,
        ),
        report=ReportSettings(output_dir="reports/daily", history_csv="reports.csv"),
        summary=SummarySettings(watchlist_limit=3, high_risk_levels=("High",)),
        scanner=ScannerSettings(
            candidate_limit=5,
            min_score=70,
            allowed_risk_levels=("Low", "Medium"),
        ),
        decision=DecisionSettings(
            high_score_threshold=80,
            low_score_threshold=55,
            high_confidence_threshold=0.75,
        ),
        portfolio_decision=PortfolioDecisionSettings(
            strong_hold_score_threshold=85,
            hold_score_threshold=70,
            reduce_score_threshold=55,
            exit_score_threshold=40,
            replace_score_threshold=60,
            replacement_min_score_gap=12,
            minimum_confidence=0.55,
            maximum_confidence=0.90,
        ),
        market_session=MarketSessionSettings(analysis_cutoff_time="15:00"),
        notification=NotificationSettings(
            enabled=False,
            dry_run=True,
            telegram=TelegramSettings(
                enabled=False,
                bot_token_env="STOCKPILOT_TELEGRAM_BOT_TOKEN",
                chat_id_env="STOCKPILOT_TELEGRAM_CHAT_ID",
            ),
            email=EmailSettings(
                enabled=False,
                smtp_host="smtp.example.com",
                smtp_port=587,
                username_env="STOCKPILOT_EMAIL_USERNAME",
                password_env="STOCKPILOT_EMAIL_PASSWORD",
                sender_env="STOCKPILOT_EMAIL_SENDER",
                recipients=(),
                use_tls=True,
            ),
        ),
        log_level="INFO",
    )
