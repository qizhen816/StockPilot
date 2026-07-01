"""Immutable data models used across StockPilot modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Position:
    """A stock position configured by the user."""

    code: str
    name: str
    cost: float
    shares: int
    sector: str = "未分类"


@dataclass(frozen=True)
class Portfolio:
    """A collection of stock positions."""

    positions: tuple[Position, ...]


@dataclass(frozen=True)
class FetcherSettings:
    """Configuration for historical market data fetching."""

    start_date: str
    adjust: str
    retry_attempts: int
    fallback_sources: tuple[str, ...]
    cache_dir: Path | None = None


@dataclass(frozen=True)
class IndicatorSettings:
    """Configuration for technical indicator calculations."""

    sma_periods: tuple[int, ...]
    ema_short_period: int
    ema_long_period: int
    macd_signal_period: int
    rsi_period: int
    atr_period: int
    volume_ratio_period: int
    highest_period: int
    lowest_period: int


@dataclass(frozen=True)
class AnalyzerSettings:
    """Configuration for indicator interpretation in the analyzer layer."""

    trend_short_ma_period: int
    trend_mid_ma_period: int
    trend_long_ma_period: int
    momentum_rsi_lower: float
    momentum_rsi_upper: float
    volume_breakout_ratio: float
    risk_rsi_high: float
    risk_atr_pct_high: float
    support_resistance_period: int
    shrink_volume_ratio: float = 0.8
    strong_volume_ratio: float = 1.2
    breakout_volume_ratio: float = 1.8
    abnormal_drawdown_pct: float = -0.05
    long_upper_shadow_ratio: float = 0.45


@dataclass(frozen=True)
class ScorerSettings:
    """Configuration for explainable score calculation."""

    trend_weight: int
    momentum_weight: int
    volume_weight: int
    risk_weight: int
    relative_strength_weight: int
    reason_confidence_step: float
    minimum_confidence: float
    maximum_confidence: float
    maximum_score: int
    relative_strength_5d_weight: float
    relative_strength_20d_weight: float
    relative_strength_60d_weight: float
    long_term_trend_penalty: int


@dataclass(frozen=True)
class ReportSettings:
    """Configuration for persisted report outputs."""

    output_dir: Path
    history_csv: Path


@dataclass(frozen=True)
class SummarySettings:
    """Configuration for deterministic natural-language summaries."""

    watchlist_limit: int
    high_risk_levels: tuple[str, ...]


@dataclass(frozen=True)
class ScannerSettings:
    """Configuration for candidate scanning and ranking."""

    candidate_limit: int
    min_score: int
    allowed_risk_levels: tuple[str, ...]
    required_trend: str = "Bullish"
    min_relative_strength_score: int = 60
    min_volume_statuses: tuple[str, ...] = ("Normal", "Strong", "Breakout")


@dataclass(frozen=True)
class DecisionSettings:
    """Configuration for trading decision support."""

    high_score_threshold: int
    low_score_threshold: int
    high_confidence_threshold: float


@dataclass(frozen=True)
class PortfolioDecisionSettings:
    """Configuration for portfolio-level decision support."""

    strong_hold_score_threshold: int
    hold_score_threshold: int
    reduce_score_threshold: int
    exit_score_threshold: int
    replace_score_threshold: int
    replacement_min_score_gap: int
    minimum_confidence: float
    maximum_confidence: float
    replacement_min_confidence: float
    replacement_switch_cost_penalty: float


@dataclass(frozen=True)
class PositionManagerSettings:
    """Configuration for position-size recommendations."""

    full_position_pct: float
    overweight_position_pct: float
    accumulate_position_pct: float
    normal_position_pct: float
    lighten_position_pct: float
    exit_position_pct: float
    near_resistance_pct: float
    wide_resistance_pct: float
    profit_protection_levels: tuple[float, ...]
    atr_stop_multiplier: float
    sector_concentration_threshold: float
    position_concentration_threshold: float
    minimum_confidence: float
    maximum_confidence: float
    pullback_position_pct: float
    late_uptrend_position_pct: float
    breakdown_position_pct: float


@dataclass(frozen=True)
class MarketSessionSettings:
    """Configuration for market-session-aware report behavior."""

    analysis_cutoff_time: str


@dataclass(frozen=True)
class TelegramSettings:
    """Configuration for Telegram notification delivery."""

    enabled: bool
    bot_token_env: str
    chat_id_env: str


@dataclass(frozen=True)
class EmailSettings:
    """Configuration for email report delivery."""

    enabled: bool
    smtp_host: str
    smtp_port: int
    username_env: str
    password_env: str
    sender_env: str
    recipients: tuple[str, ...]
    use_tls: bool


@dataclass(frozen=True)
class NotificationSettings:
    """Configuration for report notification delivery."""

    enabled: bool
    dry_run: bool
    telegram: TelegramSettings
    email: EmailSettings


@dataclass(frozen=True)
class AppSettings:
    """Application-level configuration."""

    fetcher: FetcherSettings
    indicators: IndicatorSettings
    analyzer: AnalyzerSettings
    scorer: ScorerSettings
    report: ReportSettings
    summary: SummarySettings
    scanner: ScannerSettings
    decision: DecisionSettings
    portfolio_decision: PortfolioDecisionSettings
    position_manager: PositionManagerSettings
    market_session: MarketSessionSettings
    notification: NotificationSettings
    log_level: str


@dataclass(frozen=True)
class MarketData:
    """Daily OHLCV market data for one stock."""

    code: str
    name: str
    frame: pd.DataFrame


@dataclass(frozen=True)
class FetchResult:
    """Result of attempting to fetch market data for a position."""

    position: Position
    market_data: MarketData | None
    error: str | None = None


@dataclass(frozen=True)
class IndicatorResult:
    """Technical indicator values for one stock."""

    code: str
    name: str
    frame: pd.DataFrame


@dataclass(frozen=True)
class IndicatorCalculationResult:
    """Result of attempting to calculate indicators for a fetched stock."""

    position: Position
    indicators: IndicatorResult | None
    error: str | None = None


@dataclass(frozen=True)
class PositionValuation:
    """Valuation and profit/loss metrics for one position."""

    code: str
    name: str
    shares: int
    cost_price: float
    cost_amount: float
    current_price: float
    previous_close: float | None
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    daily_pnl: float | None
    daily_pnl_pct: float | None
    sector: str = "未分类"


@dataclass(frozen=True)
class PortfolioValuation:
    """Aggregated valuation metrics for a portfolio."""

    positions: tuple[PositionValuation, ...]
    total_cost: float
    total_market_value: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    total_daily_pnl: float | None


@dataclass(frozen=True)
class PortfolioValuationResult:
    """Result of attempting to calculate portfolio valuation."""

    valuation: PortfolioValuation | None
    error: str | None = None


@dataclass(frozen=True)
class AnalysisResult:
    """Explainable analysis derived from technical indicators."""

    code: str
    name: str
    trend: str
    momentum: str
    risk: str
    support: float | None
    resistance: float | None
    reasons: tuple[str, ...]
    sector: str = "未分类"
    stock_return: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    return_60d: float | None = None
    long_term_distance_pct: float | None = None
    volume_status: str = "Unknown"
    volume_reason: str = ""
    primary_support: float | None = None
    secondary_support: float | None = None
    primary_resistance: float | None = None
    secondary_resistance: float | None = None


@dataclass(frozen=True)
class AnalysisCalculationResult:
    """Result of attempting to analyze one indicator result."""

    position: Position
    analysis: AnalysisResult | None
    error: str | None = None


@dataclass(frozen=True)
class ScoreComponent:
    """A named contribution to the final stock score."""

    name: str
    score: int
    weight: int
    reason: str


@dataclass(frozen=True)
class StockScore:
    """Explainable 0-100 stock score derived from analysis output."""

    code: str
    name: str
    score: int
    rating: str
    risk: str
    confidence: float
    components: tuple[ScoreComponent, ...]
    reasons: tuple[str, ...]
    relative_strength_score: int = 50


@dataclass(frozen=True)
class ScoreCalculationResult:
    """Result of attempting to score one analysis result."""

    position: Position
    score: StockScore | None
    error: str | None = None


@dataclass(frozen=True)
class DailySummary:
    """Natural-language daily summary derived from scored portfolio results."""

    strongest_stock: str | None
    weakest_stock: str | None
    today_risk: str
    tomorrow_watchlist: tuple[str, ...]
    operation_advice: str
    conclusion: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ScanCandidate:
    """A ranked stock candidate produced by the scanner."""

    code: str
    name: str
    score: int
    rating: str
    risk: str
    confidence: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ScannerResult:
    """Ranked scanner candidates and skipped stock count."""

    candidates: tuple[ScanCandidate, ...]
    skipped_count: int


@dataclass(frozen=True)
class DecisionResult:
    """Actionable decision support for one stock."""

    code: str
    name: str
    action: str
    confidence: float
    risk: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DecisionCalculationResult:
    """Result of attempting to generate a decision for one stock."""

    position: Position
    decision: DecisionResult | None
    error: str | None = None


@dataclass(frozen=True)
class ReplacementSuggestion:
    """A suggested candidate to replace a weak portfolio holding."""

    current_code: str
    current_name: str
    suggested_code: str
    suggested_name: str
    confidence: float
    score_gap: int
    trend_improvement: int
    relative_strength_improvement: int
    risk_improvement: int
    expected_portfolio_score_delta: int
    replacement_confidence: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RiskBreakdown:
    """Separate risk dimensions used by portfolio decisions."""

    volatility_risk: str
    trend_risk: str
    concentration_risk: str
    portfolio_risk: str


@dataclass(frozen=True)
class PortfolioAction:
    """Portfolio-aware action for one current holding."""

    code: str
    name: str
    action: str
    confidence: float
    risk: str
    risk_breakdown: RiskBreakdown
    score: int
    rank: int
    relative_rank: int
    risk_rank: int
    trend_rank: int
    total_positions: int
    relative_strength_score: int
    execution_priority: str
    replacement: ReplacementSuggestion | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioDecisionPlan:
    """Portfolio-level plan answering what to do tomorrow."""

    actions: tuple[PortfolioAction, ...]
    replacements: tuple[ReplacementSuggestion, ...]
    portfolio_score: float
    portfolio_risk_score: float
    summary: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PositionRecommendation:
    """Portfolio-aware position-size recommendation for one holding."""

    code: str
    name: str
    current_shares: int
    recommended_shares: int
    current_position_pct: float
    recommended_position_pct: float
    state: str
    trend_stage: str
    action: str
    confidence: float
    risk: str
    risk_breakdown: RiskBreakdown
    cost_price: float
    current_price: float
    unrealized_pnl_pct: float
    current_drawdown_pct: float
    suggested_stop_loss: float | None
    suggested_trailing_stop: float | None
    suggested_take_profit: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisDataSnapshot:
    """Metadata describing which market data snapshot analysis used."""

    data_date: str | None
    is_using_previous_close: bool
    advice_horizon: str
    reason: str


@dataclass(frozen=True)
class NotificationResult:
    """Result of attempting to deliver one notification channel."""

    channel: str
    sent: bool
    message: str


@dataclass(frozen=True)
class NotificationDispatchResult:
    """Results for all notification channels attempted by a dispatcher."""

    results: tuple[NotificationResult, ...]


@dataclass(frozen=True)
class PortfolioAnalysis:
    """Portfolio-level exposure and risk analysis."""

    sector_exposures: tuple[tuple[str, float], ...]
    concentration_top_position_pct: float
    largest_winner: str | None
    largest_loser: str | None
    highest_risk_position: str | None
    weakest_relative_position: str | None
    portfolio_trend_score: float
    portfolio_risk_score: float
    portfolio_risk_level: str
    portfolio_risk_reasons: tuple[str, ...]
    profit_concentration_pct: float
    profit_concentration_score: float
    profit_concentration_reasons: tuple[str, ...]
