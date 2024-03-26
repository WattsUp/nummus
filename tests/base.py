from __future__ import annotations

import datetime
import secrets
import shutil
import string
import time
import unittest
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import autodict
import numpy as np
import pandas as pd
import yfinance as yf
from sqlalchemy import orm, pool

from nummus import exceptions as exc
from nummus import global_config, sql
from nummus.models import base_uri
from tests import TEST_LOG

if TYPE_CHECKING:
    from collections.abc import Callable


class MockTicker:
    def __init__(self, symbol: str) -> None:
        self._symbol = symbol

    def history(
        self,
        start: datetime.date,
        end: datetime.date,
        *,
        actions: bool,
        raise_errors: bool,
    ) -> pd.DataFrame:
        if not actions:
            msg = "actions must be True"
            raise ValueError(msg)
        if not raise_errors:
            msg = "raise_errors must be True"
            raise ValueError(msg)
        if self._symbol not in ["BANANA", "^BANANA"]:
            msg = f"{self._symbol}: No timezone found, symbol may be delisted"
            raise Exception(msg)  # noqa: TRY002

        # Create close prices = date_ord
        # Create a split every monday
        dates: list[datetime.date] = []
        close: list[float] = []
        split: list[float] = []

        dt = datetime.datetime.combine(
            start,
            datetime.time(tzinfo=datetime.timezone.utc),
        )
        while dt.date() <= end:
            weekday = dt.weekday()
            if weekday in [5, 6]:
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

        return pd.DataFrame(index=dates, data={"Close": close, "Stock Splits": split})  # type: ignore[attr-defined]


class TestBase(unittest.TestCase):
    _TEST_ROOT = Path.cwd().joinpath(".test").resolve()
    _DATA_ROOT = Path(__file__).resolve().parent.joinpath("data")
    _P_FAIL = 1e-4
    _RNG = np.random.default_rng()

    @classmethod
    def random_string(cls, length: int = 20) -> str:
        """Generate a random string a-zA-Z.

        Args:
            length: Length of string to generate

        Returns:
            Random string
        """
        return "".join(list(cls._RNG.choice(list(string.ascii_letters), length)))

    @classmethod
    def random_decimal(
        cls,
        low: str | float | Decimal,
        high: str | float | Decimal,
        precision: int = 6,
    ) -> Decimal:
        """Generate a random decimal from a uniform distribution.

        Args:
            low: lower bound
            high: upper bound
            precision: Digits to round to

        Returns:
            Decimal between bounds rounded to precision
        """
        d_low = round(Decimal(low), precision)
        d_high = round(Decimal(high), precision)
        x = cls._RNG.uniform(float(d_low), float(d_high))
        return min(max(round(Decimal(x), precision), d_low), d_high)

    def get_session(self) -> orm.Session:
        path = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        return sql.get_session(path, None)

    @classmethod
    def _clean_test_root(cls) -> None:
        if cls._TEST_ROOT.exists():
            shutil.rmtree(cls._TEST_ROOT)

    def assertEqualWithinError(  # noqa: N802
        self,
        real: object,
        target: object,
        threshold: float,
        msg: str | None = None,
    ) -> None:
        """Assert if target != real within threshold.

        Args:
            real: Test value
            target: Target value
            threshold: Fractional amount real can be off
            msg: Error message to print
        """
        self.assertIsNotNone(real)
        if isinstance(target, dict):
            if not isinstance(real, dict):
                self.fail(msg)
            self.assertEqual(real.keys(), target.keys(), msg)
            for k, t_v in target.items():
                r_v = real[k]
                self.assertEqualWithinError(r_v, t_v, threshold, msg=f"Key: {k}")
            return
        if isinstance(target, list):
            if not isinstance(real, list):
                self.fail(msg)
            self.assertEqual(len(real), len(target), msg)
            for t_v, r_v in zip(target, real, strict=True):
                self.assertEqualWithinError(r_v, t_v, threshold, msg)
            return
        if isinstance(target, int | float):
            if not isinstance(real, int | float):
                self.fail(msg)
            error = np.abs(real if target == 0 else (real / target - 1))
            self.assertLessEqual(error, threshold, msg)
        else:
            # Decimals included here since their math should be immune from FP error
            self.assertEqual(real, target, msg)

    def assertHTTPRaises(  # noqa: N802
        self,
        rc: int,
        func: Callable,
        *args: object,
        **kwargs: object,
    ) -> None:
        """Test function raises ProblemException with the matching HTTP return code.

        Args:
            rc: HTTP code to match
            func: Callable to test
            args: Passed to func()
            kwargs: Passed to func()
        """
        with self.assertRaises(exc.http.HTTPException) as cm:
            func(*args, **kwargs)
        e: exc.http.HTTPException = cm.exception
        self.assertEqual(e.code, rc)

    def setUp(self, *, clean: bool = True) -> None:
        if clean:
            sql.drop_session()
            self._clean_test_root()
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)

        # Remove sleeping by default, mainly in read hardware interaction
        self._original_sleep = time.sleep
        time.sleep = lambda *_: None

        self._original_ticker = yf.Ticker
        yf.Ticker = MockTicker

        self._test_start = time.perf_counter()

        # Global configuration is a constant default
        global_config._CACHE.update(global_config._DEFAULTS)  # noqa: SLF001

    def tearDown(self, *, clean: bool = True) -> None:
        duration = time.perf_counter() - self._test_start
        with autodict.JSONAutoDict(str(TEST_LOG)) as d:
            d["methods"][self.id()] = duration
        if clean:
            sql.drop_session()
            self._clean_test_root()

        # Restore sleeping
        time.sleep = self._original_sleep
        yf.Ticker = self._original_ticker

    def log_speed(self, slow_duration: float, fast_duration: float) -> None:
        """Log the duration of a slow/fast A/B comparison test.

        Args:
            slow_duration: Duration of slow test
            fast_duration: Duration of fast test
        """
        with autodict.JSONAutoDict(str(TEST_LOG)) as d:
            d["speed"][self.id()] = {
                "slow": slow_duration,
                "fast": fast_duration,
                "increase": slow_duration / fast_duration,
            }

    @classmethod
    def setUpClass(cls) -> None:
        print(f"{cls.__module__}.{cls.__qualname__}[", end="", flush=True)
        cls._CLASS_START = time.perf_counter()

        # Change all engines to NullPool so timing isn't an issue
        sql._ENGINE_ARGS["poolclass"] = pool.NullPool  # noqa: SLF001

        # Generate a cipher for URI encoding
        base_uri._CIPHER = base_uri.Cipher.generate()  # noqa: SLF001

    @classmethod
    def tearDownClass(cls) -> None:
        print("]done", flush=True)
        duration = time.perf_counter() - cls._CLASS_START
        with autodict.JSONAutoDict(str(TEST_LOG)) as d:
            d["classes"][f"{cls.__module__}.{cls.__qualname__}"] = duration
