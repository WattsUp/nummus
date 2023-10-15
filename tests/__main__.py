"""Test main
"""

import os
import sys
import unittest

import autodict
import colorama

from nummus.version import __version__
from tests import TEST_LOG

colorama.init(autoreset=True)


def pre_tests():
    """Things to run before all tests"""
    print(f"Testing version {__version__}")
    if TEST_LOG.exists():
        os.remove(TEST_LOG)
    with autodict.JSONAutoDict(TEST_LOG) as d:
        d["classes"] = {}
        d["methods"] = {}


def post_tests() -> bool:
    """Things to run after all tests

    Returns:
        True if post tests were successful, False otherwise
    """
    n_slowest = 10
    with autodict.JSONAutoDict(TEST_LOG) as d:
        classes = sorted(d["classes"].items(), key=lambda item: -item[1])
        methods = sorted(d["methods"].items(), key=lambda item: -item[1])
        web_latency = sorted(d["web_latency"].items(), key=lambda item: -max(item[1]))

    print(f"{n_slowest} slowest classes")
    if len(classes) != 0:
        classes = classes[:n_slowest]
        n_pad = max(len(k) for k, _ in classes) + 1
        for cls, duration in classes:
            print(f"  {cls:{n_pad}}: {duration:6.2f}s")

    print(f"{n_slowest} slowest tests")
    if len(methods) != 0:
        methods = methods[:n_slowest]
        n_pad = max(len(k) for k, _ in methods) + 1
        for method, duration in methods:
            print(f"  {method:{n_pad}}: {duration:6.2f}s")

    print(f"{n_slowest} slowest web calls")
    if len(web_latency) != 0:
        web_latency = web_latency[:n_slowest]
        n_pad = max(len(k) for k, _ in web_latency) + 1
        for method, durations in web_latency:
            duration_ms = max(durations) * 1000
            print(f"  {method:{n_pad}}: {duration_ms:6.1f}ms")

    return True


post_fail = "--no-post-fail" not in sys.argv
if not post_fail:
    sys.argv.remove("--no-post-fail")

pre_tests()
m = unittest.main(module=None, exit=False)
post = post_tests()
sys.exit(not m.result.wasSuccessful() or (post_fail and not post))
