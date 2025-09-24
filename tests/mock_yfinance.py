from __future__ import annotations

import datetime

import pandas as pd
import yfinance
import yfinance.exceptions


class MockFunds:
    def __init__(self, symbol: str) -> None:
        self._symbol = symbol

    @property
    def sector_weightings(self) -> dict[str, float]:
        if self._symbol == "BANANA_ETF":
            return {
                "realestate": 0.1,
                "energy": 0.9,
            }
        if self._symbol == "ORANGE_ETF":
            return {
                "realestate": 0.1,
                "technology": 0.5,
                "financial_services": 0.4,
            }
        raise yfinance.exceptions.YFDataException


class MockTicker:
    def __init__(self, symbol: str) -> None:
        self._symbol = symbol

    @property
    def info(self) -> dict[str, object]:
        if self._symbol == "BANANA":
            return {"sector": "Healthcare"}
        return {}

    @property
    def funds_data(self) -> MockFunds:
        return MockFunds(self._symbol)

    def history(
        self,
        start: datetime.date,
        end: datetime.date,
        *,
        actions: bool,
        raise_errors: bool,
    ) -> pd.DataFrame:
        assert actions
        assert raise_errors
        if self._symbol not in {"BANANA", "^BANANA"}:
            msg = f"{self._symbol}: No timezone found, symbol may be delisted"
            raise Exception(msg)

        # Create close prices = date_ord
        # Create a split every monday
        dates: list[datetime.date] = []
        close: list[float] = []
        split: list[float] = []

        dt = datetime.datetime.combine(
            start,
            datetime.time(tzinfo=datetime.UTC),
        )
        while dt.date() <= end:
            weekday = dt.weekday()
            if weekday in {5, 6}:
                # No valuations on weekends
                dt += datetime.timedelta(days=1)
                continue

            dates.append(dt)
            if weekday == 0:
                # Doubling every week exceeded integer limits
                split.append(1.1)
            else:
                split.append(0.0)
            close.append(float(dt.date().toordinal()))

            dt += datetime.timedelta(days=1)

        return pd.DataFrame(
            index=pd.to_datetime(dates),
            data={"Close": close, "Stock Splits": split},
        )
