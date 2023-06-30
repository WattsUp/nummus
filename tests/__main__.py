"""Test main
"""

import os
import sys
import unittest

import autodict

from nummus.version import __version__

from tests import TEST_LOG


def pre_tests():
  """Things to run before all tests
  """
  print(f"Testing version {__version__}")
  if TEST_LOG.exists():
    os.remove(TEST_LOG)
  with autodict.JSONAutoDict(TEST_LOG) as d:
    d["classes"] = {}
    d["methods"] = {}


def post_tests():
  """Things to run after all tests
  """
  n_slowest = 10
  with autodict.JSONAutoDict(TEST_LOG) as d:
    classes = sorted(d["classes"].items(),
                     key=lambda item: -item[1])[:n_slowest]
    methods = sorted(d["methods"].items(),
                     key=lambda item: -item[1])[:n_slowest]
    api_latency = sorted(d["api_latency"].items(),
                         key=lambda item: -max(item[1]))[:n_slowest]

  print(f"{n_slowest} slowest classes")
  if len(classes) != 0:
    n_pad = max(len(k) for k, _ in classes) + 1
    for cls, duration in classes:
      print(f"  {cls:{n_pad}}: {duration:6.2f}s")

  print(f"{n_slowest} slowest tests")
  if len(methods) != 0:
    n_pad = max(len(k) for k, _ in methods) + 1
    for method, duration in methods:
      print(f"  {method:{n_pad}}: {duration:6.2f}s")

  print(f"{n_slowest} slowest API calls")
  if len(api_latency) != 0:
    n_pad = max(len(k) for k, _ in api_latency) + 1
    for method, durations in api_latency:
      duration_ms = max(durations) * 1000
      print(f"  {method:{n_pad}}: {duration_ms:6.1f}ms")


pre_tests()
m = unittest.main(module=None, exit=False)
post_tests()
sys.exit(not m.result.wasSuccessful())
