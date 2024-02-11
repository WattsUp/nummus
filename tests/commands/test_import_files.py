from __future__ import annotations

import datetime
import io
import shutil
from unittest import mock

from colorama import Fore

from nummus import portfolio
from nummus.commands import create, import_files
from nummus.models import Account, AccountCategory, Asset, AssetCategory, Transaction
from tests.base import TestBase


class TestImport(TestBase):
    def test_import(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        p = portfolio.Portfolio(path_db, None)

        # Create Accounts and Assets
        with p.get_session() as s:
            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                emergency=False,
            )
            acct_invest = Account(
                name="Monkey Investments",
                institution="Monkey Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
                emergency=False,
            )
            asset = Asset(name="BANANA", category=AssetCategory.STOCKS)
            s.add_all((acct_checking, acct_invest, asset))
            s.commit()

        file_dir = self._TEST_ROOT.joinpath("statements")
        file_dir.mkdir(parents=True, exist_ok=True)
        file_dir.joinpath("subdirectory").mkdir()

        file_a = self._TEST_ROOT.joinpath("file_a.csv")
        shutil.copyfile(self._DATA_ROOT.joinpath("transactions_required.csv"), file_a)
        file_missing = self._TEST_ROOT.joinpath("file_missing.csv")

        file_b = file_dir.joinpath("file_b.csv")
        shutil.copyfile(self._DATA_ROOT.joinpath("transactions_extras.csv"), file_b)

        file_c = file_dir.joinpath("file_c.csv")
        shutil.copyfile(self._DATA_ROOT.joinpath("transactions_lacking.csv"), file_c)

        # Try importing with a missing file, should restore from backup
        paths = [file_a, file_missing]
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = import_files.Import(path_db, None, paths)
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = c.run()
        self.assertNotEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.RED}File does not exist: {file_missing}\n"
            f"{Fore.RED}Abandoned import, restored from backup\n"
        )
        self.assertEqual(fake_stdout, target)

        # Check file_a was not imported
        with p.get_session() as s:
            transactions = s.query(Transaction).all()
            self.assertEqual(len(transactions), 0)

        # Try importing with a bad file, should restore from backup
        paths = [file_a, file_c]
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = import_files.Import(path_db, None, paths)
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = c.run()
        self.assertNotEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.RED}Unknown importer for {file_c}\n"
            f"{Fore.YELLOW}Create a custom importer in {p.importers_path}\n"
            f"{Fore.RED}Abandoned import, restored from backup\n"
        )
        self.assertEqual(fake_stdout, target)

        # Check file_a was not imported
        with p.get_session() as s:
            transactions = s.query(Transaction).all()
            self.assertEqual(len(transactions), 0)

        # Delete file so dir import works
        file_c.unlink()

        # Valid import with directories
        paths = [file_a, file_dir]
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = import_files.Import(path_db, None, paths)
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = c.run()
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.GREEN}Imported 2 files\n"
        self.assertEqual(fake_stdout, target)

        # Check all transactions were imported
        with p.get_session() as s:
            transactions = s.query(Transaction).all()
            self.assertEqual(len(transactions), 6 + 4)

        # Import same files again, should fail
        paths = [file_a, file_c]
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = import_files.Import(path_db, None, paths)
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = c.run()
        self.assertNotEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        today = datetime.date.today()
        target = (
            f"{Fore.RED}Already imported {file_a} on {today}\n"
            f"{Fore.YELLOW}Delete file or run import with --force flag "
            "which may create duplicate transactions.\n"
            f"{Fore.RED}Abandoned import, restored from backup\n"
        )
        self.assertEqual(fake_stdout, target)
