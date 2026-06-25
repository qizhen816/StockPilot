"""Logging configuration for StockPilot."""

from __future__ import annotations

import logging


def configure_logging(level: str) -> None:
    """Configure application logging with a consistent format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

