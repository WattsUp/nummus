from __future__ import annotations

from nummus import exceptions as exc
from nummus import models
from nummus.models.health_checks import HealthCheckIssue
from tests.base import TestBase


class TestHealthCheckIssue(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        d = {
            "check": self.random_string(),
            "value": self.random_string(),
            "msg": self.random_string(),
            "ignore": False,
        }

        i = HealthCheckIssue(**d)
        s.add(i)
        s.commit()

        self.assertEqual(i.check, d["check"])
        self.assertEqual(i.value, d["value"])
        self.assertEqual(i.msg, d["msg"])
        self.assertEqual(i.ignore, d["ignore"])

        # Duplicate values are bad
        i_dup = HealthCheckIssue(**d)
        s.add(i_dup)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # Short strings are bad
        self.assertRaises(exc.InvalidORMValueError, setattr, i, "check", "a")
        self.assertRaises(
            exc.IntegrityError,
            s.query(HealthCheckIssue).update,
            {"check": "a"},
        )
        s.rollback()

        # But not value
        i.value = "a"
        s.query(HealthCheckIssue).update({"value": "b"})
        s.commit()
