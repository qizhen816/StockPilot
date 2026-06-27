"""Settings loading for StockPilot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from stock_pilot.models import (
    AnalyzerSettings,
    AppSettings,
    DecisionSettings,
    EmailSettings,
    FetcherSettings,
    IndicatorSettings,
    MarketSessionSettings,
    NotificationSettings,
    PortfolioDecisionSettings,
    ReportSettings,
    ScannerSettings,
    ScorerSettings,
    SummarySettings,
    TelegramSettings,
)

logger = logging.getLogger(__name__)


class SettingsError(ValueError):
    """Raised when application settings are invalid."""


class SettingsLoader:
    """Load application settings from a YAML file."""

    def __init__(self, path: Path) -> None:
        """Create a settings loader for the given YAML path."""
        self._path = path

    def load(self) -> AppSettings:
        """Load and validate application settings."""
        logger.debug("Loading settings from %s", self._path)
        raw_settings = self._load_yaml()

        fetcher_settings = raw_settings.get("fetcher")
        if not isinstance(fetcher_settings, dict):
            raise SettingsError("settings.yaml must contain a 'fetcher' mapping")

        start_date = _required_string(fetcher_settings, "start_date", "fetcher")
        adjust = _required_string(fetcher_settings, "adjust", "fetcher")
        cache_dir = _optional_path(fetcher_settings.get("cache_dir"))
        indicator_settings = raw_settings.get("indicators")
        if not isinstance(indicator_settings, dict):
            raise SettingsError("settings.yaml must contain an 'indicators' mapping")

        analyzer_settings = raw_settings.get("analyzer")
        if not isinstance(analyzer_settings, dict):
            raise SettingsError("settings.yaml must contain an 'analyzer' mapping")

        scorer_settings = raw_settings.get("scorer")
        if not isinstance(scorer_settings, dict):
            raise SettingsError("settings.yaml must contain a 'scorer' mapping")

        report_settings = raw_settings.get("report")
        if not isinstance(report_settings, dict):
            raise SettingsError("settings.yaml must contain a 'report' mapping")

        summary_settings = raw_settings.get("summary")
        if not isinstance(summary_settings, dict):
            raise SettingsError("settings.yaml must contain a 'summary' mapping")

        scanner_settings = raw_settings.get("scanner")
        if not isinstance(scanner_settings, dict):
            raise SettingsError("settings.yaml must contain a 'scanner' mapping")

        decision_settings = raw_settings.get("decision", {})
        if not isinstance(decision_settings, dict):
            raise SettingsError("settings.yaml decision must be a mapping")

        portfolio_decision_settings = raw_settings.get("portfolio_decision")
        if not isinstance(portfolio_decision_settings, dict):
            raise SettingsError(
                "settings.yaml must contain a 'portfolio_decision' mapping"
            )

        market_session_settings = raw_settings.get("market_session")
        if not isinstance(market_session_settings, dict):
            raise SettingsError("settings.yaml must contain a 'market_session' mapping")

        notification_settings = raw_settings.get("notification")
        if not isinstance(notification_settings, dict):
            raise SettingsError("settings.yaml must contain a 'notification' mapping")

        log_level = str(raw_settings.get("log_level", "INFO")).upper()

        return AppSettings(
            fetcher=FetcherSettings(
                start_date=start_date,
                adjust=adjust,
                retry_attempts=_required_positive_int(
                    fetcher_settings, "retry_attempts", "fetcher"
                ),
                fallback_sources=_required_string_tuple(
                    fetcher_settings, "fallback_sources", "fetcher"
                ),
                cache_dir=cache_dir,
            ),
            indicators=IndicatorSettings(
                sma_periods=_required_int_tuple(
                    indicator_settings, "sma_periods", "indicators"
                ),
                ema_short_period=_required_positive_int(
                    indicator_settings, "ema_short_period", "indicators"
                ),
                ema_long_period=_required_positive_int(
                    indicator_settings, "ema_long_period", "indicators"
                ),
                macd_signal_period=_required_positive_int(
                    indicator_settings, "macd_signal_period", "indicators"
                ),
                rsi_period=_required_positive_int(
                    indicator_settings, "rsi_period", "indicators"
                ),
                atr_period=_required_positive_int(
                    indicator_settings, "atr_period", "indicators"
                ),
                volume_ratio_period=_required_positive_int(
                    indicator_settings, "volume_ratio_period", "indicators"
                ),
                highest_period=_required_positive_int(
                    indicator_settings, "highest_period", "indicators"
                ),
                lowest_period=_required_positive_int(
                    indicator_settings, "lowest_period", "indicators"
                ),
            ),
            analyzer=AnalyzerSettings(
                trend_short_ma_period=_required_positive_int(
                    analyzer_settings, "trend_short_ma_period", "analyzer"
                ),
                trend_mid_ma_period=_required_positive_int(
                    analyzer_settings, "trend_mid_ma_period", "analyzer"
                ),
                trend_long_ma_period=_required_positive_int(
                    analyzer_settings, "trend_long_ma_period", "analyzer"
                ),
                momentum_rsi_lower=_required_number(
                    analyzer_settings, "momentum_rsi_lower", "analyzer"
                ),
                momentum_rsi_upper=_required_number(
                    analyzer_settings, "momentum_rsi_upper", "analyzer"
                ),
                volume_breakout_ratio=_required_number(
                    analyzer_settings, "volume_breakout_ratio", "analyzer"
                ),
                risk_rsi_high=_required_number(
                    analyzer_settings, "risk_rsi_high", "analyzer"
                ),
                risk_atr_pct_high=_required_number(
                    analyzer_settings, "risk_atr_pct_high", "analyzer"
                ),
                support_resistance_period=_required_positive_int(
                    analyzer_settings, "support_resistance_period", "analyzer"
                ),
                shrink_volume_ratio=_optional_number(
                    analyzer_settings, "shrink_volume_ratio", 0.8
                ),
                strong_volume_ratio=_optional_number(
                    analyzer_settings, "strong_volume_ratio", 1.2
                ),
                breakout_volume_ratio=_optional_number(
                    analyzer_settings, "breakout_volume_ratio", 1.8
                ),
                abnormal_drawdown_pct=_optional_number(
                    analyzer_settings, "abnormal_drawdown_pct", -0.05
                ),
                long_upper_shadow_ratio=_optional_number(
                    analyzer_settings, "long_upper_shadow_ratio", 0.45
                ),
            ),
            scorer=_build_scorer_settings(scorer_settings),
            report=ReportSettings(
                output_dir=_required_path(report_settings, "output_dir", "report"),
                history_csv=_required_path(report_settings, "history_csv", "report"),
            ),
            summary=SummarySettings(
                watchlist_limit=_required_positive_int(
                    summary_settings, "watchlist_limit", "summary"
                ),
                high_risk_levels=_required_string_tuple(
                    summary_settings, "high_risk_levels", "summary"
                ),
            ),
            scanner=ScannerSettings(
                candidate_limit=_required_positive_int(
                    scanner_settings, "candidate_limit", "scanner"
                ),
                min_score=_required_positive_int(
                    scanner_settings, "min_score", "scanner"
                ),
                allowed_risk_levels=_required_string_tuple(
                    scanner_settings, "allowed_risk_levels", "scanner"
                ),
                required_trend=_optional_string(
                    scanner_settings, "required_trend", "Bullish"
                ),
                min_relative_strength_score=_optional_positive_int(
                    scanner_settings, "min_relative_strength_score", 60
                ),
                min_volume_statuses=_optional_string_tuple(
                    scanner_settings,
                    "min_volume_statuses",
                    ("Normal", "Strong", "Breakout"),
                ),
            ),
            decision=DecisionSettings(
                high_score_threshold=_optional_positive_int(
                    decision_settings, "high_score_threshold", 80
                ),
                low_score_threshold=_optional_positive_int(
                    decision_settings, "low_score_threshold", 55
                ),
                high_confidence_threshold=_optional_number(
                    decision_settings, "high_confidence_threshold", 0.75
                ),
            ),
            portfolio_decision=PortfolioDecisionSettings(
                strong_hold_score_threshold=_required_positive_int(
                    portfolio_decision_settings,
                    "strong_hold_score_threshold",
                    "portfolio_decision",
                ),
                hold_score_threshold=_required_positive_int(
                    portfolio_decision_settings,
                    "hold_score_threshold",
                    "portfolio_decision",
                ),
                reduce_score_threshold=_required_positive_int(
                    portfolio_decision_settings,
                    "reduce_score_threshold",
                    "portfolio_decision",
                ),
                exit_score_threshold=_required_positive_int(
                    portfolio_decision_settings,
                    "exit_score_threshold",
                    "portfolio_decision",
                ),
                replace_score_threshold=_required_positive_int(
                    portfolio_decision_settings,
                    "replace_score_threshold",
                    "portfolio_decision",
                ),
                replacement_min_score_gap=_required_positive_int(
                    portfolio_decision_settings,
                    "replacement_min_score_gap",
                    "portfolio_decision",
                ),
                minimum_confidence=_required_number(
                    portfolio_decision_settings,
                    "minimum_confidence",
                    "portfolio_decision",
                ),
                maximum_confidence=_required_number(
                    portfolio_decision_settings,
                    "maximum_confidence",
                    "portfolio_decision",
                ),
            ),
            market_session=MarketSessionSettings(
                analysis_cutoff_time=_required_time_string(
                    market_session_settings,
                    "analysis_cutoff_time",
                    "market_session",
                ),
            ),
            notification=_build_notification_settings(notification_settings),
            log_level=log_level,
        )

    def _load_yaml(self) -> dict[str, Any]:
        if not self._path.exists():
            raise SettingsError(f"Settings file does not exist: {self._path}")

        with self._path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        if not isinstance(data, dict):
            raise SettingsError("settings.yaml must contain a YAML mapping")

        return data


def _required_string(mapping: dict[str, Any], key: str, section: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SettingsError(f"{section}.{key} must be a non-empty string")
    return value.strip()


def _optional_path(value: Any) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SettingsError("fetcher.cache_dir must be a non-empty string when set")
    return Path(value).expanduser()


def _required_path(mapping: dict[str, Any], key: str, section: str) -> Path:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SettingsError(f"{section}.{key} must be a non-empty string")
    return Path(value).expanduser()


def _required_positive_int(mapping: dict[str, Any], key: str, section: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or value <= 0:
        raise SettingsError(f"{section}.{key} must be a positive integer")
    return value


def _required_int_tuple(
    mapping: dict[str, Any], key: str, section: str
) -> tuple[int, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or not value:
        raise SettingsError(f"{section}.{key} must be a non-empty integer list")

    periods = tuple(value)
    if not all(isinstance(period, int) and period > 0 for period in periods):
        raise SettingsError(f"{section}.{key} must contain positive integers")

    return periods


def _required_string_tuple(
    mapping: dict[str, Any], key: str, section: str
) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or not value:
        raise SettingsError(f"{section}.{key} must be a non-empty string list")

    items = tuple(value)
    if not all(isinstance(item, str) and item.strip() for item in items):
        raise SettingsError(f"{section}.{key} must contain non-empty strings")

    return tuple(item.strip() for item in items)


def _required_number(mapping: dict[str, Any], key: str, section: str) -> float:
    value = mapping.get(key)
    if not isinstance(value, int | float):
        raise SettingsError(f"{section}.{key} must be a number")
    return float(value)


def _required_bool(mapping: dict[str, Any], key: str, section: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise SettingsError(f"{section}.{key} must be a boolean")
    return value


def _required_time_string(mapping: dict[str, Any], key: str, section: str) -> str:
    value = _required_string(mapping, key, section)
    parts = value.split(":")
    if len(parts) != 2:
        raise SettingsError(f"{section}.{key} must use HH:MM format")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as exc:
        raise SettingsError(f"{section}.{key} must use HH:MM format") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise SettingsError(f"{section}.{key} must use HH:MM format")
    return f"{hour:02d}:{minute:02d}"


def _optional_number(mapping: dict[str, Any], key: str, default: float) -> float:
    value = mapping.get(key, default)
    if not isinstance(value, int | float):
        raise SettingsError(f"{key} must be a number")
    return float(value)


def _optional_bool(mapping: dict[str, Any], key: str, default: bool) -> bool:
    value = mapping.get(key, default)
    if not isinstance(value, bool):
        raise SettingsError(f"{key} must be a boolean")
    return value


def _optional_positive_int(mapping: dict[str, Any], key: str, default: int) -> int:
    value = mapping.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise SettingsError(f"{key} must be a positive integer")
    return value


def _optional_string(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise SettingsError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_string_tuple(
    mapping: dict[str, Any], key: str, default: tuple[str, ...]
) -> tuple[str, ...]:
    value = mapping.get(key, list(default))
    if not isinstance(value, list) or not value:
        raise SettingsError(f"{key} must be a non-empty string list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise SettingsError(f"{key} must contain non-empty strings")
    return tuple(item.strip() for item in value)


def _optional_string_list(mapping: dict[str, Any], key: str) -> tuple[str, ...]:
    value = mapping.get(key, [])
    if not isinstance(value, list):
        raise SettingsError(f"{key} must be a string list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise SettingsError(f"{key} must contain non-empty strings")
    return tuple(item.strip() for item in value)


def _build_scorer_settings(raw_settings: dict[str, Any]) -> ScorerSettings:
    settings = ScorerSettings(
        trend_weight=_required_positive_int(raw_settings, "trend_weight", "scorer"),
        volume_weight=_required_positive_int(raw_settings, "volume_weight", "scorer"),
        momentum_weight=_required_positive_int(
            raw_settings, "momentum_weight", "scorer"
        ),
        risk_weight=_required_positive_int(raw_settings, "risk_weight", "scorer"),
        relative_strength_weight=_required_positive_int(
            raw_settings, "relative_strength_weight", "scorer"
        ),
        reason_confidence_step=_required_number(
            raw_settings, "reason_confidence_step", "scorer"
        ),
        minimum_confidence=_required_number(
            raw_settings, "minimum_confidence", "scorer"
        ),
        maximum_confidence=_required_number(
            raw_settings, "maximum_confidence", "scorer"
        ),
        maximum_score=_required_positive_int(raw_settings, "maximum_score", "scorer"),
    )
    total_weight = (
        settings.trend_weight
        + settings.volume_weight
        + settings.momentum_weight
        + settings.risk_weight
        + settings.relative_strength_weight
    )
    if total_weight != 100:
        raise SettingsError("scorer weights must sum to 100")
    return settings


def _build_notification_settings(raw_settings: dict[str, Any]) -> NotificationSettings:
    telegram_settings = raw_settings.get("telegram")
    if not isinstance(telegram_settings, dict):
        raise SettingsError("notification.telegram must be a mapping")

    email_settings = raw_settings.get("email")
    if not isinstance(email_settings, dict):
        raise SettingsError("notification.email must be a mapping")

    return NotificationSettings(
        enabled=_required_bool(raw_settings, "enabled", "notification"),
        dry_run=_required_bool(raw_settings, "dry_run", "notification"),
        telegram=TelegramSettings(
            enabled=_required_bool(
                telegram_settings, "enabled", "notification.telegram"
            ),
            bot_token_env=_required_string(
                telegram_settings, "bot_token_env", "notification.telegram"
            ),
            chat_id_env=_required_string(
                telegram_settings, "chat_id_env", "notification.telegram"
            ),
        ),
        email=EmailSettings(
            enabled=_required_bool(email_settings, "enabled", "notification.email"),
            smtp_host=_required_string(
                email_settings, "smtp_host", "notification.email"
            ),
            smtp_port=_required_positive_int(
                email_settings, "smtp_port", "notification.email"
            ),
            username_env=_required_string(
                email_settings, "username_env", "notification.email"
            ),
            password_env=_required_string(
                email_settings, "password_env", "notification.email"
            ),
            sender_env=_required_string(
                email_settings, "sender_env", "notification.email"
            ),
            recipients=_optional_string_list(email_settings, "recipients"),
            use_tls=_optional_bool(email_settings, "use_tls", True),
        ),
    )
