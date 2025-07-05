from __future__ import annotations

import base64
import datetime
import io
import secrets
import shutil
import tarfile
from decimal import Decimal
from unittest import mock

import time_machine
from packaging.version import Version

from nummus import __version__, encryption
from nummus import exceptions as exc
from nummus import importers, models, portfolio
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetSector,
    AssetValuation,
    Config,
    ConfigKey,
    query_count,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    USSector,
)
from tests.base import TestBase
from tests.importers.test_raw_csv import TRANSACTIONS_EXTRAS


class TestPortfolio(TestBase):
    def test_init_properties(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")

        path_db.parent.mkdir(parents=True, exist_ok=True)

        # Database does not exist
        self.assertRaises(FileNotFoundError, portfolio.Portfolio, path_db, None)

        # Create database file
        with path_db.open("w", encoding="utf-8") as file:
            file.write("Not a db")

        # Failed to unlock
        self.assertRaises(exc.UnlockingError, portfolio.Portfolio, path_db, None)

    def test_create_unencrypted(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_salt = path_db.with_suffix(".nacl")
        path_importers = path_db.parent.joinpath("portfolio.importers")

        # Create unencrypted portfolio
        p = portfolio.Portfolio.create(path_db)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertFalse(path_salt.exists(), "Salt unexpectedly exists")
        self.assertTrue(path_importers.exists(), "importers does not exist")
        self.assertTrue(path_importers.is_dir(), "importers is not a directory")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(p.importers_path, path_importers)
        self.assertEqual(p.path, path_db)

        self.assertRaises(exc.NotEncryptedError, p.encrypt, "")
        self.assertRaises(exc.NotEncryptedError, p.decrypt, "")

        # Check config contains valid cipher and version
        with p.begin_session() as s:
            value: str = (
                s.query(Config.value).where(Config.key == ConfigKey.CIPHER).one()
            )[0]
            models.Cipher.from_bytes(base64.b64decode(value))

            value: str = (
                s.query(Config.value).where(Config.key == ConfigKey.VERSION).one()
            )[0]
            self.assertGreaterEqual(Version(value), Version(__version__))

            n = query_count(
                s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST),
            )
            self.assertEqual(n, 1)

            n = query_count(s.query(Config).where(Config.key == ConfigKey.SECRET_KEY))
            self.assertEqual(n, 1)

            # No web key since no encryption
            n = query_count(s.query(Config).where(Config.key == ConfigKey.WEB_KEY))
            self.assertEqual(n, 0)
        self.assertFalse(p.is_encrypted)

        p = None

        # Check portfolio is unencrypted
        with path_db.open("rb") as file:
            buf = file.read()
            target = b"SQLite format 3"
            self.assertEqual(buf[: len(target)], target)
            buf = None  # Clear local buffer
        self.assertFalse(
            portfolio.Portfolio.is_encrypted_path(path_db),
            "Database is unexpectedly encrypted",
        )

        # Key given to unencrypted portfolio
        self.assertRaises(
            FileNotFoundError,
            portfolio.Portfolio,
            path_db,
            self.random_string(),
        )

        # Database already exists
        self.assertRaises(FileExistsError, portfolio.Portfolio.create, path_db)

        # Reopen portfolio
        p = portfolio.Portfolio(path_db, None)
        self.assertFalse(p.migration_required())

        # Force migration required
        with p.begin_session() as s:
            # Good, now reset version
            s.query(Config).where(Config.key == ConfigKey.VERSION).update(
                {"value": "0.0.0"},
            )

        self.assertRaises(
            exc.MigrationRequiredError,
            portfolio.Portfolio,
            path_db,
            None,
        )

        with p.begin_session() as s:
            # Good, now delete version
            s.query(Config).where(Config.key == ConfigKey.VERSION).delete()

        # Missing cipher
        self.assertRaises(
            exc.ProtectedObjectNotFoundError,
            portfolio.Portfolio,
            path_db,
            None,
        )

        with p.begin_session() as s:
            # Good, now delete cipher
            s.query(Config).where(Config.key == ConfigKey.CIPHER).delete()

        # Missing cipher
        self.assertRaises(
            exc.ProtectedObjectNotFoundError,
            portfolio.Portfolio,
            path_db,
            None,
        )

        with p.begin_session() as s:
            # Good, now change encryption test value
            c = s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).one()
            c.value = self.random_string()

        # Invalid encryption test
        self.assertRaises(exc.UnlockingError, portfolio.Portfolio, path_db, None)

        # Recreate
        path_db.unlink()

        portfolio.Portfolio.create(path_db)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")

        # Delete encryption test
        p = portfolio.Portfolio(path_db, None)
        with p.begin_session() as s:
            s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).delete()

        # Missing root password
        self.assertRaises(exc.UnlockingError, portfolio.Portfolio, path_db, None)

    def test_create_encrypted(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_salt = path_db.with_suffix(".nacl")

        key = self.random_string()

        # Create encrypted portfolio
        p = portfolio.Portfolio.create(path_db, key)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_salt.exists(), "Salt does not exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)

        secret = self.random_string()
        enc_secret = p.encrypt(secret)
        result = p.decrypt_s(enc_secret)
        self.assertEqual(result, secret)
        self.assertTrue(p.is_encrypted)

        with p.begin_session() as s:
            n = query_count(s.query(Config).where(Config.key == ConfigKey.WEB_KEY))
            self.assertEqual(n, 1)

        p = None

        # Check portfolio is encrypted
        with path_db.open("rb") as file:
            buf = file.read()
            target = b"SQLite format 3"
            self.assertNotEqual(buf[: len(target)], target)
            buf = None  # Clear local buffer
        self.assertTrue(
            portfolio.Portfolio.is_encrypted_path(path_db),
            "Database is unexpectedly unencrypted",
        )

        # Database already exists
        self.assertRaises(FileExistsError, portfolio.Portfolio.create, path_db)

        # Bad key
        self.assertRaises(
            exc.UnlockingError,
            portfolio.Portfolio,
            path_db,
            self.random_string(),
        )

        # Reopen portfolio
        p = portfolio.Portfolio(path_db, key)
        with p.begin_session() as s:
            # Good, now change encryption test value
            c = s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).one()
            c.value = p.encrypt(secrets.token_bytes())

        # Invalid root password
        self.assertRaises(exc.UnlockingError, portfolio.Portfolio, path_db, key)

    def test_is_encrypted_path(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_salt = path_db.with_suffix(".nacl")

        self.assertRaises(
            FileNotFoundError,
            portfolio.Portfolio.is_encrypted_path,
            path_db,
        )

        with path_db.open("w", encoding="utf-8") as file:
            file.write("I'm a database")

        self.assertFalse(
            portfolio.Portfolio.is_encrypted_path(path_db),
            "Database is unexpectedly encrypted",
        )

        path_salt.touch()
        self.assertTrue(
            portfolio.Portfolio.is_encrypted_path(path_db),
            "Database is unexpectedly unencrypted",
        )

    def test_find(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        cache: dict[str, tuple[int, str | None]] = {}

        with p.begin_session() as s:
            acct_checking_name = "Monkey Bank Checking"
            acct_checking_number = "MONKEY-0123"
            institution = "Monkey Bank"
            self.assertRaises(
                LookupError,
                p.find,
                s,
                Account,
                acct_checking_name,
                cache,
            )

            # Create accounts
            acct_checking = Account(
                name=acct_checking_name,
                institution=institution,
                number=acct_checking_number,
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            acct_invest_0 = Account(
                name="Primate Investments",
                institution=institution,
                number="MONKEY-9999",
                category=AccountCategory.INVESTMENT,
                closed=False,
                budgeted=True,
            )
            acct_invest_1 = Account(
                name="Primate Investments 2",
                institution="Gorilla Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
                budgeted=True,
            )
            s.add_all((acct_checking, acct_invest_0, acct_invest_1))
            s.flush()
            acct_checking_id = acct_checking.id_
            acct_checking_uri = acct_checking.uri

            r_id, r_name = p.find(s, Account, acct_checking_uri, cache)
            self.assertEqual(r_id, acct_checking_id)
            self.assertEqual(r_name, acct_checking_name)

            # No match with random URI
            self.assertRaises(
                LookupError,
                p.find,
                s,
                Account,
                Account.id_to_uri(0x0FFFFFFF),
                cache,
            )

            # Find by number
            r_id, r_name = p.find(s, Account, acct_checking_number, cache)
            self.assertEqual(r_id, acct_checking_id)
            self.assertEqual(r_name, acct_checking_name)

            # Find by partial number
            r_id, r_name = p.find(s, Account, acct_checking_number[-4:], cache)
            self.assertEqual(r_id, acct_checking_id)
            self.assertEqual(r_name, acct_checking_name)

            # Find by name
            r_id, r_name = p.find(s, Account, acct_checking_name, cache)
            self.assertEqual(r_id, acct_checking_id)
            self.assertEqual(r_name, acct_checking_name)

            # More than 1 match by institution
            self.assertRaises(
                LookupError,
                p.find,
                s,
                Account,
                institution,
                cache,
            )

    def test_import_file(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        path_debug = path_db.with_suffix(".importer_debug")

        # Fail to import non-importable file
        path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
        self.assertRaises(exc.UnknownImporterError, p.import_file, path, path_debug)
        self.assertTrue(path_debug.exists(), "Debug file unexpectedly does not exists")
        path_debug.unlink()

        # Fail to match Accounts and Assets
        path = self._DATA_ROOT.joinpath("transactions_extras.csv")
        self.assertRaises(LookupError, p.import_file, path, path_debug)
        self.assertTrue(path_debug.exists(), "Debug file unexpectedly does not exists")
        path_debug.unlink()

        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            # Create accounts
            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            acct_invest = Account(
                name="Monkey Investments",
                institution="Monkey Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
                budgeted=True,
            )
            s.add_all((acct_checking, acct_invest))
            s.flush()
            acct_checking_id = acct_checking.id_
            acct_invest_id = acct_invest.id_

        # Still missing assets
        self.assertRaises(LookupError, p.import_file, path, path_debug)
        self.assertTrue(
            path_debug.exists(),
            "Debug file unexpectedly does not exists",
        )
        path_debug.unlink()

        with p.begin_session() as s:
            asset = Asset(name="BANANA", category=AssetCategory.STOCKS)
            s.add(asset)
            s.flush()
            a_id = asset.id_

        # We good now
        p.import_file(path, path_debug)
        self.assertFalse(path_debug.exists(), "Debug file unexpectedly exists")

        with p.begin_session() as s:
            transactions = s.query(Transaction).all()

            target = TRANSACTIONS_EXTRAS
            self.assertEqual(len(transactions), len(target))
            for tgt, res in zip(target, transactions, strict=True):
                if tgt["account"] == "Monkey Bank Checking":
                    tgt_acct_id = acct_checking_id
                else:
                    tgt_acct_id = acct_invest_id
                self.assertEqual(res.account_id, tgt_acct_id)
                self.assertEqual(res.date_ord, tgt["date"].toordinal())
                self.assertEqual(res.amount, tgt["amount"])
                statement = tgt["statement"] or "Asset Transaction BANANA"
                self.assertEqual(res.statement, statement)

                self.assertEqual(len(res.splits), 1)
                r_split = res.splits[0]
                self.assertEqual(r_split.amount, tgt["amount"])
                self.assertEqual(r_split.memo, tgt["memo"])
                cat_id = (
                    s.query(TransactionCategory.id_)
                    .where(
                        TransactionCategory.name
                        == (tgt["category"] or "uncategorized").lower(),
                    )
                    .one()[0]
                )
                self.assertEqual(r_split.category_id, cat_id)
                self.assertEqual(r_split.tag, tgt["tag"])
                asset_id = a_id if tgt["asset"] else None
                self.assertEqual(r_split.asset_id, asset_id)
                self.assertEqual(r_split.asset_quantity, tgt["asset_quantity"])

        # Fail to import file again
        self.assertRaises(
            exc.FileAlreadyImportedError,
            p.import_file,
            path,
            path_debug,
        )
        self.assertFalse(path_debug.exists(), "Debug file unexpectedly exists")

        with p.begin_session() as s:
            # Unclear one so it'll link
            txn = s.query(Transaction).where(Transaction.amount == Decimal(1000)).one()
            txn.cleared = False
            txn.statement = "Overwrite me"
            t_split = (
                s.query(TransactionSplit)
                .where(TransactionSplit.parent_id == txn.id_)
                .one()
            )
            t_split.parent = txn
            t_split.memo = "Don't overwrite me"

        # But it will work with force
        p.import_file(path, path_debug, force=True)
        self.assertFalse(path_debug.exists(), "Debug file unexpectedly exists")

        with p.begin_session() as s:
            txn = s.query(Transaction).where(Transaction.amount == Decimal(1000)).one()
            t_split = (
                s.query(TransactionSplit)
                .where(TransactionSplit.parent_id == txn.id_)
                .one()
            )
            self.assertTrue(txn.cleared, "Transaction did not clear")
            self.assertTrue(t_split.cleared, "TransactionSplit did not clear")
            self.assertNotEqual(txn.statement, "Overwrite me")
            self.assertEqual(t_split.memo, "Don't overwrite me")

        # Fine importing with force when not required
        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        p.import_file(path, path_debug, force=True)
        self.assertFalse(path_debug.exists(), "Debug file unexpectedly exists")

        # Fine importing with force when not required
        path = self._DATA_ROOT.joinpath("transactions_corrupt.csv")
        self.assertRaises(exc.FailedImportError, p.import_file, path, path_debug)
        self.assertTrue(
            path_debug.exists(),
            "Debug file unexpectedly does not exists",
        )

        # Install importer that returns empty list
        shutil.copyfile(
            self._DATA_ROOT.joinpath("custom_importer.py"),
            p.importers_path.joinpath("custom_importer.py"),
        )
        p._importers = importers.get_importers(p._path_importers)  # noqa: SLF001
        path = self._DATA_ROOT.joinpath("banana_bank_statement.pdf")
        self.assertRaises(exc.EmptyImportError, p.import_file, path, path_debug)

        # Cannot import future transactions
        path = self._DATA_ROOT.joinpath("transactions_future.csv")
        self.assertRaises(
            exc.FutureTransactionError,
            p.import_file,
            path,
            path_debug,
        )

        # Cannot import asset transactions need specific categories
        path = self._DATA_ROOT.joinpath("transactions_investments_bad_category.csv")
        self.assertRaises(
            ValueError,
            p.import_file,
            path,
            path_debug,
        )

        with p.begin_session() as s:
            # Clear transactions
            s.query(TransactionSplit).delete()
            s.query(Transaction).delete()
            s.flush()

        # Fallback to uncategorized if unknown
        path = self._DATA_ROOT.joinpath("transactions_bad_category.csv")
        p.import_file(path, path_debug)

        with p.begin_session() as s:
            t_split = s.query(TransactionSplit).one()
            self.assertEqual(t_split.category_id, categories["uncategorized"])

            # Clear transactions
            s.query(TransactionSplit).delete()
            s.query(Transaction).delete()
            s.flush()

        # Import investment transactions
        path = self._DATA_ROOT.joinpath("transactions_investments.csv")
        p.import_file(path, path_debug)

        with p.begin_session() as s:
            transactions = s.query(Transaction).all()

            for txn in transactions:
                self.assertEqual(txn.amount, 0)

                splits = txn.splits
                self.assertEqual(len(splits), 1 if txn.statement == "Cash Maker" else 2)
                splits = sorted(splits, key=lambda t_split: t_split.amount)

                if txn.statement == "Profit Maker":
                    # Reinvested Dividends
                    t_split = splits[0]
                    self.assertEqual(t_split.amount, Decimal("-1234.56"))
                    self.assertEqual(t_split.asset_quantity, Decimal("32.1234"))
                    self.assertEqual(t_split.asset_id, a_id)
                    self.assertEqual(
                        t_split.category_id,
                        categories["securities traded"],
                    )

                    t_split = splits[1]
                    self.assertEqual(t_split.amount, Decimal("1234.56"))
                    self.assertEqual(t_split.asset_quantity, 0)
                    self.assertEqual(t_split.asset_id, a_id)
                    self.assertEqual(
                        t_split.category_id,
                        categories["dividends received"],
                    )
                elif txn.statement == "Cash Maker":
                    # Cash Dividends
                    t_split = splits[0]
                    self.assertEqual(t_split.amount, Decimal("1234.56"))
                    self.assertEqual(t_split.asset_quantity, 0)
                    self.assertEqual(t_split.asset_id, a_id)
                    self.assertEqual(
                        t_split.category_id,
                        categories["dividends received"],
                    )
                else:
                    # Fees
                    t_split = splits[0]
                    self.assertEqual(t_split.amount, Decimal(-900))
                    self.assertEqual(t_split.asset_quantity, 0)
                    self.assertEqual(t_split.asset_id, a_id)
                    self.assertEqual(
                        t_split.category_id,
                        categories["investment fees"],
                    )

                    t_split = splits[1]
                    self.assertEqual(t_split.amount, Decimal(900))
                    self.assertEqual(t_split.asset_quantity, Decimal("-32.1234"))
                    self.assertEqual(t_split.asset_id, a_id)
                    self.assertEqual(
                        t_split.category_id,
                        categories["securities traded"],
                    )

        # Fail missing asset quantity
        path = self._DATA_ROOT.joinpath("transactions_investments_missing0.csv")
        self.assertRaises(
            exc.MissingAssetError,
            p.import_file,
            path,
            path_debug,
        )
        path = self._DATA_ROOT.joinpath("transactions_investments_missing1.csv")
        self.assertRaises(
            exc.MissingAssetError,
            p.import_file,
            path,
            path_debug,
        )

    def test_backup_restore(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)
        utc_now = datetime.datetime.now(datetime.timezone.utc)

        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)

        # Create Account
        with p.begin_session() as s:
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct)
            s.flush()

            accounts = s.query(Account).all()
            self.assertEqual(len(accounts), 1)

        # Get list of backups
        result = portfolio.Portfolio.backups(path_db)
        self.assertEqual(len(result), 0)

        with time_machine.travel(utc_now, tick=False):
            result, tar_ver = p.backup()

        path_backup_1 = path_db.with_suffix(".backup1.tar")
        self.assertEqual(result, path_backup_1)
        self.assertEqual(tar_ver, 1)

        self.assertTrue(path_backup_1.exists(), "Backup portfolio does not exist")
        self.assertEqual(path_backup_1.stat().st_mode & 0o777, 0o600)

        with tarfile.open(path_backup_1, "r") as tar:
            buf_backup = tar.extractfile(path_db.name).read()  # type: ignore[attr-defined]
            with path_db.open("rb") as file:
                buf = file.read()
            self.assertEqual(buf_backup, buf)

        buf = None
        buf_backup = None

        # Get list of backups
        result = portfolio.Portfolio.backups(path_db)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 1)
        self.assertEqual(result[0][1], utc_now)

        # Accidentally add a new Account
        with p.begin_session() as s:
            acct = Account(
                name="Monkey Bank Checking Duplicate",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct)
            s.flush()

            accounts = s.query(Account).all()
            self.assertEqual(len(accounts), 2)

        with tarfile.open(path_backup_1, "r") as tar:
            buf_backup = tar.extractfile(path_db.name).read()  # type: ignore[attr-defined]
            with path_db.open("rb") as file:
                buf = file.read()
            self.assertNotEqual(buf_backup, buf)
        buf = None
        buf_backup = None

        portfolio.Portfolio.restore(p)

        # Files should match again
        with tarfile.open(path_backup_1, "r") as tar:
            buf_backup = tar.extractfile(path_db.name).read()  # type: ignore[attr-defined]
            with path_db.open("rb") as file:
                buf = file.read()
            self.assertEqual(buf_backup, buf)
        path_timestamp = path_db.with_name("_timestamp")
        self.assertFalse(path_timestamp.exists(), "_timestamp unexpectedly exists")

        buf = None
        buf_backup = None

        # Only the original account present
        with p.begin_session() as s:
            accounts = s.query(Account).all()
            self.assertEqual(len(accounts), 1)

        # Can't restore if wrong version requested
        self.assertRaises(FileNotFoundError, portfolio.Portfolio.restore, p, tar_ver=2)

        # Another backup should increment the version
        p.backup()

        path_backup_2 = path_db.with_suffix(".backup2.tar")

        self.assertTrue(path_backup_2.exists(), "Backup portfolio does not exist")
        self.assertEqual(path_backup_2.stat().st_mode & 0o777, 0o600)

        # Can't restore if no backup exists
        path_backup_1.unlink()
        path_backup_2.unlink()
        self.assertRaises(FileNotFoundError, portfolio.Portfolio.restore, p)

        # For encrypted portfolios, backup should include the salt
        if not encryption.AVAILABLE:
            return
        path_salt = path_db.with_suffix(".nacl")
        key = self.random_string()
        # Recreate
        path_db.unlink()
        p = portfolio.Portfolio.create(path_db, key)

        with time_machine.travel(utc_now, tick=False):
            result, tar_ver = p.backup()

        self.assertEqual(result, path_backup_1)
        self.assertEqual(tar_ver, 1)

        self.assertTrue(path_backup_1.exists(), "Backup portfolio does not exist")
        self.assertEqual(path_backup_1.stat().st_mode & 0o777, 0o600)

        with tarfile.open(path_backup_1, "r") as tar:
            buf_backup = tar.extractfile(path_salt.name).read()  # type: ignore[attr-defined]
            with path_salt.open("rb") as file:
                buf = file.read()
            self.assertEqual(buf_backup, buf)

        # Check invalid tars are invalid
        path_backup_3 = path_db.with_suffix(".backup3.tar")
        # Empty tar
        with tarfile.open(path_backup_3, "w") as tar:
            pass
        self.assertRaises(
            exc.InvalidBackupTarError,
            portfolio.Portfolio.backups,
            path_db,
        )

        # _timestamp being a directory will return None in extractfile
        with tarfile.open(path_backup_3, "w") as tar:
            info = tarfile.TarInfo("_timestamp")
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        self.assertRaises(
            exc.InvalidBackupTarError,
            portfolio.Portfolio.backups,
            path_db,
        )

        # Missing files
        with tarfile.open(path_backup_3, "w") as tar:
            pass
        self.assertRaises(
            exc.InvalidBackupTarError,
            portfolio.Portfolio.restore,
            path_db,
            3,
        )

        # Path traversal files are bad
        with tarfile.open(path_backup_3, "w") as tar:
            info = tarfile.TarInfo("_timestamp")
            tar.addfile(info)
            info = tarfile.TarInfo(path_db.name)
            tar.addfile(info)

            info = tarfile.TarInfo("../injection.sh")
            tar.addfile(info)
        self.assertRaises(
            exc.InvalidBackupTarError,
            portfolio.Portfolio.restore,
            path_db,
            3,
        )

    def test_clean(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        path_other_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)
        _ = portfolio.Portfolio.create(path_other_db)

        today = datetime.datetime.now().astimezone().date()
        today_ord = today.toordinal()

        path_dir = path_db.with_suffix(".things")
        path_dir.mkdir()

        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_other_db.exists(), "Portfolio does not exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_other_db.stat().st_mode & 0o777, 0o600)

        # Create Account
        with p.begin_session() as s:
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct)
            s.flush()

            n = query_count(s.query(Account))
            self.assertEqual(n, 1)

            a = Asset(
                name="BANANA",
                category=AssetCategory.ITEM,
            )
            s.add(a)
            s.flush()

            av = AssetValuation(
                asset_id=a.id_,
                date_ord=today_ord,
                value=self.random_decimal(0, 1),
            )
            s.add(av)
            s.flush()

            n = query_count(s.query(AssetValuation))
            self.assertEqual(n, 1)

        path_backup_1, tar_ver = p.backup()
        self.assertEqual(tar_ver, 1)
        path_backup_2, tar_ver = p.backup()
        self.assertEqual(tar_ver, 2)
        path_backup_3, tar_ver = p.backup()
        self.assertEqual(tar_ver, 3)

        # Test for real this time
        result, tar_ver = p.backup()

        path_backup_4 = path_db.with_suffix(".backup4.tar")
        self.assertEqual(result, path_backup_4)
        self.assertEqual(tar_ver, 4)

        self.assertTrue(path_backup_4.exists(), "Backup portfolio does not exist")
        self.assertEqual(path_backup_4.stat().st_mode & 0o777, 0o600)

        size_before = path_db.stat().st_size

        # Clean, expect old backups to be purged
        r_before, r_after = p.clean()

        size_after = path_db.stat().st_size
        self.assertEqual(r_before, size_before)
        self.assertEqual(r_after, size_after)

        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_other_db.exists(), "Portfolio does not exist")
        self.assertFalse(path_dir.exists(), "Portfolio things directory does exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_other_db.stat().st_mode & 0o777, 0o600)

        self.assertTrue(path_backup_1.exists(), "Backup #1 does not exist")
        self.assertFalse(path_backup_2.exists(), "Backup #2 does exist")
        self.assertFalse(path_backup_3.exists(), "Backup #3 does exist")
        self.assertFalse(path_backup_4.exists(), "Backup #4 does exist")

        # Check AssetValuations were pruned
        with p.begin_session() as s:
            n = query_count(s.query(AssetValuation))
            self.assertEqual(n, 0)

        # Validate restoring only backup goes back before the prune
        portfolio.Portfolio.restore(p)
        with p.begin_session() as s:
            n = query_count(s.query(AssetValuation))
            self.assertEqual(n, 1)

    def test_update_assets(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.datetime.now().astimezone().date()

        with p.begin_session() as s:
            # Delete index assets
            s.query(Asset).delete()
            s.flush()

            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            # Create assets
            name = "Banana Inc."
            a = Asset(name=name, category=AssetCategory.ITEM)
            a_house = Asset(name="House", category=AssetCategory.REAL_ESTATE)

            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )

            s.add_all((a, a_house, acct))
            s.flush()
            a_id = a.id_
            acct_id = acct.id_

            # Buy the house but no ticker so excluded
            txn = Transaction(
                account_id=acct.id_,
                date=today,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_house.id_,
                asset_quantity_unadjusted=1,
                category_id=categories["securities traded"],
            )
            s.add_all((txn, t_split))

        # No assets with tickers
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            result = p.update_assets()
        fake_stderr = fake_stderr.getvalue()
        self.assertIn("Updating Assets:", fake_stderr)
        self.assertEqual(result, [])

        ticker = "BANANA"
        with p.begin_session() as s:
            s.query(Asset).where(Asset.id_ == a_id).update({"ticker": ticker})

        # No assets with transactions
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            result = p.update_assets()
        fake_stderr = fake_stderr.getvalue()
        self.assertIn("Updating Assets:", fake_stderr)
        self.assertEqual(result, [])

        # Sectors were updated
        with p.begin_session() as s:
            query = (
                s.query(AssetSector)
                .with_entities(AssetSector.sector, AssetSector.weight)
                .where(AssetSector.asset_id == a_id)
            )
            sectors: dict[USSector, Decimal] = dict(query.all())  # type: ignore[attr-defined]
            target = {
                USSector.HEALTHCARE: Decimal(1),
            }
            self.assertEqual(sectors, target)

        with p.begin_session() as s:
            # Add a transaction
            date = datetime.date(2023, 5, 1)
            txn = Transaction(
                account_id=acct_id,
                date=date,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id,
                asset_quantity_unadjusted=1,
                category_id=categories["securities traded"],
            )
            s.add_all((txn, t_split))
            s.flush()
            a = s.query(Asset).where(Asset.id_ == a_id).one()
            a.update_splits()

        first_valuation_date = date - datetime.timedelta(days=7)
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            result = p.update_assets()
        target = [(name, ticker, first_valuation_date, today, None)]
        self.assertEqual(result, target)

        with p.begin_session() as s:
            # Currently holding so should include today or Friday
            last_weekday = today - datetime.timedelta(days=max(0, today.weekday() - 4))
            v = (
                s.query(AssetValuation)
                .where(AssetValuation.asset_id == a_id)
                .order_by(AssetValuation.date_ord.desc())
                .first()
            )
            self.assertEqual(v and v.date_ord, last_weekday.toordinal())

            # Sell asset so it should not include today
            txn = Transaction(
                account_id=acct_id,
                date=date,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id,
                asset_quantity_unadjusted=-1,
                category_id=categories["securities traded"],
            )
            s.add_all((txn, t_split))
            s.flush()
            a = s.query(Asset).where(Asset.id_ == a_id).one()
            a.update_splits()

        last_valuation_date = date + datetime.timedelta(days=7)
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            result = p.update_assets()
        target = [
            (name, ticker, first_valuation_date, last_valuation_date, None),
        ]
        self.assertEqual(result, target)

        with p.begin_session() as s:
            v = (
                s.query(AssetValuation)
                .where(AssetValuation.asset_id == a_id)
                .order_by(AssetValuation.date_ord.desc())
                .first()
            )
            self.assertEqual(v and v.date_ord, last_valuation_date.toordinal())

            # Bad ticker should fail nicely
            ticker = "ORANGE"
            s.query(Asset).where(Asset.id_ == a_id).update({"ticker": ticker})

        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            result = p.update_assets()
        target = [
            (
                name,
                ticker,
                None,
                None,
                "ORANGE: No timezone found, symbol may be delisted",
            ),
        ]
        self.assertEqual(result, target)

    def test_change_key(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        key = self.random_string()

        # Create encrypted portfolio
        p = portfolio.Portfolio.create(path_db, key)

        # WEB_KEY is key encrypted with key
        web_key = key
        with p.begin_session() as s:
            expected_encrypted = (
                s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
            )
            if expected_encrypted is None:
                self.fail("WEB_KEY is missing")
            expected = p.decrypt_s(expected_encrypted)
            self.assertEqual(expected, web_key)

        new_key = self.random_string()
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            p.change_key(new_key)
        with p.begin_session() as s:
            expected_encrypted = (
                s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
            )
            if expected_encrypted is None:
                self.fail("WEB_KEY is missing")
            expected = p.decrypt_s(expected_encrypted)
            self.assertEqual(expected, web_key)

        # Unlocking with new_key works
        portfolio.Portfolio(path_db, new_key)

        # Unlocking with key doesn't work
        self.assertRaises(exc.UnlockingError, portfolio.Portfolio, path_db, key)

    def test_change_web_key(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        key = self.random_string()

        # Create encrypted portfolio
        p = portfolio.Portfolio.create(path_db, key)

        with p.begin_session() as s:
            expected_encrypted = (
                s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
            )
            if expected_encrypted is None:
                self.fail("WEB_KEY is missing")
            expected = p.decrypt_s(expected_encrypted)
            self.assertEqual(expected, key)

        new_key = self.random_string()
        p.change_web_key(new_key)
        with p.begin_session() as s:
            expected_encrypted = (
                s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
            )
            if expected_encrypted is None:
                self.fail("WEB_KEY is missing")
            expected = p.decrypt_s(expected_encrypted)
            self.assertEqual(expected, new_key)
            self.assertNotEqual(expected, key)
