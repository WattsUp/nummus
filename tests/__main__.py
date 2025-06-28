from __future__ import annotations

import json
import sys
import unittest

import colorama

from nummus.version import __version__
from tests import TEST_LOG, TestLog

colorama.init(autoreset=True)


def pre_tests() -> None:
    """Things to run before all tests."""
    print(f"Testing version {__version__}")  # noqa: T201
    TEST_LOG.unlink(missing_ok=True)
    d: TestLog = {
        "classes": {},
        "methods": {},
    }
    with TEST_LOG.open("w", encoding="utf-8") as file:
        json.dump(d, file)


def post_tests() -> bool:
    """Things to run after all tests.

    Returns:
        True if post tests were successful, False otherwise
    """
    n_slowest = 10
    with TEST_LOG.open("r", encoding="utf-8") as file:
        d: TestLog = json.load(file)
    classes = sorted(d["classes"].items(), key=lambda item: -item[1])
    methods = sorted(d["methods"].items(), key=lambda item: -item[1])

    print(f"{n_slowest} slowest classes")  # noqa: T201
    if len(classes) != 0:
        classes = classes[:n_slowest]
        n_pad = max(len(k) for k, _ in classes) + 1
        for cls, duration in classes:
            print(f"  {cls:{n_pad}}: {duration:6.2f}s")  # noqa: T201

    print(f"{n_slowest} slowest tests")  # noqa: T201
    if len(methods) != 0:
        methods = methods[:n_slowest]
        n_pad = max(len(k) for k, _ in methods) + 1
        for method, duration in methods:
            print(f"  {method:{n_pad}}: {duration:6.2f}s")  # noqa: T201

    return True


post_fail = "--no-post-fail" not in sys.argv
if not post_fail:
    sys.argv.remove("--no-post-fail")

pre_tests()
m = unittest.main(module=None, exit=False)
all_passed = m.result.wasSuccessful()
if all_passed:
    post = post_tests()
    sys.exit(post_fail and not post)
else:
    sys.exit(1)
