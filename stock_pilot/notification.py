"""Notification delivery for generated StockPilot reports."""

from __future__ import annotations

import json
import logging
import os
import smtplib
import urllib.request
from collections.abc import Callable
from email.message import EmailMessage
from pathlib import Path

from stock_pilot.models import (
    EmailSettings,
    NotificationDispatchResult,
    NotificationResult,
    NotificationSettings,
)
from stock_pilot.reporter import DailyReportPayload

logger = logging.getLogger(__name__)

TelegramSender = Callable[[str, str, str], None]
EmailSender = Callable[[EmailMessage, EmailSettings], None]


class NotificationDispatcher:
    """Dispatch finished reports to configured notification channels."""

    def __init__(
        self,
        settings: NotificationSettings,
        telegram_sender: TelegramSender | None = None,
        email_sender: EmailSender | None = None,
    ) -> None:
        """Create a dispatcher with optional sender overrides for tests."""
        self._settings = settings
        self._telegram_sender = telegram_sender or _send_telegram_message
        self._email_sender = email_sender or _send_email_message

    def dispatch(
        self, payload: DailyReportPayload, markdown_path: Path
    ) -> NotificationDispatchResult:
        """Send the generated daily report through enabled notification channels."""
        if not self._settings.enabled:
            return NotificationDispatchResult(
                results=(
                    NotificationResult(
                        channel="notification",
                        sent=False,
                        message="notification is disabled",
                    ),
                )
            )

        results: list[NotificationResult] = []
        if self._settings.telegram.enabled:
            results.append(self._dispatch_telegram(payload, markdown_path))
        if self._settings.email.enabled:
            results.append(self._dispatch_email(payload, markdown_path))

        if not results:
            results.append(
                NotificationResult(
                    channel="notification",
                    sent=False,
                    message="no notification channel is enabled",
                )
            )

        return NotificationDispatchResult(results=tuple(results))

    def _dispatch_telegram(
        self, payload: DailyReportPayload, markdown_path: Path
    ) -> NotificationResult:
        if self._settings.dry_run:
            return NotificationResult(
                channel="telegram",
                sent=False,
                message=f"dry-run: would send {markdown_path}",
            )

        token = os.environ.get(self._settings.telegram.bot_token_env, "").strip()
        chat_id = os.environ.get(self._settings.telegram.chat_id_env, "").strip()
        if not token or not chat_id:
            return NotificationResult(
                channel="telegram",
                sent=False,
                message="missing Telegram token or chat id environment variable",
            )

        try:
            self._telegram_sender(token, chat_id, _build_telegram_text(payload))
        except Exception as exc:  # pragma: no cover - exercised through fake senders.
            logger.exception("Telegram notification failed")
            return NotificationResult(
                channel="telegram",
                sent=False,
                message=f"failed: {exc}",
            )

        return NotificationResult(
            channel="telegram",
            sent=True,
            message="sent",
        )

    def _dispatch_email(
        self, payload: DailyReportPayload, markdown_path: Path
    ) -> NotificationResult:
        if self._settings.dry_run:
            return NotificationResult(
                channel="email",
                sent=False,
                message=f"dry-run: would send {markdown_path}",
            )

        if not self._settings.email.recipients:
            return NotificationResult(
                channel="email",
                sent=False,
                message="email recipients are not configured",
            )

        username = os.environ.get(self._settings.email.username_env, "").strip()
        password = os.environ.get(self._settings.email.password_env, "").strip()
        sender = os.environ.get(self._settings.email.sender_env, "").strip()
        if not username or not password or not sender:
            return NotificationResult(
                channel="email",
                sent=False,
                message="missing email account environment variable",
            )

        try:
            message = _build_email_message(
                payload=payload,
                markdown_path=markdown_path,
                sender=sender,
                recipients=self._settings.email.recipients,
            )
            self._email_sender(message, self._settings.email)
        except Exception as exc:  # pragma: no cover - exercised through fake senders.
            logger.exception("Email notification failed")
            return NotificationResult(
                channel="email",
                sent=False,
                message=f"failed: {exc}",
            )

        return NotificationResult(
            channel="email",
            sent=True,
            message="sent",
        )


def _send_telegram_message(token: str, chat_id: str, text: str) -> None:
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        url=f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def _send_email_message(message: EmailMessage, settings: EmailSettings) -> None:
    username = os.environ[settings.username_env]
    password = os.environ[settings.password_env]
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.use_tls:
            server.starttls()
        server.login(username, password)
        server.send_message(message)


def _build_telegram_text(payload: DailyReportPayload) -> str:
    watchlist = "；".join(payload.summary.tomorrow_watchlist) or "-"
    return "\n".join(
        [
            f"StockPilot 日报 {payload.report_date.isoformat()}",
            f"结论：{payload.summary.conclusion}",
            f"今日风险：{payload.summary.today_risk}",
            f"明日观察：{watchlist}",
        ]
    )


def _build_email_message(
    payload: DailyReportPayload,
    markdown_path: Path,
    sender: str,
    recipients: tuple[str, ...],
) -> EmailMessage:
    content = markdown_path.read_text(encoding="utf-8")
    message = EmailMessage()
    message["Subject"] = f"StockPilot 日报 {payload.report_date.isoformat()}"
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(content)
    return message
