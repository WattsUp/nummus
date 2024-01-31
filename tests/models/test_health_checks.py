from __future__ import annotations

from nummus import models
from nummus.models import health_checks
from tests.base import TestBase


class TestHealthCheckIssue(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        d = {
            "check": self.random_string(),
            "value": self.random_string(),
            "ignore": False,
        }

        i = health_checks.HealthCheckIssue(**d)
        s.add(i)
        s.commit()

        self.assertEqual(i.check, d["check"])
        self.assertEqual(i.value, d["value"])
        self.assertEqual(i.ignore, d["ignore"])
