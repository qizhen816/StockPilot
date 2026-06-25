"""Technical indicator calculations for StockPilot."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from stock_pilot.models import (
    FetchResult,
    IndicatorCalculationResult,
    IndicatorResult,
    IndicatorSettings,
    MarketData,
)

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """Calculate deterministic technical indicators from OHLCV data."""

    def __init__(self, settings: IndicatorSettings) -> None:
        """Create an indicator calculator with immutable settings."""
        self._settings = settings

    def calculate(self, market_data: MarketData) -> IndicatorResult:
        """Calculate all configured v0.2 indicators for one stock."""
        logger.debug(
            "Calculating indicators for %s %s", market_data.code, market_data.name
        )
        frame = _require_columns(
            market_data.frame.copy(),
            required_columns=("close", "high", "low", "volume"),
        )

        for period in self._settings.sma_periods:
            frame[f"ma{period}"] = simple_moving_average(frame["close"], period)

        frame[f"ema{self._settings.ema_short_period}"] = exponential_moving_average(
            frame["close"], self._settings.ema_short_period
        )
        frame[f"ema{self._settings.ema_long_period}"] = exponential_moving_average(
            frame["close"], self._settings.ema_long_period
        )
        frame["macd"], frame["macd_signal"], frame["macd_histogram"] = macd(
            close=frame["close"],
            short_period=self._settings.ema_short_period,
            long_period=self._settings.ema_long_period,
            signal_period=self._settings.macd_signal_period,
        )
        frame[f"rsi{self._settings.rsi_period}"] = relative_strength_index(
            frame["close"], self._settings.rsi_period
        )
        frame[f"atr{self._settings.atr_period}"] = average_true_range(
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            period=self._settings.atr_period,
        )
        frame["volume_ratio"] = volume_ratio(
            frame["volume"], self._settings.volume_ratio_period
        )
        frame[f"highest{self._settings.highest_period}"] = highest_high(
            frame["high"], self._settings.highest_period
        )
        frame[f"lowest{self._settings.lowest_period}"] = lowest_low(
            frame["low"], self._settings.lowest_period
        )

        return IndicatorResult(
            code=market_data.code,
            name=market_data.name,
            frame=frame,
        )

    def calculate_all(
        self, fetch_results: tuple[FetchResult, ...]
    ) -> tuple[IndicatorCalculationResult, ...]:
        """Calculate indicators for successful fetch results."""
        results: list[IndicatorCalculationResult] = []
        for fetch_result in fetch_results:
            if fetch_result.market_data is None:
                results.append(
                    IndicatorCalculationResult(
                        position=fetch_result.position,
                        indicators=None,
                        error=fetch_result.error,
                    )
                )
                continue

            try:
                results.append(
                    IndicatorCalculationResult(
                        position=fetch_result.position,
                        indicators=self.calculate(fetch_result.market_data),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Failed to calculate indicators for %s",
                    fetch_result.position.code,
                )
                results.append(
                    IndicatorCalculationResult(
                        position=fetch_result.position,
                        indicators=None,
                        error=str(exc),
                    )
                )
        return tuple(results)


def simple_moving_average(series: pd.Series, period: int) -> pd.Series:
    """Calculate a simple moving average."""
    _validate_period(period)
    return series.rolling(window=period, min_periods=period).mean()


def exponential_moving_average(series: pd.Series, period: int) -> pd.Series:
    """Calculate an exponential moving average."""
    _validate_period(period)
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def macd(
    close: pd.Series,
    short_period: int,
    long_period: int,
    signal_period: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD line, signal line, and histogram."""
    _validate_period(short_period)
    _validate_period(long_period)
    _validate_period(signal_period)
    if short_period >= long_period:
        raise ValueError("MACD short_period must be less than long_period")

    short_ema = exponential_moving_average(close, short_period)
    long_ema = exponential_moving_average(close, long_period)
    macd_line = short_ema - long_ema
    signal_line = exponential_moving_average(macd_line, signal_period)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def relative_strength_index(close: pd.Series, period: int) -> pd.Series:
    """Calculate RSI using average gains and losses over the configured period."""
    _validate_period(period)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    average_gain = gain.rolling(window=period, min_periods=period).mean()
    average_loss = loss.rolling(window=period, min_periods=period).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))

    no_loss = average_loss == 0
    has_gain = average_gain > 0
    no_movement = (average_gain == 0) & no_loss
    rsi = rsi.mask(no_loss & has_gain, 100)
    rsi = rsi.mask(no_movement, 50)
    return rsi


def average_true_range(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int,
) -> pd.Series:
    """Calculate ATR from high, low, and close prices."""
    _validate_period(period)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window=period, min_periods=period).mean()


def volume_ratio(volume: pd.Series, period: int) -> pd.Series:
    """Calculate volume divided by its rolling average."""
    _validate_period(period)
    average_volume = volume.rolling(window=period, min_periods=period).mean()
    return volume / average_volume.replace(0, np.nan)


def highest_high(high: pd.Series, period: int) -> pd.Series:
    """Calculate the rolling highest high."""
    _validate_period(period)
    return high.rolling(window=period, min_periods=period).max()


def lowest_low(low: pd.Series, period: int) -> pd.Series:
    """Calculate the rolling lowest low."""
    _validate_period(period)
    return low.rolling(window=period, min_periods=period).min()


def _validate_period(period: int) -> None:
    if period <= 0:
        raise ValueError("Indicator period must be greater than zero")


def _require_columns(
    frame: pd.DataFrame, required_columns: tuple[str, ...]
) -> pd.DataFrame:
    missing_columns = [
        column for column in required_columns if column not in frame.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Market data frame is missing required columns: {missing}")
    return frame
