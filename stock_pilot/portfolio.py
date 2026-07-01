"""Portfolio loading for StockPilot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from stock_pilot.models import (
    FetchResult,
    Portfolio,
    PortfolioAnalysis,
    PortfolioValuation,
    PortfolioValuationResult,
    Position,
    PositionValuation,
    ScoreCalculationResult,
    StockScore,
)

logger = logging.getLogger(__name__)


class PortfolioError(ValueError):
    """Raised when portfolio configuration is invalid."""


class PortfolioLoader:
    """Load portfolio positions from a YAML file."""

    def __init__(self, path: Path) -> None:
        """Create a portfolio loader for the given YAML path."""
        self._path = path

    def load(self) -> Portfolio:
        """Load and validate configured positions."""
        logger.debug("Loading portfolio from %s", self._path)
        raw_portfolio = self._load_yaml()
        stocks = raw_portfolio.get("stocks")

        if not isinstance(stocks, dict) or not stocks:
            raise PortfolioError(
                "portfolio.yaml must contain a non-empty 'stocks' mapping"
            )

        positions = tuple(
            self._build_position(code=str(code), data=data)
            for code, data in stocks.items()
        )
        return Portfolio(positions=positions)

    def _load_yaml(self) -> dict[str, Any]:
        if not self._path.exists():
            raise PortfolioError(f"Portfolio file does not exist: {self._path}")

        with self._path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        if not isinstance(data, dict):
            raise PortfolioError("portfolio.yaml must contain a YAML mapping")

        return data

    def _build_position(self, code: str, data: Any) -> Position:
        if not isinstance(data, dict):
            raise PortfolioError(f"Stock {code} must be a mapping")

        name = _required_string(data, "name", code)
        cost = _required_float(data, "cost", code)
        shares = _required_int(data, "shares", code)
        sector = _normalize_sector(
            _optional_string(data, "sector", _infer_sector(name))
        )

        if shares <= 0:
            raise PortfolioError(f"Stock {code}.shares must be greater than zero")
        if cost <= 0:
            raise PortfolioError(f"Stock {code}.cost must be greater than zero")

        return Position(
            code=code.zfill(6),
            name=name,
            cost=cost,
            shares=shares,
            sector=sector,
        )


def _required_string(mapping: dict[str, Any], key: str, stock_code: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PortfolioError(f"Stock {stock_code}.{key} must be a non-empty string")
    return value.strip()


def _required_float(mapping: dict[str, Any], key: str, stock_code: str) -> float:
    value = mapping.get(key)
    if not isinstance(value, int | float):
        raise PortfolioError(f"Stock {stock_code}.{key} must be a number")
    return float(value)


def _required_int(mapping: dict[str, Any], key: str, stock_code: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int):
        raise PortfolioError(f"Stock {stock_code}.{key} must be an integer")
    return value


def _optional_string(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise PortfolioError(f"Stock {key} must be a non-empty string")
    return value.strip()


def _infer_sector(name: str) -> str:
    rules = (
        ("Semiconductor", ("半导体", "太极", "通富")),
        ("PCB", ("兴森", "PCB")),
        ("Medicine", ("药", "双鹤", "恩华")),
        ("Power", ("电力", "福能")),
        ("Defense", ("航天", "军工", "Defense")),
        ("AI", ("人工智能", "AI")),
    )
    for sector, keywords in rules:
        if any(keyword in name for keyword in keywords):
            return sector
    return "Others"


def _normalize_sector(value: str) -> str:
    aliases = {
        "未分类": "Others",
        "Unknown": "Others",
        "Other": "Others",
        "科技": "Technology",
        "医药": "Medicine",
        "医疗": "Medicine",
        "电力": "Power",
        "半导体": "Semiconductor",
        "军工": "Defense",
    }
    return aliases.get(value, value)


class PortfolioValuationCalculator:
    """Calculate portfolio valuation from positions and fetched market data."""

    def calculate(
        self,
        portfolio: Portfolio,
        fetch_results: tuple[FetchResult, ...],
    ) -> PortfolioValuationResult:
        """Calculate valuation metrics for all successfully fetched positions."""
        market_data_by_code = {
            result.position.code: result.market_data
            for result in fetch_results
            if result.market_data is not None
        }

        valuations: list[PositionValuation] = []
        for position in portfolio.positions:
            market_data = market_data_by_code.get(position.code)
            if market_data is None:
                logger.warning(
                    "Skipping valuation for %s without market data", position.code
                )
                continue

            try:
                valuations.append(
                    self.calculate_position(
                        position=position,
                        frame=market_data.frame,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to value position %s", position.code)
                return PortfolioValuationResult(valuation=None, error=str(exc))

        if not valuations:
            return PortfolioValuationResult(
                valuation=None,
                error="No positions could be valued from fetched market data",
            )

        total_cost = sum(item.cost_amount for item in valuations)
        total_market_value = sum(item.market_value for item in valuations)
        total_unrealized_pnl = total_market_value - total_cost
        total_unrealized_pnl_pct = _ratio(total_unrealized_pnl, total_cost)
        daily_values = [
            item.daily_pnl for item in valuations if item.daily_pnl is not None
        ]
        total_daily_pnl = sum(daily_values) if daily_values else None

        return PortfolioValuationResult(
            valuation=PortfolioValuation(
                positions=tuple(valuations),
                total_cost=total_cost,
                total_market_value=total_market_value,
                total_unrealized_pnl=total_unrealized_pnl,
                total_unrealized_pnl_pct=total_unrealized_pnl_pct,
                total_daily_pnl=total_daily_pnl,
            )
        )

    def calculate_position(
        self,
        position: Position,
        frame: pd.DataFrame,
    ) -> PositionValuation:
        """Calculate valuation metrics for one position."""
        _require_columns(frame, ("close",))
        if frame.empty:
            raise PortfolioError(f"Market data for {position.code} is empty")

        current_price = float(frame.iloc[-1]["close"])
        previous_close = _previous_close(frame)
        cost_amount = position.cost * position.shares
        market_value = current_price * position.shares
        unrealized_pnl = market_value - cost_amount
        daily_pnl = None
        daily_pnl_pct = None

        if previous_close is not None:
            daily_pnl = (current_price - previous_close) * position.shares
            daily_pnl_pct = _ratio(current_price - previous_close, previous_close)

        return PositionValuation(
            code=position.code,
            name=position.name,
            shares=position.shares,
            cost_price=position.cost,
            cost_amount=cost_amount,
            current_price=current_price,
            previous_close=previous_close,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=_ratio(unrealized_pnl, cost_amount),
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            sector=position.sector,
        )


def _previous_close(frame: pd.DataFrame) -> float | None:
    if len(frame) < 2:
        return None
    return float(frame.iloc[-2]["close"])


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _require_columns(frame: pd.DataFrame, required_columns: tuple[str, ...]) -> None:
    missing_columns = [
        column for column in required_columns if column not in frame.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise PortfolioError(
            f"Market data frame is missing required columns: {missing}"
        )


class PortfolioAnalyzer:
    """Analyze portfolio-level exposure, concentration, and risk."""

    def analyze(
        self,
        valuation_result: PortfolioValuationResult,
        score_results: tuple[ScoreCalculationResult, ...],
    ) -> PortfolioAnalysis:
        """Generate portfolio-level analysis from valuations and scores."""
        if valuation_result.valuation is None:
            return PortfolioAnalysis(
                sector_exposures=(),
                concentration_top_position_pct=0.0,
                largest_winner=None,
                largest_loser=None,
                highest_risk_position=None,
                weakest_relative_position=None,
                portfolio_trend_score=0.0,
                portfolio_risk_score=0.0,
                portfolio_risk_level="Unknown",
                portfolio_risk_reasons=("Portfolio valuation is unavailable",),
                profit_concentration_pct=0.0,
                profit_concentration_score=0.0,
                profit_concentration_reasons=("Portfolio valuation is unavailable",),
            )

        valuation = valuation_result.valuation
        score_by_code = {
            result.position.code: result.score
            for result in score_results
            if result.score is not None
        }
        risk_score = _portfolio_risk_score(score_results)
        risk_reasons = _portfolio_risk_reasons(
            valuation=valuation,
            score_results=score_results,
        )
        profit_concentration = _profit_concentration(valuation)
        return PortfolioAnalysis(
            sector_exposures=_sector_exposures(valuation),
            concentration_top_position_pct=_top_concentration(valuation),
            largest_winner=_largest_winner(valuation),
            largest_loser=_largest_loser(valuation),
            highest_risk_position=_highest_risk_position(score_results),
            weakest_relative_position=_weakest_relative_position(score_results),
            portfolio_trend_score=_average_score(score_by_code),
            portfolio_risk_score=risk_score,
            portfolio_risk_level=_portfolio_risk_level(risk_score),
            portfolio_risk_reasons=risk_reasons,
            profit_concentration_pct=profit_concentration,
            profit_concentration_score=profit_concentration * 100,
            profit_concentration_reasons=_profit_concentration_reasons(
                valuation,
                profit_concentration,
            ),
        )


def _sector_exposures(valuation: PortfolioValuation) -> tuple[tuple[str, float], ...]:
    if valuation.total_market_value == 0:
        return ()
    exposures: dict[str, float] = {}
    for position in valuation.positions:
        exposures[position.sector] = exposures.get(position.sector, 0.0) + (
            position.market_value / valuation.total_market_value
        )
    return tuple(sorted(exposures.items(), key=lambda item: item[1], reverse=True))


def _top_concentration(valuation: PortfolioValuation) -> float:
    if valuation.total_market_value == 0 or not valuation.positions:
        return 0.0
    return max(position.market_value for position in valuation.positions) / (
        valuation.total_market_value
    )


def _largest_winner(valuation: PortfolioValuation) -> str | None:
    if not valuation.positions:
        return None
    winner = max(valuation.positions, key=lambda item: item.unrealized_pnl)
    return f"{winner.name}（{winner.code}）"


def _largest_loser(valuation: PortfolioValuation) -> str | None:
    if not valuation.positions:
        return None
    loser = min(valuation.positions, key=lambda item: item.unrealized_pnl)
    return f"{loser.name}（{loser.code}）"


def _highest_risk_position(
    score_results: tuple[ScoreCalculationResult, ...],
) -> str | None:
    risk_rank = {"High": 3, "Medium": 2, "Low": 1}
    scores = [result.score for result in score_results if result.score is not None]
    if not scores:
        return None
    score = max(scores, key=lambda item: risk_rank.get(item.risk, 0))
    return f"{score.name}（{score.code}）"


def _weakest_relative_position(
    score_results: tuple[ScoreCalculationResult, ...],
) -> str | None:
    scores = [result.score for result in score_results if result.score is not None]
    if not scores:
        return None
    score = min(scores, key=lambda item: item.relative_strength_score)
    return f"{score.name}（{score.code}）"


def _average_score(score_by_code: dict[str, StockScore]) -> float:
    scores = [score.score for score in score_by_code.values()]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _portfolio_risk_score(
    score_results: tuple[ScoreCalculationResult, ...],
) -> float:
    risk_points = {"Low": 25.0, "Medium": 60.0, "High": 90.0}
    scores = [result.score for result in score_results if result.score is not None]
    if not scores:
        return 0.0
    return sum(risk_points.get(score.risk, 50.0) for score in scores) / len(scores)


def _portfolio_risk_level(risk_score: float) -> str:
    if risk_score >= 70:
        return "High"
    if risk_score >= 40:
        return "Medium"
    return "Low"


def _portfolio_risk_reasons(
    valuation: PortfolioValuation,
    score_results: tuple[ScoreCalculationResult, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    top_concentration = _top_concentration(valuation)
    if top_concentration >= 0.25:
        reasons.append(f"Largest position concentration is {top_concentration:.0%}")

    sector_exposures = _sector_exposures(valuation)
    if sector_exposures and sector_exposures[0][1] >= 0.45:
        sector, weight = sector_exposures[0]
        reasons.append(f"{sector} exposure is relatively high at {weight:.0%}")

    high_risk = [
        result.score.name
        for result in score_results
        if result.score is not None and result.score.risk == "High"
    ]
    if high_risk:
        reasons.append("High-risk holdings: " + "、".join(high_risk))

    losing_positions = [
        position.name
        for position in valuation.positions
        if position.unrealized_pnl < 0
    ]
    if losing_positions:
        reasons.append("Drawdown positions: " + "、".join(losing_positions[:3]))

    if not reasons:
        reasons.append("Portfolio risk is balanced across current holdings")
    return tuple(reasons)


def _profit_concentration(valuation: PortfolioValuation) -> float:
    profitable = [
        position for position in valuation.positions if position.unrealized_pnl > 0
    ]
    total_profit = sum(position.unrealized_pnl for position in profitable)
    if total_profit <= 0:
        return 0.0
    top_two_profit = sum(
        position.unrealized_pnl
        for position in sorted(
            profitable,
            key=lambda item: item.unrealized_pnl,
            reverse=True,
        )[:2]
    )
    return top_two_profit / total_profit


def _profit_concentration_reasons(
    valuation: PortfolioValuation,
    concentration: float,
) -> tuple[str, ...]:
    profitable = sorted(
        [position for position in valuation.positions if position.unrealized_pnl > 0],
        key=lambda item: item.unrealized_pnl,
        reverse=True,
    )
    if not profitable:
        return ("No profitable positions are available",)
    leaders = "、".join(position.name for position in profitable[:2])
    if concentration >= 0.75:
        return (
            f"Profit concentration is high at {concentration:.0%}",
            f"Most portfolio profit comes from {leaders}",
        )
    if concentration >= 0.55:
        return (
            f"Profit concentration is medium at {concentration:.0%}",
            f"Main profit contributors are {leaders}",
        )
    return (
        f"Profit concentration is balanced at {concentration:.0%}",
        f"Main profit contributors are {leaders}",
    )
