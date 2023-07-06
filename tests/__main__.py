"""Test main
"""

import os
import sys
import unittest

import autodict
import colorama
from colorama import Fore

from nummus.version import __version__

from tests import TEST_LOG, web

colorama.init(autoreset=True)


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

  api_coverage = web.api_coverage()

  if len(api_coverage) != 0:
    n_pad = max(len(k) for k in api_coverage) + 1

    print(f"{'Endpoint':{n_pad}} Method "
          "Codes CMiss "
          "Query QMiss "
          "  Cover  Missing")
    print_width = (n_pad + 1 + 6 + 1 + 5 + 1 + 5 + 1 + 5 + 1 + 5 + 1 + 7 + 2 +
                   7)
    print("-" * print_width)

    total_rc = 0
    total_rc_miss = 0
    total_queries = 0
    total_queries_miss = 0

    for endpoint, data in sorted(api_coverage.items(), key=lambda x: x[0]):
      for method, branches in sorted(data.items(), key=lambda x: x[0]):
        rc = 0
        rc_miss = 0
        queries = 0
        queries_miss = 0
        missing = []
        for branch, hit in branches.items():
          if isinstance(branch, int):
            rc += 1
            if not hit:
              rc_miss += 1
              missing.append(str(branch))
          else:
            queries += 1
            if not hit:
              queries_miss += 1
              if branch is None:
                missing.append("No queries")
              else:
                missing.append(f"?{branch}=")
        missing = sorted(missing)

        total_rc += rc
        total_rc_miss += rc_miss
        total_queries += queries
        total_queries_miss += queries_miss

        n_miss = rc_miss + queries_miss
        n_total = rc + queries
        cover = 1 - n_miss / max(1, n_total)

        if method == "GET":
          method = f"{Fore.BLUE}{method:6}{Fore.RESET}"
        elif method == "POST":
          method = f"{Fore.GREEN}{method:6}{Fore.RESET}"
        elif method == "PUT":
          method = f"{Fore.YELLOW}{method:6}{Fore.RESET}"
        elif method == "DELETE":
          method = f"{Fore.RED}{method:6}{Fore.RESET}"
        else:
          method = f"{method:6}"

        print(f"{endpoint:{n_pad}} {method} "
              f"{rc:5} {rc_miss:5} "
              f"{queries:5} {queries_miss:5} "
              f"{cover * 100:6.2f}%  "
              f"{', '.join(missing)}")

    n_miss = total_rc_miss + total_queries_miss
    n_total = total_rc + total_queries
    cover = 1 - n_miss / max(1, n_total)
    print("-" * print_width)
    print(f"{'TOTAL':{n_pad}} {'':6} "
          f"{total_rc:5} {total_rc_miss:5} "
          f"{total_queries:5} {total_queries_miss:5} "
          f"{cover * 100:6.2f}%")


pre_tests()
m = unittest.main(module=None, exit=False)
post_tests()
sys.exit(not m.result.wasSuccessful())
