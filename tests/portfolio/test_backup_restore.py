from __future__ import annotations

import tarfile
from typing import TYPE_CHECKING

import pytest

from nummus import encryption
from nummus import exceptions as exc
from nummus.models import Config, ConfigKey
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    import datetime
    from pathlib import Path


def test_backup(utc_frozen: datetime.datetime, empty_portfolio: Portfolio) -> None:
    path_db = empty_portfolio.path
    path_salt = path_db.with_suffix(".nacl")

    path_tar, tar_ver = empty_portfolio.backup()
    assert path_tar.exists()
    assert path_tar.is_file()
    assert path_tar.stat().st_mode & 0o777 == 0o600
    assert tar_ver == 1

    with tarfile.open(path_tar, "r") as tar:
        file = tar.extractfile(path_db.name)
        assert file is not None
        buf_backup = file.read()
        with path_db.open("rb") as file:
            buf = file.read()
        assert buf_backup == buf

        file = tar.extractfile("_timestamp")
        assert file is not None
        buf_ts = file.read()
        assert buf_ts == utc_frozen.isoformat().encode()

        assert path_salt.name not in tar.getnames()


def test_backup_second(empty_portfolio: Portfolio) -> None:
    empty_portfolio.backup()
    path_tar, tar_ver = empty_portfolio.backup()
    assert path_tar.exists()
    assert path_tar.is_file()
    assert path_tar.stat().st_mode & 0o777 == 0o600
    assert tar_ver == 2


def test_backups_empty(empty_portfolio: Portfolio) -> None:
    assert not Portfolio.backups(empty_portfolio)


def test_backups(utc_frozen: datetime.datetime, empty_portfolio: Portfolio) -> None:
    empty_portfolio.backup()
    empty_portfolio.backup()
    empty_portfolio.backup()

    target = [(i + 1, utc_frozen) for i in range(3)]
    assert Portfolio.backups(empty_portfolio) == target


def test_backups_no_ts(empty_portfolio: Portfolio) -> None:
    path = empty_portfolio.path.with_suffix(".backup1.tar")
    with tarfile.open(path, "w") as _:
        pass

    with pytest.raises(exc.InvalidBackupTarError):
        Portfolio.backups(empty_portfolio.path)


def test_backups_ts_dir(empty_portfolio: Portfolio) -> None:
    path = empty_portfolio.path.with_suffix(".backup1.tar")
    with tarfile.open(path, "w") as tar:
        info = tarfile.TarInfo("_timestamp")
        info.type = tarfile.DIRTYPE
        tar.addfile(info)

    with pytest.raises(exc.InvalidBackupTarError):
        Portfolio.backups(empty_portfolio.path)


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_backup_encrypted(empty_portfolio_encrypted: tuple[Portfolio, str]) -> None:
    p, _ = empty_portfolio_encrypted
    path_db = p.path
    path_salt = path_db.with_suffix(".nacl")

    path_tar, tar_ver = p.backup()
    assert path_tar.exists()
    assert path_tar.is_file()
    assert path_tar.stat().st_mode & 0o777 == 0o600
    assert tar_ver == 1

    with tarfile.open(path_tar, "r") as tar:
        file = tar.extractfile(path_db.name)
        assert file is not None
        buf_backup = file.read()
        with path_db.open("rb") as file:
            buf = file.read()
        assert buf_backup == buf

        assert path_salt.name in tar.getnames()


def test_clean(empty_portfolio: Portfolio) -> None:
    path_1 = empty_portfolio.path.with_suffix(".backup1.tar")
    path_2 = empty_portfolio.path.with_suffix(".backup2.tar")
    path_dir = empty_portfolio.path.with_suffix(".things")
    path_1.touch()
    path_2.touch()
    path_dir.mkdir()
    assert path_1.stat().st_size == 0

    size_b = empty_portfolio.clean()
    assert size_b[0] == empty_portfolio.path.stat().st_size
    assert size_b[0] >= size_b[1]

    assert path_1.exists()
    assert path_1.stat().st_size > 0
    assert not path_2.exists()
    assert not path_dir.exists()


def test_restore_non_existant(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.db"
    with pytest.raises(FileNotFoundError):
        Portfolio.restore(path)


def test_restore_no_ts(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.db"
    path_tar = path.with_suffix(".backup1.tar")
    with tarfile.open(path_tar, "w") as _:
        pass

    with pytest.raises(exc.InvalidBackupTarError):
        Portfolio.restore(path)


def test_restore_path_traversal(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.db"
    path_tar = path.with_suffix(".backup1.tar")
    with tarfile.open(path_tar, "w") as tar:
        info = tarfile.TarInfo("_timestamp")
        tar.addfile(info)
        info = tarfile.TarInfo(path.name)
        tar.addfile(info)

        info = tarfile.TarInfo("../injection.sh")
        tar.addfile(info)

    with pytest.raises(exc.InvalidBackupTarError):
        Portfolio.restore(path)


def test_restore(empty_portfolio: Portfolio) -> None:
    # Delete ENCRYPTION_TEST so reload fails
    with empty_portfolio.begin_session() as s:
        s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).delete()
    empty_portfolio.backup()
    empty_portfolio.path.unlink()

    with pytest.raises(exc.ProtectedObjectNotFoundError):
        Portfolio.restore(empty_portfolio)

    assert empty_portfolio.path.exists()


def test_restore_path(empty_portfolio: Portfolio) -> None:
    # Delete ENCRYPTION_TEST so reload fails
    with empty_portfolio.begin_session() as s:
        s.query(Config).where(Config.key == ConfigKey.ENCRYPTION_TEST).delete()
    empty_portfolio.backup()
    empty_portfolio.path.unlink()

    Portfolio.restore(empty_portfolio.path)

    assert empty_portfolio.path.exists()

    with pytest.raises(exc.ProtectedObjectNotFoundError):
        empty_portfolio._unlock()


def test_restore_version_not_found(empty_portfolio: Portfolio) -> None:
    with pytest.raises(FileNotFoundError):
        Portfolio.restore(empty_portfolio, tar_ver=100)
