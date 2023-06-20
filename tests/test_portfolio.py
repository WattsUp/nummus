"""Test module nummus.portfolio
"""

import autodict

from nummus import portfolio, sql, models

from tests import base


class TestPortfolio(base.TestBase):
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
    self.assertTrue(path_db.exists())
    self.assertTrue(path_config.exists())
    self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)
    sql.drop_session()

    # Check portfolio is unencrypted
    with open(path_db, "rb") as file:
      buf = file.read()
      target = b"SQLite format 3"
      self.assertEqual(target, buf[:len(target)])
      buf = None  # Clear local buffer

    # Database already exists
    self.assertRaises(FileExistsError, portfolio.Portfolio.create, path_db)

    # Reopen portfolio
    p = portfolio.Portfolio(path_db, None)
    with p.get_session() as s:
      # Good, now change root password
      user: models.Credentials = s.query(models.Credentials).filter(
          models.Credentials.site == p._NUMMUS_SITE,  # pylint: disable=protected-access
          models.Credentials.user == p._NUMMUS_USER).first()  # pylint: disable=protected-access
      user.password = self.random_string()
      s.commit()

    # Invalid root password
    self.assertRaises(ValueError, portfolio.Portfolio, path_db, None)

    # Recreate
    path_db.unlink()
    path_config.unlink()

    portfolio.Portfolio.create(path_db)
    self.assertTrue(path_db.exists())
    self.assertTrue(path_config.exists())
    sql.drop_session()

    # Delete root
    p = portfolio.Portfolio(path_db, None)
    with p.get_session() as s:
      user: models.Credentials = s.query(models.Credentials).filter(
          models.Credentials.site == p._NUMMUS_SITE,  # pylint: disable=protected-access
          models.Credentials.user == p._NUMMUS_USER).first()  # pylint: disable=protected-access
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
    self.assertTrue(path_db.exists())
    self.assertTrue(path_config.exists())
    self.assertEqual(path_config.stat().st_mode & 0o777, 0o600)
    sql.drop_session()

    # Check portfolio is encrypted
    with open(path_db, "rb") as file:
      buf = file.read()
      target = b"SQLite format 3"
      self.assertNotEqual(target, buf[:len(target)])
      buf = None  # Clear local buffer

    # Database already exists
    self.assertRaises(FileExistsError, portfolio.Portfolio.create, path_db)

    # Bad key
    self.assertRaises(TypeError, portfolio.Portfolio, path_db,
                      self.random_string())

    # Reopen portfolio
    p = portfolio.Portfolio(path_db, key)
    with p.get_session() as s:
      # Good, now change root password
      user: models.Credentials = s.query(models.Credentials).filter(
          models.Credentials.site == p._NUMMUS_SITE,  # pylint: disable=protected-access
          models.Credentials.user == p._NUMMUS_USER).first()  # pylint: disable=protected-access
      user.password = p._enc.encrypt(self.random_string().encode())  # pylint: disable=protected-access
      s.commit()

    # Invalid root password
    self.assertRaises(ValueError, portfolio.Portfolio, path_db, key)

    # Recreate
    path_db.unlink()
    path_config.unlink()
    portfolio.Portfolio.create(path_db, key)
    self.assertTrue(path_db.exists())
    self.assertTrue(path_config.exists())
    sql.drop_session()

    # Change root password to unencrypted
    p = portfolio.Portfolio(path_db, key)
    with p.get_session() as s:
      # Good, now change root password
      user: models.Credentials = s.query(models.Credentials).filter(
          models.Credentials.site == p._NUMMUS_SITE,  # pylint: disable=protected-access
          models.Credentials.user == p._NUMMUS_USER).first()  # pylint: disable=protected-access
      user.password = key
      s.commit()

    # Invalid unencrypted password
    self.assertRaises(PermissionError, portfolio.Portfolio, path_db, key)
