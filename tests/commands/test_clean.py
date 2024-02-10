from __future__ import annotations

import io
from unittest import mock

from colorama import Fore

from nummus import portfolio
from nummus.commands import clean_, create_
from tests.base import TestBase


class TestClean(TestBase):
    def test_clean(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_backup_1 = path_db.with_suffix(".backup1.tar.gz")
        path_backup_2 = path_db.with_suffix(".backup2.tar.gz")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create_.create(path_db, None, force=False, no_encrypt=True)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        p.backup()
        p.backup()

        self.assertTrue(path_backup_1.exists(), "Backup #1 does not exist")
        self.assertTrue(path_backup_2.exists(), "Backup #2 does not exist")

        size_before = path_db.stat().st_size

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = clean_.clean(p)
        self.assertEqual(rc, 0)
        size_after = path_db.stat().st_size
        p_change = size_before - size_after

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Portfolio cleaned\n"
            f"{Fore.CYAN}Portfolio was optimized by "
            f"{p_change / 1000:.1f}KB/{p_change / 1024:.1f}KiB\n"
        )
        self.assertEqual(fake_stdout, target)

        self.assertTrue(path_backup_1.exists(), "Backup #1 does not exist")
        self.assertFalse(path_backup_2.exists(), "Backup #2 does exist")
