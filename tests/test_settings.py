"""Tests for settings loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from stock_pilot.settings import SettingsError, SettingsLoader


def test_settings_loader_loads_fetcher_settings(tmp_path: Path) -> None:
    """SettingsLoader should parse fetcher and logging configuration."""
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
log_level: DEBUG
fetcher:
  start_date: "20200101"
  adjust: qfq
  retry_attempts: 2
  fallback_sources: ["eastmoney", "tencent"]
  cache_dir: reports/cache
indicators:
  sma_periods: [5, 10, 20, 60]
  ema_short_period: 12
  ema_long_period: 26
  macd_signal_period: 9
  rsi_period: 14
  atr_period: 14
  volume_ratio_period: 20
  highest_period: 20
  lowest_period: 20
analyzer:
  trend_short_ma_period: 5
  trend_mid_ma_period: 20
  trend_long_ma_period: 60
  momentum_rsi_lower: 55
  momentum_rsi_upper: 75
  volume_breakout_ratio: 1.3
  risk_rsi_high: 80
  risk_atr_pct_high: 0.08
  support_resistance_period: 20
scorer:
  trend_weight: 40
  volume_weight: 20
  momentum_weight: 15
  risk_weight: 15
  relative_strength_weight: 10
  reason_confidence_step: 0.04
  minimum_confidence: 0.55
  maximum_confidence: 0.90
  maximum_score: 95
  relative_strength_5d_weight: 0.30
  relative_strength_20d_weight: 0.40
  relative_strength_60d_weight: 0.30
  long_term_trend_penalty: 10
report:
  output_dir: reports/daily
  history_csv: reports/history.csv
summary:
  watchlist_limit: 3
  high_risk_levels: ["High"]
scanner:
  candidate_limit: 5
  min_score: 70
  allowed_risk_levels: ["Low", "Medium"]
portfolio_decision:
  strong_hold_score_threshold: 85
  hold_score_threshold: 70
  reduce_score_threshold: 55
  exit_score_threshold: 40
  replace_score_threshold: 60
  replacement_min_score_gap: 12
  minimum_confidence: 0.55
  maximum_confidence: 0.90
  replacement_min_confidence: 0.68
  replacement_switch_cost_penalty: 0.08
position_manager:
  full_position_pct: 1.0
  overweight_position_pct: 1.25
  accumulate_position_pct: 0.75
  normal_position_pct: 0.50
  lighten_position_pct: 0.25
  exit_position_pct: 0.0
  near_resistance_pct: 0.03
  wide_resistance_pct: 0.08
  profit_protection_levels: [0.05, 0.10, 0.15, 0.20]
  atr_stop_multiplier: 2.0
  sector_concentration_threshold: 0.60
  position_concentration_threshold: 0.25
  minimum_confidence: 0.55
  maximum_confidence: 0.90
  pullback_position_pct: 1.0
  late_uptrend_position_pct: 0.75
  breakdown_position_pct: 0.25
market_session:
  analysis_cutoff_time: "15:00"
notification:
  enabled: false
  dry_run: true
  telegram:
    enabled: false
    bot_token_env: STOCKPILOT_TELEGRAM_BOT_TOKEN
    chat_id_env: STOCKPILOT_TELEGRAM_CHAT_ID
  email:
    enabled: false
    smtp_host: smtp.example.com
    smtp_port: 587
    username_env: STOCKPILOT_EMAIL_USERNAME
    password_env: STOCKPILOT_EMAIL_PASSWORD
    sender_env: STOCKPILOT_EMAIL_SENDER
    recipients: []
    use_tls: true
""",
        encoding="utf-8",
    )

    settings = SettingsLoader(path).load()

    assert settings.log_level == "DEBUG"
    assert settings.fetcher.start_date == "20200101"
    assert settings.fetcher.adjust == "qfq"
    assert settings.fetcher.cache_dir == Path("reports/cache")
    assert settings.indicators.sma_periods == (5, 10, 20, 60)
    assert settings.indicators.ema_short_period == 12
    assert settings.indicators.ema_long_period == 26
    assert settings.analyzer.trend_mid_ma_period == 20
    assert settings.analyzer.volume_breakout_ratio == 1.3
    assert settings.scorer.trend_weight == 40
    assert settings.scorer.relative_strength_weight == 10
    assert settings.scorer.maximum_score == 95
    assert settings.scorer.relative_strength_20d_weight == 0.40
    assert settings.scorer.long_term_trend_penalty == 10
    assert settings.report.output_dir == Path("reports/daily")
    assert settings.report.history_csv == Path("reports/history.csv")
    assert settings.summary.watchlist_limit == 3
    assert settings.summary.high_risk_levels == ("High",)
    assert settings.scanner.candidate_limit == 5
    assert settings.scanner.min_score == 70
    assert settings.scanner.allowed_risk_levels == ("Low", "Medium")
    assert settings.portfolio_decision.strong_hold_score_threshold == 85
    assert settings.portfolio_decision.replacement_min_score_gap == 12
    assert settings.portfolio_decision.maximum_confidence == 0.90
    assert settings.portfolio_decision.replacement_min_confidence == 0.68
    assert settings.position_manager.accumulate_position_pct == 0.75
    assert settings.position_manager.profit_protection_levels == (
        0.05,
        0.10,
        0.15,
        0.20,
    )
    assert settings.position_manager.maximum_confidence == 0.90
    assert settings.position_manager.pullback_position_pct == 1.0
    assert settings.market_session.analysis_cutoff_time == "15:00"
    assert settings.notification.enabled is False
    assert settings.notification.dry_run is True
    assert settings.notification.telegram.bot_token_env == (
        "STOCKPILOT_TELEGRAM_BOT_TOKEN"
    )
    assert settings.notification.email.smtp_port == 587
    assert settings.notification.email.recipients == ()


def test_settings_loader_requires_fetcher_section(tmp_path: Path) -> None:
    """SettingsLoader should reject settings without fetcher configuration."""
    path = tmp_path / "settings.yaml"
    path.write_text("log_level: INFO\n", encoding="utf-8")

    with pytest.raises(SettingsError):
        SettingsLoader(path).load()


def test_settings_loader_requires_indicators_section(tmp_path: Path) -> None:
    """SettingsLoader should reject settings without indicator configuration."""
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
log_level: INFO
fetcher:
  start_date: "20200101"
  adjust: qfq
  retry_attempts: 2
  fallback_sources: ["eastmoney", "tencent"]
""",
        encoding="utf-8",
    )

    with pytest.raises(SettingsError):
        SettingsLoader(path).load()


def test_settings_loader_requires_analyzer_section(tmp_path: Path) -> None:
    """SettingsLoader should reject settings without analyzer configuration."""
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
log_level: INFO
fetcher:
  start_date: "20200101"
  adjust: qfq
  retry_attempts: 2
  fallback_sources: ["eastmoney", "tencent"]
indicators:
  sma_periods: [5, 10, 20, 60]
  ema_short_period: 12
  ema_long_period: 26
  macd_signal_period: 9
  rsi_period: 14
  atr_period: 14
  volume_ratio_period: 20
  highest_period: 20
  lowest_period: 20
""",
        encoding="utf-8",
    )

    with pytest.raises(SettingsError):
        SettingsLoader(path).load()


def test_settings_loader_requires_scorer_section(tmp_path: Path) -> None:
    """SettingsLoader should reject settings without scorer configuration."""
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
log_level: INFO
fetcher:
  start_date: "20200101"
  adjust: qfq
  retry_attempts: 2
  fallback_sources: ["eastmoney", "tencent"]
indicators:
  sma_periods: [5, 10, 20, 60]
  ema_short_period: 12
  ema_long_period: 26
  macd_signal_period: 9
  rsi_period: 14
  atr_period: 14
  volume_ratio_period: 20
  highest_period: 20
  lowest_period: 20
analyzer:
  trend_short_ma_period: 5
  trend_mid_ma_period: 20
  trend_long_ma_period: 60
  momentum_rsi_lower: 55
  momentum_rsi_upper: 75
  volume_breakout_ratio: 1.3
  risk_rsi_high: 80
  risk_atr_pct_high: 0.08
  support_resistance_period: 20
""",
        encoding="utf-8",
    )

    with pytest.raises(SettingsError):
        SettingsLoader(path).load()


def test_settings_loader_requires_score_weights_to_sum_to_100(tmp_path: Path) -> None:
    """SettingsLoader should reject score weights that do not sum to 100."""
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
log_level: INFO
fetcher:
  start_date: "20200101"
  adjust: qfq
  retry_attempts: 2
  fallback_sources: ["eastmoney", "tencent"]
indicators:
  sma_periods: [5, 10, 20, 60]
  ema_short_period: 12
  ema_long_period: 26
  macd_signal_period: 9
  rsi_period: 14
  atr_period: 14
  volume_ratio_period: 20
  highest_period: 20
  lowest_period: 20
analyzer:
  trend_short_ma_period: 5
  trend_mid_ma_period: 20
  trend_long_ma_period: 60
  momentum_rsi_lower: 55
  momentum_rsi_upper: 75
  volume_breakout_ratio: 1.3
  risk_rsi_high: 80
  risk_atr_pct_high: 0.08
  support_resistance_period: 20
scorer:
  trend_weight: 40
  volume_weight: 20
  momentum_weight: 15
  risk_weight: 15
  relative_strength_weight: 9
  reason_confidence_step: 0.04
  minimum_confidence: 0.50
  maximum_confidence: 0.95
""",
        encoding="utf-8",
    )

    with pytest.raises(SettingsError):
        SettingsLoader(path).load()


def test_settings_loader_requires_report_section(tmp_path: Path) -> None:
    """SettingsLoader should reject settings without report configuration."""
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
log_level: INFO
fetcher:
  start_date: "20200101"
  adjust: qfq
  retry_attempts: 2
  fallback_sources: ["eastmoney", "tencent"]
indicators:
  sma_periods: [5, 10, 20, 60]
  ema_short_period: 12
  ema_long_period: 26
  macd_signal_period: 9
  rsi_period: 14
  atr_period: 14
  volume_ratio_period: 20
  highest_period: 20
  lowest_period: 20
analyzer:
  trend_short_ma_period: 5
  trend_mid_ma_period: 20
  trend_long_ma_period: 60
  momentum_rsi_lower: 55
  momentum_rsi_upper: 75
  volume_breakout_ratio: 1.3
  risk_rsi_high: 80
  risk_atr_pct_high: 0.08
  support_resistance_period: 20
scorer:
  trend_weight: 40
  volume_weight: 20
  momentum_weight: 15
  risk_weight: 15
  relative_strength_weight: 10
  reason_confidence_step: 0.04
  minimum_confidence: 0.50
  maximum_confidence: 0.95
""",
        encoding="utf-8",
    )

    with pytest.raises(SettingsError):
        SettingsLoader(path).load()


def test_settings_loader_requires_summary_section(tmp_path: Path) -> None:
    """SettingsLoader should reject settings without summary configuration."""
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
log_level: INFO
fetcher:
  start_date: "20200101"
  adjust: qfq
  retry_attempts: 2
  fallback_sources: ["eastmoney", "tencent"]
indicators:
  sma_periods: [5, 10, 20, 60]
  ema_short_period: 12
  ema_long_period: 26
  macd_signal_period: 9
  rsi_period: 14
  atr_period: 14
  volume_ratio_period: 20
  highest_period: 20
  lowest_period: 20
analyzer:
  trend_short_ma_period: 5
  trend_mid_ma_period: 20
  trend_long_ma_period: 60
  momentum_rsi_lower: 55
  momentum_rsi_upper: 75
  volume_breakout_ratio: 1.3
  risk_rsi_high: 80
  risk_atr_pct_high: 0.08
  support_resistance_period: 20
scorer:
  trend_weight: 40
  volume_weight: 20
  momentum_weight: 15
  risk_weight: 15
  relative_strength_weight: 10
  reason_confidence_step: 0.04
  minimum_confidence: 0.50
  maximum_confidence: 0.95
report:
  output_dir: reports/daily
  history_csv: reports/history.csv
""",
        encoding="utf-8",
    )

    with pytest.raises(SettingsError):
        SettingsLoader(path).load()
