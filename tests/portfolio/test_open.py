from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from nummus import encryption
from nummus import exceptions as exc
from nummus.models import Asset, Config, ConfigKey, query_count, TransactionCategory
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path


def test_non_existant(tmp_path: Path) -> None:
    path = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        Portfolio(path, None)

    with pytest.raises(FileNotFoundError):
        Portfolio.is_encrypted_path(path)


def test_corrupted(tmp_path: Path) -> None:
    path = tmp_path / "missing.db"
    with path.open("wb") as file:
        file.write(b"fake")
    with pytest.raises(exc.UnlockingError):
        Portfolio(path, None)


def test_already_exists(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.db"
    path.touch()
    with pytest.raises(FileExistsError):
        Portfolio.create(path)


def test_unencrypted(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.db"
    path_importers = path.with_suffix(".importers")
    path_salt = path.with_suffix(".nacl")
    p = Portfolio.create(path)

    assert path.exists()
    assert path_importers.exists()
    assert path_importers.is_dir()
    assert not path_salt.exists()
    assert p.path == path
    assert p.importers_path == path_importers

    assert not p.is_encrypted
    assert not Portfolio.is_encrypted_path(path)

    with p.begin_session() as s:
        assert query_count(s.query(Config)) == 4
        assert query_count(s.query(TransactionCategory)) > 0
        assert query_count(s.query(Asset)) > 0

    with pytest.raises(exc.NotEncryptedError):
        p.encrypt("")

    with pytest.raises(exc.NotEncryptedError):
        p.decrypt("")

    with pytest.raises(exc.NotEncryptedError):
        p.decrypt_s("")


def test_migration_required(tmp_path: Path, data_path: Path) -> None:
    path_original = data_path / "old_versions" / "v0.1.16.db"
    path_db = tmp_path / "portfolio.v0.2.db"
    shutil.copyfile(path_original, path_db)

    with pytest.raises(exc.MigrationRequiredError):
        Portfolio(path_db, None)


@pytest.mark.parametrize(
    "key",
    [
        ConfigKey.ENCRYPTION_TEST,
        ConfigKey.CIPHER,
        ConfigKey.VERSION,
    ],
)
def test_no_encryption_test(
    empty_portfolio: Portfolio,
    key: ConfigKey,
) -> None:
    with empty_portfolio.begin_session() as s:
        s.query(Config).where(Config.key == key).delete()

    with pytest.raises(exc.ProtectedObjectNotFoundError):
        Portfolio(empty_portfolio.path, None)


def test_bad_encryption_test(empty_portfolio: Portfolio) -> None:
    with empty_portfolio.begin_session() as s:
        s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).update(
            {"value": "fake"},
        )

    with pytest.raises(exc.UnlockingError):
        Portfolio(empty_portfolio.path, None)


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_encrypted(tmp_path: Path, rand_str: str) -> None:
    path = tmp_path / "portfolio.db"
    path_importers = path.with_suffix(".importers")
    path_salt = path.with_suffix(".nacl")
    p = Portfolio.create(path, rand_str)

    assert path.exists()
    assert path_importers.exists()
    assert path_importers.is_dir()
    assert path_salt.exists()
    assert path_salt.is_file()

    assert p.is_encrypted
    assert Portfolio.is_encrypted_path(path)

    with p.begin_session() as s:
        assert query_count(s.query(Config)) == 5
        assert query_count(s.query(TransactionCategory)) > 0
        assert query_count(s.query(Asset)) > 0


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_encrypted_no_salt(
    empty_portfolio_encrypted: tuple[Portfolio, str],
) -> None:
    p, key = empty_portfolio_encrypted
    path_salt = p.path.with_suffix(".nacl")
    path_salt.unlink()

    with pytest.raises(FileNotFoundError):
        Portfolio(p.path, key)


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_encrypted_bad_enc_test(
    empty_portfolio_encrypted: tuple[Portfolio, str],
) -> None:
    p, key = empty_portfolio_encrypted
    with p.begin_session() as s:
        s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).update(
            {"value": "fake"},
        )

    with pytest.raises(exc.UnlockingError):
        Portfolio(p.path, key)


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_encrypt(
    empty_portfolio_encrypted: tuple[Portfolio, str],
    rand_str: str,
) -> None:
    p, _ = empty_portfolio_encrypted
    assert p.decrypt_s(p.encrypt(rand_str)) == rand_str
