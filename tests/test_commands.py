from __future__ import annotations

import datetime
import io
import shutil
import textwrap
from decimal import Decimal
from unittest import mock

from colorama import Fore
from typing_extensions import override

from nummus import commands
from nummus import custom_types as t
from nummus import encryption, health_checks, portfolio
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestCommands(TestBase):
    def test_create_unencrypted(self) -> None:
        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = commands.utils.getpass.getpass

        queue: t.Strings = []

        def mock_input(to_print: str) -> str:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            commands.utils.getpass.getpass = mock_input

            path_db = self._TEST_ROOT.joinpath("portfolio.db")
            path_salt = path_db.with_suffix(".nacl")
            path_password = self._TEST_ROOT.joinpath(".password")
            key = self.random_string()
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"  {key}  \n\n")

            # Create unencrypted
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.create(path_db, None, force=False, no_encrypt=True)
            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio created at {path_db}\n"
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertFalse(path_salt.exists(), "Salt unexpectedly exists")

            # Check portfolio is unencrypted
            with path_db.open("rb") as file:
                buf = file.read()
                target = b"SQLite format 3"
                self.assertEqual(buf[: len(target)], target)
                buf = None  # Clear local buffer

            # Fail to overwrite
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.create(path_db, None, force=False, no_encrypt=True)
            fake_stdout = fake_stdout.getvalue()
            self.assertIn(f"Cannot overwrite portfolio at {path_db}", fake_stdout)
            self.assertNotEqual(rc, 0)

            # Overwrite
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.create(path_db, None, force=True, no_encrypt=True)
            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio created at {path_db}\n"
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertFalse(path_salt.exists(), "Salt unexpectedly exists")

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            commands.utils.getpass.getpass = original_get_pass

    def test_create_encrypted(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = commands.utils.getpass.getpass

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            commands.utils.getpass.getpass = mock_input

            path_db = self._TEST_ROOT.joinpath("portfolio.db")
            path_salt = path_db.with_suffix(".nacl")
            path_password = self._TEST_ROOT.joinpath(".password")
            key = self.random_string()
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"  {key}  \n\n")

            # Create encrypted
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.create(
                    path_db,
                    path_password,
                    force=False,
                    no_encrypt=False,
                )
            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio created at {path_db}\n"
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertTrue(path_salt.exists(), "Salt does not exist")

            # Check password is correct
            portfolio.Portfolio(path_db, key)

            # Create encrypted
            queue = [key, key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.create(
                    path_db,
                    path_password.with_suffix(".nonexistent"),
                    force=True,
                    no_encrypt=False,
                )
            fake_stdout = fake_stdout.getvalue()
            target = (
                "Please enter password: \n"
                "Please confirm password: \n"
                f"{Fore.GREEN}Portfolio created at {path_db}\n"
            )
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertTrue(path_salt.exists(), "Salt does not exist")

            # Check password is correct
            portfolio.Portfolio(path_db, key)

            # Create encrypted
            queue = [self.random_string(7), key, key + "typo", key, key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.create(path_db, None, force=True, no_encrypt=False)
            fake_stdout = fake_stdout.getvalue()
            target = (
                "Please enter password: \n"
                f"{Fore.RED}Password must be at least 8 characters\n"
                "Please enter password: \n"
                "Please confirm password: \n"
                f"{Fore.RED}Passwords must match\n"
                "Please enter password: \n"
                "Please confirm password: \n"
                f"{Fore.GREEN}Portfolio created at {path_db}\n"
            )
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertTrue(path_salt.exists(), "Salt does not exist")

            # Check password is correct
            portfolio.Portfolio(path_db, key)

            # Cancel on first prompt
            queue = [None]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.create(path_db, None, force=True, no_encrypt=False)
            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \n"
            self.assertEqual(fake_stdout, target)
            self.assertNotEqual(rc, 0)

            # Cancel on second prompt
            queue = [key, None]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.create(path_db, None, force=True, no_encrypt=False)
            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \nPlease confirm password: \n"
            self.assertEqual(fake_stdout, target)
            self.assertNotEqual(rc, 0)

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            commands.utils.getpass.getpass = original_get_pass

    def test_unlock_unencrypted(self) -> None:
        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = commands.utils.getpass.getpass

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            commands.utils.getpass.getpass = mock_input  # type: ignore[attr-defined]

            path_db = self._TEST_ROOT.joinpath("portfolio.db")

            # Non-existent Portfolio
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = commands.unlock(path_db, None)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.RED}Portfolio does not exist at {path_db}. Run nummus create\n"
            )
            self.assertEqual(fake_stdout, target)

            # Create and unlock unencrypted Portfolio
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                commands.create(path_db, None, force=False, no_encrypt=True)
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = commands.unlock(path_db, None)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            commands.utils.getpass.getpass = original_get_pass

    def test_unlock_encrypted(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = commands.utils.getpass.getpass

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            commands.utils.getpass.getpass = mock_input  # type: ignore[attr-defined]

            path_db = self._TEST_ROOT.joinpath("portfolio.db")

            # Create and unlock encrypted Portfolio
            key = self.random_string()
            queue = [key, key]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                commands.create(path_db, None, force=True, no_encrypt=False)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertTrue(
                portfolio.Portfolio.is_encrypted(path_db),
                "Portfolio is not encrypted",
            )

            # Password file does not exist
            path_password = self._TEST_ROOT.joinpath(".password")
            self.assertFalse(path_password.exists(), "Password does exist")
            queue = [key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = commands.unlock(path_db, path_password)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"Please enter password: \n{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

            # Password file does exist
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"{key}\n")
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = commands.unlock(path_db, path_password)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

            # Password file does exist but incorrect
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"not the {key}\n")
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = commands.unlock(path_db, path_password)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.RED}Could not decrypt with password file\n"
            self.assertEqual(fake_stdout, target)

            # No password file at all
            queue = [key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = commands.unlock(path_db, None)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"Please enter password: \n{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

            # Cancel entry
            queue = [None]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = commands.unlock(path_db, None)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \n"
            self.assertEqual(fake_stdout, target)

            # 3 failed attempts
            queue = ["bad", "still wrong", "not going to work"]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = commands.unlock(path_db, None)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = (
                "Please enter password: \n"
                f"{Fore.RED}Incorrect password\n"
                "Please enter password: \n"
                f"{Fore.RED}Incorrect password\n"
                "Please enter password: \n"
                f"{Fore.RED}Incorrect password\n"
                f"{Fore.RED}Too many incorrect attempts\n"
            )
            self.assertEqual(fake_stdout, target)

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            commands.utils.getpass.getpass = original_get_pass

    def test_import_files(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path_db, None, force=False, no_encrypt=True)
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
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.import_files(p, paths)
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
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.import_files(p, paths)
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
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.import_files(p, paths)
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
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.import_files(p, paths)
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

    def test_backup_restore(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_backup = path_db.with_suffix(".backup1.tar.gz")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path_db, None, force=False, no_encrypt=True)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.restore(path_db, None, list_ver=True)
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.RED}No backups found, run nummus backup"
        self.assertEqual(fake_stdout[: len(target)], target)

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.backup(p)
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.GREEN}Portfolio backed up to {path_backup}\n"
        self.assertEqual(fake_stdout, target)

        self.assertTrue(path_backup.exists(), "Backup does not exist")

        path_db.unlink()
        self.assertFalse(path_db.exists(), "Portfolio does exist")

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.restore(path_db, None, list_ver=True)
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.CYAN}Backup # 1 created at"
        self.assertEqual(fake_stdout[: len(target)], target)

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.restore(path_db, None)
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.CYAN}Extracted backup tar.gz\n"
            f"{Fore.GREEN}Portfolio is unlocked\n"
            f"{Fore.GREEN}Portfolio restored for {path_db}\n"
        )
        self.assertEqual(fake_stdout, target)

        self.assertTrue(path_db.exists(), "Portfolio does not exist")

        path_backup.unlink()
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.restore(path_db, None, tar_ver=1)
        self.assertNotEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.RED}Backup does not exist {path_backup}\n"
        self.assertEqual(fake_stdout, target)

    def test_clean(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_backup_1 = path_db.with_suffix(".backup1.tar.gz")
        path_backup_2 = path_db.with_suffix(".backup2.tar.gz")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path_db, None, force=False, no_encrypt=True)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        p.backup()
        p.backup()

        self.assertTrue(path_backup_1.exists(), "Backup #1 does not exist")
        self.assertTrue(path_backup_2.exists(), "Backup #2 does not exist")

        size_before = path_db.stat().st_size

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.clean(p)
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

    def test_update_assets(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path_db, None, force=False, no_encrypt=True)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        today = datetime.date.today()

        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            # Create assets
            a = Asset(name="Banana Inc.", category=AssetCategory.ITEM)
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                emergency=False,
            )

            s.add_all((a, acct))
            s.commit()
            a_id = a.id_
            acct_id = acct.id_

            # Add a transaction
            date = datetime.date(2023, 5, 1)
            date_ord = date.toordinal()
            txn = Transaction(
                account_id=acct.id_,
                date_ord=date_ord,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a.id_,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))
            s.commit()
            a.update_splits()
            s.commit()

        first_valuation_date = date - datetime.timedelta(days=7)
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("sys.stderr", new=io.StringIO()) as _,
        ):
            rc = commands.update_assets(p)

        self.assertNotEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.YELLOW}No assets were updated"
        self.assertEqual(fake_stdout[: len(target)], target)

        with p.get_session() as s:
            a = s.query(Asset).where(Asset.id_ == a_id).one()
            a.ticker = "BANANA"
            s.commit()

        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("sys.stderr", new=io.StringIO()) as _,
        ):
            rc = commands.update_assets(p)

        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Asset Banana Inc. (BANANA) updated from "
            f"{first_valuation_date} to {today}"
        )
        self.assertEqual(fake_stdout[: len(target)], target)

        # Sell asset so it should not include today
        last_valuation_date = date + datetime.timedelta(days=7)
        with p.get_session() as s:
            txn = Transaction(
                account_id=acct_id,
                date_ord=date_ord,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id,
                asset_quantity_unadjusted=-1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))
            s.commit()

            a = s.query(Asset).where(Asset.id_ == a_id).one()
            a.update_splits()
            s.commit()

        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("sys.stderr", new=io.StringIO()) as _,
        ):
            rc = commands.update_assets(p)

        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Asset Banana Inc. (BANANA) updated from "
            f"{first_valuation_date} to {last_valuation_date}"
        )
        self.assertEqual(fake_stdout[: len(target)], target)

        # Have a bad ticker
        with p.get_session() as s:
            a = s.query(Asset).where(Asset.id_ == a_id).one()
            a.ticker = "ORANGE"
            s.commit()

        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("sys.stderr", new=io.StringIO()) as _,
        ):
            rc = commands.update_assets(p)

        self.assertNotEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.RED}Asset Banana Inc. (ORANGE) failed to update. "
            "Error: BANANA: No timezone found, symbol may be delisted"
        )
        self.assertEqual(fake_stdout[: len(target)], target)

    def test_summarize(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path_db, None, force=False, no_encrypt=True)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        original_terminal_size = shutil.get_terminal_size
        try:
            shutil.get_terminal_size = lambda: (80, 24)

            p_dict = {
                "n_accounts": 1,
                "n_assets": 1,
                "n_transactions": 1,
                "n_valuations": 1,
                "net_worth": Decimal(90),
                "accounts": [
                    {
                        "name": "Monkey Bank Checking",
                        "institution": "Monkey Bank",
                        "category": "Cash",
                        "value": Decimal(90),
                        "age": "1 days",
                        "profit": Decimal(0),
                    },
                ],
                "total_asset_value": Decimal(14),
                "assets": [
                    {
                        "name": "Apple",
                        "description": "",
                        "value": Decimal(14),
                        "profit": Decimal(0),
                        "category": "Real estate",
                        "ticker": None,
                    },
                ],
                "db_size": 1024 * 10,
            }

            def mock_summarize(*_, include_all: bool = False) -> t.DictAny:
                self.assertFalse(include_all, "include_all was unexpectedly True")
                return p_dict

            p.summarize = mock_summarize

            target = textwrap.dedent(
                """\
            Portfolio file size is 10.2KB/10.0KiB
            There is 1 account, 1 of which is currently open
            ╭──────────────────────┬─────────────┬──────────┬────────┬────────┬────────╮
            │         Name         │ Institution │ Category │ Value  │ Profit │  Age   │
            ╞══════════════════════╪═════════════╪══════════╪════════╪════════╪════════╡
            │ Monkey Bank Checking │ Monkey Bank │ Cash     │ $90.00 │  $0.00 │ 1 days │
            ╞══════════════════════╪═════════════╪══════════╪════════╪════════╪════════╡
            │ Total                │             │          │ $90.00 │        │        │
            ╰──────────────────────┴─────────────┴──────────┴────────┴────────┴────────╯
            There is 1 asset, 1 of which is currently held
            ╭───────┬─────────────┬─────────────┬────────┬────────┬────────╮
            │ Name  │ Description │    Class    │ Ticker │ Value  │ Profit │
            ╞═══════╪═════════════╪═════════════╪════════╪════════╪════════╡
            │ Apple │             │ Real estate │        │ $14.00 │  $0.00 │
            ╞═══════╪═════════════╪═════════════╪════════╪════════╪════════╡
            │ Total │             │             │        │ $14.00 │        │
            ╰───────┴─────────────┴─────────────┴────────┴────────┴────────╯
            There is 1 asset valuation
            There is 1 transaction
            """,
            )
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                commands.summarize(p)
            fake_stdout = fake_stdout.getvalue()
            self.assertEqual(fake_stdout, target)

            p_dict = {
                "n_accounts": 2,
                "n_assets": 3,
                "n_transactions": 4,
                "n_valuations": 5,
                "net_worth": Decimal(90),
                "accounts": [
                    {
                        "name": "Monkey Bank Checking",
                        "institution": "Monkey Bank",
                        "category": "Cash",
                        "value": Decimal(90),
                        "age": "1 days",
                        "profit": Decimal(0),
                    },
                    {
                        "name": "Monkey Bank Credit",
                        "institution": "Monkey Bank",
                        "category": "Credit",
                        "value": Decimal(0),
                        "age": "1 days",
                        "profit": Decimal(0),
                    },
                ],
                "total_asset_value": Decimal(114),
                "assets": [
                    {
                        "name": "Apple",
                        "description": "Tech company",
                        "value": Decimal(14),
                        "profit": Decimal(0),
                        "category": "Real estate",
                        "ticker": None,
                    },
                    {
                        "name": "Banana",
                        "description": None,
                        "value": Decimal(100),
                        "profit": Decimal(0),
                        "category": "Stocks",
                        "ticker": "BANANA",
                    },
                ],
                "db_size": 1024 * 10,
            }

            target = textwrap.dedent(
                """\
            Portfolio file size is 10.2KB/10.0KiB
            There are 2 accounts, 2 of which are currently open
            ╭──────────────────────┬─────────────┬──────────┬────────┬────────┬────────╮
            │         Name         │ Institution │ Category │ Value  │ Profit │  Age   │
            ╞══════════════════════╪═════════════╪══════════╪════════╪════════╪════════╡
            │ Monkey Bank Checking │ Monkey Bank │ Cash     │ $90.00 │  $0.00 │ 1 days │
            │ Monkey Bank Credit   │ Monkey Bank │ Credit   │  $0.00 │  $0.00 │ 1 days │
            ╞══════════════════════╪═════════════╪══════════╪════════╪════════╪════════╡
            │ Total                │             │          │ $90.00 │        │        │
            ╰──────────────────────┴─────────────┴──────────┴────────┴────────┴────────╯
            There are 3 assets, 2 of which are currently held
            ╭────────┬──────────────┬─────────────┬────────┬─────────┬────────╮
            │  Name  │ Description  │    Class    │ Ticker │  Value  │ Profit │
            ╞════════╪══════════════╪═════════════╪════════╪═════════╪════════╡
            │ Apple  │ Tech company │ Real estate │        │  $14.00 │  $0.00 │
            │ Banana │              │ Stocks      │ BANANA │ $100.00 │  $0.00 │
            ╞════════╪══════════════╪═════════════╪════════╪═════════╪════════╡
            │ Total  │              │             │        │ $114.00 │        │
            ╰────────┴──────────────┴─────────────┴────────┴─────────┴────────╯
            There are 5 asset valuations
            There are 4 transactions
            """,
            )
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                commands.summarize(p)
            fake_stdout = fake_stdout.getvalue()
            self.assertEqual(fake_stdout, target)
        finally:
            shutil.get_terminal_size = original_terminal_size

    def test_health_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path_db, None, force=False, no_encrypt=True)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        d = {}

        class MockCheck(health_checks.Base):
            _NAME = "Mock Check"
            _DESC = "This description spans\nTWO lines"
            _SEVERE = False

            @override
            def test(self) -> None:
                self._issues_raw = dict(d)
                self._commit_issues()

        original_checks = health_checks.CHECKS

        try:
            health_checks.CHECKS = [MockCheck]

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.health_check(p)
            self.assertEqual(rc, 0)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Check 'Mock Check' has no issues\n"
            self.assertEqual(fake_stdout, target)

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.health_check(p, always_descriptions=True)
            self.assertEqual(rc, 0)

            desc = f"{Fore.CYAN}    This description spans\n    TWO lines\n"
            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Check 'Mock Check' has no issues\n{desc}"
            self.assertEqual(fake_stdout, target)

            d["0"] = "Missing important information\nincluding this"
            d["1"] = "Missing some info"

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.health_check(p, limit=0)
            self.assertNotEqual(rc, 0)

            with p.get_session() as s:
                n = s.query(HealthCheckIssue).count()
                self.assertEqual(n, 2)

                c = s.query(HealthCheckIssue).where(HealthCheckIssue.value == "0").one()
                self.assertEqual(c.check, "Mock Check")
                self.assertEqual(c.value, "0")
                self.assertEqual(c.ignore, False)

                uri_0 = c.uri

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.YELLOW}Check 'Mock Check'\n{desc}"
                f"{Fore.YELLOW}  Has the following issues:\n"
                f"  [{uri_0}] Missing important information\n  including this\n"
                f"{Fore.MAGENTA}  And 1 more issues, use --limit flag to see more\n"
                f"{Fore.MAGENTA}Use web interface to fix issues\n"
                f"{Fore.MAGENTA}Or silence false positives with: "
                f"nummus health --ignore {uri_0} ...\n"
            )
            self.assertEqual(fake_stdout, target)

            d.pop("1")

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.health_check(p, ignores=[uri_0])
            self.assertEqual(rc, 0)

            with p.get_session() as s:
                c = s.query(HealthCheckIssue).one()
                self.assertEqual(c.check, "Mock Check")
                self.assertEqual(c.value, "0")
                self.assertEqual(c.ignore, True)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Check 'Mock Check' has no issues\n"
            self.assertEqual(fake_stdout, target)

            MockCheck._SEVERE = True  # noqa: SLF001
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.health_check(p, no_ignores=True)
            self.assertNotEqual(rc, 0)

            with p.get_session() as s:
                c = s.query(HealthCheckIssue).one()
                self.assertEqual(c.check, "Mock Check")
                self.assertEqual(c.value, "0")
                self.assertEqual(c.ignore, True)

                uri = c.uri

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.RED}Check 'Mock Check'\n{desc}"
                f"{Fore.RED}  Has the following issues:\n"
                f"  [{uri}] Missing important information\n  including this\n"
                f"{Fore.MAGENTA}Use web interface to fix issues\n"
                f"{Fore.MAGENTA}Or silence false positives with: "
                f"nummus health --ignore {uri} ...\n"
            )
            self.assertEqual(fake_stdout, target)

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.health_check(p, clear_ignores=True)
            self.assertNotEqual(rc, 0)

            with p.get_session() as s:
                c = s.query(HealthCheckIssue).one()
                self.assertEqual(c.check, "Mock Check")
                self.assertEqual(c.value, "0")
                self.assertEqual(c.ignore, False)

                uri = c.uri

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.RED}Check 'Mock Check'\n{desc}"
                f"{Fore.RED}  Has the following issues:\n"
                f"  [{uri}] Missing important information\n  including this\n"
                f"{Fore.MAGENTA}Use web interface to fix issues\n"
                f"{Fore.MAGENTA}Or silence false positives with: "
                f"nummus health --ignore {uri} ...\n"
            )
            self.assertEqual(fake_stdout, target)

            # Solving the issue should get rid of the Ignore
            d.pop("0")
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = commands.health_check(p)
            self.assertEqual(rc, 0)

            with p.get_session() as s:
                n = s.query(HealthCheckIssue).count()
                self.assertEqual(n, 0)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Check 'Mock Check' has no issues\n"
            self.assertEqual(fake_stdout, target)
        finally:
            health_checks.CHECKS = original_checks
