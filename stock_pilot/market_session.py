"""Market-session-aware selection of analysis data snapshots."""

from __future__ import annotations

from datetime import datetime, time

import pandas as pd

from stock_pilot.models import (
    AnalysisDataSnapshot,
    FetchResult,
    MarketData,
    MarketSessionSettings,
)


class AnalysisDataSelector:
    """Select complete daily bars for indicator and analysis calculations."""

    def __init__(self, settings: MarketSessionSettings) -> None:
        """Create a selector with a configurable analysis cutoff time."""
        self._cutoff = _parse_time(settings.analysis_cutoff_time)

    def select(
        self,
        fetch_results: tuple[FetchResult, ...],
        current_time: datetime,
    ) -> tuple[tuple[FetchResult, ...], AnalysisDataSnapshot]:
        """Return fetch results suitable for analysis and snapshot metadata."""
        if current_time.time() >= self._cutoff:
            return (
                fetch_results,
                AnalysisDataSnapshot(
                    data_date=_latest_data_date(fetch_results),
                    is_using_previous_close=False,
                    advice_horizon="tomorrow",
                    reason="Market close cutoff has passed; using latest daily bar",
                ),
            )

        selected_results = tuple(
            _drop_current_day_bar(result, current_time.date())
            for result in fetch_results
        )
        return (
            selected_results,
            AnalysisDataSnapshot(
                data_date=_latest_data_date(selected_results),
                is_using_previous_close=True,
                advice_horizon="today",
                reason="Before market close cutoff; using previous completed close",
            ),
        )


def _drop_current_day_bar(result: FetchResult, current_date: object) -> FetchResult:
    if result.market_data is None:
        return result

    frame = result.market_data.frame
    if "date" not in frame.columns or frame.empty:
        return result

    dates = pd.to_datetime(frame["date"]).dt.date
    if dates.iloc[-1] != current_date:
        return result

    selected = frame.loc[dates < current_date].copy().reset_index(drop=True)
    if selected.empty:
        return result

    return FetchResult(
        position=result.position,
        market_data=MarketData(
            code=result.market_data.code,
            name=result.market_data.name,
            frame=selected,
        ),
        error=result.error,
    )


def _latest_data_date(fetch_results: tuple[FetchResult, ...]) -> str | None:
    dates: list[pd.Timestamp] = []
    for result in fetch_results:
        if result.market_data is None:
            continue
        frame = result.market_data.frame
        if frame.empty or "date" not in frame.columns:
            continue
        dates.append(pd.to_datetime(frame.iloc[-1]["date"]))
    if not dates:
        return None
    return max(dates).date().isoformat()


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))
