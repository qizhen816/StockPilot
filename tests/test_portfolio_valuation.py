"""Tests for portfolio valuation calculations."""

from __future__ import annotations

import pandas as pd

from stock_pilot.models import FetchResult, MarketData, Portfolio, Position
from stock_pilot.portfolio import PortfolioValuationCalculator


def test_calculate_position_values_market_value_and_pnl() -> None:
    """Position valuation should calculate cost, value, and PnL metrics."""
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    frame = pd.DataFrame({"close": [11.0, 12.0]})

    valuation = PortfolioValuationCalculator().calculate_position(position, frame)

    assert valuation.cost_amount == 1000.0
    assert valuation.market_value == 1200.0
    assert valuation.unrealized_pnl == 200.0
    assert valuation.unrealized_pnl_pct == 0.2
    assert valuation.daily_pnl == 100.0
    assert valuation.daily_pnl_pct == 1.0 / 11.0


def test_calculate_position_handles_single_day_without_daily_pnl() -> None:
    """Daily PnL should be unavailable when previous close is missing."""
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    frame = pd.DataFrame({"close": [12.0]})

    valuation = PortfolioValuationCalculator().calculate_position(position, frame)

    assert valuation.previous_close is None
    assert valuation.daily_pnl is None
    assert valuation.daily_pnl_pct is None


def test_calculate_portfolio_aggregates_position_values() -> None:
    """Portfolio valuation should aggregate all valued positions."""
    positions = (
        Position(code="002436", name="兴森科技", cost=10.0, shares=100),
        Position(code="002156", name="通富微电", cost=20.0, shares=50),
    )
    portfolio = Portfolio(positions=positions)
    fetch_results = (
        FetchResult(
            position=positions[0],
            market_data=MarketData(
                code="002436",
                name="兴森科技",
                frame=pd.DataFrame({"close": [11.0, 12.0]}),
            ),
        ),
        FetchResult(
            position=positions[1],
            market_data=MarketData(
                code="002156",
                name="通富微电",
                frame=pd.DataFrame({"close": [18.0, 22.0]}),
            ),
        ),
    )

    result = PortfolioValuationCalculator().calculate(portfolio, fetch_results)

    assert result.error is None
    assert result.valuation is not None
    assert result.valuation.total_cost == 2000.0
    assert result.valuation.total_market_value == 2300.0
    assert result.valuation.total_unrealized_pnl == 300.0
    assert result.valuation.total_unrealized_pnl_pct == 0.15
    assert result.valuation.total_daily_pnl == 300.0


def test_calculate_portfolio_returns_error_without_market_data() -> None:
    """Portfolio valuation should fail explicitly when no position has data."""
    position = Position(code="002436", name="兴森科技", cost=10.0, shares=100)
    portfolio = Portfolio(positions=(position,))
    fetch_results = (
        FetchResult(position=position, market_data=None, error="network error"),
    )

    result = PortfolioValuationCalculator().calculate(portfolio, fetch_results)

    assert result.valuation is None
    assert result.error == "No positions could be valued from fetched market data"
