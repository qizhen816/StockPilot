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
  minimum_confidence: 0.50
  maximum_confidence: 0.95
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
    assert settings.report.output_dir == Path("reports/daily")
    assert settings.report.history_csv == Path("reports/history.csv")
    assert settings.summary.watchlist_limit == 3
    assert settings.summary.high_risk_levels == ("High",)
    assert settings.scanner.candidate_limit == 5
    assert settings.scanner.min_score == 70
    assert settings.scanner.allowed_risk_levels == ("Low", "Medium")


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
