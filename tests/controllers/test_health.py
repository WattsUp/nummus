from __future__ import annotations

import datetime

import time_machine

from nummus.health_checks import CHECKS, UnlockedTransactions
from nummus.models import (
    Config,
    ConfigKey,
    HealthCheckIssue,
    Transaction,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestHealth(WebTestBase):
    def test_page(self) -> None:
        self._setup_portfolio()
        endpoint = "health.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("Health checks never ran", result)

    def test_refresh(self) -> None:
        p = self._portfolio
        self._setup_portfolio()

        with p.begin_session() as s:
            c = (
                s.query(Config)
                .where(Config.key == ConfigKey.LAST_HEALTH_CHECK_TS)
                .one_or_none()
            )
            self.assertIsNone(c)

        utc_now = datetime.datetime.now(datetime.timezone.utc)

        endpoint = "health.refresh"
        with time_machine.travel(utc_now, tick=False):
            result, _ = self.web_post(endpoint)
        self.assertIn("Last checks ran 0.0 s ago", result)
        self.assertIn("Monkey Bank Checking: $100.00 to Apple is unlocked", result)

        with p.begin_session() as s:
            c = (
                s.query(Config)
                .where(Config.key == ConfigKey.LAST_HEALTH_CHECK_TS)
                .one()
            )
            self.assertEqual(c.value, utc_now.isoformat())

            # Fix issues
            s.query(Transaction).update({"locked": True})
            s.query(TransactionSplit).update({"locked": True})

        # Run again and it'll update the Config
        utc_now += datetime.timedelta(seconds=10)
        with time_machine.travel(utc_now, tick=False):
            result, _ = self.web_post(endpoint)
        self.assertIn("Last checks ran 0.0 s ago", result)
        self.assertNotIn("Monkey Bank Checking: $100.00 to Apple is unlocked", result)

        with p.begin_session() as s:
            c = (
                s.query(Config)
                .where(Config.key == ConfigKey.LAST_HEALTH_CHECK_TS)
                .one()
            )
            self.assertEqual(c.value, utc_now.isoformat())

    def test_ignore(self) -> None:
        p = self._portfolio
        self._setup_portfolio()

        utc_now = datetime.datetime.now(datetime.timezone.utc)

        endpoint = "health.refresh"
        with time_machine.travel(utc_now, tick=False):
            result, _ = self.web_post(endpoint)
        self.assertIn("Last checks ran 0.0 s ago", result)
        self.assertIn("Monkey Bank Checking: $100.00 to Apple is unlocked", result)

        with p.begin_session() as s:
            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.check == UnlockedTransactions.name)
                .one()
            )
            self.assertFalse(i.ignore)
            i_uri = i.uri

        endpoint = "health.ignore"
        with time_machine.travel(utc_now + datetime.timedelta(seconds=10), tick=False):
            result, _ = self.web_put((endpoint, {"uri": i_uri}))
        self.assertIn("Last checks ran 10.0 s ago", result)
        self.assertNotIn("Monkey Bank Checking: $100.00 to Apple is unlocked", result)

    def test_check(self) -> None:
        self._setup_portfolio()

        endpoint = "health.page"
        result, _ = self.web_get(endpoint)
        self.assertEqual(result.count("checked"), len(CHECKS))

        endpoint = "health.check"
        result, _ = self.web_put((endpoint, {"name": UnlockedTransactions.name}))
        self.assertEqual(result.count("checked"), len(CHECKS) - 1)

        endpoint = "health.page"
        result, _ = self.web_get(endpoint)
        self.assertEqual(result.count("checked"), len(CHECKS) - 1)

        endpoint = "health.check"
        result, _ = self.web_put(
            (endpoint, {"name": UnlockedTransactions.name}),
            data={"closed": True},
        )
        self.assertEqual(result.count("checked"), len(CHECKS))

        endpoint = "health.page"
        result, _ = self.web_get(endpoint)
        self.assertEqual(result.count("checked"), len(CHECKS))
