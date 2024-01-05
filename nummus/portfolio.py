"""Portfolio of financial records."""

from __future__ import annotations

import base64
import datetime
import hashlib
import io
import re
import secrets
import shutil
import tarfile
from pathlib import Path

import autodict
import sqlalchemy
import sqlalchemy.exc
import tqdm
from sqlalchemy import orm

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus import importers, models, sql, version
from nummus.models import (
    Account,
    Asset,
    Credentials,
    ImportedFile,
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

    def __init__(self, path: str | Path, key: str | None) -> None:
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
        self._path_importers = self._path_db.parent.joinpath(f"{name}.importers")
        self._path_ssl = self._path_db.parent.joinpath(f"{name}.ssl")
        if not self._path_db.exists():
            msg = f"Portfolio at {self._path_db} does not exist, use Portfolio.create()"
            raise FileNotFoundError(msg)
        if not self._path_config.exists():
            msg = "Portfolio configuration does not exist, cannot open database"
            raise FileNotFoundError(msg)
        self._path_images.mkdir(exist_ok=True)  # Make if it doesn't exist
        self._path_importers.mkdir(exist_ok=True)  # Make if it doesn't exist
        self._path_ssl.mkdir(exist_ok=True)  # Make if it doesn't exist
        self._config = autodict.JSONAutoDict(str(self._path_config), save_on_exit=False)

        if key is None:
            self._enc = None
        else:
            self._enc = encryption.Encryption(key)  # type: ignore[attr-defined]
        self._unlock()

        self._importers = importers.get_importers(self._path_importers)

    @property
    def path(self) -> Path:
        """Path to Portfolio database."""
        return self._path_db

    @property
    def importers_path(self) -> Path:
        """Path to Portfolio importers."""
        return self._path_importers

    @staticmethod
    def is_encrypted(path: str | Path) -> bool:
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
        with autodict.JSONAutoDict(str(path_config), save_on_exit=False) as config:
            return config["encrypt"]

    @staticmethod
    def create(path: str | Path, key: str | None = None) -> Portfolio:
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
        path_importers = path_db.parent.joinpath(f"{name}.importers")
        path_ssl = path_db.parent.joinpath(f"{name}.ssl")

        enc = None
        if encryption is not None and key is not None:
            enc = encryption.Encryption(key)

        path_db.parent.mkdir(parents=True, exist_ok=True)
        path_images.mkdir(exist_ok=True)
        path_importers.mkdir(exist_ok=True)
        path_ssl.mkdir(exist_ok=True)
        salt = secrets.token_urlsafe()
        config = autodict.JSONAutoDict(str(path_config))
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
            UnlockingError if database file fails to open
        """
        # Drop any open session
        sql.drop_session(self._path_db)
        try:
            with self.get_session() as s:
                user: Credentials | None = (
                    s.query(Credentials)
                    .where(
                        Credentials.site == self._NUMMUS_SITE,
                        Credentials.user == self._NUMMUS_USER,
                    )
                    .first()
                )
        except exc.DatabaseError as e:
            msg = f"Failed to open database {self._path_db}"
            raise exc.UnlockingError(msg) from e

        if user is None:
            msg = "Root password not found"
            raise exc.UnlockingError(msg)

        if self._enc is None:
            if user.password != self._NUMMUS_PASSWORD:
                msg = "Root password did not match"
                raise exc.UnlockingError(msg)
        else:
            salt: str = self._config["salt"]
            key_salted = self._enc.key + salt.encode()
            try:
                password_decrypted = self._enc.decrypt(user.password)
            except ValueError as e:
                msg = "Failed to decrypt root password"
                raise exc.UnlockingError(msg) from e
            if password_decrypted != key_salted:
                msg = "Root user's password did not match"
                raise exc.UnlockingError(msg)
        # Load Cipher
        models.load_cipher(base64.b64decode(self._config["cipher"]))
        # All good :)

    def get_session(self) -> orm.Session:
        """Get SQL Session to the database.

        Returns:
            Open Session
        """
        return sql.get_session(self._path_db, self._config, self._enc)

    def encrypt(self, secret: bytes | str) -> str:
        """Encrypt a secret using the key.

        Args:
            secret: Secret object

        Returns:
            base64 encoded encrypted object

        Raises:
            NotEncryptedError if portfolio does not support encryption
        """
        if self._enc is None:
            raise exc.NotEncryptedError
        return self._enc.encrypt(secret)

    def decrypt(self, enc_secret: str) -> bytes:
        """Decrypt an encoded secret using the key.

        Args:
            enc_secret: base64 encoded encrypted object

        Returns:
            bytes decoded object

        Raises:
            NotEncryptedError if portfolio does not support encryption
        """
        if self._enc is None:
            raise exc.NotEncryptedError
        return self._enc.decrypt(enc_secret)

    def decrypt_s(self, enc_secret: str) -> str:
        """Decrypt an encoded secret using the key.

        Args:
            enc_secret: base64 encoded encrypted string

        Returns:
            decoded string
        """
        return self.decrypt(enc_secret).decode()

    def import_file(self, path: Path, *_, force: bool = False) -> None:
        """Import a file into the Portfolio.

        Args:
            path: Path to file to import
            force: True will not check for already imported files

        Raises:
            FileAlreadyImportedError if file has already been imported
            UnknownImporterError if no importer is found for file
            TypeError if importer returns wrong types
            KeyError if account or asset cannot be resolved
        """
        # Compute hash of file contents to check if already imported
        sha = hashlib.sha256()
        with path.open("rb") as file:
            sha.update(file.read())
        h = sha.hexdigest()
        if not force:
            with self.get_session() as s:
                existing: ImportedFile | None = (
                    s.query(ImportedFile).where(ImportedFile.hash_ == h).scalar()
                )
                if existing is not None:
                    date = datetime.date.fromordinal(existing.date_ord)
                    raise exc.FileAlreadyImportedError(date, path)

        i = importers.get_importer(path, self._importers)
        if i is None:
            raise exc.UnknownImporterError(path)
        ctx = f"<importer={i.__class__.__name__}, file={path}>"

        with self.get_session() as s:
            categories: dict[str, TransactionCategory] = {
                cat.name: cat for cat in s.query(TransactionCategory).all()
            }
            # Cache a mapping from account/asset name to the ID
            acct_mapping: t.DictInt = {}
            asset_mapping: t.DictInt = {}
            txns: list[tuple[Transaction, TransactionSplit]] = []
            txns_raw = i.run()
            if not txns_raw:
                msg = f"Importer returned no transactions, ctx={ctx}"
                raise TypeError(msg)
            for d in txns_raw:
                # Create a single split for each transaction
                category_s = d.pop("category", "Uncategorized")
                if not isinstance(category_s, str):  # pragma: no cover
                    # Don't need to test debug code
                    msg = f"Category is not a string, ctx={ctx}"
                    raise TypeError(msg)
                date = d.pop("date")
                if not isinstance(date, datetime.date):  # pragma: no cover
                    # Don't need to test debug code
                    msg = f"Date is not a datetime.date, ctx={ctx}"
                    raise TypeError(msg)
                d["date_ord"] = date.toordinal()
                d_split: importers.TxnDict = {
                    "amount": d["amount"],  # Both split and parent have amount
                    "payee": d.pop("payee", None),
                    "description": d.pop("description", None),
                    "category_id": categories[category_s].id_,
                    "tag": d.pop("tag", None),
                    "asset_quantity_unadjusted": d.pop("asset_quantity", None),
                }

                acct_raw = d.pop("account")
                if not isinstance(acct_raw, str):  # pragma: no cover
                    # Don't need to test debug code
                    msg = f"Account is not a string, ctx={ctx}"
                    raise TypeError(msg)
                acct_id = acct_mapping.get(acct_raw)
                if acct_id is None:
                    acct = self.find_account(acct_raw, session=s)
                    if not isinstance(acct, Account):
                        msg = f"Could not find Account by '{acct_raw}', ctx={ctx}"
                        raise KeyError(msg)
                    acct_id = acct.id_
                    acct_mapping[acct_raw] = acct_id
                d["account_id"] = acct_id

                asset_raw = d.pop("asset", None)
                if asset_raw is not None:
                    if not isinstance(asset_raw, str):  # pragma: no cover
                        # Don't need to test debug code
                        msg = f"Asset is not a string, ctx={ctx}"
                        raise TypeError(msg)
                    # Find its ID
                    asset_id = asset_mapping.get(asset_raw)
                    if asset_id is None:
                        asset = self.find_asset(asset_raw, session=s)
                        if not isinstance(asset, Asset):
                            msg = f"Could not find Asset by '{asset_raw}', ctx={ctx}"
                            raise KeyError(msg)
                        asset_id = asset.id_
                        asset_mapping[asset_raw] = asset_id
                    d_split["asset_id"] = asset_id

                txns.append((Transaction(**d), TransactionSplit(**d_split)))

            # All good, add transactions and commit
            for txn, t_split in txns:
                t_split.parent = txn
                s.add_all((txn, t_split))

            # Add file hash to prevent importing again
            if force:
                existing = s.query(ImportedFile).where(ImportedFile.hash_ == h).scalar()
                if existing is not None:
                    s.delete(existing)
                    s.commit()

            s.add(ImportedFile(hash_=h))
            s.commit()

    def find_account(
        self,
        search: int | str,
        session: orm.Session | None = None,
    ) -> int | Account | None:
        """Find a matching Account by name, URI, institution, or ID.

        Args:
            search: Search query
            session: Session to use, will return Account not id

        Returns:
            Account ID or None if no matches found
            If session is not None: return Account object or None
        """

        def _find(s: orm.Session) -> int | None:
            if isinstance(search, int):
                # See if search is an ID first...
                query = s.query(Account.id_).where(Account.id_ == search)
                return search if query.count() == 1 else None
            try:
                # See if query is an URI
                id_ = Account.uri_to_id(search)
            except (exc.InvalidURIError, exc.WrongURITypeError):
                pass
            else:
                query = s.query(Account.id_).where(Account.id_ == id_)
                try:
                    return query.one()[0]
                except (exc.NoResultFound, exc.MultipleResultsFound):
                    pass

            # Maybe a number next
            query = s.query(Account.id_).where(Account.number == search)
            try:
                return query.one()[0]
            except (exc.NoResultFound, exc.MultipleResultsFound):
                pass

            # Maybe an institution next
            query = s.query(Account.id_).where(Account.institution == search)
            try:
                return query.one()[0]
            except (exc.NoResultFound, exc.MultipleResultsFound):
                pass

            # Maybe a name next
            query = s.query(Account.id_).where(Account.name == search)
            try:
                return query.one()[0]
            except (exc.NoResultFound, exc.MultipleResultsFound):
                pass

            return None

        if session is None:
            with self.get_session() as s:
                return _find(s)
        a_id = _find(session)
        if a_id is None:
            return None
        return session.query(Account).where(Account.id_ == a_id).one()

    def find_asset(
        self,
        search: int | str,
        session: orm.Session | None = None,
    ) -> int | Asset | None:
        """Find a matching Asset by name, URI, or ID.

        Args:
            search: Search query
            session: Session to use, will return Asset not id

        Returns:
            Asset ID or None if no matches found
            If session is not None: return Asset object or None
        """

        def _find(s: orm.Session) -> int | None:
            if isinstance(search, int):
                # See if search is an ID first...
                query = s.query(Asset.id_).where(Asset.id_ == search)
                return search if query.count() == 1 else None
            try:
                # See if search is an URI
                id_ = Asset.uri_to_id(search)
            except (exc.InvalidURIError, exc.WrongURITypeError):
                pass
            else:
                query = s.query(Asset.id_).where(Asset.id_ == id_)
                try:
                    return query.one()[0]
                except (exc.NoResultFound, exc.MultipleResultsFound):
                    pass

            # Maybe a ticker next
            query = s.query(Asset.id_).where(Asset.ticker == search)
            try:
                return query.one()[0]
            except (exc.NoResultFound, exc.MultipleResultsFound):
                pass

            # Maybe a name next
            query = s.query(Asset.id_).where(Asset.name == search)
            try:
                return query.one()[0]
            except (exc.NoResultFound, exc.MultipleResultsFound):
                pass

            return None

        if session is None:
            with self.get_session() as s:
                return _find(s)
        acct_id = _find(session)
        if acct_id is None:
            return None
        return session.query(Asset).where(Asset.id_ == acct_id).one()

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
                    file = self._path_images.joinpath(asset.image_name)  # type: ignore[attr-defined]
                    files.append(file)

            for file in files:
                tar.add(file, arcname=file.relative_to(parent))
            # Add a timestamp of when it was created
            info = tarfile.TarInfo("_timestamp")
            buf = datetime.datetime.utcnow().isoformat().encode()
            info.size = len(buf)
            tar.addfile(info, io.BytesIO(buf))

        path_backup.chmod(0o600)  # Only owner can read/write
        return path_backup, tar_ver

    @staticmethod
    def backups(p: str | Path | Portfolio) -> list[tuple[int, datetime.datetime]]:
        """Get a list of all backups for this portfolio.

        Args:
            p: Path to database file, or Portfolio which will get its path

        Returns:
            List[(tar_ver, created timestamp), ...]
        """
        backups: list[tuple[int, datetime.datetime]] = []

        path_db = Path(p._path_db if isinstance(p, Portfolio) else p)  # noqa: SLF001
        path_db = path_db.resolve().with_suffix(".db")
        parent = path_db.parent
        name = path_db.with_suffix("").name

        # Find latest backup file for this Portfolio
        re_filter = re.compile(rf"^{name}.backup(\d+).tar.gz$")
        for file in parent.iterdir():
            m = re_filter.match(file.name)
            if m is None:
                continue
            # tar archive preserved owner and mode so no need to set these
            with tarfile.open(file, "r:gz") as tar:
                file_ts = tar.extractfile("_timestamp")
                if file_ts is None:  # pragma: no cover
                    # Backup file should always have timestamp file
                    msg = "timestamp file is None"
                    raise TypeError(msg)
                tar_ver = int(m[1])
                ts = datetime.datetime.fromisoformat(file_ts.read().decode())
                ts = ts.replace(tzinfo=datetime.timezone.utc)
                backups.append((tar_ver, ts))
        return sorted(backups, key=lambda item: item[0])

    def clean(self) -> None:
        """Delete any unused files, creates a new backup."""
        # Create a backup before optimizations
        path_backup, _ = self.backup()

        # Prune unused AssetValuations
        with self.get_session() as s:
            for asset in s.query(Asset).all():
                asset.prune_valuations()
            s.commit()

        # Optimize database
        with self.get_session() as s:
            s.execute(sqlalchemy.text("VACUUM"))
            s.commit()

        path_backup_optimized, _ = self.backup()

        # Delete all files that start with name except the fresh backups
        parent = self._path_db.parent
        name = self._path_db.with_suffix("").name
        for file in parent.iterdir():
            if file in (path_backup, path_backup_optimized):
                continue
            if file == self._path_importers:
                continue
            if file.name.startswith(f"{name}."):
                if file.is_dir():
                    shutil.rmtree(file)
                else:
                    file.unlink()

        # Move backup to i=1
        path_new = parent.joinpath(f"{name}.backup1.tar.gz")
        shutil.move(path_backup, path_new)

        # Move optimized backup to i=2
        path_new = parent.joinpath(f"{name}.backup2.tar.gz")
        shutil.move(path_backup_optimized, path_new)

        # Restore the optimized version
        Portfolio.restore(self, tar_ver=2)

        # Delete optimized backup version since that is the live version
        path_new.unlink()

    @staticmethod
    def restore(p: str | Path | Portfolio, tar_ver: int | None = None) -> None:
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
                str(p._path_config),  # noqa: SLF001
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

    def update_assets(
        self,
    ) -> list[tuple[str, str, t.Date | None, t.Date | None, str | None]]:
        """Update asset valuations using web sources.

        Returns:
            Assets that were updated
            [
                (name, ticker, start date, end date, error),
                ...
            ]
        """
        today = datetime.date.today()
        today_ord = today.toordinal()
        updated: list[tuple[str, str, t.Date | None, t.Date | None, str | None]] = []

        with self.get_session() as s:
            assets = s.query(Asset).where(Asset.ticker.isnot(None)).all()
            ids = [asset.id_ for asset in assets]

            # Get currently held assets
            asset_qty = Account.get_asset_qty_all(s, today_ord, today_ord)
            currently_held_assets: set[int] = set()
            for acct_assets in asset_qty.values():
                for a_id, qty in acct_assets.items():
                    if a_id in ids and qty[0] != 0:
                        currently_held_assets.add(a_id)

            bar = tqdm.tqdm(assets, desc="Updating Assets")
            for asset in bar:
                name = asset.name
                ticker = asset.ticker or ""
                try:
                    start, end = asset.update_valuations(
                        s,
                        through_today=asset.id_ in currently_held_assets,
                    )
                except exc.AssetWebError as e:
                    updated.append((name, ticker, None, None, str(e)))
                else:
                    if start is not None:
                        updated.append((name, ticker, start, end, None))
                    # start & end are None if there are no transactions for the Asset

            s.commit()

        return updated
