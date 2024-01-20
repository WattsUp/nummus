from __future__ import annotations

from nummus import exceptions as exc
from nummus import models
from nummus.models import config
from tests.base import TestBase


class TestConfig(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        d = {
            "key": config.ConfigKey.VERSION,
            "value": self.random_string(),
        }

        c = config.Config(**d)
        s.add(c)
        s.commit()

        self.assertEqual(c.key, d["key"])
        self.assertEqual(c.value, d["value"])

        # Duplicate keys are bad
        c = config.Config(key=d["key"], value=self.random_string())
        s.add(c)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()
