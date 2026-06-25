"""Tests for portfolio loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from stock_pilot.portfolio import PortfolioError, PortfolioLoader


def test_portfolio_loader_loads_positions(tmp_path: Path) -> None:
    """PortfolioLoader should return immutable position data."""
    path = tmp_path / "portfolio.yaml"
    path.write_text(
        """
stocks:
  "2436":
    name: 兴森科技
    cost: 50.411
    shares: 100
""",
        encoding="utf-8",
    )

    portfolio = PortfolioLoader(path).load()

    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].code == "002436"
    assert portfolio.positions[0].name == "兴森科技"
    assert portfolio.positions[0].cost == 50.411
    assert portfolio.positions[0].shares == 100


def test_portfolio_loader_rejects_empty_stocks(tmp_path: Path) -> None:
    """PortfolioLoader should reject missing stock positions."""
    path = tmp_path / "portfolio.yaml"
    path.write_text("stocks: {}\n", encoding="utf-8")

    with pytest.raises(PortfolioError):
        PortfolioLoader(path).load()

