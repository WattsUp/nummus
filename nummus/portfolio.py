"""Portfolio of financial records."""

from __future__ import annotations

import base64
import datetime
import hashlib
import io
import re
import shutil
import sys
import tarfile
from pathlib import Path

import sqlalchemy
import tqdm
from rapidfuzz import process
from sqlalchemy import orm

from nummus import encryption
from nummus import exceptions as exc
from nummus import importers, models, sql, utils, version
from nummus.models import (
    Account,
    Asset,
    Config,
    ConfigKey,
    ImportedFile,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)


class Portfolio:
    """A collection of financial records.

    Records include: transactions, accounts, and assets
    """

    _ENCRYPTION_TEST_VALUE = "nummus encryption test string"

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
        self._path_salt = self._path_db.with_suffix(".nacl")
        self._path_importers = self._path_db.parent.joinpath(f"{name}.importers")
        self._path_ssl = self._path_db.parent.joinpath(f"{name}.ssl")
        if not self._path_db.exists():
            msg = f"Portfolio at {self._path_db} does not exist, use Portfolio.create()"
            raise FileNotFoundError(msg)
        self._path_importers.mkdir(exist_ok=True)  # Make if it doesn't exist
        self._path_ssl.mkdir(exist_ok=True)  # Make if it doesn't exist

        if key is None:
            self._enc = None
        elif self._path_salt.exists():
            with self._path_salt.open("rb") as file:
                enc_config = file.read()
            self._enc = encryption.Encryption(key, enc_config)  # type: ignore[attr-defined]
        else:
            msg = f"Portfolio at {self._path_db} does have salt file"
            raise FileNotFoundError(msg)
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
        path_salt = path_db.with_suffix(".nacl")
        return path_salt.exists()

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
        path_salt = path_db.with_suffix(".nacl")
        path_importers = path_db.parent.joinpath(f"{name}.importers")
        path_ssl = path_db.parent.joinpath(f"{name}.ssl")

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

        path_db.parent.mkdir(parents=True, exist_ok=True)
        path_importers.mkdir(exist_ok=True)
        path_ssl.mkdir(exist_ok=True)
        path_ssl.chmod(0o700)  # Only owner can read/write

        cipher_bytes = models.Cipher.generate().to_bytes()
        cipher_b64 = base64.b64encode(cipher_bytes).decode()

        if enc is None:
            test_value = Portfolio._ENCRYPTION_TEST_VALUE
        else:
            test_value = enc.encrypt(Portfolio._ENCRYPTION_TEST_VALUE)

        with sql.get_session(path_db, enc) as s:
            models.metadata_create_all(s)

            c_version = Config(
                key=ConfigKey.VERSION,
                value=str(version.__version__),
            )
            c_enc_test = Config(
                key=ConfigKey.ENCRYPTION_TEST,
                value=test_value,
            )
            c_cipher = Config(
                key=ConfigKey.CIPHER,
                value=cipher_b64,
            )

            s.add_all((c_version, c_enc_test, c_cipher))
            s.commit()
        path_db.chmod(0o600)  # Only owner can read/write

        p = Portfolio(path_db, key)
        with p.get_session() as s:
            TransactionCategory.add_default(s)
            Asset.add_indices(s)
        return p

    def _unlock(self) -> None:
        """Unlock the database.

        Raises:
            UnlockingError if database file fails to open
            ProtectedObjectNotFoundError if URI cipher is missing
        """
        # Drop any open session
        sql.drop_session(self._path_db)
        try:
            with self.get_session() as s:
                try:
                    value: str = (
                        s.query(Config.value)
                        .where(Config.key == ConfigKey.ENCRYPTION_TEST)
                        .one()
                    )[0]
                except exc.NoResultFound as e:
                    msg = "Config.ENCRYPTION_TEST not found"
                    raise exc.UnlockingError(msg) from e
        except exc.DatabaseError as e:
            msg = f"Failed to open database {self._path_db}"
            raise exc.UnlockingError(msg) from e

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
        with self.get_session() as s:
            try:
                cipher_b64: str = (
                    s.query(Config.value).where(Config.key == ConfigKey.CIPHER).one()
                )[0]
            except exc.NoResultFound as e:
                msg = "Config.CIPHER not found"
                raise exc.ProtectedObjectNotFoundError(msg) from e
            models.load_cipher(base64.b64decode(cipher_b64))
        # All good :)

    def get_session(self) -> orm.Session:
        """Get SQL Session to the database.

        Returns:
            Open Session
        """
        return sql.get_session(self._path_db, self._enc)

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

    def import_file(self, path: Path, path_debug: Path, *, force: bool = False) -> None:
        """Import a file into the Portfolio.

        Args:
            path: Path to file to import
            path_debug: Path to temporary debug file
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
                try:
                    existing_date_ord: int = (
                        s.query(ImportedFile.date_ord)
                        .where(ImportedFile.hash_ == h)
                        .one()[0]
                    )
                except exc.NoResultFound:
                    # No conflicts
                    pass
                else:
                    date = datetime.date.fromordinal(existing_date_ord)
                    raise exc.FileAlreadyImportedError(date, path)

        i = importers.get_importer(path, path_debug, self._importers)
        if i is None:
            raise exc.UnknownImporterError(path)
        ctx = f"<importer={i.__class__.__name__}, file={path}>"
        today = datetime.date.today()

        with self.get_session() as s:
            categories: dict[str, TransactionCategory] = {
                cat.name: cat for cat in s.query(TransactionCategory).all()
            }
            # Cache a mapping from account/asset name to the ID
            acct_mapping: dict[str, int] = {}
            asset_mapping: dict[str, tuple[int, str]] = {}
            try:
                txns_raw = i.run()
            except Exception as e:
                msg = f"Importer failed, ctx={ctx}"
                raise exc.FailedImportError(path, i) from e
            if not txns_raw:
                raise exc.EmptyImportError(path, i)
            for d in txns_raw:
                # Create a single split for each transaction
                acct_raw = d["account"]
                acct_id = acct_mapping.get(acct_raw)
                if acct_id is None:
                    acct = self.find_account(acct_raw, session=s)
                    if not isinstance(acct, Account):
                        msg = f"Could not find Account by '{acct_raw}', ctx={ctx}"
                        raise KeyError(msg)
                    acct_id = acct.id_
                    acct_mapping[acct_raw] = acct_id

                statement = d["statement"]

                asset_raw = d["asset"]
                asset_id: int | None = None
                if asset_raw:
                    # Find its ID
                    try:
                        asset_id, asset_name = asset_mapping[asset_raw]
                    except KeyError as e:
                        asset = self.find_asset(asset_raw, session=s)
                        if not isinstance(asset, Asset):
                            msg = f"Could not find Asset by '{asset_raw}', ctx={ctx}"
                            raise KeyError(msg) from e
                        asset_id = asset.id_
                        asset_name = asset.name
                        asset_mapping[asset_raw] = (asset_id, asset_name)
                    if not statement:
                        statement = f"Asset Transaction {asset_name}"

                category_name = d["category"] or "Uncategorized"

                if d["date"] > today:
                    raise exc.FutureTransactionError

                match_id: int | None = None
                if asset_id is not None:
                    if category_name == "Investment Fees":
                        # Associate fees with asset
                        amount = abs(d["amount"])
                        qty = d["asset_quantity"]
                        if qty is None or asset_id is None:
                            msg = f"Investment Fees needs Asset and quantity, ctx={ctx}"
                            raise exc.MissingAssetError(msg)
                        qty = abs(qty)

                        txn = Transaction(
                            account_id=acct_id,
                            amount=0,
                            date=d["date"],
                            statement=statement,
                            linked=True,
                            # Asset transactions are immediately locked
                            locked=True,
                        )
                        t_split_0 = TransactionSplit(
                            parent=txn,
                            amount=amount,
                            payee=d["payee"],
                            description=d["description"],
                            category_id=categories["Securities Traded"].id_,
                            asset_id=asset_id,
                            asset_quantity_unadjusted=-qty,
                        )
                        t_split_1 = TransactionSplit(
                            parent=txn,
                            amount=-amount,
                            payee=d["payee"],
                            description=d["description"],
                            category_id=categories["Investment Fees"].id_,
                            asset_id=asset_id,
                            asset_quantity_unadjusted=0,
                        )
                        s.add_all((txn, t_split_0, t_split_1))
                        continue
                    if category_name == "Dividends Received":
                        # Associate dividends with asset
                        amount = abs(d["amount"])
                        qty = d["asset_quantity"]
                        if qty is None or asset_id is None:
                            msg = (
                                "Dividends Received needs Asset and quantity,"
                                f" ctx={ctx}"
                            )
                            raise exc.MissingAssetError(msg)
                        qty = abs(qty)

                        txn = Transaction(
                            account_id=acct_id,
                            amount=0,
                            date=d["date"],
                            statement=statement,
                            linked=True,
                            # Asset transactions are immediately locked
                            locked=True,
                        )
                        t_split_0 = TransactionSplit(
                            parent=txn,
                            amount=-amount,
                            payee=d["payee"],
                            description=d["description"],
                            category_id=categories["Securities Traded"].id_,
                            asset_id=asset_id,
                            asset_quantity_unadjusted=qty,
                        )
                        t_split_1 = TransactionSplit(
                            parent=txn,
                            amount=amount,
                            payee=d["payee"],
                            description=d["description"],
                            category_id=categories["Dividends Received"].id_,
                            asset_id=asset_id,
                            asset_quantity_unadjusted=0,
                        )
                        s.add_all((txn, t_split_0, t_split_1))
                        continue
                else:
                    # Don't match if an asset transaction
                    date_ord = d["date"].toordinal()
                    matches = list(
                        s.query(Transaction)
                        .with_entities(Transaction.id_, Transaction.date_ord)
                        .where(
                            Transaction.account_id == acct_id,
                            Transaction.amount == d["amount"],
                            Transaction.date_ord >= date_ord - 5,
                            Transaction.date_ord <= date_ord + 5,
                            Transaction.linked.is_(False),
                        )
                        .all(),
                    )
                    matches = sorted(matches, key=lambda x: abs(x[1] - date_ord))
                    # If only one match on closest day, link transaction
                    if len(matches) == 1 or (
                        len(matches) > 1 and matches[0][1] != matches[1][1]
                    ):
                        match_id = matches[0][0]

                try:
                    category_id = categories[category_name].id_
                except KeyError as e:
                    msg = f"Could not find category '{category_name}', ctx={ctx}"
                    raise exc.UnknownCategoryError(msg) from e

                if match_id:
                    s.query(Transaction).where(Transaction.id_ == match_id).update(
                        {"linked": True, "statement": statement},
                    )
                    s.query(TransactionSplit).where(
                        TransactionSplit.parent_id == match_id,
                    ).update({"linked": True})
                else:
                    txn = Transaction(
                        account_id=acct_id,
                        amount=d["amount"],
                        date=d["date"],
                        statement=statement,
                        linked=True,
                        # Asset transactions are immediately locked
                        locked=asset_id is not None,
                    )
                    t_split = TransactionSplit(
                        amount=d["amount"],
                        payee=d["payee"],
                        description=d["description"],
                        tag=d["tag"],
                        category_id=category_id,
                        asset_id=asset_id,
                        asset_quantity_unadjusted=d["asset_quantity"],
                    )
                    t_split.parent = txn
                    s.add_all((txn, t_split))

            # Add file hash to prevent importing again
            if force:
                s.query(ImportedFile).where(ImportedFile.hash_ == h).delete()
                s.commit()
            s.add(ImportedFile(hash_=h))
            s.commit()

        # If successful, delete the temp file
        path_debug.unlink()

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

    def find_similar_transaction(
        self,
        txn: Transaction,
        *,
        cache_ok: bool = True,
        do_commit: bool = True,
    ) -> int | None:
        """Find the most similar Transaction.

        Args:
            txn: Transaction to compare to
            cache_ok: If available, use Transaction.similar_txn_id
            do_commit: If match found, set similar_txn_id and commit

        Returns:
            Most similar Transaction.id_
        """
        s = orm.object_session(txn)
        if s is None:
            raise exc.UnboundExecutionError

        if cache_ok and txn.similar_txn_id is not None:
            return txn.similar_txn_id

        # Similar transaction must be within this range
        amount_min = min(
            txn.amount * (1 - utils.MATCH_PERCENT),
            txn.amount - utils.MATCH_ABSOLUTE,
        )
        amount_max = max(
            txn.amount * (1 + utils.MATCH_PERCENT),
            txn.amount + utils.MATCH_ABSOLUTE,
        )

        def commit_match(matching_row: int | sqlalchemy.Row[tuple[int]]) -> int:
            id_ = matching_row if isinstance(matching_row, int) else matching_row[0]
            if do_commit:
                txn.similar_txn_id = id_
                s.commit()
            return id_

        # Convert txn.amount to the raw SQL value to make a raw query
        amount_raw = Transaction.amount.type.process_bind_param(txn.amount, None)
        sort_closest_amount = sqlalchemy.text(f"abs({amount_raw} - amount)")

        cat_asset_linked = {
            t_cat_id
            for t_cat_id, in s.query(TransactionCategory.id_)
            .where(TransactionCategory.asset_linked.is_(True))
            .all()
        }

        # Check within Account first, exact matches
        # If this matches, great, no post filtering needed
        query = (
            s.query(Transaction.id_)
            .where(
                Transaction.account_id == txn.account_id,
                Transaction.id_ != txn.id_,
                Transaction.locked.is_(True),
                Transaction.amount >= amount_min,
                Transaction.amount <= amount_max,
                Transaction.statement == txn.statement,
            )
            .order_by(sort_closest_amount)
        )
        row = query.first()
        if row is not None:
            return commit_match(row)

        # Maybe exact statement but different account
        query = (
            s.query(Transaction.id_)
            .where(
                Transaction.id_ != txn.id_,
                Transaction.locked.is_(True),
                Transaction.amount >= amount_min,
                Transaction.amount <= amount_max,
                Transaction.statement == txn.statement,
            )
            .order_by(sort_closest_amount)
        )
        row = query.first()
        if row is not None:
            return commit_match(row)

        # Maybe exact statement but different amount
        query = (
            s.query(Transaction.id_)
            .where(
                Transaction.id_ != txn.id_,
                Transaction.locked.is_(True),
                Transaction.statement == txn.statement,
            )
            .order_by(sort_closest_amount)
        )
        row = query.first()
        if row is not None:
            return commit_match(row)

        # No statements match, choose highest fuzzy matching statement
        query = (
            s.query(Transaction)
            .with_entities(
                Transaction.id_,
                Transaction.statement,
            )
            .where(
                Transaction.id_ != txn.id_,
                Transaction.locked.is_(True),
                Transaction.amount >= amount_min,
                Transaction.amount <= amount_max,
            )
            .order_by(sort_closest_amount)
        )
        statements: dict[int, str] = {
            t_id: re.sub(r"[0-9]+", "", statement).lower()
            for t_id, statement in query.yield_per(YIELD_PER)
        }
        if len(statements) == 0:
            return None
        # Don't match a Transaction if it has a Securities Traded split
        has_asset_linked = {
            id_
            for id_, in s.query(TransactionSplit.parent_id)
            .where(
                TransactionSplit.parent_id.in_(statements),
                TransactionSplit.category_id.in_(cat_asset_linked),
            )
            .distinct()
        }
        statements = {
            t_id: statement
            for t_id, statement in statements.items()
            if t_id not in has_asset_linked
        }
        if len(statements) == 0:
            return None
        extracted = process.extract(
            re.sub(r"[0-9]+", "", txn.statement).lower(),
            statements,
            limit=None,
            score_cutoff=utils.SEARCH_THRESHOLD,
        )
        if len(extracted) == 0:
            # There are transactions with similar amounts but not close statement
            # Return the closest in amount and account
            # Aka proceed with all matches
            matches = {t_id: 50 for t_id in statements}
        else:
            matches = {t_id: score for _, score, t_id in extracted}

        # Add a bonuse points for closeness in price and same account
        query = (
            s.query(Transaction)
            .with_entities(
                Transaction.id_,
                Transaction.account_id,
                Transaction.amount,
            )
            .where(Transaction.id_.in_(matches))
        )
        matches_bonus: dict[int, float] = {}
        for t_id, acct_id, amount in query.yield_per(YIELD_PER):
            # 5% off will reduce score by 5%
            amount_diff_percent = abs(amount - txn.amount) / txn.amount
            score = matches[t_id] * float(1 - amount_diff_percent)
            if acct_id == txn.account_id:
                # Extra 10 points for same account
                score += 10
            matches_bonus[t_id] = score

        # Sort by best score and return best id
        best_id = sorted(matches_bonus.items(), key=lambda item: -item[1])[0][0]
        return commit_match(best_id)

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
            files: list[Path] = [self._path_db]

            if self._path_salt.exists():
                files.append(self._path_salt)
            if self.ssl_cert_path.exists():
                files.append(self.ssl_cert_path)
                files.append(self.ssl_key_path)

            for file in files:
                tar.add(file, arcname=file.relative_to(parent))
            # Add a timestamp of when it was created
            info = tarfile.TarInfo("_timestamp")
            buf = datetime.datetime.now(datetime.timezone.utc).isoformat().encode()
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
                ts = ts.replace(tzinfo=datetime.timezone.utc)
                backups.append((tar_ver, ts))
        return sorted(backups, key=lambda item: item[0])

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
        with self.get_session() as s:
            for asset in s.query(Asset).yield_per(YIELD_PER):
                asset.prune_valuations()
                asset.autodetect_interpolate()
            s.commit()

        # Optimize database
        with self.get_session() as s:
            s.execute(sqlalchemy.text("VACUUM"))
            s.commit()

        path_backup_optimized, _ = self.backup()
        size_after = self._path_db.stat().st_size

        # Delete all files that start with name except the fresh backups
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

        return (size_before, size_after)

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
            required = {
                "_timestamp",
                re.sub(r"\.backup\d+.tar.gz$", ".db", path_backup.name),
            }
            members = tar.getmembers()
            member_paths = [member.path for member in members]
            for member in required:
                if member not in member_paths:
                    msg = f"Backup is missing required file: {member}"
                    raise exc.InvalidBackupTarError(msg)
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
    ) -> list[
        tuple[
            str,
            str,
            datetime.date | None,
            datetime.date | None,
            str | None,
        ]
    ]:
        """Update asset valuations using web sources.

        Returns:
            Assets that were updated
            [
                (
                    name,
                    ticker,
                    start date,
                    end date,
                    error,
                ),
                ...
            ]
        """
        today = datetime.date.today()
        today_ord = today.toordinal()
        updated: list[
            tuple[
                str,
                str,
                datetime.date | None,
                datetime.date | None,
                str | None,
            ]
        ] = []

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
                        through_today=asset.id_ in currently_held_assets,
                    )
                except exc.AssetWebError as e:
                    updated.append((name, ticker, None, None, str(e)))
                else:
                    if start is not None:
                        updated.append((name, ticker, start, end, None))
                    # start & end are None if there are no transactions for the Asset

            s.commit()

            # Auto update if asset needs interpolation
            for asset in s.query(Asset).all():
                asset.autodetect_interpolate()
            s.commit()

        return updated
