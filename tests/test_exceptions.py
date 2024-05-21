from __future__ import annotations

import inspect
from types import ModuleType

from nummus import exceptions as exc
from tests.base import TestBase


class TestExceptions(TestBase):
    def test_all_exported(self) -> None:
        # Test every exception is in __all__
        exceptions = {
            "http",  # export http for usage: exc.http.HTTPException
        }
        for k in dir(exc):
            if k[0] == "_":
                continue
            obj = getattr(exc, k)
            if not inspect.isclass(obj):
                continue
            if isinstance(obj, ModuleType):
                continue

            self.assertTrue(
                issubclass(obj, Exception),
                f"{obj} is not subclass of Exception",
            )
            exceptions.add(k)

            # Next checks are for nummus custom exceptions only
            if obj.__module__ != exc.__name__:
                continue

            # Class is direct subclass of Exception so try/excepts only work with
            # the specific exception
            self.assertEqual(obj.__base__, Exception)
        self.assertEqual(set(exc.__all__), exceptions)
