from __future__ import annotations

import secrets
import shutil
import string
import time
import unittest
from decimal import Decimal
from pathlib import Path

import autodict
import numpy as np
from sqlalchemy import orm, pool
from werkzeug import exceptions

from nummus import custom_types as t
from nummus import sql
from tests import TEST_LOG


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
        low: str | float | t.Real,
        high: str | float | t.Real,
        precision: int = 6,
        size: int = 1,
    ) -> t.Real | t.Reals:
        """Generate a random decimal from a uniform distribution.

        Args:
            low: lower bound
            high: upper bound
            precision: Digits to round to
            size: number of Decimals to generate

        Returns:
            Decimal between bounds rounded to precision
        """
        if size > 1:
            return [cls.random_decimal(low, high, precision) for _ in range(size)]
        d_low = round(Decimal(low), precision)
        d_high = round(Decimal(high), precision)
        result = round(Decimal(cls._RNG.uniform(d_low, d_high)), precision)
        if result <= d_low:
            return d_low
        if result >= d_high:
            return d_high
        return result

    def get_session(self) -> orm.Session:
        config = autodict.AutoDict(encrypt=False)
        path = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        return sql.get_session(path, config)

    @classmethod
    def _clean_test_root(cls) -> None:
        if cls._TEST_ROOT.exists():
            shutil.rmtree(cls._TEST_ROOT)

    def assertEqualWithinError(  # noqa: N802
        self,
        target: t.Any,
        real: t.Any,
        threshold: float,
        msg: str | None = None,
    ) -> None:
        """Assert if target != real within threshold.

        Args:
            target: Target value
            real: Test value
            threshold: Fractional amount real can be off
            msg: Error message to print
        """
        self.assertIsNotNone(real)
        if isinstance(target, dict):
            self.assertIsInstance(real, dict, msg)
            self.assertEqual(target.keys(), real.keys(), msg)
            for k, t_v in target.items():
                r_v = real[k]
                self.assertEqualWithinError(t_v, r_v, threshold, msg=f"Key: {k}")
            return
        if isinstance(target, list):
            self.assertIsInstance(real, list, msg)
            self.assertEqual(len(target), len(real), msg)
            for t_v, r_v in zip(target, real, strict=True):
                self.assertEqualWithinError(t_v, r_v, threshold, msg)
            return
        if isinstance(target, int | float):
            self.assertIsInstance(real, int | float, msg)
            error = np.abs(real if target == 0 else (real / target - 1))
            self.assertLessEqual(error, threshold, msg)
        else:
            # Decimals included here since their math should be immune from FP error
            self.assertEqual(target, real, msg)

    def assertHTTPRaises(  # noqa: N802
        self,
        rc: int,
        func: t.Callable,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        """Test function raises ProblemException with the matching HTTP return code.

        Args:
            rc: HTTP code to match
            func: Callable to test
            args: Passed to func()
            kwargs: Passed to func()
        """
        with self.assertRaises(exceptions.HTTPException) as cm:
            func(*args, **kwargs)
        e: exceptions.HTTPException = cm.exception
        self.assertEqual(rc, e.code)

    def setUp(self, *, clean: bool = True) -> None:
        if clean:
            sql.drop_session()
            self._clean_test_root()
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)

        # Remove sleeping by default, mainly in read hardware interaction
        self._original_sleep = time.sleep
        time.sleep = lambda *_: None

        self._test_start = time.perf_counter()

    def tearDown(self, *, clean: bool = True) -> None:
        duration = time.perf_counter() - self._test_start
        with autodict.JSONAutoDict(TEST_LOG) as d:
            d["methods"][self.id()] = duration
        if clean:
            sql.drop_session()
            self._clean_test_root()

        # Restore sleeping
        time.sleep = self._original_sleep

    def log_speed(self, slow_duration: float, fast_duration: float) -> None:
        """Log the duration of a slow/fast A/B comparison test.

        Args:
            slow_duration: Duration of slow test
            fast_duration: Duration of fast test
        """
        with autodict.JSONAutoDict(TEST_LOG) as d:
            d["speed"][self.id_()] = {
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

    @classmethod
    def tearDownClass(cls) -> None:
        print("]done", flush=True)
        duration = time.perf_counter() - cls._CLASS_START
        with autodict.JSONAutoDict(TEST_LOG) as d:
            d["classes"][f"{cls.__module__}.{cls.__qualname__}"] = duration
