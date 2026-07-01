"""Tests for dashboard table builders."""

from __future__ import annotations

from dashboard import (
    analysis_frame,
    decision_frame,
    portfolio_analysis_frame,
    portfolio_decision_frame,
    portfolio_valuation_frame,
    position_recommendation_frame,
    replacement_frame,
    scanner_frame,
    score_frame,
)
from tests.test_reporter import _payload


def test_dashboard_frames_are_built_from_payload() -> None:
    """工作台表格构建函数应把报告数据转成中文表格。"""
    payload = _payload()

    assert portfolio_valuation_frame(payload).iloc[0]["名称"] == "兴森科技"
    assert portfolio_analysis_frame(payload).iloc[0]["项目"] == "最大持仓集中度"
    assert portfolio_decision_frame(payload).iloc[0]["动作"] == "强势持有"
    assert position_recommendation_frame(payload).iloc[0]["动作"] == "部分止盈"
    assert replacement_frame(payload).empty
    assert score_frame(payload).iloc[0]["分数"] == 95
    assert decision_frame(payload).iloc[0]["行动"] == "强势持有"
    assert scanner_frame(payload).iloc[0]["排名"] == 1
    assert analysis_frame(payload).iloc[0]["趋势"] == "偏多"
