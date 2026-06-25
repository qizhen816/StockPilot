"""Explainable analysis derived from indicator results."""

from __future__ import annotations

import logging
from math import isnan

import pandas as pd

from stock_pilot.models import (
    AnalysisCalculationResult,
    AnalysisResult,
    AnalyzerSettings,
    IndicatorCalculationResult,
    IndicatorResult,
)

logger = logging.getLogger(__name__)


class Analyzer:
    """Analyze indicator results without scoring or generating suggestions."""

    def __init__(self, settings: AnalyzerSettings) -> None:
        """Create an analyzer with immutable rule settings."""
        self._settings = settings

    def analyze(
        self, indicators: IndicatorResult, sector: str = "未分类"
    ) -> AnalysisResult:
        """Analyze one stock's latest indicator state."""
        frame = indicators.frame
        if frame.empty:
            raise ValueError(f"Indicator frame for {indicators.code} is empty")

        latest = frame.iloc[-1]
        previous = frame.iloc[-2] if len(frame) >= 2 else None
        reasons: list[str] = []

        trend = self._analyze_trend(latest, previous, reasons)
        momentum = self._analyze_momentum(latest, reasons)
        volume_status, volume_reason = self._analyze_volume(latest)
        reasons.append(volume_reason)
        risk = self._analyze_risk(latest, reasons)
        stock_return = _stock_return(latest, previous)
        supports = self._support_levels(latest)
        resistances = self._resistance_levels(latest)

        if supports[0] is not None:
            reasons.append("Primary support from MA20/recent low/ATR stop")
        if resistances[0] is not None:
            reasons.append("Primary resistance from recent high/ATR target")

        return AnalysisResult(
            code=indicators.code,
            name=indicators.name,
            trend=trend,
            momentum=momentum,
            risk=risk,
            support=supports[0],
            resistance=resistances[0],
            reasons=tuple(reasons),
            sector=sector,
            stock_return=stock_return,
            volume_status=volume_status,
            volume_reason=volume_reason,
            primary_support=supports[0],
            secondary_support=supports[1],
            primary_resistance=resistances[0],
            secondary_resistance=resistances[1],
        )

    def analyze_all(
        self, indicator_results: tuple[IndicatorCalculationResult, ...]
    ) -> tuple[AnalysisCalculationResult, ...]:
        """Analyze all successful indicator results without stopping on failures."""
        results: list[AnalysisCalculationResult] = []
        for indicator_result in indicator_results:
            if indicator_result.indicators is None:
                results.append(
                    AnalysisCalculationResult(
                        position=indicator_result.position,
                        analysis=None,
                        error=indicator_result.error,
                    )
                )
                continue

            try:
                results.append(
                    AnalysisCalculationResult(
                        position=indicator_result.position,
                        analysis=self.analyze(
                            indicator_result.indicators,
                            sector=indicator_result.position.sector,
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Failed to analyze indicators for %s",
                    indicator_result.position.code,
                )
                results.append(
                    AnalysisCalculationResult(
                        position=indicator_result.position,
                        analysis=None,
                        error=str(exc),
                    )
                )
        return tuple(results)

    def _analyze_trend(
        self,
        latest: pd.Series,
        previous: pd.Series | None,
        reasons: list[str],
    ) -> str:
        close = _required_number(latest, "close")
        mid_ma_key = f"ma{self._settings.trend_mid_ma_period}"
        long_ma_key = f"ma{self._settings.trend_long_ma_period}"
        mid_ma = _latest_number(latest, mid_ma_key)
        long_ma = _latest_number(latest, long_ma_key)
        previous_mid_ma = _latest_number(previous, mid_ma_key)
        macd_value = _latest_number(latest, "macd")
        macd_signal = _latest_number(latest, "macd_signal")

        bullish_signals = 0
        bearish_signals = 0

        signal_delta = _compare_signal(
            close,
            mid_ma,
            bullish_reason=f"Close above {mid_ma_key.upper()}",
            bearish_reason=f"Close below {mid_ma_key.upper()}",
            reasons=reasons,
        )
        bullish_signals += signal_delta[0]
        bearish_signals += signal_delta[1]

        signal_delta = _compare_signal(
            mid_ma,
            previous_mid_ma,
            bullish_reason=f"{mid_ma_key.upper()} rising",
            bearish_reason=f"{mid_ma_key.upper()} falling",
            reasons=reasons,
        )
        bullish_signals += signal_delta[0]
        bearish_signals += signal_delta[1]

        signal_delta = _compare_signal(
            close,
            long_ma,
            bullish_reason=f"Close above {long_ma_key.upper()}",
            bearish_reason=f"Close below {long_ma_key.upper()}",
            reasons=reasons,
        )
        bullish_signals += signal_delta[0]
        bearish_signals += signal_delta[1]

        signal_delta = _compare_signal(
            macd_value,
            macd_signal,
            bullish_reason="MACD above signal",
            bearish_reason="MACD below signal",
            reasons=reasons,
        )
        bullish_signals += signal_delta[0]
        bearish_signals += signal_delta[1]

        if bullish_signals >= 3:
            return "Bullish"
        if bearish_signals >= 3:
            return "Bearish"
        return "Neutral"

    def _analyze_momentum(self, latest: pd.Series, reasons: list[str]) -> str:
        rsi = _latest_number(latest, "rsi14")
        volume = _latest_number(latest, "volume_ratio")
        histogram = _latest_number(latest, "macd_histogram")

        strong_signals = 0
        weak_signals = 0

        if rsi is not None:
            if (
                self._settings.momentum_rsi_lower
                <= rsi
                <= self._settings.momentum_rsi_upper
            ):
                strong_signals += 1
                reasons.append("RSI in strong momentum range")
            elif rsi < self._settings.momentum_rsi_lower:
                weak_signals += 1
                reasons.append("RSI below momentum range")

        if volume is not None:
            if volume >= self._settings.volume_breakout_ratio:
                strong_signals += 1
                reasons.append("Volume breakout")
            elif volume < 1:
                weak_signals += 1
                reasons.append("Volume below rolling average")

        if histogram is not None:
            if histogram > 0:
                strong_signals += 1
                reasons.append("MACD histogram positive")
            elif histogram < 0:
                weak_signals += 1
                reasons.append("MACD histogram negative")

        if strong_signals >= 2:
            return "Strong"
        if weak_signals >= 2:
            return "Weak"
        return "Medium"

    def _analyze_risk(self, latest: pd.Series, reasons: list[str]) -> str:
        close = _required_number(latest, "close")
        open_price = _latest_number(latest, "open")
        high = _latest_number(latest, "high")
        low = _latest_number(latest, "low")
        rsi = _latest_number(latest, "rsi14")
        atr = _latest_number(latest, "atr14")
        volume_ratio = _latest_number(latest, "volume_ratio")
        recent_low = _latest_number(
            latest, f"lowest{self._settings.support_resistance_period}"
        )
        pct_change = _latest_number(latest, "pct_change")
        risk_signals = 0

        if rsi is not None and rsi >= self._settings.risk_rsi_high:
            risk_signals += 1
            reasons.append("RSI risk threshold exceeded")

        if atr is not None and close > 0:
            atr_pct = atr / close
            if atr_pct >= self._settings.risk_atr_pct_high:
                risk_signals += 1
                reasons.append("ATR volatility threshold exceeded")

        drawdown_risk = (
            pct_change is not None
            and pct_change / 100 <= self._settings.abnormal_drawdown_pct
        )
        shadow_risk = _has_long_upper_shadow(
            open_price=open_price,
            high=high,
            low=low,
            close=close,
            threshold=self._settings.long_upper_shadow_ratio,
        )
        downside_breakout = recent_low is not None and close < recent_low

        if (
            volume_ratio is not None
            and volume_ratio >= self._settings.strong_volume_ratio
            and (drawdown_risk or shadow_risk or downside_breakout)
        ):
            risk_signals += 1
            reasons.append("Abnormal volume risk")

        if drawdown_risk:
            risk_signals += 1
            reasons.append("Abnormal drawdown risk")

        if shadow_risk:
            risk_signals += 1
            reasons.append("Long upper shadow risk")

        if downside_breakout:
            risk_signals += 1
            reasons.append("Downside breakout risk")

        if risk_signals >= 2:
            return "High"
        if risk_signals >= 1:
            return "Medium"
        return "Low"

    def _analyze_volume(self, latest: pd.Series) -> tuple[str, str]:
        volume_ratio = _latest_number(latest, "volume_ratio")
        if volume_ratio is None:
            return "Unknown", "Volume status unavailable"
        if volume_ratio < self._settings.shrink_volume_ratio:
            return (
                "Shrink",
                (
                    f"Today's volume is {volume_ratio:.0%} of rolling average: "
                    "shrink volume"
                ),
            )
        if volume_ratio >= self._settings.breakout_volume_ratio:
            return (
                "Breakout",
                (
                    f"Today's volume is {volume_ratio:.0%} of rolling average: "
                    "breakout volume"
                ),
            )
        if volume_ratio >= self._settings.strong_volume_ratio:
            return (
                "Strong",
                (
                    f"Today's volume is {volume_ratio:.0%} of rolling average: "
                    "strong volume"
                ),
            )
        return (
            "Normal",
            f"Today's volume is {volume_ratio:.0%} of rolling average: normal volume",
        )

    def _support_levels(self, latest: pd.Series) -> tuple[float | None, float | None]:
        close = _required_number(latest, "close")
        ma20 = _latest_number(latest, "ma20")
        atr = _latest_number(latest, "atr14")
        recent_low = _latest_number(
            latest, f"lowest{self._settings.support_resistance_period}"
        )
        candidates = [
            value
            for value in (ma20, recent_low, _atr_stop(close, atr))
            if value is not None and value <= close
        ]
        return _nearest_levels(candidates, reverse=True)

    def _resistance_levels(
        self, latest: pd.Series
    ) -> tuple[float | None, float | None]:
        close = _required_number(latest, "close")
        atr = _latest_number(latest, "atr14")
        recent_high = _latest_number(
            latest, f"highest{self._settings.support_resistance_period}"
        )
        candidates = [
            value
            for value in (recent_high, _atr_target(close, atr))
            if value is not None and value >= close
        ]
        return _nearest_levels(candidates, reverse=False)


def _required_number(row: pd.Series, key: str) -> float:
    value = _latest_number(row, key)
    if value is None:
        raise ValueError(f"Indicator result is missing required value: {key}")
    return value


def _latest_number(row: pd.Series | None, key: str) -> float | None:
    if row is None or key not in row:
        return None
    value = row[key]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if isnan(number):
        return None
    return number


def _compare_signal(
    value: float | None,
    reference: float | None,
    bullish_reason: str,
    bearish_reason: str,
    reasons: list[str],
) -> tuple[int, int]:
    if value is None or reference is None:
        return 0, 0
    if value > reference:
        reasons.append(bullish_reason)
        return 1, 0
    if value < reference:
        reasons.append(bearish_reason)
        return 0, 1
    return 0, 0


def _stock_return(latest: pd.Series, previous: pd.Series | None) -> float | None:
    close = _latest_number(latest, "close")
    previous_close = _latest_number(previous, "close")
    if close is None or previous_close is None or previous_close == 0:
        return None
    return (close - previous_close) / previous_close


def _has_long_upper_shadow(
    open_price: float | None,
    high: float | None,
    low: float | None,
    close: float,
    threshold: float,
) -> bool:
    if open_price is None or high is None or low is None:
        return False
    price_range = high - low
    if price_range <= 0:
        return False
    upper_shadow = high - max(open_price, close)
    return upper_shadow / price_range >= threshold


def _atr_stop(close: float, atr: float | None) -> float | None:
    if atr is None:
        return None
    return close - (2 * atr)


def _atr_target(close: float, atr: float | None) -> float | None:
    if atr is None:
        return None
    return close + (2 * atr)


def _nearest_levels(
    values: list[float],
    reverse: bool,
) -> tuple[float | None, float | None]:
    unique_values = sorted(set(values), reverse=reverse)
    primary = unique_values[0] if unique_values else None
    secondary = unique_values[1] if len(unique_values) > 1 else None
    return primary, secondary
