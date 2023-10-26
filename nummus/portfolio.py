"""Portfolio of financial records."""

from __future__ import annotations

import base64
import re
import secrets
import shutil
import tarfile
from pathlib import Path

import autodict
import sqlalchemy
import sqlalchemy.exc
from sqlalchemy import orm

from nummus import custom_types as t
from nummus import importers, models, sql, version
from nummus.models import (
    Account,
    Asset,
    Credentials,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)

try:
    from nummus import encryption
except ImportError:
    print("Could not import nummus.encryption, encryption not available")
    print("Install libsqlcipher: apt install libsqlcipher-dev")
    print("Install encrypt extra: pip install nummus[encrypt]")
    encryption = None


class Portfolio:
    """A collection of financial records.

    Records include: transactions, accounts, and assets
    """

    # Have a root user so that unlock can test decryption
    _NUMMUS_SITE = "nummus"
    _NUMMUS_USER = "root"
    _NUMMUS_PASSWORD = "unencrypted database"  # noqa: S105

    def __init__(self, path: str, key: str) -> None:
        """Initialize Portfolio.

        Args:
            path: Path to database file
            key: String password to unlock database encryption

        Raises:
            FileNotFoundError if database does not exist
        """
        self._path_db = Path(path).resolve().with_suffix(".db")
        name = self._path_db.with_suffix("").name
        self._path_config = self._path_db.with_suffix(".config")
        self._path_images = self._path_db.parent.joinpath(f"{name}.images")
        self._path_ssl = self._path_db.parent.joinpath(f"{name}.ssl")
        if not self._path_db.exists():
            msg = f"Portfolio at {self._path_db} does not exist, use Portfolio.create()"
            raise FileNotFoundError(msg)
        if not self._path_config.exists():
            msg = "Portfolio configuration does not exist, cannot open database"
            raise FileNotFoundError(msg)
        self._path_images.mkdir(exist_ok=True)  # Make if it doesn't exist
        self._path_ssl.mkdir(exist_ok=True)  # Make if it doesn't exist
        self._config = autodict.JSONAutoDict(self._path_config, save_on_exit=False)

        if key is None:
            self._enc = None
        else:
            self._enc = encryption.Encryption(key.encode())
        self._unlock()

    @property
    def path(self) -> Path:
        """Path to Portfolio database."""
        return self._path_db

    @staticmethod
    def is_encrypted(path: str) -> bool:
        """Check Portfolio's config for encryption status.

        Args:
            path: Path to database file

        Returns:
            True if Portfolio is encrypted

        Raises:
            FileNotFound if database or configuration does not exist
        """
        path_db = Path(path)
        if not path_db.exists():
            msg = f"Database does not exist at {path_db}"
            raise FileNotFoundError(msg)
        path_config = path_db.with_suffix(".config")
        if not path_config.exists():
            msg = f"Portfolio configuration does not exist, for {path_db}"
            raise FileNotFoundError(msg)
        with autodict.JSONAutoDict(path_config, save_on_exit=False) as config:
            return config["encrypt"]

    @staticmethod
    def create(path: str, key: str | None = None) -> Portfolio:
        """Create a new Portfolio.

        Saves database and configuration file

        Args:
            path: Path to database file
            key: String password to unlock database encryption

        Returns:
            Portfolio linked to newly created database

        Raises:
            FileExistsError if database already exists
        """
        path_db = Path(path).resolve()
        if path_db.exists():
            msg = f"Database already exists at {path_db}"
            raise FileExistsError(msg)
        # Drop any existing engine to database
        sql.drop_session(path_db)
        name = path_db.with_suffix("").name
        path_config = path_db.with_suffix(".config")
        path_images = path_db.parent.joinpath(f"{name}.images")
        path_ssl = path_db.parent.joinpath(f"{name}.ssl")

        enc = None
        if encryption is not None and key is not None:
            enc = encryption.Encryption(key.encode())

        path_db.parent.mkdir(parents=True, exist_ok=True)
        path_images.mkdir(exist_ok=True)
        path_ssl.mkdir(exist_ok=True)
        salt = secrets.token_urlsafe()
        config = autodict.JSONAutoDict(path_config)
        config.clear()
        config["version"] = str(version.__version__)
        config["key_version"] = 1  # Increment if there is a breaking change
        config["salt"] = salt
        config["encrypt"] = enc is not None
        cipher_bytes = models.Cipher.generate().to_bytes()
        config["cipher"] = base64.b64encode(cipher_bytes).decode()
        config.save()
        path_config.chmod(0o600)  # Only owner can read/write
        path_images.chmod(0o700)  # Only owner can read/write
        path_ssl.chmod(0o700)  # Only owner can read/write

        if enc is None:
            password = Portfolio._NUMMUS_PASSWORD
        else:
            key_salted = enc.key + salt.encode()
            password = enc.encrypt(key_salted)

        with sql.get_session(path_db, config, enc) as s:
            models.metadata_create_all(s)

            nummus_user = Credentials(
                site=Portfolio._NUMMUS_SITE,
                user=Portfolio._NUMMUS_USER,
                password=password,
            )
            s.add(nummus_user)
            s.commit()
        path_db.chmod(0o600)  # Only owner can read/write

        p = Portfolio(path_db, key)
        with p.get_session() as s:
            TransactionCategory.add_default(s)
        return p

    def _unlock(self) -> None:
        """Unlock the database.

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
                user: Credentials = (
                    s.query(Credentials)
                    .where(
                        Credentials.site == self._NUMMUS_SITE,
                        Credentials.user == self._NUMMUS_USER,
                    )
                    .first()
                )
        except sqlalchemy.exc.DatabaseError as e:
            msg = f"Failed to open database {self._path_db}"
            raise TypeError(msg) from e

        if user is None:
            msg = "Root password not found"
            raise KeyError(msg)

        if self._enc is None:
            if user.password != self._NUMMUS_PASSWORD:
                msg = "Root password did not match"
                raise ValueError(msg)
        else:
            salt: str = self._config["salt"]
            key_salted = self._enc.key + salt.encode()
            try:
                password_decrypted = self._enc.decrypt(user.password)
            except ValueError as e:
                msg = "Failed to decrypt root password"
                raise PermissionError(msg) from e
            if password_decrypted != key_salted:
                msg = "Root user's password did not match"
                raise ValueError(msg)
        # Load Cipher
        models.load_cipher(base64.b64decode(self._config["cipher"]))
        # All good :)

    def get_session(self) -> orm.Session:
        """Get SQL Session to the database.

        Returns:
            Open Session
        """
        return sql.get_session(self._path_db, self._config, self._enc)

    def import_file(self, path: Path) -> None:
        """Import a file into the Portfolio.

        Args:
            path: Path to file to import

        Raises:
            KeyError if account or asset cannot be resolved
        """
        i = importers.get_importer(path)
        if i is None:
            msg = f"File is an unknown type: {path}"
            raise TypeError(msg)

        # Cache a mapping from account/asset name to the ID
        with self.get_session() as s:
            categories: dict[str, TransactionCategory] = {
                cat.name: cat for cat in s.query(TransactionCategory).all()
            }
            account_mapping: t.DictInt = {}
            asset_mapping: t.DictInt = {}
            transactions: list[tuple[Transaction, TransactionSplit]] = []
            for d in i.run():
                # Create a single split for each transaction
                category_s = d.pop("category", "Uncategorized")
                d_split: importers.TxnDict = {
                    "amount": d["amount"],  # Both split and parent have amount
                    "payee": d.pop("payee", None),
                    "description": d.pop("description", None),
                    "category_id": categories[category_s].id_,
                    "tag": d.pop("tag", None),
                    "asset_quantity_unadjusted": d.pop("asset_quantity", None),
                }

                account_raw = d.pop("account")
                account_id = account_mapping.get(account_raw)
                if account_id is None:
                    account = self.find_account(account_raw, session=s)
                    if account is None:
                        msg = f"Could not find Account by '{account_raw}'"
                        raise KeyError(msg)
                    account_id = account.id_
                    account_mapping[account_raw] = account_id
                d["account_id"] = account_id

                asset_raw = d.pop("asset", None)
                if asset_raw is not None:
                    # Find its ID
                    asset_id = asset_mapping.get(asset_raw)
                    if asset_id is None:
                        asset = self.find_asset(asset_raw, session=s)
                        if asset is None:
                            msg = f"Could not find Asset by '{asset_raw}'"
                            raise KeyError(msg)
                        asset_id = asset.id_
                        asset_mapping[asset_raw] = asset_id
                    d_split["asset_id"] = asset_id

                transactions.append((Transaction(**d), TransactionSplit(**d_split)))

            # All good, add transactions and commit
            for txn, t_split in transactions:
                t_split.parent = txn
                s.add_all((txn, t_split))
            s.commit()

    def find_account(
        self,
        query: t.IntOrStr,
        session: orm.Session = None,
    ) -> int | Account:
        """Find a matching Account by name, URI, institution, or ID.

        Args:
            query: Search query
            session: Session to use, will return Account not id

        Returns:
            Account ID or None if no matches found
            If session is not None: return Account object or None
        """

        def _find(s: orm.Session) -> Account:
            if isinstance(query, int):
                # See if account is an ID first...
                matches = s.query(Account).where(Account.id_ == query).all()
                return matches[0] if len(matches) == 1 else None
            try:
                # See if query is an URI
                id_ = Account.uri_to_id(query)
                matches = s.query(Account).where(Account.id_ == id_).all()
                if len(matches) == 1:
                    return matches[0]
            except TypeError:
                pass

            # Maybe a name next
            matches = s.query(Account).where(Account.name == query).all()
            if len(matches) == 1:
                return matches[0]

            # Last chance, institution
            matches = s.query(Account).where(Account.institution == query).all()
            if len(matches) == 1:
                return matches[0]
            return None

        if session is None:
            with self.get_session() as s:
                acct = _find(s)
                if acct is None:
                    return None
                return acct.id_
        else:
            return _find(session)

    def find_asset(
        self,
        query: t.IntOrStr,
        session: orm.Session = None,
    ) -> int | Asset:
        """Find a matching Asset by name, URI, or ID.

        Args:
            query: Search query
            session: Session to use, will return Asset not id

        Returns:
            Asset ID or None if no matches found
            If session is not None: return Asset object or None
        """

        def _find(s: orm.Session) -> Asset:
            if isinstance(query, int):
                # See if account is an ID first...
                matches = s.query(Asset).where(Asset.id_ == query).all()
                return matches[0] if len(matches) == 1 else None
            try:
                # See if query is an URI
                id_ = Asset.uri_to_id(query)
                matches = s.query(Asset).where(Asset.id_ == id_).all()
                if len(matches) == 1:
                    return matches[0]
            except TypeError:
                pass

            # Maybe a name next
            matches = s.query(Asset).where(Asset.name == query).all()
            if len(matches) == 1:
                return matches[0]
            return None

        if session is None:
            with self.get_session() as s:
                acct = _find(s)
                if acct is None:
                    return None
                return acct.id_
        else:
            return _find(session)

    def backup(self) -> tuple[Path, int]:
        """Back up database, duplicates files.

        Returns:
            (Path to newly created backup tar.gz, backup version)
        """
        # Find latest backup file for this Portfolio
        i = 0
        parent = self._path_db.parent
        name = self._path_db.with_suffix("").name
        re_filter = re.compile(rf"^{name}.backup(\d+).tar.gz$")
        for file in parent.iterdir():
            m = re_filter.match(file.name)
            if m is not None:
                i = max(i, int(m.group(1)))
        tar_ver = i + 1

        path_backup = self._path_db.with_suffix(f".backup{tar_ver}.tar.gz")

        with tarfile.open(path_backup, "w:gz") as tar:
            files: t.Paths = [self._path_db, self._path_config]

            if self.ssl_cert_path.exists():
                files.append(self.ssl_cert_path)
                files.append(self.ssl_key_path)

            # Get every image
            with self.get_session() as s:
                query = s.query(Asset).where(Asset.img_suffix.is_not(None))
                for asset in query.all():
                    # Query whole object okay, need image_name property
                    file = self._path_images.joinpath(asset.image_name)
                    files.append(file)

            for file in files:
                tar.add(file, arcname=file.relative_to(parent))

        path_backup.chmod(0o600)  # Only owner can read/write
        return path_backup, tar_ver

    def clean(self) -> None:
        """Delete any unused files, creates a new backup."""
        # Create a backup
        path_backup, _ = self.backup()

        # Optimize database
        with self.get_session() as s:
            s.execute(sqlalchemy.text("VACUUM"))

        # Backup again
        path_backup, _ = self.backup()

        # Delete all files that start with name except path_backup
        parent = self._path_db.parent
        name = self._path_db.with_suffix("").name
        for file in parent.iterdir():
            if file == path_backup:
                continue
            if file.name.startswith(f"{name}."):
                if file.is_dir():
                    shutil.rmtree(file)
                else:
                    file.unlink()

        # Move backup to i=1
        shutil.move(path_backup, parent.joinpath(f"{name}.backup1.tar.gz"))

        # Restore
        Portfolio.restore(self, tar_ver=1)

    @staticmethod
    def restore(p: str | Portfolio, tar_ver: int | None = None) -> None:
        """Restore Portfolio from backup.

        Args:
            p: Path to database file, or Portfolio which will get its path
            tar_ver: Backup version to restore, None will use latest

        Raises:
            FileNotFoundError if backup does not exist
        """
        path_db = Path(p._path_db if isinstance(p, Portfolio) else p)  # noqa: SLF001
        path_db = path_db.resolve().with_suffix(".db")
        parent = path_db.parent
        name = path_db.with_suffix("").name

        if tar_ver is None:
            # Find latest backup file for this Portfolio
            i = 0
            re_filter = re.compile(rf"^{name}.backup(\d+).tar.gz$")
            for file in parent.iterdir():
                m = re_filter.match(file.name)
                if m is not None:
                    i = max(i, int(m.group(1)))
            if i == 0:
                msg = f"No backup exists for {path_db}"
                raise FileNotFoundError(msg)
            tar_ver = i

        path_backup = parent.joinpath(f"{name}.backup{tar_ver}.tar.gz")
        if not path_backup.exists():
            msg = f"Backup does not exist {path_backup}"
            raise FileNotFoundError(msg)

        # Drop any dangling sessions
        sql.drop_session(path_db)

        # tar archive preserved owner and mode so no need to set these
        with tarfile.open(path_backup, "r:gz") as tar:
            tar.extractall(parent)

        # Reload Portfolio
        if isinstance(p, Portfolio):
            p._config = autodict.JSONAutoDict(  # noqa: SLF001
                p._path_config,  # noqa: SLF001
                save_on_exit=False,
            )
            p._unlock()  # noqa: SLF001

    @property
    def image_path(self) -> Path:
        """Get path to image folder."""
        return self._path_images

    @property
    def ssl_cert_path(self) -> Path:
        """Get path to SSL certificate."""
        return self._path_ssl.joinpath("cert.pem")

    @property
    def ssl_key_path(self) -> Path:
        """Get path to SSL certificate key."""
        return self._path_ssl.joinpath("key.pem")
