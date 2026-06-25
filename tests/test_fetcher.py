"""Tests for market data fetcher retry and fallback behavior."""

from __future__ import annotations

import pandas as pd

from stock_pilot import fetcher
from stock_pilot.fetcher import MarketDataFetcher
from stock_pilot.models import FetcherSettings, Position


def test_market_data_fetcher_falls_back_to_tencent(monkeypatch) -> None:
    """MarketDataFetcher should use fallback source when Eastmoney fails."""
    calls: list[str] = []

    def fake_fetch_from_source(
        source: str,
        code: str,
        start_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        calls.append(source)
        if source == "eastmoney":
            raise RuntimeError("eastmoney down")
        return pd.DataFrame(
            {
                "date": ["2026-06-24", "2026-06-25"],
                "open": [10.0, 11.0],
                "close": [11.0, 12.0],
                "high": [11.5, 12.5],
                "low": [9.5, 10.5],
                "amount": [1000.0, 1200.0],
            }
        )

    monkeypatch.setattr(fetcher, "_fetch_from_source", fake_fetch_from_source)

    result = MarketDataFetcher(
        FetcherSettings(
            start_date="20200101",
            adjust="qfq",
            retry_attempts=1,
            fallback_sources=("eastmoney", "tencent"),
        )
    ).fetch(Position(code="002436", name="兴森科技", cost=10.0, shares=100))

    assert calls == ["eastmoney", "tencent"]
    assert result.frame.iloc[-1]["close"] == 12.0
    assert "volume" in result.frame.columns


def test_market_data_fetcher_retries_same_source(monkeypatch) -> None:
    """MarketDataFetcher should retry a failing source before moving on."""
    calls: list[str] = []

    def fake_fetch_from_source(
        source: str,
        code: str,
        start_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        calls.append(source)
        if len(calls) == 1:
            raise RuntimeError("temporary failure")
        return pd.DataFrame(
            {
                "日期": ["2026-06-25"],
                "开盘": [10.0],
                "收盘": [11.0],
                "最高": [11.5],
                "最低": [9.5],
                "成交量": [1000.0],
            }
        )

    monkeypatch.setattr(fetcher, "_fetch_from_source", fake_fetch_from_source)

    MarketDataFetcher(
        FetcherSettings(
            start_date="20200101",
            adjust="qfq",
            retry_attempts=2,
            fallback_sources=("eastmoney",),
        )
    ).fetch(Position(code="002436", name="兴森科技", cost=10.0, shares=100))

    assert calls == ["eastmoney", "eastmoney"]
