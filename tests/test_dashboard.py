"""Tests for dashboard table builders."""

from __future__ import annotations

from dashboard import (
    analysis_frame,
    decision_frame,
    portfolio_analysis_frame,
    portfolio_decision_frame,
    portfolio_valuation_frame,
    replacement_frame,
    scanner_frame,
    score_frame,
)
from tests.test_reporter import _payload


def test_dashboard_frames_are_built_from_payload() -> None:
    """Dashboard helpers should convert payload data into tabular frames."""
    payload = _payload()

    assert portfolio_valuation_frame(payload).iloc[0]["名称"] == "兴森科技"
    assert portfolio_analysis_frame(payload).iloc[0]["项目"] == "最大持仓集中度"
    assert portfolio_decision_frame(payload).iloc[0]["动作"] == "Strong Hold"
    assert replacement_frame(payload).empty
    assert score_frame(payload).iloc[0]["分数"] == 95
    assert decision_frame(payload).iloc[0]["行动"] == "Strong Hold"
    assert scanner_frame(payload).iloc[0]["排名"] == 1
    assert analysis_frame(payload).iloc[0]["趋势"] == "Bullish"
