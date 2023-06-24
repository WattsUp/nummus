"""Test module nummus.portfolio
"""

import uuid

import autodict

from nummus import portfolio, sql
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           Credentials, Transaction)

from tests.base import TestBase
from tests.importers.test_raw_csv import TRANSACTIONS_EXTRAS


class TestPortfolio(TestBase):
  """Test Portfolio class
  """

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

    # Create unencrypted portfolio
    portfolio.Portfolio.create(path_db)
    self.assertTrue(path_db.exists(), "Portfolio does not exist")
    self.assertTrue(path_config.exists(), "Config does not exist")
    self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
    self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)
    sql.drop_session()

    # Check portfolio is unencrypted
    with open(path_db, "rb") as file:
      buf = file.read()
      target = b"SQLite format 3"
      self.assertEqual(target, buf[:len(target)])
      buf = None  # Clear local buffer
    self.assertFalse(portfolio.Portfolio.is_encrypted(path_db),
                     "Database is unexpectedly encrypted")

    # Database already exists
    self.assertRaises(FileExistsError, portfolio.Portfolio.create, path_db)

    # Reopen portfolio
    p = portfolio.Portfolio(path_db, None)
    with p.get_session() as s:
      # Good, now change root password
      user: Credentials = s.query(Credentials).filter(
          Credentials.site == p._NUMMUS_SITE,  # pylint: disable=protected-access
          Credentials.user == p._NUMMUS_USER).first()  # pylint: disable=protected-access
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
      user: Credentials = s.query(Credentials).filter(
          Credentials.site == p._NUMMUS_SITE,  # pylint: disable=protected-access
          Credentials.user == p._NUMMUS_USER).first()  # pylint: disable=protected-access
      s.delete(user)
      s.commit()

    # Missing root password
    self.assertRaises(KeyError, portfolio.Portfolio, path_db, None)

  def test_create_encrypted(self):
    if portfolio.encryption is None:
      self.skipTest("Encryption is not installed")

    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    path_config = path_db.with_suffix(".config")

    key = self.random_string()

    # Create unencrypted portfolio
    portfolio.Portfolio.create(path_db, key)
    self.assertTrue(path_db.exists(), "Portfolio does not exist")
    self.assertTrue(path_config.exists(), "Config does not exist")
    self.assertEqual(path_db.stat().st_mode & 0o777, 0o600)
    self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)
    sql.drop_session()

    # Check portfolio is encrypted
    with open(path_db, "rb") as file:
      buf = file.read()
      target = b"SQLite format 3"
      self.assertNotEqual(target, buf[:len(target)])
      buf = None  # Clear local buffer
    self.assertTrue(portfolio.Portfolio.is_encrypted(path_db),
                    "Database is unexpectedly unencrypted")

    # Database already exists
    self.assertRaises(FileExistsError, portfolio.Portfolio.create, path_db)

    # Bad key
    self.assertRaises(TypeError, portfolio.Portfolio, path_db,
                      self.random_string())

    # Reopen portfolio
    p = portfolio.Portfolio(path_db, key)
    with p.get_session() as s:
      # Good, now change root password
      user: Credentials = s.query(Credentials).filter(
          Credentials.site == p._NUMMUS_SITE,  # pylint: disable=protected-access
          Credentials.user == p._NUMMUS_USER).first()  # pylint: disable=protected-access
      user.password = p._enc.encrypt(self.random_string().encode())  # pylint: disable=protected-access
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
      user: Credentials = s.query(Credentials).filter(
          Credentials.site == p._NUMMUS_SITE,  # pylint: disable=protected-access
          Credentials.user == p._NUMMUS_USER).first()  # pylint: disable=protected-access
      user.password = key
      s.commit()

    # Invalid unencrypted password
    self.assertRaises(PermissionError, portfolio.Portfolio, path_db, key)

  def test_is_encrypted(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    path_config = path_db.with_suffix(".config")

    self.assertRaises(FileNotFoundError, portfolio.Portfolio.is_encrypted,
                      path_db)

    with open(path_db, "w", encoding="utf-8") as file:
      file.write("I'm a database")

    # Still missing config
    self.assertRaises(FileNotFoundError, portfolio.Portfolio.is_encrypted,
                      path_db)

    with autodict.JSONAutoDict(path_config) as c:
      c["encrypt"] = True

    self.assertTrue(portfolio.Portfolio.is_encrypted(path_db),
                    "Database is unexpectedly unencrypted")

    with autodict.JSONAutoDict(path_config) as c:
      c["encrypt"] = False

    self.assertFalse(portfolio.Portfolio.is_encrypted(path_db),
                     "Database is unexpectedly encrypted")

    path_db.unlink()

  def test_find_account(self):
    path_db = self._TEST_ROOT.joinpath(f"{uuid.uuid4()}.db")
    p = portfolio.Portfolio.create(path_db)

    result = p._find_account("Monkey Bank Checking")  # pylint: disable=protected-access
    self.assertIsNone(result)

    # Create accounts
    a_checking = Account(name="Monkey Bank Checking",
                         institution="Monkey Bank",
                         category=AccountCategory.CASH)
    a_invest_0 = Account(name="Primate Investments",
                         institution="Monkey Bank",
                         category=AccountCategory.INVESTMENT)
    a_invest_1 = Account(name="Primate Investments",
                         institution="Gorilla Bank",
                         category=AccountCategory.INVESTMENT)
    with p.get_session() as s:
      s.add_all((a_checking, a_invest_0, a_invest_1))
      s.commit()

      # Refresh the objects whilst in the session, else DetachedInstanceError
      a_checking = s.query(Account).where(Account.id == a_checking.id).first()
      a_invest_0 = s.query(Account).where(Account.id == a_invest_0.id).first()
      a_invest_1 = s.query(Account).where(Account.id == a_invest_1.id).first()

    # Find by ID, kinda redundant but lol: id = find(id)
    result = p._find_account(a_checking.id)  # pylint: disable=protected-access
    self.assertEqual(a_checking.id, result)
    result = p._find_account(a_invest_0.id)  # pylint: disable=protected-access
    self.assertEqual(a_invest_0.id, result)
    result = p._find_account(a_invest_1.id)  # pylint: disable=protected-access
    self.assertEqual(a_invest_1.id, result)

    # Find by name
    result = p._find_account("Monkey Bank Checking")  # pylint: disable=protected-access
    self.assertEqual(a_checking.id, result)

    # More than 1 match by name
    result = p._find_account("Primate Investments")  # pylint: disable=protected-access
    self.assertIsNone(result)

    # Find by institution
    result = p._find_account("Gorilla Bank")  # pylint: disable=protected-access
    self.assertEqual(a_invest_1.id, result)

  def test_find_asset(self):
    path_db = self._TEST_ROOT.joinpath(f"{uuid.uuid4()}.db")
    p = portfolio.Portfolio.create(path_db)

    result = p._find_asset("BANANA")  # pylint: disable=protected-access
    self.assertIsNone(result)

    # Create accounts
    a_banana = Asset(name="BANANA", category=AssetCategory.ITEM)
    a_apple_0 = Asset(name="APPLE", category=AssetCategory.ITEM)
    a_apple_1 = Asset(name="APPLE", category=AssetCategory.SECURITY)
    with p.get_session() as s:
      s.add_all((a_banana, a_apple_0, a_apple_1))
      s.commit()

      # Refresh the objects whilst in the session, else DetachedInstanceError
      a_banana = s.query(Asset).where(Asset.id == a_banana.id).first()
      a_apple_0 = s.query(Asset).where(Asset.id == a_apple_0.id).first()
      a_apple_1 = s.query(Asset).where(Asset.id == a_apple_1.id).first()

    # Find by ID, kinda redundant but lol: id = find(id)
    result = p._find_asset(a_banana.id)  # pylint: disable=protected-access
    self.assertEqual(a_banana.id, result)
    result = p._find_asset(a_apple_0.id)  # pylint: disable=protected-access
    self.assertEqual(a_apple_0.id, result)
    result = p._find_asset(a_apple_1.id)  # pylint: disable=protected-access
    self.assertEqual(a_apple_1.id, result)

    # Find by name
    result = p._find_asset("BANANA")  # pylint: disable=protected-access
    self.assertEqual(a_banana.id, result)

    # More than 1 match by name
    result = p._find_asset("APPLE")  # pylint: disable=protected-access
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

    # Create accounts
    a_checking = Account(name="Monkey Bank Checking",
                         institution="Monkey Bank",
                         category=AccountCategory.CASH)
    a_invest = Account(name="Monkey Investments",
                       institution="Monkey Bank",
                       category=AccountCategory.INVESTMENT)
    with p.get_session() as s:
      s.add_all((a_checking, a_invest))
      s.commit()

      # Refresh the objects whilst in the session, else DetachedInstanceError
      a_checking = s.query(Account).where(Account.id == a_checking.id).first()
      a_invest = s.query(Account).where(Account.id == a_invest.id).first()

    # Still missing assets
    self.assertRaises(KeyError, p.import_file, path)

    a_banana = Asset(name="BANANA", category=AssetCategory.SECURITY)
    with p.get_session() as s:
      s.add(a_banana)
      s.commit()

      # Refresh the objects whilst in the session, else DetachedInstanceError
      a_banana = s.query(Asset).where(Asset.id == a_banana.id).first()

    # We good now
    p.import_file(path)

    with p.get_session() as s:
      transactions = s.query(Transaction).all()

      target = TRANSACTIONS_EXTRAS
      self.assertEqual(len(target), len(transactions))
      for t, r in zip(target, transactions):
        for k, t_v in t.items():
          # Fix test value for linked properties
          if k == "asset":
            t_v = a_banana
          elif k == "account":
            if t_v == "Monkey Bank Checking":
              t_v = a_checking
            else:
              t_v = a_invest

          r_v = getattr(r, k)
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
      a = Account(name="Monkey Bank Checking",
                  institution="Monkey Bank",
                  category=AccountCategory.CASH)
      s.add(a)
      s.commit()

      accounts = s.query(Account).all()
      self.assertEqual(1, len(accounts))

    p.backup()

    path_db_backup = path_db.with_suffix(".backup.db")
    path_config_backup = path_config.with_suffix(".backup.config")

    self.assertTrue(path_db_backup.exists(), "Backup portfolio does not exist")
    self.assertTrue(path_config_backup.exists(), "Backup config does not exist")
    self.assertEqual(path_db_backup.stat().st_mode & 0o777, 0o600)
    self.assertEqual(path_config_backup.stat().st_mode & 0o777, 0o600)

    with open(path_db_backup, "rb") as file:
      buf_backup = file.read()
    with open(path_db, "rb") as file:
      buf = file.read()
    self.assertEqual(buf, buf_backup)
    with open(path_config_backup, "rb") as file:
      buf_backup = file.read()
    with open(path_config, "rb") as file:
      buf = file.read()
    self.assertEqual(buf, buf_backup)
    buf = None
    buf_backup = None

    # Accidentally add a new Account
    with p.get_session() as s:
      a = Account(name="Monkey Bank Checking Duplicate",
                  institution="Monkey Bank",
                  category=AccountCategory.CASH)
      s.add(a)
      s.commit()

      accounts = s.query(Account).all()
      self.assertEqual(2, len(accounts))

    with open(path_db_backup, "rb") as file:
      buf_backup = file.read()
    with open(path_db, "rb") as file:
      buf = file.read()
    self.assertNotEqual(buf, buf_backup)
    buf = None
    buf_backup = None

    p.restore()

    # Files should match again
    with open(path_db_backup, "rb") as file:
      buf_backup = file.read()
    with open(path_db, "rb") as file:
      buf = file.read()
    self.assertEqual(buf, buf_backup)
    buf = None
    buf_backup = None

    # Only the original account present
    with p.get_session() as s:
      accounts = s.query(Account).all()
      self.assertEqual(1, len(accounts))

    # Can't restore if backup config is missing
    path_config_backup.unlink()
    self.assertRaises(FileNotFoundError, p.restore)

    # Can't restore if backup database is missing
    path_db_backup.unlink()
    self.assertRaises(FileNotFoundError, p.restore)
