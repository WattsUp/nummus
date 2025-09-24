"""Portfolio of financial records."""

from __future__ import annotations

import base64
import datetime
import hashlib
import io
import operator
import re
import secrets
import shutil
import sys
import tarfile
from pathlib import Path
from typing import NamedTuple, TYPE_CHECKING

import sqlalchemy
import tqdm
from packaging.version import Version
from sqlalchemy import func, orm

from nummus import __version__, encryption
from nummus import exceptions as exc
from nummus import importers, migrations, models, sql, utils
from nummus.models import (
    Account,
    Asset,
    Config,
    ConfigKey,
    ImportedFile,
    one_or_none,
    query_to_dict,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    import contextlib

    from nummus.importers.base import TxnDict
    from nummus.models import (
        Base,
    )


class AssetUpdate(NamedTuple):
    """Information about an asset update event."""

    name: str
    ticker: str
    start: datetime.date | None
    end: datetime.date | None
    error: str | None


class Portfolio:
    """A collection of financial records.

    Records include: transactions, accounts, and assets
    """

    _ENCRYPTION_TEST_VALUE = "nummus encryption test string"

    def __init__(
        self,
        path: str | Path,
        key: str | None,
        *,
        check_migration: bool = True,
    ) -> None:
        """Initialize Portfolio.

        Args:
            path: Path to database file
            key: String password to unlock database encryption
            check_migration: True will check if migration is required

        Raises:
            FileNotFoundError: If database does not exist
            MigrationRequiredError: If migration is required

        """
        self._path_db = Path(path).resolve().with_suffix(".db")
        self._path_salt = self._path_db.with_suffix(".nacl")
        self._path_importers = self._path_db.with_suffix(".importers")
        if not self._path_db.exists():
            msg = f"Portfolio at {self._path_db} does not exist, use Portfolio.create()"
            raise FileNotFoundError(msg)
        self._path_importers.mkdir(exist_ok=True)  # Make if it doesn't exist

        if key is None:
            self._enc = None
        elif self._path_salt.exists():
            with self._path_salt.open("rb") as file:
                enc_config = file.read()
            self._enc = encryption.Encryption(key, enc_config)
        else:
            msg = f"Portfolio at {self._path_db} does not have salt file"
            raise FileNotFoundError(msg)
        self._session_maker = orm.sessionmaker(self.get_engine())
        configs = self._unlock()

        self._importers = importers.get_importers(self._path_importers)

        version_str = configs.get(ConfigKey.VERSION)
        if check_migration and (v := self.migration_required(version_str)):
            msg = f"Portfolio requires migration to v{v}"
            raise exc.MigrationRequiredError(msg)

    @property
    def path(self) -> Path:
        """Path to Portfolio database."""
        return self._path_db

    @property
    def path_salt(self) -> Path:
        """Path to Portfolio salt database."""
        return self._path_salt

    @property
    def importers_path(self) -> Path:
        """Path to Portfolio importers."""
        return self._path_importers

    @classmethod
    def is_encrypted_path(cls, path: str | Path) -> bool:
        """Check Portfolio's config for encryption status.

        Args:
            path: Path to database file

        Returns:
            True if Portfolio is encrypted

        Raises:
            FileNotFoundError: If database or configuration does not exist

        """
        path_db = Path(path)
        if not path_db.exists():
            msg = f"Database does not exist at {path_db}"
            raise FileNotFoundError(msg)
        path_salt = path_db.with_suffix(".nacl")
        return path_salt.exists()

    @property
    def is_encrypted(self) -> bool:
        """Check if portfolio is encrypted."""
        return self._enc is not None

    @classmethod
    def create(cls, path: str | Path, key: str | None = None) -> Portfolio:
        """Create a new Portfolio.

        Saves database and configuration file

        Args:
            path: Path to database file
            key: String password to unlock database encryption

        Returns:
            Portfolio linked to newly created database

        Raises:
            FileExistsError: If database already exists

        """
        path_db = Path(path).resolve()
        if path_db.exists():
            msg = f"Database already exists at {path_db}"
            raise FileExistsError(msg)
        path_salt = path_db.with_suffix(".nacl")
        path_importers = path_db.with_suffix(".importers")

        path_db.parent.mkdir(parents=True, exist_ok=True)
        path_importers.mkdir(exist_ok=True)

        enc = None
        enc_config = None
        if encryption.AVAILABLE and key is not None:
            enc, enc_config = encryption.Encryption.create(key)
            with path_salt.open("wb") as file:
                file.write(enc_config)
            path_salt.chmod(0o600)  # Only owner can read/write
        else:
            # Remove salt if unencrypted
            path_salt.unlink(missing_ok=True)

        cipher_bytes = models.Cipher.generate().to_bytes()
        cipher_b64 = base64.b64encode(cipher_bytes).decode()

        if enc is None:
            test_value = Portfolio._ENCRYPTION_TEST_VALUE
        else:
            test_value = enc.encrypt(Portfolio._ENCRYPTION_TEST_VALUE)

        engine = sql.get_engine(path_db, enc)
        with orm.Session(engine) as s:
            with s.begin():
                models.metadata_create_all(s)

            with s.begin():
                # If developing a migration, current version will be less
                # Set new portfolio to max of nummus version and MIGRATORS
                v = max(
                    Version(__version__),
                    *[m.min_version() for m in migrations.MIGRATORS],
                )

                c_version = Config(
                    key=ConfigKey.VERSION,
                    value=str(v),
                )
                c_enc_test = Config(
                    key=ConfigKey.ENCRYPTION_TEST,
                    value=test_value,
                )
                c_cipher = Config(
                    key=ConfigKey.CIPHER,
                    value=cipher_b64,
                )
                c_key = Config(
                    key=ConfigKey.SECRET_KEY,
                    value=secrets.token_hex(),
                )

                s.add_all((c_version, c_enc_test, c_cipher, c_key))

                if enc is not None and key is not None:
                    c_web_key = Config(
                        key=ConfigKey.WEB_KEY,
                        value=enc.encrypt(key),
                    )
                    s.add(c_web_key)
        path_db.chmod(0o600)  # Only owner can read/write

        p = Portfolio(path_db, key)
        with p.begin_session() as s:
            TransactionCategory.add_default(s)
            Asset.add_indices(s)
        return p

    def _unlock(self) -> dict[ConfigKey, str]:
        """Unlock the database.

        Returns:
            Configuration properties

        Raises:
            UnlockingError: If database file fails to open
            ProtectedObjectNotFoundError: If URI cipher is missing

        """
        try:
            with self.begin_session() as s:
                query = s.query(Config).with_entities(Config.key, Config.value)
                configs: dict[ConfigKey, str] = query_to_dict(query)
        except exc.DatabaseError as e:
            msg = f"Failed to open database {self._path_db}"
            raise exc.UnlockingError(msg) from e

        value = configs.get(ConfigKey.ENCRYPTION_TEST)
        if value is None:
            msg = "Config.ENCRYPTION_TEST not found"
            raise exc.ProtectedObjectNotFoundError(msg)

        if self._enc is not None:
            try:
                value = self._enc.decrypt_s(value)
            except ValueError as e:
                msg = "Failed to decrypt root password"
                raise exc.UnlockingError(msg) from e

        if value != self._ENCRYPTION_TEST_VALUE:
            msg = "Test value did not match"
            raise exc.UnlockingError(msg)
        # Load Cipher
        cipher_b64 = configs.get(ConfigKey.CIPHER)
        if cipher_b64 is None:
            msg = "Config.CIPHER not found"
            raise exc.ProtectedObjectNotFoundError(msg)
        models.load_cipher(base64.b64decode(cipher_b64))
        # All good :)
        return configs

    def get_engine(self) -> sqlalchemy.Engine:
        """Get SQL Engine to the database.

        Returns:
            Engine

        """
        return sql.get_engine(self._path_db, self._enc)

    def begin_session(self) -> contextlib.AbstractContextManager[orm.Session]:
        """Get SQL Session to the database.

        Returns:
            Open Session

        """
        return self._session_maker.begin()

    def encrypt(self, secret: bytes | str) -> str:
        """Encrypt a secret using the key.

        Args:
            secret: Secret object

        Returns:
            base64 encoded encrypted object

        Raises:
            NotEncryptedError: If portfolio does not support encryption

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
            NotEncryptedError: If portfolio does not support encryption

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

    @property
    def db_version(self) -> Version:
        """Check the version of portfolio is current and does not need migration.

        Returns:
            Version of database

        Raises:
            ProtectedObjectNotFoundError: If VERSION is not found

        """
        with self.begin_session() as s:
            try:
                v = (
                    s.query(Config.value)
                    .where(Config.key == ConfigKey.VERSION)
                    .one()[0]
                )
            except exc.NoResultFound as e:
                msg = "Config.VERSION not found"
                raise exc.ProtectedObjectNotFoundError(msg) from e

            return Version(v)

    def migration_required(self, version_str: str | None) -> Version | None:
        """Check if migration is required.

        Args:
            version_str: Config VERSION value, will skip extra query

        Returns:
            Version to migrate to or None if migration not required

        """
        v_db = self.db_version if version_str is None else Version(version_str)
        for m in migrations.MIGRATORS[::-1]:
            v_m = m.min_version()
            if v_db < v_m:
                return v_m
        return None

    def import_file(self, path: Path, path_debug: Path, *, force: bool = False) -> None:
        """Import a file into the Portfolio.

        Args:
            path: Path to file to import
            path_debug: Path to temporary debug file
            force: True will not check for already imported files

        Raises:
            FileAlreadyImportedError: If file has already been imported
            FutureTransactionError: If transaction date is in the future
            FailedImportError: If importer encounters an error
            EmptyImportError: If importer returns no transactions

        """
        # Compute hash of file contents to check if already imported
        sha = hashlib.sha256()
        with path.open("rb") as file:
            sha.update(file.read())
        h = sha.hexdigest()
        with self.begin_session() as s:
            if force:
                s.query(ImportedFile).where(ImportedFile.hash_ == h).delete()
            existing_date_ord: int | None = (
                s.query(ImportedFile.date_ord).where(ImportedFile.hash_ == h).scalar()
            )
            if existing_date_ord is not None:
                date = datetime.date.fromordinal(existing_date_ord)
                raise exc.FileAlreadyImportedError(date, path)

            i = importers.get_importer(path, path_debug, self._importers)
            today = datetime.datetime.now(datetime.UTC).date()

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}
            # Cache a mapping from account/asset name to the ID
            acct_mapping: dict[str, tuple[int, str | None]] = {}
            asset_mapping: dict[str, tuple[int, str | None]] = {}
            try:
                txns_raw = i.run()
            except Exception as e:
                raise exc.FailedImportError(path, i) from e
            if not txns_raw:
                raise exc.EmptyImportError(path, i)
            for d in txns_raw:
                if d["date"] > today:
                    raise exc.FutureTransactionError

                # Create a single split for each transaction
                acct_raw = d["account"]
                acct_id, _ = self.find(s, Account, acct_raw, acct_mapping)

                asset_raw = d["asset"]
                asset_id: int | None = None
                if asset_raw:
                    asset_id, asset_name = self.find(s, Asset, asset_raw, asset_mapping)
                    if not d["statement"]:
                        d["statement"] = f"Asset Transaction {asset_name}"

                self._import_transaction(s, d, acct_id, asset_id, categories)

            # Add file hash to prevent importing again
            s.add(ImportedFile(hash_=h))

            # Update splits on each touched
            query = s.query(Asset).where(
                Asset.id_.in_(a_id for a_id, _ in asset_mapping.values()),
            )
            for asset in query.all():
                asset.update_splits()

        # If successful, delete the temp file
        path_debug.unlink()

    def _import_transaction(
        self,
        s: orm.Session,
        d: TxnDict,
        acct_id: int,
        asset_id: int | None,
        categories: dict[str, int],
    ) -> None:
        if asset_id is not None:
            self._import_asset_transaction(s, d, acct_id, asset_id, categories)
            return

        # See if anything matches
        date_ord = d["date"].toordinal()
        matches = list(
            s.query(Transaction)
            .with_entities(Transaction.id_, Transaction.date_ord)
            .where(
                Transaction.account_id == acct_id,
                Transaction.amount == d["amount"],
                Transaction.date_ord >= date_ord - 5,
                Transaction.date_ord <= date_ord + 5,
                Transaction.cleared.is_(False),
            )
            .all(),
        )
        matches = sorted(matches, key=lambda x: abs(x[1] - date_ord))
        # If only one match on closest day, link transaction
        if len(matches) == 1 or (len(matches) > 1 and matches[0][1] != matches[1][1]):
            match_id = matches[0][0]
            statement_clean = Transaction.clean_strings("statement", d["statement"])
            s.query(Transaction).where(Transaction.id_ == match_id).update(
                {
                    "cleared": True,
                    "statement": statement_clean,
                },
            )
            s.query(TransactionSplit).where(
                TransactionSplit.parent_id == match_id,
            ).update({"cleared": True})
            return

        category_name = (d["category"] or "uncategorized").lower()
        try:
            category_id = categories[category_name]
        except KeyError:
            category_id = categories["uncategorized"]

        txn = Transaction(
            account_id=acct_id,
            amount=d["amount"],
            date=d["date"],
            statement=d["statement"],
            payee=d["payee"],
            cleared=True,
        )
        t_split = TransactionSplit(
            amount=d["amount"],
            memo=d["memo"],
            category_id=category_id,
        )
        t_split.parent = txn
        s.add_all((txn, t_split))

    @classmethod
    def _import_asset_transaction(
        cls,
        s: orm.Session,
        d: TxnDict,
        acct_id: int,
        asset_id: int,
        categories: dict[str, int],
    ) -> None:
        category_name = (d["category"] or "uncategorized").lower()
        if category_name == "investment fees":
            # Associate fees with asset
            amount = abs(d["amount"])
            qty = d["asset_quantity"]
            if qty is None:
                msg = "Investment Fees needs Asset and quantity"
                raise exc.MissingAssetError(msg)
            qty = abs(qty)

            txn = Transaction(
                account_id=acct_id,
                amount=0,
                date=d["date"],
                statement=d["statement"],
                payee=d["payee"],
                cleared=True,
            )
            t_split_0 = TransactionSplit(
                parent=txn,
                amount=amount,
                memo=d["memo"],
                category_id=categories["securities traded"],
                asset_id=asset_id,
                asset_quantity_unadjusted=-qty,
            )
            t_split_1 = TransactionSplit(
                parent=txn,
                amount=-amount,
                memo=d["memo"],
                category_id=categories["investment fees"],
                asset_id=asset_id,
                asset_quantity_unadjusted=0,
            )
            s.add_all((txn, t_split_0, t_split_1))
            return
        if category_name == "dividends received":
            # Associate dividends with asset
            amount = abs(d["amount"])
            qty = d["asset_quantity"]
            if qty is None or asset_id is None:
                msg = "Dividends Received needs Asset and quantity"
                raise exc.MissingAssetError(msg)
            qty = abs(qty)

            txn = Transaction(
                account_id=acct_id,
                amount=0,
                date=d["date"],
                statement=d["statement"],
                payee=d["payee"],
                cleared=True,
            )
            t_split_0 = TransactionSplit(
                parent=txn,
                amount=amount,
                memo=d["memo"],
                category_id=categories["dividends received"],
                asset_id=asset_id,
                asset_quantity_unadjusted=0,
            )
            t_split_1 = TransactionSplit(
                parent=txn,
                amount=-amount,
                memo=d["memo"],
                category_id=categories["securities traded"],
                asset_id=asset_id,
                asset_quantity_unadjusted=qty,
            )
            s.add_all((txn, t_split_0))
            if qty != 0:
                # Zero quantity means cash dividends, not reinvested
                s.add(t_split_1)
            return
        if category_name == "securities traded":
            txn = Transaction(
                account_id=acct_id,
                amount=d["amount"],
                date=d["date"],
                statement=d["statement"],
                payee=d["payee"],
                cleared=True,
            )
            t_split = TransactionSplit(
                amount=d["amount"],
                memo=d["memo"],
                category_id=categories[category_name],
                asset_id=asset_id,
                asset_quantity_unadjusted=d["asset_quantity"],
            )
            t_split.parent = txn
            s.add_all((txn, t_split))
            return

        msg = f"'{category_name}' is not a valid category for asset transaction"
        raise exc.InvalidAssetTransactionCategoryError(msg)

    @classmethod
    def find(
        cls,
        s: orm.Session,
        model: type[Base],
        search: str,
        cache: dict[str, tuple[int, str | None]],
    ) -> tuple[int, str | None]:
        """Find a matching object by  uri, or field value.

        Args:
            s: Session to use
            model: Type of model to search for
            search: Search query
            cache: Cache results to speed up look ups

        Returns:
            tuple(id_, name)

        Raises:
            NoResultFound: if object not found

        """
        id_, name = cache.get(search, (None, None))
        if id_ is not None:
            return id_, name

        def cache_and_return(m: Base) -> tuple[int, str | None]:
            id_ = m.id_
            name: str | None = getattr(m, "name", None)
            cache[search] = id_, name
            return id_, name

        try:
            # See if query is an URI
            id_ = model.uri_to_id(search)
        except (exc.InvalidURIError, exc.WrongURITypeError):
            pass
        else:
            query = s.query(model).where(model.id_ == id_)
            if m := one_or_none(query):
                return cache_and_return(m)

        properties: list[orm.QueryableAttribute] = {
            Account: [Account.number, Account.institution, Account.name],
            Asset: [Asset.ticker, Asset.name],
        }[model]
        for prop in properties:
            # Exact?
            query = s.query(model).where(prop == search)
            if m := one_or_none(query):
                return cache_and_return(m)

            # Exact lower case?
            query = s.query(model).where(prop.ilike(search))
            if m := one_or_none(query):
                return cache_and_return(m)

            # For account number, see if there is one ending in the search
            query = s.query(model).where(prop.ilike(f"%{search}"))
            if prop is Account.number and (m := one_or_none(query)):
                return cache_and_return(m)

        msg = f"{model.__name__} matching '{search}' could not be found"
        raise exc.NoResultFound(msg)

    def backup(self) -> tuple[Path, int]:
        """Back up database, duplicates files.

        Returns:
            (Path to newly created backup tar, backup version)

        """
        # Find latest backup file for this Portfolio
        i = 0
        parent = self._path_db.parent
        name = self._path_db.with_suffix("").name
        re_filter = re.compile(rf"^{name}.backup(\d+).tar$")
        for file in parent.iterdir():
            m = re_filter.match(file.name)
            if m is not None:
                i = max(i, int(m.group(1)))
        tar_ver = i + 1

        path_backup = self._path_db.with_suffix(f".backup{tar_ver}.tar")

        with tarfile.open(path_backup, "w") as tar:
            files: list[Path] = [self._path_db]

            if self._path_salt.exists():
                files.append(self._path_salt)

            for file in files:
                tar.add(file, arcname=file.relative_to(parent))
            # Add a timestamp of when it was created
            info = tarfile.TarInfo("_timestamp")
            buf = datetime.datetime.now(datetime.UTC).isoformat().encode()
            info.size = len(buf)
            tar.addfile(info, io.BytesIO(buf))

        path_backup.chmod(0o600)  # Only owner can read/write
        return path_backup, tar_ver

    @classmethod
    def backups(cls, p: str | Path | Portfolio) -> list[tuple[int, datetime.datetime]]:
        """Get a list of all backups for this portfolio.

        Args:
            p: Path to database file, or Portfolio which will get its path

        Returns:
            List[(tar_ver, created timestamp), ...]

        Raises:
            InvalidBackupTarError: If backup is missing timestamp

        """
        backups: list[tuple[int, datetime.datetime]] = []

        path_db = Path(p.path if isinstance(p, Portfolio) else p)
        path_db = path_db.resolve().with_suffix(".db")
        parent = path_db.parent
        name = path_db.with_suffix("").name

        # Find latest backup file for this Portfolio
        re_filter = re.compile(rf"^{name}.backup(\d+).tar$")
        for file in parent.iterdir():
            m = re_filter.match(file.name)
            if m is None:
                continue
            # tar archive preserved owner and mode so no need to set these
            with tarfile.open(file, "r") as tar:
                try:
                    file_ts = tar.extractfile("_timestamp")
                except KeyError as e:
                    # Backup file should always have timestamp file
                    msg = "Backup is missing timestamp"
                    raise exc.InvalidBackupTarError(msg) from e
                if file_ts is None:
                    # Backup file should always have timestamp file
                    msg = "Backup is missing timestamp"
                    raise exc.InvalidBackupTarError(msg)
                tar_ver = int(m[1])
                ts = datetime.datetime.fromisoformat(file_ts.read().decode())
                ts = ts.replace(tzinfo=datetime.UTC)
                backups.append((tar_ver, ts))
        return sorted(backups, key=operator.itemgetter(0))

    def clean(self) -> tuple[int, int]:
        """Delete any unused files, creates a new backup.

        Returns:
            Size of files in bytes:
            (portfolio before, portfolio after)

        """
        parent = self._path_db.parent
        name = self._path_db.with_suffix("").name

        # Create a backup before optimizations
        path_backup, _ = self.backup()
        size_before = self._path_db.stat().st_size

        # Prune unused AssetValuations
        with self.begin_session() as s:
            for asset in s.query(Asset).yield_per(YIELD_PER):
                asset.prune_valuations()
                asset.autodetect_interpolate()

        # Optimize database
        with self.begin_session() as s:
            s.execute(sqlalchemy.text("VACUUM"))

        path_backup_optimized, _ = self.backup()
        size_after = self._path_db.stat().st_size

        # Delete all files that start with name except the fresh backups
        for file in parent.iterdir():
            if file in {path_backup, path_backup_optimized}:
                continue
            if file == self._path_importers:
                continue
            if file.name.startswith(f"{name}."):
                if file.is_dir():
                    shutil.rmtree(file)
                else:
                    file.unlink()

        # Move backup to i=1
        path_new = parent.joinpath(f"{name}.backup1.tar")
        shutil.move(path_backup, path_new)

        # Move optimized backup to i=2
        path_new = parent.joinpath(f"{name}.backup2.tar")
        shutil.move(path_backup_optimized, path_new)

        # Restore the optimized version
        Portfolio.restore(self, tar_ver=2)

        # Delete optimized backup version since that is the live version
        path_new.unlink()

        return (size_before, size_after)

    @classmethod
    def restore(cls, p: str | Path | Portfolio, tar_ver: int | None = None) -> None:
        """Restore Portfolio from backup.

        Args:
            p: Path to database file, or Portfolio which will get its path
            tar_ver: Backup version to restore, None will use latest

        Raises:
            FileNotFoundError: If backup does not exist
            InvalidBackupTarError: If backup is missing required files

        """
        path_db = Path(p.path if isinstance(p, Portfolio) else p)
        path_db = path_db.resolve()
        parent = path_db.parent
        stem = path_db.stem

        tar_ver = tar_ver or cls._latest_backup_version(path_db)

        path_backup = parent.joinpath(f"{stem}.backup{tar_ver}.tar")
        if not path_backup.exists():
            msg = f"Backup does not exist {path_backup}"
            raise FileNotFoundError(msg)

        # tar archive preserved owner and mode so no need to set these
        with tarfile.open(path_backup, "r") as tar:
            required = {
                "_timestamp",
                re.sub(r"\.backup\d+.tar$", ".db", path_backup.name),
            }
            members = tar.getmembers()
            member_paths = [member.path for member in members]
            missing = [m for m in required if m not in member_paths]
            if missing:
                msg = f"Backup is missing required files: {missing}"
                raise exc.InvalidBackupTarError(msg)

            cls.delete_files(path_db)
            for member in members:
                if member.path == "_timestamp":
                    continue
                dest = parent.joinpath(member.path).resolve()
                if not dest.is_relative_to(parent):
                    # Dest should still be relative to parent else, path traversal
                    msg = "Backup contains a file outside of destination"
                    raise exc.InvalidBackupTarError(msg)

                if (
                    (3, 10, 12) <= sys.version_info < (3, 11)
                    or (3, 11, 4) <= sys.version_info < (3, 12)
                    or (3, 12) <= sys.version_info < (3, 14)
                ):  # pragma: no cover
                    # These versions add filter parameter
                    # Don't care which one gets covered
                    tar.extract(member, parent, filter="data")
                else:  # pragma: no cover
                    tar.extract(member, parent)

        # Reload Portfolio
        if isinstance(p, Portfolio):
            p._unlock()  # noqa: SLF001

    @classmethod
    def _latest_backup_version(cls, path_db: Path) -> int:
        """Get the latest backup version available.

        Args:
            path_db: Path to portfolio

        Returns:
            latest version

        Raises:
            FileNotFoundError: if no backups exists

        """
        parent = path_db.parent
        stem = path_db.stem
        # Find latest backup file for this Portfolio
        i = 0
        re_filter = re.compile(rf"^{stem}.backup(\d+).tar$")
        for file in parent.iterdir():
            if m := re_filter.match(file.name):
                i = max(i, int(m.group(1)))
        if i == 0:
            msg = f"No backup exists for {path_db}"
            raise FileNotFoundError(msg)
        return i

    @classmethod
    def delete_files(cls, path_db: Path) -> None:
        """Delete all files and folder for portfolio.

        Args:
            path_db: Path to portfolio

        """
        path_db.unlink(missing_ok=True)
        path_db.with_suffix(".nacl").unlink(missing_ok=True)

        path = path_db.with_suffix(".importers")
        if path.exists() and not path.is_symlink():
            shutil.rmtree(path)

    def update_assets(self, *, no_bars: bool = False) -> list[AssetUpdate]:
        """Update asset valuations using web sources.

        Args:
            no_bars: True disables progress bars

        Returns:
            Assets that were updated
            [AssetUpdate for each]

        """
        today = datetime.datetime.now(datetime.UTC).date()
        today_ord = today.toordinal()
        updated: list[AssetUpdate] = []

        with self.begin_session() as s:
            assets = s.query(Asset).where(Asset.ticker.isnot(None)).all()
            ids = [asset.id_ for asset in assets]

            # Get currently held assets
            asset_qty = Account.get_asset_qty_all(s, today_ord, today_ord)
            currently_held_assets: set[int] = set()
            for acct_assets in asset_qty.values():
                for a_id in ids:
                    if acct_assets[a_id][0] != 0:
                        currently_held_assets.add(a_id)

            bar = tqdm.tqdm(assets, desc="Updating Assets", disable=no_bars)
            for asset in bar:
                name = asset.name
                ticker = asset.ticker or ""
                asset.update_sectors()
                try:
                    start, end = asset.update_valuations(
                        through_today=asset.id_ in currently_held_assets,
                    )
                except exc.AssetWebError as e:
                    updated.append(AssetUpdate(name, ticker, None, None, str(e)))
                else:
                    if start is not None:
                        updated.append(AssetUpdate(name, ticker, start, end, None))
                    # start & end are None if there are no transactions for the Asset

            # Auto update if asset needs interpolation
            for asset in s.query(Asset).all():
                asset.autodetect_interpolate()

        return updated

    def change_key(self, key: str) -> None:
        """Change portfolio password.

        This also works to add encryption to an unencrypted portfolio.

        Args:
            key: New portfolio key

        Raises:
            InvalidKeyError: If key does not match minimum requirements

        """
        if len(key) < utils.MIN_PASS_LEN:
            msg = f"Password must be at least {utils.MIN_PASS_LEN} characters"
            raise exc.InvalidKeyError(msg)

        # Changing portfolio password requires recreating it
        path_new = self._path_db.with_suffix(".new.db")
        dst = Portfolio.create(path_new, key)

        engine_src = self.get_engine()
        engine_dst = dst.get_engine()

        exclude_tables = {"config"}

        def filter_(tables: list[sqlalchemy.Table]) -> list[sqlalchemy.Table]:
            return [table for table in tables if table.name not in exclude_tables]

        with engine_src.connect() as conn_src, engine_dst.connect() as conn_dst:
            metadata_src = sqlalchemy.MetaData()
            metadata_src.reflect(bind=engine_src)
            metadata_dst = sqlalchemy.MetaData()
            metadata_dst.reflect(bind=engine_dst)

            # Drop destination tables in order of foreign keys
            for table in reversed(filter_(metadata_dst.sorted_tables)):
                table.drop(bind=engine_dst)
            metadata_dst.clear()
            metadata_dst.reflect(bind=engine_dst)

            # Create destination tables in order of foreign keys
            for table in filter_(metadata_src.sorted_tables):
                table.create(bind=engine_dst)
            metadata_dst.clear()
            metadata_dst.reflect(bind=engine_dst)

            # Count total number of rows for progress bar
            col = func.count(sqlalchemy.literal_column("*"))
            n = 0
            for table in filter_(metadata_src.sorted_tables):
                query = sqlalchemy.select(col).select_from(table)
                result = conn_src.execute(query).scalar_one()
                n += result

            # Copy each row, metadata is the same so order of columns is the same
            with tqdm.tqdm(desc="Copying rows", total=n) as bar:
                for table in filter_(metadata_dst.sorted_tables):
                    table_src = metadata_src.tables[table.name]
                    statement = table.insert()
                    select = conn_src.execute(table_src.select())
                    for row in select:
                        conn_dst.execute(statement.values(row))
                        bar.update()

            conn_dst.commit()

        # Use new encryption key
        with self.begin_session() as s:
            value_encrypted: str | None = (
                s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
            )
            value = key if value_encrypted is None else self.decrypt_s(value_encrypted)
        dst.change_web_key(value)

        # Move new database into existing
        shutil.copyfile(dst.path, self.path)
        shutil.copyfile(dst.path_salt, self.path_salt)

        # Test unlock
        self._enc = dst._enc  # noqa: SLF001
        self._session_maker = orm.sessionmaker(self.get_engine())
        self._unlock()

        # And delete temporary
        self.delete_files(dst.path)

    def change_web_key(self, key: str) -> None:
        """Change password used to access web.

        Args:
            key: New web key

        Raises:
            InvalidKeyError: If key does not match minimum requirements

        """
        if len(key) < utils.MIN_PASS_LEN:
            msg = f"Password must be at least {utils.MIN_PASS_LEN} characters"
            raise exc.InvalidKeyError(msg)

        key_encrypted = self.encrypt(key)
        with self.begin_session() as s:
            s.query(Config).where(Config.key == ConfigKey.WEB_KEY).update(
                {Config.value: key_encrypted},
            )
