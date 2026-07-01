"""StockPilot 的 Streamlit 工作台入口。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from stock_pilot.logging_config import configure_logging
from stock_pilot.pipeline import run_daily_pipeline
from stock_pilot.portfolio import PortfolioLoader
from stock_pilot.reporter import (
    DailyReportPayload,
    _translate_action,
    _translate_momentum,
    _translate_position_state,
    _translate_priority,
    _translate_reason,
    _translate_risk,
    _translate_trend,
    _translate_trend_stage,
)
from stock_pilot.settings import SettingsLoader

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"
DEFAULT_PORTFOLIO_PATH = PROJECT_ROOT / "config" / "portfolio.yaml"


def main() -> None:
    """运行 Streamlit 工作台。"""
    try:
        import streamlit as st  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "运行工作台需要安装 Streamlit。"
            "请先执行 'pip install -r requirements.txt' 安装依赖。"
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
        st.subheader("组合仓位建议")
        st.dataframe(position_recommendation_frame(payload), use_container_width=True)
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
    """生成持仓估值表。"""
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
    """生成组合分析表。"""
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
            {
                "项目": "组合风险等级",
                "值": _translate_risk(analysis.portfolio_risk_level),
            },
            {
                "项目": "组合风险原因",
                "值": _join_reasons(analysis.portfolio_risk_reasons),
            },
            {"项目": "盈利集中度", "值": analysis.profit_concentration_pct},
            {"项目": "盈利集中度分", "值": analysis.profit_concentration_score},
            {
                "项目": "盈利集中原因",
                "值": _join_reasons(analysis.profit_concentration_reasons),
            },
        ]
    )


def score_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """生成个股评分表。"""
    return pd.DataFrame(
        [
            {
                "代码": result.score.code,
                "名称": result.score.name,
                "分数": result.score.score,
                "评级": result.score.rating,
                "风险": _translate_risk(result.score.risk),
                "置信度": result.score.confidence,
                "相对强弱": result.score.relative_strength_score,
            }
            for result in payload.score_results
            if result.score is not None
        ]
    )


def portfolio_decision_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """生成组合决策表。"""
    return pd.DataFrame(
        [
            {
                "排名": action.rank,
                "代码": action.code,
                "名称": action.name,
                "动作": _translate_action(action.action),
                "综合排名": action.rank,
                "相对排名": action.relative_rank,
                "风险排名": action.risk_rank,
                "趋势排名": action.trend_rank,
                "分数": action.score,
                "风险": _translate_risk(action.risk),
                "波动风险": _translate_risk(action.risk_breakdown.volatility_risk),
                "趋势风险": _translate_risk(action.risk_breakdown.trend_risk),
                "集中度风险": _translate_risk(action.risk_breakdown.concentration_risk),
                "组合风险": _translate_risk(action.risk_breakdown.portfolio_risk),
                "优先级": _translate_priority(action.execution_priority),
                "置信度": action.confidence,
                "相对强弱": action.relative_strength_score,
                "原因": _join_reasons(action.reasons),
            }
            for action in payload.portfolio_decision_plan.actions
        ]
    )


def replacement_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """生成替换候选表。"""
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
                "替换置信度": suggestion.replacement_confidence,
                "原因": _join_reasons(suggestion.reasons),
            }
            for suggestion in payload.portfolio_decision_plan.replacements
        ]
    )


def position_recommendation_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """生成仓位建议表。"""
    return pd.DataFrame(
        [
            {
                "代码": recommendation.code,
                "名称": recommendation.name,
                "当前股数": recommendation.current_shares,
                "建议股数": recommendation.recommended_shares,
                "建议仓位": recommendation.recommended_position_pct,
                "状态": _translate_position_state(recommendation.state),
                "趋势阶段": _translate_trend_stage(recommendation.trend_stage),
                "动作": _translate_action(recommendation.action),
                "风险": _translate_risk(recommendation.risk),
                "波动风险": _translate_risk(
                    recommendation.risk_breakdown.volatility_risk
                ),
                "趋势风险": _translate_risk(recommendation.risk_breakdown.trend_risk),
                "集中度风险": _translate_risk(
                    recommendation.risk_breakdown.concentration_risk
                ),
                "组合风险": _translate_risk(
                    recommendation.risk_breakdown.portfolio_risk
                ),
                "置信度": recommendation.confidence,
                "成本价": recommendation.cost_price,
                "现价": recommendation.current_price,
                "浮盈亏": recommendation.unrealized_pnl_pct,
                "当前回撤": recommendation.current_drawdown_pct,
                "止损": recommendation.suggested_stop_loss,
                "跟踪止损": recommendation.suggested_trailing_stop,
                "止盈参考": recommendation.suggested_take_profit,
                "原因": _join_reasons(recommendation.reasons),
            }
            for recommendation in payload.position_recommendations
        ]
    )


def decision_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """生成个股决策表。"""
    return pd.DataFrame(
        [
            {
                "代码": result.decision.code,
                "名称": result.decision.name,
                "行动": _translate_action(result.decision.action),
                "风险": _translate_risk(result.decision.risk),
                "置信度": result.decision.confidence,
                "原因": _join_reasons(result.decision.reasons),
            }
            for result in payload.decision_results
            if result.decision is not None
        ]
    )


def scanner_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """生成候选扫描表。"""
    return pd.DataFrame(
        [
            {
                "排名": index,
                "代码": candidate.code,
                "名称": candidate.name,
                "分数": candidate.score,
                "评级": candidate.rating,
                "风险": _translate_risk(candidate.risk),
                "置信度": candidate.confidence,
                "原因": _join_reasons(candidate.reasons),
            }
            for index, candidate in enumerate(
                payload.scanner_result.candidates, start=1
            )
        ]
    )


def analysis_frame(payload: DailyReportPayload) -> pd.DataFrame:
    """生成分析明细表。"""
    return pd.DataFrame(
        [
            {
                "代码": result.analysis.code,
                "名称": result.analysis.name,
                "板块": result.analysis.sector,
                "趋势": _translate_trend(result.analysis.trend),
                "动量": _translate_momentum(result.analysis.momentum),
                "风险": _translate_risk(result.analysis.risk),
                "量能": _translate_volume_status(result.analysis.volume_status),
                "支撑位": result.analysis.support,
                "压力位": result.analysis.resistance,
                "原因": _join_reasons(result.analysis.reasons),
            }
            for result in payload.analysis_results
            if result.analysis is not None
        ]
    )


def _join_reasons(reasons: tuple[str, ...]) -> str:
    """把原因列表翻译并合并为中文说明。"""
    return "；".join(_translate_reason(reason) for reason in reasons)


def _translate_volume_status(value: str) -> str:
    """翻译量能状态。"""
    return {
        "Strong": "较强",
        "Breakout": "突破",
        "Normal": "正常",
        "Shrink": "收缩",
        "Unknown": "未知",
    }.get(value, value)


if __name__ == "__main__":
    main()
