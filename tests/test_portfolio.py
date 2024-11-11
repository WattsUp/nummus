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

from nummus import encryption
from nummus import exceptions as exc
from nummus import importers, models, portfolio, sql, version
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetValuation,
    Config,
    ConfigKey,
    Transaction,
    TransactionCategory,
    TransactionSplit,
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
        path_ssl = path_db.parent.joinpath("portfolio.ssl")

        # Create unencrypted portfolio
        p = portfolio.Portfolio.create(path_db)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertFalse(path_salt.exists(), "Salt unexpectedly exists")
        self.assertTrue(path_importers.exists(), "importers does not exist")
        self.assertTrue(path_importers.is_dir(), "importers is not a directory")
        self.assertTrue(path_ssl.exists(), "ssl does not exist")
        self.assertTrue(path_ssl.is_dir(), "ssl is not a directory")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_ssl.stat().st_mode & 0o777, 0o700)
        self.assertEqual(p.importers_path, path_importers)
        self.assertEqual(p.path, path_db)
        self.assertEqual(p.ssl_cert_path, path_ssl.joinpath("cert.pem"))
        self.assertEqual(p.ssl_key_path, path_ssl.joinpath("key.pem"))

        self.assertRaises(exc.NotEncryptedError, p.encrypt, "")
        self.assertRaises(exc.NotEncryptedError, p.decrypt, "")

        # Check config contains valid cipher and version
        with p.get_session() as s:
            value: str = (
                s.query(Config.value).where(Config.key == ConfigKey.CIPHER).one()
            )[0]
            models.Cipher.from_bytes(base64.b64decode(value))

            value: str = (
                s.query(Config.value).where(Config.key == ConfigKey.VERSION).one()
            )[0]
            self.assertEqual(value, str(version.__version__))

            n = s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).count()
            self.assertEqual(n, 1)

            n = s.query(Config).where(Config.key == ConfigKey.SECRET_KEY).count()
            self.assertEqual(n, 1)

        p = None
        sql.drop_session()

        # Check portfolio is unencrypted
        with path_db.open("rb") as file:
            buf = file.read()
            target = b"SQLite format 3"
            self.assertEqual(buf[: len(target)], target)
            buf = None  # Clear local buffer
        self.assertFalse(
            portfolio.Portfolio.is_encrypted(path_db),
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
        with p.get_session() as s:
            # Good, now delete cipher
            s.query(Config).where(Config.key == ConfigKey.CIPHER).delete()
            s.commit()

        # Missing cipher
        self.assertRaises(
            exc.ProtectedObjectNotFoundError,
            portfolio.Portfolio,
            path_db,
            None,
        )

        with p.get_session() as s:
            # Good, now change encryption test value
            c = s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).one()
            c.value = self.random_string()
            s.commit()

        # Invalid encryption test
        self.assertRaises(exc.UnlockingError, portfolio.Portfolio, path_db, None)

        # Recreate
        path_db.unlink()

        portfolio.Portfolio.create(path_db)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        sql.drop_session()

        # Delete encryption test
        p = portfolio.Portfolio(path_db, None)
        with p.get_session() as s:
            s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).delete()
            s.commit()

        # Missing root password
        self.assertRaises(exc.UnlockingError, portfolio.Portfolio, path_db, None)

    def test_create_encrypted(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_salt = path_db.with_suffix(".nacl")
        path_ssl = path_db.parent.joinpath("portfolio.ssl")

        key = self.random_string()

        # Create encrypted portfolio
        p = portfolio.Portfolio.create(path_db, key)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_salt.exists(), "Salt does not exist")
        self.assertTrue(path_ssl.exists(), "ssl does not exist")
        self.assertTrue(path_ssl.is_dir(), "ssl is not a directory")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_ssl.stat().st_mode & 0o777, 0o700)

        secret = self.random_string()
        enc_secret = p.encrypt(secret)
        result = p.decrypt_s(enc_secret)
        self.assertEqual(result, secret)

        p = None
        sql.drop_session()

        # Check portfolio is encrypted
        with path_db.open("rb") as file:
            buf = file.read()
            target = b"SQLite format 3"
            self.assertNotEqual(buf[: len(target)], target)
            buf = None  # Clear local buffer
        self.assertTrue(
            portfolio.Portfolio.is_encrypted(path_db),
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
        with p.get_session() as s:
            # Good, now change encryption test value
            c = s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).one()
            c.value = p.encrypt(secrets.token_bytes())
            s.commit()

        # Invalid root password
        self.assertRaises(exc.UnlockingError, portfolio.Portfolio, path_db, key)

    def test_is_encrypted(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_salt = path_db.with_suffix(".nacl")

        self.assertRaises(FileNotFoundError, portfolio.Portfolio.is_encrypted, path_db)

        with path_db.open("w", encoding="utf-8") as file:
            file.write("I'm a database")

        self.assertFalse(
            portfolio.Portfolio.is_encrypted(path_db),
            "Database is unexpectedly encrypted",
        )

        path_salt.touch()
        self.assertTrue(
            portfolio.Portfolio.is_encrypted(path_db),
            "Database is unexpectedly unencrypted",
        )

    def test_find_account(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        result = p.find_account("Monkey Bank Checking")
        self.assertIsNone(result)

        with p.get_session() as s:
            # Create accounts
            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                number="MONKEY-0123",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            acct_invest_0 = Account(
                name="Primate Investments",
                institution="Monkey Bank",
                number="MONKEY-9999",
                category=AccountCategory.INVESTMENT,
                closed=False,
                budgeted=True,
            )
            acct_invest_1 = Account(
                name="Primate Investments",
                institution="Gorilla Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
                budgeted=True,
            )
            s.add_all((acct_checking, acct_invest_0, acct_invest_1))
            s.commit()

            # Find by ID, kinda redundant but lol: id = find(id)
            result = p.find_account(acct_checking.id_)
            self.assertEqual(result, acct_checking.id_)
            result = p.find_account(acct_invest_0.id_)
            self.assertEqual(result, acct_invest_0.id_)
            result = p.find_account(acct_invest_1.id_)
            self.assertEqual(result, acct_invest_1.id_)
            result = p.find_account(10)
            self.assertIsNone(result)

            # Find by URI
            result = p.find_account(acct_checking.uri)
            self.assertEqual(result, acct_checking.id_)

            # No match with random URI
            result = p.find_account(Account.id_to_uri(0x0FFFFFFF))
            self.assertIsNone(result)

            # Find by number
            result = p.find_account("MONKEY-0123")
            self.assertEqual(result, acct_checking.id_)

            # Find by name
            result = p.find_account("Monkey Bank Checking")
            self.assertEqual(result, acct_checking.id_)

            # More than 1 match by name
            result = p.find_account("Primate Investments")
            self.assertIsNone(result)

            # Find by institution
            result = p.find_account("Gorilla Bank")
            self.assertEqual(result, acct_invest_1.id_)

    def test_find_asset(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        result = p.find_asset("BANANA")
        self.assertIsNone(result)

        with p.get_session() as s:
            # Create assets
            a_banana = Asset(name="Banana", category=AssetCategory.ITEM)
            a_apple_0 = Asset(name="Apple", category=AssetCategory.ITEM)
            a_apple_1 = Asset(
                name="Tech Company",
                category=AssetCategory.STOCKS,
                ticker="APPLE",
            )
            s.add_all((a_banana, a_apple_0, a_apple_1))
            s.commit()

            # Find by ID, kinda redundant but lol: id = find(id)
            result = p.find_asset(a_banana.id_)
            self.assertEqual(result, a_banana.id_)
            result = p.find_asset(a_apple_0.id_)
            self.assertEqual(result, a_apple_0.id_)
            result = p.find_asset(a_apple_1.id_)
            self.assertEqual(result, a_apple_1.id_)
            result = p.find_asset(10)
            self.assertIsNone(result)

            # Find by URI
            result = p.find_asset(a_banana.uri)
            self.assertEqual(result, a_banana.id_)

            # No match with random URI
            result = p.find_asset(Asset.id_to_uri(0x0FFFFFFF))
            self.assertIsNone(result)

            # Find by name
            result = p.find_asset("Banana")
            self.assertEqual(result, a_banana.id_)

            # Find by ticker
            result = p.find_asset("APPLE")
            self.assertEqual(result, a_apple_1.id_)

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
        self.assertRaises(KeyError, p.import_file, path, path_debug)
        self.assertTrue(path_debug.exists(), "Debug file unexpectedly does not exists")
        path_debug.unlink()

        with p.get_session() as s:
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
            s.commit()

            # Still missing assets
            self.assertRaises(KeyError, p.import_file, path, path_debug)
            self.assertTrue(
                path_debug.exists(),
                "Debug file unexpectedly does not exists",
            )
            path_debug.unlink()

            asset = Asset(name="BANANA", category=AssetCategory.STOCKS)
            s.add(asset)
            s.commit()
            a_id = asset.id_

            # We good now
            p.import_file(path, path_debug)
            self.assertFalse(path_debug.exists(), "Debug file unexpectedly exists")

            transactions = s.query(Transaction).all()

            target = TRANSACTIONS_EXTRAS
            self.assertEqual(len(transactions), len(target))
            for tgt, res in zip(target, transactions, strict=True):
                if tgt["account"] == "Monkey Bank Checking":
                    tgt_acct_id = acct_checking.id_
                else:
                    tgt_acct_id = acct_invest.id_
                self.assertEqual(res.account_id, tgt_acct_id)
                self.assertEqual(res.date_ord, tgt["date"].toordinal())
                self.assertEqual(res.amount, tgt["amount"])
                statement = tgt["statement"] or "Asset Transaction BANANA"
                self.assertEqual(res.statement, statement)

                self.assertEqual(len(res.splits), 1)
                r_split = res.splits[0]
                self.assertEqual(r_split.amount, tgt["amount"])
                self.assertEqual(r_split.description, tgt["description"])
                cat_id = (
                    s.query(TransactionCategory.id_)
                    .where(
                        TransactionCategory.name
                        == (tgt["category"] or "Uncategorized"),
                    )
                    .one()[0]
                )
                self.assertEqual(r_split.category_id, cat_id)
                self.assertEqual(r_split.tag, tgt["tag"])
                asset_id = asset.id_ if tgt["asset"] else None
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

            # Unlink one so it'll link
            txn = (
                s.query(Transaction).where(Transaction.amount == Decimal("1000")).one()
            )
            txn.linked = False
            txn.statement = "Overwrite me"
            t_split = (
                s.query(TransactionSplit)
                .where(TransactionSplit.parent_id == txn.id_)
                .one()
            )
            t_split.parent = txn
            t_split.description = "Don't overwrite me"
            s.commit()

            # But it will work with force
            p.import_file(path, path_debug, force=True)
            self.assertFalse(path_debug.exists(), "Debug file unexpectedly exists")

            self.assertTrue(txn.linked, "Transaction did not link")
            self.assertTrue(t_split.linked, "TransactionSplit did not link")
            self.assertNotEqual(txn.statement, "Overwrite me")
            self.assertEqual(t_split.description, "Don't overwrite me")

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

            # Fail unknown category
            path = self._DATA_ROOT.joinpath("transactions_bad_category.csv")
            self.assertRaises(
                exc.UnknownCategoryError,
                p.import_file,
                path,
                path_debug,
            )

            # Clear transactions
            s.query(TransactionSplit).delete()
            s.query(Transaction).delete()
            s.commit()

            # Import investment transactions
            path = self._DATA_ROOT.joinpath("transactions_investments.csv")
            p.import_file(path, path_debug)

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
                        categories["Securities Traded"],
                    )

                    t_split = splits[1]
                    self.assertEqual(t_split.amount, Decimal("1234.56"))
                    self.assertEqual(t_split.asset_quantity, 0)
                    self.assertEqual(t_split.asset_id, a_id)
                    self.assertEqual(
                        t_split.category_id,
                        categories["Dividends Received"],
                    )
                elif txn.statement == "Cash Maker":
                    # Cash Dividends
                    t_split = splits[0]
                    self.assertEqual(t_split.amount, Decimal("1234.56"))
                    self.assertEqual(t_split.asset_quantity, 0)
                    self.assertEqual(t_split.asset_id, a_id)
                    self.assertEqual(
                        t_split.category_id,
                        categories["Dividends Received"],
                    )
                else:
                    # Fees
                    t_split = splits[0]
                    self.assertEqual(t_split.amount, Decimal("-900"))
                    self.assertEqual(t_split.asset_quantity, 0)
                    self.assertEqual(t_split.asset_id, a_id)
                    self.assertEqual(
                        t_split.category_id,
                        categories["Investment Fees"],
                    )

                    t_split = splits[1]
                    self.assertEqual(t_split.amount, Decimal("900"))
                    self.assertEqual(t_split.asset_quantity, Decimal("-32.1234"))
                    self.assertEqual(t_split.asset_id, a_id)
                    self.assertEqual(
                        t_split.category_id,
                        categories["Securities Traded"],
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
        with p.get_session() as s:
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct)
            s.commit()

            accounts = s.query(Account).all()
            self.assertEqual(len(accounts), 1)

        # Get list of backups
        result = portfolio.Portfolio.backups(path_db)
        self.assertEqual(len(result), 0)

        with time_machine.travel(utc_now, tick=False):
            result, tar_ver = p.backup()

        path_backup_1 = path_db.with_suffix(".backup1.tar.gz")
        self.assertEqual(result, path_backup_1)
        self.assertEqual(tar_ver, 1)

        self.assertTrue(path_backup_1.exists(), "Backup portfolio does not exist")
        self.assertEqual(path_backup_1.stat().st_mode & 0o777, 0o600)

        with tarfile.open(path_backup_1, "r:gz") as tar:
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
        with p.get_session() as s:
            acct = Account(
                name="Monkey Bank Checking Duplicate",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct)
            s.commit()

            accounts = s.query(Account).all()
            self.assertEqual(len(accounts), 2)

        with tarfile.open(path_backup_1, "r:gz") as tar:
            buf_backup = tar.extractfile(path_db.name).read()  # type: ignore[attr-defined]
            with path_db.open("rb") as file:
                buf = file.read()
            self.assertNotEqual(buf_backup, buf)
        buf = None
        buf_backup = None

        portfolio.Portfolio.restore(p)

        # Files should match again
        with tarfile.open(path_backup_1, "r:gz") as tar:
            buf_backup = tar.extractfile(path_db.name).read()  # type: ignore[attr-defined]
            with path_db.open("rb") as file:
                buf = file.read()
            self.assertEqual(buf_backup, buf)
        path_timestamp = path_db.with_name("_timestamp")
        self.assertFalse(path_timestamp.exists(), "_timestamp unexpectedly exists")

        buf = None
        buf_backup = None

        # Only the original account present
        with p.get_session() as s:
            accounts = s.query(Account).all()
            self.assertEqual(len(accounts), 1)

        # Can't restore if wrong version requested
        self.assertRaises(FileNotFoundError, portfolio.Portfolio.restore, p, tar_ver=2)

        # Another backup should increment the version
        p.backup()

        path_backup_2 = path_db.with_suffix(".backup2.tar.gz")

        self.assertTrue(path_backup_2.exists(), "Backup portfolio does not exist")
        self.assertEqual(path_backup_2.stat().st_mode & 0o777, 0o600)

        # Can't restore if no backup exists
        path_backup_1.unlink()
        path_backup_2.unlink()
        self.assertRaises(FileNotFoundError, portfolio.Portfolio.restore, p)

        # Backups should include the SSL certs
        path_cert = p.ssl_cert_path
        path_key = p.ssl_key_path
        path_cert_rel = str(path_cert.relative_to(self._TEST_ROOT))
        path_key_rel = str(path_key.relative_to(self._TEST_ROOT))
        ssl_cert = self.random_string().encode()
        ssl_key = self.random_string().encode()

        with path_cert.open("wb") as file:
            file.write(ssl_cert)
        with path_key.open("wb") as file:
            file.write(ssl_key)

        p.backup()
        with tarfile.open(path_backup_1, "r:gz") as tar:
            buf_backup = tar.extractfile(path_cert_rel).read()  # type: ignore[attr-defined]
            self.assertEqual(buf_backup, ssl_cert)
            buf_backup = tar.extractfile(path_key_rel).read()  # type: ignore[attr-defined]
            self.assertEqual(buf_backup, ssl_key)
        buf_backup = None

        path_db.unlink()
        path_cert.unlink()
        path_key.unlink()

        # Restoring brings certs back too
        portfolio.Portfolio.restore(path_db)

        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_cert.exists(), "SSL cert does not exist")
        self.assertTrue(path_key.exists(), "SSL key does not exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)

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

        self.assertEqual(result, path_backup_2)
        self.assertEqual(tar_ver, 2)

        self.assertTrue(path_backup_2.exists(), "Backup portfolio does not exist")
        self.assertEqual(path_backup_2.stat().st_mode & 0o777, 0o600)

        with tarfile.open(path_backup_2, "r:gz") as tar:
            buf_backup = tar.extractfile(path_salt.name).read()  # type: ignore[attr-defined]
            with path_salt.open("rb") as file:
                buf = file.read()
            self.assertEqual(buf_backup, buf)

        # Check invalid tars are invalid
        path_backup_3 = path_db.with_suffix(".backup3.tar.gz")
        # Empty tar
        with tarfile.open(path_backup_3, "w:gz") as tar:
            pass
        self.assertRaises(
            exc.InvalidBackupTarError,
            portfolio.Portfolio.backups,
            path_db,
        )

        # _timestamp being a directory will return None in extractfile
        with tarfile.open(path_backup_3, "w:gz") as tar:
            info = tarfile.TarInfo("_timestamp")
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        self.assertRaises(
            exc.InvalidBackupTarError,
            portfolio.Portfolio.backups,
            path_db,
        )

        # Missing files
        with tarfile.open(path_backup_3, "w:gz") as tar:
            pass
        self.assertRaises(
            exc.InvalidBackupTarError,
            portfolio.Portfolio.restore,
            path_db,
            3,
        )

        # Path traversal files are bad
        with tarfile.open(path_backup_3, "w:gz") as tar:
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

        today = datetime.date.today()
        today_ord = today.toordinal()

        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_other_db.exists(), "Portfolio does not exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_other_db.stat().st_mode & 0o777, 0o600)

        # Create Account
        with p.get_session() as s:
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct)
            s.commit()

            n = s.query(Account).count()
            self.assertEqual(n, 1)

            a = Asset(
                name="BANANA",
                category=AssetCategory.ITEM,
            )
            s.add(a)
            s.commit()

            av = AssetValuation(
                asset_id=a.id_,
                date_ord=today_ord,
                value=self.random_decimal(0, 1),
            )
            s.add(av)
            s.commit()

            n = s.query(AssetValuation).count()
            self.assertEqual(n, 1)

        path_backup_1, tar_ver = p.backup()
        self.assertEqual(tar_ver, 1)
        path_backup_2, tar_ver = p.backup()
        self.assertEqual(tar_ver, 2)
        path_backup_3, tar_ver = p.backup()
        self.assertEqual(tar_ver, 3)

        # Test for real this time
        result, tar_ver = p.backup()

        path_backup_4 = path_db.with_suffix(".backup4.tar.gz")
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
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_other_db.stat().st_mode & 0o777, 0o600)

        self.assertTrue(path_backup_1.exists(), "Backup #1 does not exist")
        self.assertFalse(path_backup_2.exists(), "Backup #2 does exist")
        self.assertFalse(path_backup_3.exists(), "Backup #3 does exist")
        self.assertFalse(path_backup_4.exists(), "Backup #4 does exist")

        # Check AssetValuations were pruned
        with p.get_session() as s:
            n = s.query(AssetValuation).count()
            self.assertEqual(n, 0)

        # Validate restoring only backup goes back before the prune
        portfolio.Portfolio.restore(p)
        with p.get_session() as s:
            n = s.query(AssetValuation).count()
            self.assertEqual(n, 1)

    def test_update_assets(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()

        with p.get_session() as s:
            # Delete index assets
            s.query(Asset).delete()
            s.commit()

            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            # Create assets
            a = Asset(name="Banana Inc.", category=AssetCategory.ITEM)
            a_house = Asset(name="House", category=AssetCategory.REAL_ESTATE)

            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )

            s.add_all((a, a_house, acct))
            s.commit()

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
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))
            s.commit()

            # No assets with tickers
            with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
                result = p.update_assets()
            fake_stderr = fake_stderr.getvalue()
            self.assertIn("Updating Assets:", fake_stderr)
            self.assertEqual(result, [])

            a.ticker = "BANANA"
            s.commit()

            # No assets with transactions
            with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
                result = p.update_assets()
            fake_stderr = fake_stderr.getvalue()
            self.assertIn("Updating Assets:", fake_stderr)
            self.assertEqual(result, [])

            # Add a transaction
            date = datetime.date(2023, 5, 1)
            txn = Transaction(
                account_id=acct.id_,
                date=date,
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
            with mock.patch("sys.stderr", new=io.StringIO()) as _:
                result = p.update_assets()
            target = [(a.name, a.ticker, first_valuation_date, today, None)]
            self.assertEqual(result, target)

            # Currently holding so should include today or Friday
            last_weekday = today - datetime.timedelta(days=max(0, today.weekday() - 4))
            v = (
                s.query(AssetValuation)
                .where(AssetValuation.asset_id == a.id_)
                .order_by(AssetValuation.date_ord.desc())
                .first()
            )
            self.assertEqual(v and v.date_ord, last_weekday.toordinal())

            # Sell asset so it should not include today
            txn = Transaction(
                account_id=acct.id_,
                date=date,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a.id_,
                asset_quantity_unadjusted=-1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))
            s.commit()
            a.update_splits()
            s.commit()

            last_valuation_date = date + datetime.timedelta(days=7)
            with mock.patch("sys.stderr", new=io.StringIO()) as _:
                result = p.update_assets()
            target = [
                (a.name, a.ticker, first_valuation_date, last_valuation_date, None),
            ]
            self.assertEqual(result, target)

            v = (
                s.query(AssetValuation)
                .where(AssetValuation.asset_id == a.id_)
                .order_by(AssetValuation.date_ord.desc())
                .first()
            )
            self.assertEqual(v and v.date_ord, last_valuation_date.toordinal())

            # Bad ticker should fail nicely
            a.ticker = "ORANGE"
            s.commit()

            with mock.patch("sys.stderr", new=io.StringIO()) as _:
                result = p.update_assets()
            target = [
                (
                    a.name,
                    a.ticker,
                    None,
                    None,
                    "ORANGE: No timezone found, symbol may be delisted",
                ),
            ]
            self.assertEqual(result, target)

    def test_find_similar_transactions(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()

        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            acct_0 = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            acct_1 = Account(
                name="Monkey Bank Credit",
                institution="Monkey Bank",
                category=AccountCategory.CREDIT,
                closed=False,
                budgeted=True,
            )
            s.add_all((acct_0, acct_1))
            s.commit()

            txn_0 = Transaction(
                account_id=acct_0.id_,
                date=today,
                amount=100,
                statement="Banana Store",
            )
            t_split_0 = TransactionSplit(
                amount=txn_0.amount,
                parent=txn_0,
                category_id=categories["Uncategorized"],
            )

            s.add_all((txn_0, t_split_0))
            s.commit()

            txn_1 = Transaction(
                account_id=acct_0.id_,
                date=today,
                amount=100,
                statement="Banana Store",
            )
            t_split_1 = TransactionSplit(
                amount=txn_1.amount,
                parent=txn_1,
                category_id=categories["Uncategorized"],
            )
            s.add_all((txn_1, t_split_1))
            s.commit()

            txn_2 = Transaction(
                account_id=acct_1.id_,
                date=today,
                amount=100,
                statement="Banana Store",
            )
            t_split_2 = TransactionSplit(
                amount=txn_2.amount,
                parent=txn_2,
                category_id=categories["Uncategorized"],
            )
            s.add_all((txn_2, t_split_2))
            s.commit()

            # None are locked so no candidates at all
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertIsNone(result)

            txn_1.locked = True
            txn_2.locked = True
            txn_1.linked = True
            txn_2.linked = True

            # txn_0 and txn_1 have same statement and same account
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertEqual(result, txn_1.id_)

            # do_commit=False means it isn't cached
            self.assertIsNone(txn_0.similar_txn_id)

            # txn_1 amount is outside limits, should match txn_2
            txn_1.amount = Decimal(10)
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertEqual(result, txn_2.id_)

            # txn_2 amount is outside limits but further away, should match txn_1
            txn_2.amount = Decimal(9)
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertEqual(result, txn_1.id_)

            # Different statement, both outside amount range
            txn_0.statement = "Gas station 1234"
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertIsNone(result)

            # No fuzzy matches at all and no amounts close
            txn_0.amount = Decimal(1000)
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertIsNone(result)

            # No fuzzy matches at all but amount if close enough
            # txn_2 is closer but txn_1 is same account
            txn_0.amount = Decimal(8)
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertEqual(result, txn_1.id_)

            # Make fuzzy close, txn_1 is same account so more points
            txn_1.statement = "Gas station 5678"
            txn_2.statement = "gas station 90"
            txn_1.amount = Decimal(9)
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertEqual(result, txn_1.id_)

            # Cannot match if a split has an asset_linked
            t_split_1.category_id = categories["Securities Traded"]
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertEqual(result, txn_2.id_)

            t_split_2.category_id = categories["Securities Traded"]
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=False)
            self.assertIsNone(result)

            t_split_1.category_id = categories["Uncategorized"]
            t_split_2.category_id = categories["Uncategorized"]
            s.commit()

            # txn_2 is closer so more points being closer
            txn_2.amount = Decimal(8.5)
            txn_2.account_id = acct_0.id_
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=True)
            self.assertEqual(result, txn_2.id_)
            self.assertEqual(txn_0.similar_txn_id, txn_2.id_)

            # Even though txn_1 is exact statement match, cache is used
            txn_1.statement = "Gas station 1234"
            s.commit()
            result = p.find_similar_transaction(txn_0, do_commit=True)
            self.assertEqual(result, txn_2.id_)
            self.assertEqual(txn_0.similar_txn_id, txn_2.id_)

            # Force not using cache will update similar
            result = p.find_similar_transaction(txn_0, do_commit=True, cache_ok=False)
            self.assertEqual(result, txn_1.id_)
            self.assertEqual(txn_0.similar_txn_id, txn_1.id_)
