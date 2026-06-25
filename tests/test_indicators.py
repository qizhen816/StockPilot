"""Tests for technical indicator calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stock_pilot.indicators import (
    IndicatorCalculator,
    average_true_range,
    exponential_moving_average,
    highest_high,
    lowest_low,
    macd,
    relative_strength_index,
    simple_moving_average,
    volume_ratio,
)
from stock_pilot.models import IndicatorSettings, MarketData


def test_simple_moving_average_calculates_expected_values() -> None:
    """SMA should average the latest configured window."""
    series = pd.Series([1, 2, 3, 4, 5], dtype=float)

    result = simple_moving_average(series, period=3)
    expected = pd.Series([np.nan, np.nan, 2.0, 3.0, 4.0])

    pd.testing.assert_series_equal(result, expected)


def test_exponential_moving_average_matches_pandas_formula() -> None:
    """EMA should delegate to pandas ewm with deterministic parameters."""
    series = pd.Series([10, 11, 12, 13, 14], dtype=float)

    result = exponential_moving_average(series, period=3)
    expected = series.ewm(span=3, adjust=False, min_periods=3).mean()

    pd.testing.assert_series_equal(result, expected)


def test_macd_calculates_line_signal_and_histogram() -> None:
    """MACD histogram should equal MACD line minus signal line."""
    close = pd.Series(np.linspace(10, 30, 40), dtype=float)

    macd_line, signal_line, histogram = macd(close, 12, 26, 9)

    pd.testing.assert_series_equal(histogram, macd_line - signal_line)


def test_macd_rejects_invalid_period_order() -> None:
    """MACD should require short period to be less than long period."""
    close = pd.Series([1, 2, 3], dtype=float)

    with pytest.raises(ValueError):
        macd(close, 26, 12, 9)


def test_relative_strength_index_handles_all_gain_window() -> None:
    """RSI should be 100 when the full window has gains and no losses."""
    close = pd.Series([1, 2, 3, 4, 5], dtype=float)

    result = relative_strength_index(close, period=3)

    assert result.iloc[-1] == 100


def test_average_true_range_calculates_expected_values() -> None:
    """ATR should average true range over the configured period."""
    high = pd.Series([11, 13, 14, 16], dtype=float)
    low = pd.Series([9, 10, 12, 13], dtype=float)
    close = pd.Series([10, 12, 13, 15], dtype=float)

    result = average_true_range(high, low, close, period=2)
    expected = pd.Series([np.nan, 2.5, 2.5, 2.5])

    pd.testing.assert_series_equal(result, expected)


def test_volume_ratio_calculates_volume_over_average() -> None:
    """Volume ratio should divide volume by its rolling average."""
    volume = pd.Series([100, 200, 300], dtype=float)

    result = volume_ratio(volume, period=2)
    expected = pd.Series([np.nan, 200 / 150, 300 / 250])

    pd.testing.assert_series_equal(result, expected)


def test_highest_and_lowest_calculate_rolling_extremes() -> None:
    """Rolling extremes should use only the latest configured window."""
    high = pd.Series([10, 12, 11, 15], dtype=float)
    low = pd.Series([8, 9, 7, 10], dtype=float)

    expected_high = pd.Series([np.nan, np.nan, 12.0, 15.0])
    expected_low = pd.Series([np.nan, np.nan, 7.0, 7.0])

    pd.testing.assert_series_equal(highest_high(high, period=3), expected_high)
    pd.testing.assert_series_equal(lowest_low(low, period=3), expected_low)


def test_indicator_calculator_adds_configured_columns() -> None:
    """IndicatorCalculator should return an IndicatorResult with all v0.2 columns."""
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=80),
            "open": np.linspace(10, 20, 80),
            "high": np.linspace(11, 21, 80),
            "low": np.linspace(9, 19, 80),
            "close": np.linspace(10, 20, 80),
            "volume": np.linspace(1000, 2000, 80),
        }
    )
    settings = IndicatorSettings(
        sma_periods=(5, 10, 20, 60),
        ema_short_period=12,
        ema_long_period=26,
        macd_signal_period=9,
        rsi_period=14,
        atr_period=14,
        volume_ratio_period=20,
        highest_period=20,
        lowest_period=20,
    )

    result = IndicatorCalculator(settings).calculate(
        MarketData(code="002436", name="兴森科技", frame=frame)
    )

    expected_columns = {
        "ma5",
        "ma10",
        "ma20",
        "ma60",
        "ema12",
        "ema26",
        "macd",
        "macd_signal",
        "macd_histogram",
        "rsi14",
        "atr14",
        "volume_ratio",
        "highest20",
        "lowest20",
    }
    assert expected_columns.issubset(result.frame.columns)
    assert result.code == "002436"
    assert result.name == "兴森科技"
