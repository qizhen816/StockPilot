"""Market data fetching with AKShare."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

import pandas as pd

from stock_pilot.models import FetcherSettings, FetchResult, MarketData, Position

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Download daily OHLCV market data for A-share stocks."""

    def __init__(self, settings: FetcherSettings) -> None:
        """Create a fetcher with immutable fetcher settings."""
        self._settings = settings

    def fetch(self, position: Position) -> MarketData:
        """Fetch historical daily OHLCV data for one position."""
        logger.info("Fetching historical data for %s %s", position.code, position.name)
        errors: list[str] = []
        for source in self._settings.fallback_sources:
            for attempt in range(1, self._settings.retry_attempts + 1):
                try:
                    raw_frame = _fetch_from_source(
                        source=source,
                        code=position.code,
                        start_date=self._settings.start_date,
                        adjust=self._settings.adjust,
                    )
                    frame = _normalize_ohlcv_frame(raw_frame)
                    if frame.empty:
                        raise RuntimeError(f"{source} returned empty data")
                    return MarketData(
                        code=position.code,
                        name=position.name,
                        frame=frame,
                    )
                except Exception as exc:  # noqa: BLE001
                    message = f"{source} attempt {attempt}: {exc}"
                    logger.warning("Fetch failed for %s: %s", position.code, message)
                    errors.append(message)

        joined_errors = "; ".join(errors)
        raise RuntimeError(f"All market data sources failed: {joined_errors}")

    def fetch_all(self, positions: tuple[Position, ...]) -> tuple[FetchResult, ...]:
        """Fetch historical data for all positions without stopping on one failure."""
        results: list[FetchResult] = []
        for position in positions:
            try:
                results.append(
                    FetchResult(position=position, market_data=self.fetch(position))
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to fetch data for %s", position.code)
                results.append(
                    FetchResult(position=position, market_data=None, error=str(exc))
                )
        return tuple(results)


def _fetch_from_source(
    source: str,
    code: str,
    start_date: str,
    adjust: str,
) -> pd.DataFrame:
    functions = _load_akshare_hist_functions()
    if source == "eastmoney":
        return functions.eastmoney(
            symbol=code,
            period="daily",
            start_date=start_date,
            adjust=adjust,
        )
    if source == "tencent":
        return functions.tencent(
            symbol=_tencent_symbol(code),
            start_date=start_date,
            end_date=date.today().strftime("%Y%m%d"),
            adjust=adjust,
        )
    raise ValueError(f"Unsupported market data source: {source}")


class _AkshareHistFunctions:
    """AKShare historical data callables."""

    def __init__(
        self,
        eastmoney: Callable[..., pd.DataFrame],
        tencent: Callable[..., pd.DataFrame],
    ) -> None:
        self.eastmoney = eastmoney
        self.tencent = tencent


def _load_akshare_hist_functions() -> _AkshareHistFunctions:
    try:
        import akshare as ak  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "AKShare is required for market data fetching. "
            "Install dependencies with 'pip install -r requirements.txt'."
        ) from exc
    return _AkshareHistFunctions(
        eastmoney=ak.stock_zh_a_hist,
        tencent=ak.stock_zh_a_hist_tx,
    )


def _tencent_symbol(code: str) -> str:
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    return f"{prefix}{code}"


def _normalize_ohlcv_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    rename_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "turnover",
        "振幅": "amplitude",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
        "换手率": "turnover_rate",
        "amount": "volume",
    }
    normalized = frame.rename(columns=rename_map).copy()

    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"])
        normalized = normalized.sort_values("date").reset_index(drop=True)

    return normalized
