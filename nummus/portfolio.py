"""Portfolio of financial records
"""

from __future__ import annotations

import pathlib

import autodict
from sqlalchemy import orm

from nummus import common, models, sql, version

try:
  from nummus import encryption  # pylint: disable=import-outside-toplevel
except ImportError:
  print("Could not import nummus.encryption, encryption not available")
  print("Install libsqlcipher: apt install libsqlcipher-dev")
  print("Install encrypt extra: pip install nummus[encrypt]")
  encryption = None


class Portfolio:
  """A collection of financial records

  Records include: transactions, accounts, and assets
  """

  # Have a root user so that unlock can test decryption
  _NUMMUS_SITE = "nummus"
  _NUMMUS_USER = "root"
  _NUMMUS_PASSWORD = "unencrypted database"

  def __init__(self, path: str, key: str) -> None:
    """Initialize Portfolio

    Args:
      path: Path to database file
      key: String password to unlock database encryption

    Raises:
      FileNotFoundError if database does not exist
    """
    self._path_db = pathlib.Path(path)
    self._path_config = self._path_db.with_suffix(".config")
    if not self._path_db.exists():
      raise FileNotFoundError(f"Portfolio at {self._path_db} does not exist, "
                              "use Portfolio.create()")
    if not self._path_config.exists():
      raise FileNotFoundError("Portfolio configuration does not exist, "
                              "cannot open database")
    self._config = autodict.JSONAutoDict(self._path_config, save_on_exit=False)

    if key is None:
      self._enc = None
    else:
      self._enc = encryption.Encryption(key.encode())
    self._unlock()

  @staticmethod
  def create(path: str, key: str = None) -> Portfolio:
    """Create a new Portfolio

    Saves database and configuration file

    Args:
      path: Path to database file
      key: String password to unlock database encryption

    Returns:
      Portfolio linked to newly created database

    Raises:
      FileExistsError if database already exists
    """
    path_db = pathlib.Path(path)
    if path_db.exists():
      raise FileExistsError(f"Database already exists at {path_db}")
    # Drop any existing engine to database
    sql.drop_session(path_db)
    path_config = path_db.with_suffix(".config")

    enc = None
    if encryption is not None and key is not None:
      enc = encryption.Encryption(key.encode())

    path_db.parent.mkdir(parents=True, exist_ok=True)
    salt = common.random_string(min_length=50, max_length=100)
    config = autodict.JSONAutoDict(path_config)
    config.clear()
    config["version"] = str(version.__version__)
    config["key_version"] = 1  # Increment if there is a breaking change
    config["salt"] = salt
    config["encrypt"] = enc is not None
    config.save()
    path_config.chmod(0o600)  # Only owner can read/write

    if enc is None:
      password = Portfolio._NUMMUS_PASSWORD
    else:
      key_salted = enc.key + salt.encode()
      password = enc.encrypt(key_salted)

    with sql.get_session(path_db, config, enc) as session:
      models.metadata_create_all(session)

      nummus_user = models.Credentials(site=Portfolio._NUMMUS_SITE,
                                       user=Portfolio._NUMMUS_USER,
                                       password=password)
      session.add(nummus_user)
      session.commit()

    return Portfolio(path_db, key)

  def _unlock(self) -> None:
    """Unlock the database

    Raises:
      TypeError if database file fails to open
      PermissionError if decryption failed
      KeyError if root password is missing
      ValueError if root password does not match expected
    """
    # Drop any open session
    sql.drop_session(self._path_db)
    try:
      with self.get_session() as s:
        user: models.Credentials = s.query(models.Credentials).filter(
            models.Credentials.site == self._NUMMUS_SITE,
            models.Credentials.user == self._NUMMUS_USER).first()
    except models.exc.DatabaseError as e:
      raise TypeError(f"Failed to open database {self._path_db}") from e

    if user is None:
      raise KeyError("Root password not found")

    if self._enc is None:
      if user.password != self._NUMMUS_PASSWORD:
        raise ValueError("Root password did not match")
    else:
      salt: str = self._config["salt"]
      key_salted = self._enc.key + salt.encode()
      try:
        password_decrypted = self._enc.decrypt(user.password)
      except ValueError as e:
        raise PermissionError("Failed to decrypt root password") from e
      if password_decrypted != key_salted:
        raise ValueError("Root user's password did not match")
    # All good :)

  def get_session(self) -> orm.Session:
    """Get SQL Session to the database

    Returns:
      Open Session
    """
    return sql.get_session(self._path_db, self._config, self._enc)
