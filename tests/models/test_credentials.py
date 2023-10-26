from __future__ import annotations

from nummus import models
from nummus.models import credentials
from tests.base import TestBase


class TestCredentials(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        d = {
            "site": self.random_string(),
            "user": self.random_string(),
            "password": self.random_string(),
        }

        c = credentials.Credentials(**d)
        s.add(c)
        s.commit()

        self.assertEqual(c.site, d["site"])
        self.assertEqual(c.user, d["user"])
        self.assertEqual(c.password, d["password"])
