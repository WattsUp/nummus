from __future__ import annotations

import io
from unittest import mock

from colorama import Fore

from nummus.commands import create, unlock
from tests.base import TestBase


class TestUnlock(TestBase):
    def test_unlock_unencrypted(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")

        # Create and unlock unencrypted Portfolio
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            c = unlock.Unlock(path_db, None)
            c.run()

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.GREEN}Portfolio is unlocked\n"
        self.assertEqual(fake_stdout, target)
