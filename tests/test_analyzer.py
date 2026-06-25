"""Tests for explainable indicator analysis."""

from __future__ import annotations

import pandas as pd

from stock_pilot.analyzer import Analyzer
from stock_pilot.models import (
    AnalyzerSettings,
    IndicatorCalculationResult,
    IndicatorResult,
    Position,
)


def _settings() -> AnalyzerSettings:
    return AnalyzerSettings(
        trend_short_ma_period=5,
        trend_mid_ma_period=20,
        trend_long_ma_period=60,
        momentum_rsi_lower=55,
        momentum_rsi_upper=75,
        volume_breakout_ratio=1.3,
        risk_rsi_high=80,
        risk_atr_pct_high=0.08,
        support_resistance_period=20,
    )


def test_analyzer_detects_bullish_strong_low_risk_state() -> None:
    """Analyzer should classify a strong bullish setup from indicators."""
    frame = pd.DataFrame(
        {
            "close": [11.0, 12.0],
            "ma20": [10.0, 10.5],
            "ma60": [9.0, 9.5],
            "macd": [0.2, 0.4],
            "macd_signal": [0.1, 0.2],
            "macd_histogram": [0.1, 0.2],
            "rsi14": [60.0, 65.0],
            "atr14": [0.5, 0.6],
            "volume_ratio": [1.1, 1.5],
            "highest20": [12.2, 12.5],
            "lowest20": [8.5, 8.8],
        }
    )

    result = Analyzer(_settings()).analyze(
        IndicatorResult(code="002436", name="兴森科技", frame=frame)
    )

    assert result.trend == "Bullish"
    assert result.momentum == "Strong"
    assert result.risk == "Low"
    assert result.support == 10.8
    assert result.primary_support == 10.8
    assert result.secondary_support == 10.5
    assert result.resistance == 12.5
    assert "Close above MA20" in result.reasons
    assert "Volume breakout" in result.reasons


def test_analyzer_detects_bearish_weak_high_risk_state() -> None:
    """Analyzer should classify bearish trend and high risk when signals align."""
    frame = pd.DataFrame(
        {
            "close": [10.0, 9.0],
            "ma20": [10.5, 10.2],
            "ma60": [11.0, 10.8],
            "macd": [-0.2, -0.4],
            "macd_signal": [-0.1, -0.2],
            "macd_histogram": [-0.1, -0.2],
            "rsi14": [78.0, 82.0],
            "atr14": [0.7, 0.9],
            "volume_ratio": [1.0, 0.8],
            "highest20": [12.0, 11.5],
            "lowest20": [8.8, 8.6],
        }
    )

    result = Analyzer(_settings()).analyze(
        IndicatorResult(code="002156", name="通富微电", frame=frame)
    )

    assert result.trend == "Bearish"
    assert result.momentum == "Weak"
    assert result.risk == "High"
    assert "Close below MA20" in result.reasons
    assert "RSI risk threshold exceeded" in result.reasons


def test_analyze_all_preserves_indicator_failures() -> None:
    """Analyzer should pass upstream indicator errors through as analysis failures."""
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    results = (
        IndicatorCalculationResult(
            position=position,
            indicators=None,
            error="indicator failed",
        ),
    )

    analyzed = Analyzer(_settings()).analyze_all(results)

    assert analyzed[0].position == position
    assert analyzed[0].analysis is None
    assert analyzed[0].error == "indicator failed"
