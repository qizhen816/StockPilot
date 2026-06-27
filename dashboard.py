"""Streamlit dashboard entry point for StockPilot."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from stock_pilot.logging_config import configure_logging
from stock_pilot.pipeline import run_daily_pipeline
from stock_pilot.portfolio import PortfolioLoader
from stock_pilot.reporter import DailyReportPayload
from stock_pilot.settings import SettingsLoader

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"
DEFAULT_PORTFOLIO_PATH = PROJECT_ROOT / "config" / "portfolio.yaml"


def main() -> None:
    """Run the Streamlit dashboard."""
    try:
        import streamlit as st  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "Streamlit is required for the dashboard. "
            "Install dependencies with 'pip install -r requirements.txt'."
        ) from exc

    st.set_page_config(page_title="StockPilot", layout="wide")
    st.title("StockPilot")

    settings = SettingsLoader(DEFAULT_SETTINGS_PATH).load()
    configure_logging(settings.log_level)
    portfolio = PortfolioLoader(DEFAULT_PORTFOLIO_PATH).load()

    with st.spinner("正在生成盘后分析..."):
        payload = run_daily_pipeline(settings=settings, portfolio=portfolio)

    _render_dashboard(st, payload)


def _render_dashboard(st: object, payload: DailyReportPayload) -> None:
    mode = (
        "上一完整收盘日"
        if payload.analysis_snapshot.is_using_previous_close
        else "最新日线"
    )
    st.caption(
        f"报告日期：{payload.report_date.isoformat()} ｜ "
        f"分析数据：{payload.analysis_snapshot.data_date or '-'} ｜ "
        f"分析模式：{mode}"
    )
    _render_summary(st, payload)

    tabs = st.tabs(["组合", "计划", "评分", "候选", "图表", "明细"])
    with tabs[0]:
        st.subheader("组合概览")
        st.dataframe(portfolio_valuation_frame(payload), use_container_width=True)
        st.dataframe(portfolio_analysis_frame(payload), use_container_width=True)
    with tabs[1]:
        st.subheader("明日组合计划")
        st.info(payload.portfolio_decision_plan.summary)
        st.dataframe(portfolio_decision_frame(payload), use_container_width=True)
        st.dataframe(replacement_frame(payload), use_container_width=True)
    with tabs[2]:
        st.subheader("评分与决策")
        st.dataframe(score_frame(payload), use_container_width=True)
        st.dataframe(decision_frame(payload), use_container_width=True)
    with tabs[3]:
        st.subheader("候选扫描")
        st.dataframe(scanner_frame(payload), use_container_width=True)
    with tabs[4]:
        st.subheader("评分分布")
        scores = score_frame(payload)
        if not scores.empty:
            st.bar_chart(scores.set_index("名称")["分数"])
        st.subheader("持仓市值")
        valuations = portfolio_valuation_frame(payload)
        if not valuations.empty:
            st.bar_chart(valuations.set_index("名称")["市值"])
    with tabs[5]:
        st.subheader("分析明细")
        st.dataframe(analysis_frame(payload), use_container_width=True)


def _render_summary(st: object, payload: DailyReportPayload) -> None:
    summary = payload.summary
    col1, col2, col3 = st.columns(3)
    col1.metric("最强个股", summary.strongest_stock or "-")
    col2.metric("组合分", f"{payload.portfolio_decision_plan.portfolio_score:.1f}")
    col3.metric("风险分", f"{payload.portfolio_decision_plan.portfolio_risk_score:.1f}")
    st.info(summary.conclusion)


def portfolio_valuation_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """Build a portfolio valuation table for dashboard rendering."""
    valuation = payload.portfolio_valuation.valuation
    if valuation is None:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "代码": item.code,
                "名称": item.name,
                "板块": item.sector,
                "股数": item.shares,
                "成本价": item.cost_price,
                "现价": item.current_price,
                "市值": item.market_value,
                "浮动盈亏": item.unrealized_pnl,
                "盈亏比例": item.unrealized_pnl_pct,
                "日内盈亏": item.daily_pnl,
            }
            for item in valuation.positions
        ]
    )


def portfolio_analysis_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """Build a portfolio-level analysis table for dashboard rendering."""
    analysis = payload.portfolio_analysis
    return pd.DataFrame(
        [
            {"项目": "最大持仓集中度", "值": analysis.concentration_top_position_pct},
            {"项目": "最大盈利个股", "值": analysis.largest_winner or "-"},
            {"项目": "最大亏损个股", "值": analysis.largest_loser or "-"},
            {"项目": "最高风险个股", "值": analysis.highest_risk_position or "-"},
            {
                "项目": "最弱相对强弱个股",
                "值": analysis.weakest_relative_position or "-",
            },
            {"项目": "组合趋势分", "值": analysis.portfolio_trend_score},
            {"项目": "组合风险分", "值": analysis.portfolio_risk_score},
            {"项目": "组合风险等级", "值": analysis.portfolio_risk_level},
            {"项目": "组合风险原因", "值": "；".join(analysis.portfolio_risk_reasons)},
        ]
    )


def score_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """Build a stock score table for dashboard rendering."""
    return pd.DataFrame(
        [
            {
                "代码": result.score.code,
                "名称": result.score.name,
                "分数": result.score.score,
                "评级": result.score.rating,
                "风险": result.score.risk,
                "置信度": result.score.confidence,
                "相对强弱": result.score.relative_strength_score,
            }
            for result in payload.score_results
            if result.score is not None
        ]
    )


def portfolio_decision_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """Build a portfolio decision table for dashboard rendering."""
    return pd.DataFrame(
        [
            {
                "排名": action.rank,
                "代码": action.code,
                "名称": action.name,
                "动作": action.action,
                "综合排名": action.rank,
                "相对排名": action.relative_rank,
                "风险排名": action.risk_rank,
                "趋势排名": action.trend_rank,
                "分数": action.score,
                "风险": action.risk,
                "置信度": action.confidence,
                "相对强弱": action.relative_strength_score,
                "原因": "；".join(action.reasons),
            }
            for action in payload.portfolio_decision_plan.actions
        ]
    )


def replacement_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """Build a replacement suggestion table for dashboard rendering."""
    return pd.DataFrame(
        [
            {
                "当前代码": suggestion.current_code,
                "当前名称": suggestion.current_name,
                "候选代码": suggestion.suggested_code,
                "候选名称": suggestion.suggested_name,
                "分差": suggestion.score_gap,
                "趋势改善": suggestion.trend_improvement,
                "相对强弱改善": suggestion.relative_strength_improvement,
                "风险改善": suggestion.risk_improvement,
                "预期组合分改善": suggestion.expected_portfolio_score_delta,
                "置信度": suggestion.confidence,
                "原因": "；".join(suggestion.reasons),
            }
            for suggestion in payload.portfolio_decision_plan.replacements
        ]
    )


def decision_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """Build a decision-support table for dashboard rendering."""
    return pd.DataFrame(
        [
            {
                "代码": result.decision.code,
                "名称": result.decision.name,
                "行动": result.decision.action,
                "风险": result.decision.risk,
                "置信度": result.decision.confidence,
                "原因": "；".join(result.decision.reasons),
            }
            for result in payload.decision_results
            if result.decision is not None
        ]
    )


def scanner_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """Build a scanner candidate table for dashboard rendering."""
    return pd.DataFrame(
        [
            {
                "排名": index,
                "代码": candidate.code,
                "名称": candidate.name,
                "分数": candidate.score,
                "评级": candidate.rating,
                "风险": candidate.risk,
                "置信度": candidate.confidence,
                "原因": "；".join(candidate.reasons),
            }
            for index, candidate in enumerate(
                payload.scanner_result.candidates, start=1
            )
        ]
    )


def analysis_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """Build an analysis detail table for dashboard rendering."""
    return pd.DataFrame(
        [
            {
                "代码": result.analysis.code,
                "名称": result.analysis.name,
                "板块": result.analysis.sector,
                "趋势": result.analysis.trend,
                "动量": result.analysis.momentum,
                "风险": result.analysis.risk,
                "量能": result.analysis.volume_status,
                "支撑位": result.analysis.support,
                "压力位": result.analysis.resistance,
                "原因": "；".join(result.analysis.reasons),
            }
            for result in payload.analysis_results
            if result.analysis is not None
        ]
    )


if __name__ == "__main__":
    main()
