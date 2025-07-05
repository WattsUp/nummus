from __future__ import annotations

import datetime

from nummus import exceptions as exc
from nummus import models
from nummus.models import imported_file
from tests.base import TestBase


class TestImportedFile(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.datetime.now().astimezone().date()
        today_ord = today.toordinal()

        d = {
            "hash_": self.random_string(),
        }

        f = imported_file.ImportedFile(**d)
        s.add(f)
        s.commit()

        # Default date is today
        self.assertEqual(f.date_ord, today_ord)
        self.assertEqual(f.hash_, d["hash_"])

        # Duplicate hash_ are bad
        f = imported_file.ImportedFile(date_ord=today_ord + 1, hash_=d["hash_"])
        s.add(f)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()
