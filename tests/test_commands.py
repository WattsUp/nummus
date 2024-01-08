from __future__ import annotations

import datetime
import io
import shutil
from unittest import mock

from colorama import Fore

from nummus import commands
from nummus import custom_types as t
from nummus import portfolio
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
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
            path_config = path_db.with_suffix(".config")
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
            self.assertTrue(path_config.exists(), "Config does not exist")

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
            self.assertTrue(path_config.exists(), "Config does not exist")

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            commands.utils.getpass.getpass = original_get_pass

    def test_create_encrypted(self) -> None:
        if portfolio.encryption is None:
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
            path_config = path_db.with_suffix(".config")
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
            self.assertTrue(path_config.exists(), "Config does not exist")

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
            self.assertTrue(path_config.exists(), "Config does not exist")

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
            self.assertTrue(path_config.exists(), "Config does not exist")

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
        if portfolio.encryption is None:
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

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = commands.clean(p)
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.GREEN}Portfolio cleaned\n"
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
