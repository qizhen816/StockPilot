"""Tests for report notification delivery."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from test_reporter import _payload

from stock_pilot.models import (
    EmailSettings,
    NotificationSettings,
    TelegramSettings,
)
from stock_pilot.notification import NotificationDispatcher


def test_notification_dispatcher_returns_disabled_result(tmp_path: Path) -> None:
    """Disabled notifications should not call any channel sender."""
    calls: list[str] = []
    path = _markdown_path(tmp_path)

    result = NotificationDispatcher(
        _settings(enabled=False),
        telegram_sender=lambda token, chat_id, text: calls.append("telegram"),
        email_sender=lambda message, settings: calls.append("email"),
    ).dispatch(_payload(), path)

    assert calls == []
    assert result.results[0].channel == "notification"
    assert result.results[0].sent is False
    assert result.results[0].message == "notification is disabled"


def test_notification_dispatcher_supports_dry_run(tmp_path: Path) -> None:
    """Dry-run notifications should report intended channels without sending."""
    calls: list[str] = []
    path = _markdown_path(tmp_path)

    result = NotificationDispatcher(
        _settings(enabled=True, dry_run=True, telegram=True, email=True),
        telegram_sender=lambda token, chat_id, text: calls.append("telegram"),
        email_sender=lambda message, settings: calls.append("email"),
    ).dispatch(_payload(), path)

    assert calls == []
    assert [item.channel for item in result.results] == ["telegram", "email"]
    assert all(item.sent is False for item in result.results)
    assert all(
        item.message.startswith("dry-run: would send ") for item in result.results
    )


def test_notification_dispatcher_sends_telegram(
    tmp_path: Path, monkeypatch
) -> None:
    """Telegram delivery should use configured environment variables."""
    sent_messages: list[tuple[str, str, str]] = []
    path = _markdown_path(tmp_path)
    monkeypatch.setenv("STOCKPILOT_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("STOCKPILOT_TELEGRAM_CHAT_ID", "chat-id")

    result = NotificationDispatcher(
        _settings(enabled=True, dry_run=False, telegram=True),
        telegram_sender=lambda token, chat_id, text: sent_messages.append(
            (token, chat_id, text)
        ),
    ).dispatch(_payload(), path)

    assert result.results[0].sent is True
    assert sent_messages[0][0] == "token"
    assert sent_messages[0][1] == "chat-id"
    assert "StockPilot 日报 2026-06-25" in sent_messages[0][2]


def test_notification_dispatcher_sends_email(tmp_path: Path, monkeypatch) -> None:
    """Email delivery should build a Markdown email from the generated report."""
    sent_messages: list[EmailMessage] = []
    path = _markdown_path(tmp_path)
    monkeypatch.setenv("STOCKPILOT_EMAIL_USERNAME", "user")
    monkeypatch.setenv("STOCKPILOT_EMAIL_PASSWORD", "password")
    monkeypatch.setenv("STOCKPILOT_EMAIL_SENDER", "stockpilot@example.com")

    result = NotificationDispatcher(
        _settings(
            enabled=True,
            dry_run=False,
            email=True,
            recipients=("owner@example.com",),
        ),
        email_sender=lambda message, settings: sent_messages.append(message),
    ).dispatch(_payload(), path)

    assert result.results[0].sent is True
    assert sent_messages[0]["Subject"] == "StockPilot 日报 2026-06-25"
    assert sent_messages[0]["To"] == "owner@example.com"
    assert "StockPilot 日报" in sent_messages[0].get_content()


def _markdown_path(tmp_path: Path) -> Path:
    path = tmp_path / "2026-06-25.md"
    path.write_text("# StockPilot 日报\n", encoding="utf-8")
    return path


def _settings(
    *,
    enabled: bool,
    dry_run: bool = True,
    telegram: bool = False,
    email: bool = False,
    recipients: tuple[str, ...] = (),
) -> NotificationSettings:
    return NotificationSettings(
        enabled=enabled,
        dry_run=dry_run,
        telegram=TelegramSettings(
            enabled=telegram,
            bot_token_env="STOCKPILOT_TELEGRAM_BOT_TOKEN",
            chat_id_env="STOCKPILOT_TELEGRAM_CHAT_ID",
        ),
        email=EmailSettings(
            enabled=email,
            smtp_host="smtp.example.com",
            smtp_port=587,
            username_env="STOCKPILOT_EMAIL_USERNAME",
            password_env="STOCKPILOT_EMAIL_PASSWORD",
            sender_env="STOCKPILOT_EMAIL_SENDER",
            recipients=recipients,
            use_tls=True,
        ),
    )
