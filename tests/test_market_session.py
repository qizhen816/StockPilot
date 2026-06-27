"""Tests for market-session-aware analysis data selection."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from stock_pilot.market_session import AnalysisDataSelector
from stock_pilot.models import (
    FetchResult,
    MarketData,
    MarketSessionSettings,
    Position,
)


def test_analysis_data_selector_uses_previous_close_before_cutoff() -> None:
    """Before cutoff, today's partial bar should not enter analysis data."""
    result = _fetch_result()

    selected, snapshot = AnalysisDataSelector(_settings()).select(
        fetch_results=(result,),
        current_time=datetime(2026, 6, 26, 14, 30),
    )

    frame = selected[0].market_data.frame
    assert frame.iloc[-1]["date"].date().isoformat() == "2026-06-25"
    assert snapshot.is_using_previous_close is True
    assert snapshot.advice_horizon == "today"


def test_analysis_data_selector_uses_latest_bar_after_cutoff() -> None:
    """After cutoff, latest daily data should be used for analysis."""
    result = _fetch_result()

    selected, snapshot = AnalysisDataSelector(_settings()).select(
        fetch_results=(result,),
        current_time=datetime(2026, 6, 26, 15, 1),
    )

    frame = selected[0].market_data.frame
    assert frame.iloc[-1]["date"].date().isoformat() == "2026-06-26"
    assert snapshot.is_using_previous_close is False
    assert snapshot.advice_horizon == "tomorrow"


def _settings() -> MarketSessionSettings:
    return MarketSessionSettings(analysis_cutoff_time="15:00")


def _fetch_result() -> FetchResult:
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-24", "2026-06-25", "2026-06-26"]),
            "open": [10.0, 10.5, 11.0],
            "high": [10.8, 11.2, 11.8],
            "low": [9.8, 10.2, 10.8],
            "close": [10.5, 11.0, 11.5],
            "volume": [1000, 1200, 1500],
        }
    )
    return FetchResult(
        position=position,
        market_data=MarketData(code=position.code, name=position.name, frame=frame),
    )
