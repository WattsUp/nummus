"""Test module nummus.portfolio
"""

import tarfile
import uuid

import autodict

from nummus import portfolio, sql
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    Credentials,
    Transaction,
    TransactionCategory,
)
from tests.base import TestBase
from tests.importers.test_raw_csv import TRANSACTIONS_EXTRAS


class TestPortfolio(TestBase):
    """Test Portfolio class"""

    def test_init_properties(self):
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_config = path_db.with_suffix(".config")

        path_db.parent.mkdir(parents=True, exist_ok=True)

        # Database does not exist
        self.assertRaises(FileNotFoundError, portfolio.Portfolio, path_db, None)

        # Create database file
        with open(path_db, "w", encoding="utf-8") as file:
            file.write("Not a db")

        # Still missing config
        self.assertRaises(FileNotFoundError, portfolio.Portfolio, path_db, None)

        # Make config
        autodict.JSONAutoDict(path_config).save()

        # Failed to unlock
        self.assertRaises(TypeError, portfolio.Portfolio, path_db, None)

    def test_create_unencrypted(self):
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_config = path_db.with_suffix(".config")
        path_images = path_db.parent.joinpath("portfolio.images")
        path_ssl = path_db.parent.joinpath("portfolio.ssl")

        # Create unencrypted portfolio
        p = portfolio.Portfolio.create(path_db)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_config.exists(), "Config does not exist")
        self.assertTrue(path_images.exists(), "images does not exist")
        self.assertTrue(path_images.is_dir(), "images is not a directory")
        self.assertTrue(path_ssl.exists(), "ssl does not exist")
        self.assertTrue(path_ssl.is_dir(), "ssl is not a directory")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_images.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path_ssl.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path_images, p.image_path)
        self.assertEqual(path_db, p.path)
        self.assertEqual(path_ssl.joinpath("cert.pem"), p.ssl_cert_path)
        self.assertEqual(path_ssl.joinpath("key.pem"), p.ssl_key_path)
        p = None
        sql.drop_session()

        # Check portfolio is unencrypted
        with open(path_db, "rb") as file:
            buf = file.read()
            target = b"SQLite format 3"
            self.assertEqual(target, buf[: len(target)])
            buf = None  # Clear local buffer
        self.assertFalse(
            portfolio.Portfolio.is_encrypted(path_db),
            "Database is unexpectedly encrypted",
        )

        # Database already exists
        self.assertRaises(FileExistsError, portfolio.Portfolio.create, path_db)

        # Reopen portfolio
        p = portfolio.Portfolio(path_db, None)
        with p.get_session() as s:
            # Good, now change root password
            user: Credentials = (
                s.query(Credentials)
                .where(
                    Credentials.site
                    == p._NUMMUS_SITE,  # pylint: disable=protected-access
                    Credentials.user == p._NUMMUS_USER,
                )
                .first()
            )  # pylint: disable=protected-access
            user.password = self.random_string()
            s.commit()

        # Invalid root password
        self.assertRaises(ValueError, portfolio.Portfolio, path_db, None)

        # Recreate
        path_db.unlink()
        path_config.unlink()

        portfolio.Portfolio.create(path_db)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_config.exists(), "Config does not exist")
        sql.drop_session()

        # Delete root
        p = portfolio.Portfolio(path_db, None)
        with p.get_session() as s:
            user: Credentials = (
                s.query(Credentials)
                .where(
                    Credentials.site
                    == p._NUMMUS_SITE,  # pylint: disable=protected-access
                    Credentials.user == p._NUMMUS_USER,
                )
                .first()
            )  # pylint: disable=protected-access
            s.delete(user)
            s.commit()

        # Missing root password
        self.assertRaises(KeyError, portfolio.Portfolio, path_db, None)

    def test_create_encrypted(self):
        if portfolio.encryption is None:
            self.skipTest("Encryption is not installed")

        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_config = path_db.with_suffix(".config")
        path_images = path_db.parent.joinpath("portfolio.images")
        path_ssl = path_db.parent.joinpath("portfolio.ssl")

        key = self.random_string()

        # Create unencrypted portfolio
        portfolio.Portfolio.create(path_db, key)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_config.exists(), "Config does not exist")
        self.assertTrue(path_images.exists(), "images does not exist")
        self.assertTrue(path_images.is_dir(), "images is not a directory")
        self.assertTrue(path_ssl.exists(), "ssl does not exist")
        self.assertTrue(path_ssl.is_dir(), "ssl is not a directory")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_images.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path_ssl.stat().st_mode & 0o777, 0o700)
        sql.drop_session()

        # Check portfolio is encrypted
        with open(path_db, "rb") as file:
            buf = file.read()
            target = b"SQLite format 3"
            self.assertNotEqual(target, buf[: len(target)])
            buf = None  # Clear local buffer
        self.assertTrue(
            portfolio.Portfolio.is_encrypted(path_db),
            "Database is unexpectedly unencrypted",
        )

        # Database already exists
        self.assertRaises(FileExistsError, portfolio.Portfolio.create, path_db)

        # Bad key
        self.assertRaises(TypeError, portfolio.Portfolio, path_db, self.random_string())

        # Reopen portfolio
        p = portfolio.Portfolio(path_db, key)
        with p.get_session() as s:
            # Good, now change root password
            user: Credentials = (
                s.query(Credentials)
                .where(
                    Credentials.site
                    == p._NUMMUS_SITE,  # pylint: disable=protected-access
                    Credentials.user == p._NUMMUS_USER,
                )
                .first()
            )  # pylint: disable=protected-access
            user.password = p._enc.encrypt(
                self.random_string().encode()
            )  # pylint: disable=protected-access
            s.commit()

        # Invalid root password
        self.assertRaises(ValueError, portfolio.Portfolio, path_db, key)

        # Recreate
        path_db.unlink()
        path_config.unlink()
        portfolio.Portfolio.create(path_db, key)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_config.exists(), "Config does not exist")
        sql.drop_session()

        # Change root password to unencrypted
        p = portfolio.Portfolio(path_db, key)
        with p.get_session() as s:
            # Good, now change root password
            user: Credentials = (
                s.query(Credentials)
                .where(
                    Credentials.site
                    == p._NUMMUS_SITE,  # pylint: disable=protected-access
                    Credentials.user == p._NUMMUS_USER,
                )
                .first()
            )  # pylint: disable=protected-access
            user.password = key
            s.commit()

        # Invalid unencrypted password
        self.assertRaises(PermissionError, portfolio.Portfolio, path_db, key)

    def test_is_encrypted(self):
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_config = path_db.with_suffix(".config")

        self.assertRaises(FileNotFoundError, portfolio.Portfolio.is_encrypted, path_db)

        with open(path_db, "w", encoding="utf-8") as file:
            file.write("I'm a database")

        # Still missing config
        self.assertRaises(FileNotFoundError, portfolio.Portfolio.is_encrypted, path_db)

        with autodict.JSONAutoDict(path_config) as c:
            c["encrypt"] = True

        self.assertTrue(
            portfolio.Portfolio.is_encrypted(path_db),
            "Database is unexpectedly unencrypted",
        )

        with autodict.JSONAutoDict(path_config) as c:
            c["encrypt"] = False

        self.assertFalse(
            portfolio.Portfolio.is_encrypted(path_db),
            "Database is unexpectedly encrypted",
        )

        path_db.unlink()

    def test_find_account(self):
        path_db = self._TEST_ROOT.joinpath(f"{uuid.uuid4()}.db")
        p = portfolio.Portfolio.create(path_db)

        result = p.find_account("Monkey Bank Checking")
        self.assertIsNone(result)

        with p.get_session() as s:
            # Create accounts
            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
            )
            acct_invest_0 = Account(
                name="Primate Investments",
                institution="Monkey Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
            )
            acct_invest_1 = Account(
                name="Primate Investments",
                institution="Gorilla Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
            )
            s.add_all((acct_checking, acct_invest_0, acct_invest_1))
            s.commit()

            # Find by ID, kinda redundant but lol: id = find(id)
            result = p.find_account(acct_checking.id)
            self.assertEqual(acct_checking.id, result)
            result = p.find_account(acct_invest_0.id)
            self.assertEqual(acct_invest_0.id, result)
            result = p.find_account(acct_invest_1.id)
            self.assertEqual(acct_invest_1.id, result)
            result = p.find_account(10)
            self.assertIsNone(result)

            # Find by UUID
            result = p.find_account(acct_checking.uuid)
            self.assertEqual(acct_checking.id, result)

            # Find by name
            result = p.find_account("Monkey Bank Checking")
            self.assertEqual(acct_checking.id, result)

            # More than 1 match by name
            result = p.find_account("Primate Investments")
            self.assertIsNone(result)

            # Find by institution
            result = p.find_account("Gorilla Bank")
            self.assertEqual(acct_invest_1.id, result)

    def test_find_asset(self):
        path_db = self._TEST_ROOT.joinpath(f"{uuid.uuid4()}.db")
        p = portfolio.Portfolio.create(path_db)

        result = p.find_asset("BANANA")
        self.assertIsNone(result)

        with p.get_session() as s:
            # Create assets
            a_banana = Asset(name="BANANA", category=AssetCategory.ITEM)
            a_apple_0 = Asset(name="APPLE", category=AssetCategory.ITEM)
            a_apple_1 = Asset(name="APPLE", category=AssetCategory.SECURITY)
            s.add_all((a_banana, a_apple_0, a_apple_1))
            s.commit()

            # Find by ID, kinda redundant but lol: id = find(id)
            result = p.find_asset(a_banana.id)
            self.assertEqual(a_banana.id, result)
            result = p.find_asset(a_apple_0.id)
            self.assertEqual(a_apple_0.id, result)
            result = p.find_asset(a_apple_1.id)
            self.assertEqual(a_apple_1.id, result)
            result = p.find_asset(10)
            self.assertIsNone(result)

            # Find by UUID
            result = p.find_asset(a_banana.uuid)
            self.assertEqual(a_banana.id, result)

            # Find by name
            result = p.find_asset("BANANA")
            self.assertEqual(a_banana.id, result)

            # More than 1 match by name
            result = p.find_asset("APPLE")
            self.assertIsNone(result)

    def test_import_file(self):
        path_db = self._TEST_ROOT.joinpath(f"{uuid.uuid4()}.db")
        p = portfolio.Portfolio.create(path_db)

        # Fail to import non-importable file
        path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
        self.assertRaises(TypeError, p.import_file, path)

        # Fail to match Accounts and Assets
        path = self._DATA_ROOT.joinpath("transactions_extras.csv")
        self.assertRaises(KeyError, p.import_file, path)

        with p.get_session() as s:
            # Create accounts
            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
            )
            acct_invest = Account(
                name="Monkey Investments",
                institution="Monkey Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
            )
            s.add_all((acct_checking, acct_invest))
            s.commit()

            # Still missing assets
            self.assertRaises(KeyError, p.import_file, path)

            asset = Asset(name="BANANA", category=AssetCategory.SECURITY)
            s.add(asset)
            s.commit()

            # We good now
            p.import_file(path)

            transactions = s.query(Transaction).all()

            target = TRANSACTIONS_EXTRAS
            self.assertEqual(len(target), len(transactions))
            split_properties = [
                "payee",
                "description",
                "category",
                "tag",
                "asset",
                "asset_quantity",
                "asset_id",
            ]
            for tgt, res in zip(target, transactions):
                self.assertEqual(1, len(res.splits))
                r_split = res.splits[0]
                for k, t_v in tgt.items():
                    # Fix test value for linked properties
                    if k == "asset":
                        k = "asset_id"
                        t_v = asset.id
                    elif k == "account":
                        k = "account_id"
                        if t_v == "Monkey Bank Checking":
                            t_v = acct_checking.id
                        else:
                            t_v = acct_invest.id

                    if k == "category":
                        cat_id = r_split.category_id
                        r_v = (
                            s.query(TransactionCategory)
                            .where(TransactionCategory.id == cat_id)
                            .first()
                        )
                        self.assertEqual(t_v, r_v.name)
                    elif k in split_properties:
                        r_v = getattr(r_split, k)
                        self.assertEqual(t_v, r_v)
                    elif k == "amount":
                        self.assertEqual(t_v, res.amount)
                        self.assertEqual(t_v, r_split.amount)
                    else:
                        r_v = getattr(res, k)
                        self.assertEqual(t_v, r_v)

    def test_backup_restore(self):
        path_db = self._TEST_ROOT.joinpath(f"{uuid.uuid4()}.db")
        path_config = path_db.with_suffix(".config")
        p = portfolio.Portfolio.create(path_db)

        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_config.exists(), "Config does not exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)

        # Create Account
        with p.get_session() as s:
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
            )
            s.add(acct)
            s.commit()

            accounts = s.query(Account).all()
            self.assertEqual(1, len(accounts))

        result, tar_ver = p.backup()

        path_backup_1 = path_db.with_suffix(".backup1.tar.gz")
        self.assertEqual(path_backup_1, result)
        self.assertEqual(1, tar_ver)

        self.assertTrue(path_backup_1.exists(), "Backup portfolio does not exist")
        self.assertEqual(path_backup_1.stat().st_mode & 0o777, 0o600)

        with tarfile.open(path_backup_1, "r:gz") as tar:
            buf_backup = tar.extractfile(path_db.name).read()
            with open(path_db, "rb") as file:
                buf = file.read()
            self.assertEqual(buf, buf_backup)

            buf_backup = tar.extractfile(path_config.name).read()
            with open(path_config, "rb") as file:
                buf = file.read()
            self.assertEqual(buf, buf_backup)
        buf = None
        buf_backup = None

        # Accidentally add a new Account
        with p.get_session() as s:
            acct = Account(
                name="Monkey Bank Checking Duplicate",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
            )
            s.add(acct)
            s.commit()

            accounts = s.query(Account).all()
            self.assertEqual(2, len(accounts))

        with tarfile.open(path_backup_1, "r:gz") as tar:
            buf_backup = tar.extractfile(path_db.name).read()
            with open(path_db, "rb") as file:
                buf = file.read()
            self.assertNotEqual(buf, buf_backup)
        buf = None
        buf_backup = None

        portfolio.Portfolio.restore(p)

        # Files should match again
        with tarfile.open(path_backup_1, "r:gz") as tar:
            buf_backup = tar.extractfile(path_db.name).read()
            with open(path_db, "rb") as file:
                buf = file.read()
            self.assertEqual(buf, buf_backup)

            buf_backup = tar.extractfile(path_config.name).read()
            with open(path_config, "rb") as file:
                buf = file.read()
            self.assertEqual(buf, buf_backup)
        buf = None
        buf_backup = None

        # Only the original account present
        with p.get_session() as s:
            accounts = s.query(Account).all()
            self.assertEqual(1, len(accounts))

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

        # Backups should include the images and SSL certs
        with p.get_session() as s:
            asset = Asset(
                name=self.random_string(),
                category=AssetCategory.CASH,
                img_suffix=".png",
            )
            s.add(asset)
            s.commit()

            path_a_img = p.image_path.joinpath(asset.image_name)
            path_a_img_rel = str(path_a_img.relative_to(self._TEST_ROOT))
            a_img = self.random_string().encode()

            with open(path_a_img, "wb") as file:
                file.write(a_img)

        path_cert = p.ssl_cert_path
        path_key = p.ssl_key_path
        path_cert_rel = str(path_cert.relative_to(self._TEST_ROOT))
        path_key_rel = str(path_key.relative_to(self._TEST_ROOT))
        ssl_cert = self.random_string().encode()
        ssl_key = self.random_string().encode()

        with open(path_cert, "wb") as file:
            file.write(ssl_cert)
        with open(path_key, "wb") as file:
            file.write(ssl_key)

        p.backup()
        with tarfile.open(path_backup_1, "r:gz") as tar:
            buf_backup = tar.extractfile(path_a_img_rel).read()
            self.assertEqual(a_img, buf_backup)
            buf_backup = tar.extractfile(path_cert_rel).read()
            self.assertEqual(ssl_cert, buf_backup)
            buf_backup = tar.extractfile(path_key_rel).read()
            self.assertEqual(ssl_key, buf_backup)
        a_img = None
        buf_backup = None

        path_db.unlink()
        path_config.unlink()
        path_a_img.unlink()
        path_cert.unlink()
        path_key.unlink()

        # Restoring brings asset images back too
        portfolio.Portfolio.restore(path_db)

        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_config.exists(), "Config does not exist")
        self.assertTrue(path_a_img.exists(), "Asset image does not exist")
        self.assertTrue(path_cert.exists(), "SSL cert does not exist")
        self.assertTrue(path_key.exists(), "SSL key does not exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)

    def test_clean(self):
        path_db = self._TEST_ROOT.joinpath(f"{uuid.uuid4()}.db")
        path_other_db = self._TEST_ROOT.joinpath(f"{uuid.uuid4()}.db")
        path_config = path_db.with_suffix(".config")
        p = portfolio.Portfolio.create(path_db)
        _ = portfolio.Portfolio.create(path_other_db)

        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_other_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_config.exists(), "Config does not exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_other_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)

        # Create Account
        with p.get_session() as s:
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
            )
            s.add(acct)
            s.commit()

            accounts = s.query(Account).all()
            self.assertEqual(1, len(accounts))

        path_backup_1, tar_ver = p.backup()
        self.assertEqual(1, tar_ver)
        path_backup_2, tar_ver = p.backup()
        self.assertEqual(2, tar_ver)
        path_backup_3, tar_ver = p.backup()
        self.assertEqual(3, tar_ver)

        # Test for real this time
        result, tar_ver = p.backup()

        path_backup_4 = path_db.with_suffix(".backup4.tar.gz")
        self.assertEqual(path_backup_4, result)
        self.assertEqual(4, tar_ver)

        self.assertTrue(path_backup_4.exists(), "Backup portfolio does not exist")
        self.assertEqual(path_backup_4.stat().st_mode & 0o777, 0o600)

        # Make an asset image
        path_a_img = p.image_path.joinpath(f"{uuid.uuid4()}.png")
        with open(path_a_img, "wb") as file:
            file.write(self.random_string().encode())

        # Clean, expect old backups and old images to be purged
        p.clean()

        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_other_db.exists(), "Portfolio does not exist")
        self.assertTrue(path_config.exists(), "Config does not exist")
        self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_other_db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)

        self.assertFalse(path_a_img.exists(), "Asset image does exist")

        self.assertTrue(path_backup_1.exists(), "Backup #1 does not exist")
        self.assertFalse(path_backup_2.exists(), "Backup #2 does exist")
        self.assertFalse(path_backup_3.exists(), "Backup #3 does exist")
        self.assertFalse(path_backup_4.exists(), "Backup #4 does exist")
