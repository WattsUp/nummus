from __future__ import annotations

from typing import override, TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.importers.base import TransactionImporter
from nummus.importers.raw_csv import CSVTransactionImporter
from nummus.importers.top import get_importer, get_importers
from tests import data
from tests.data.custom_importer import BananaBankImporter

if TYPE_CHECKING:
    from pathlib import Path

    from nummus.importers.base import TxnDicts


class Derived(TransactionImporter):
    @classmethod
    def is_importable(
        cls,
        suffix: str,
        buf: bytes | None,
        buf_pdf: list[str] | None,
    ) -> bool:
        _ = suffix
        _ = buf
        _ = buf_pdf
        return False

    @override
    def run(self) -> TxnDicts:
        return []


def test_init_without_buf() -> None:
    with pytest.raises(exc.NoImporterBufferError):
        Derived()


def test_init_with_raw_buf(data_path: Path) -> None:
    path = data_path / "transactions_required.csv"
    buf = path.read_bytes()
    i = Derived(buf=buf)
    assert i._buf == buf


def test_init_with_pdf_buf(data_path: Path) -> None:
    path = data_path / "transactions_required.csv"
    buf_pdf = path.read_text().splitlines()
    i = Derived(buf_pdf=buf_pdf)
    assert i._buf_pdf == buf_pdf


@pytest.mark.parametrize(
    ("file", "target"),
    [
        ("transactions_required.csv", CSVTransactionImporter),
        ("transactions_extras.csv", CSVTransactionImporter),
        ("transactions_lacking.csv", None),
        ("banana_bank_statement.pdf", None),
    ],
)
def test_get_importer(
    tmp_path: Path,
    data_path: Path,
    file: str,
    target: type[TransactionImporter] | None,
) -> None:
    available = get_importers(None)
    path = data_path / file
    path_debug = tmp_path / "portfolio.importer_debug"
    assert not path_debug.exists()
    if target is None:
        with pytest.raises(exc.UnknownImporterError):
            get_importer(path, path_debug, available)
    else:
        i = get_importer(path, path_debug, available)
        assert isinstance(i, target)
    assert path_debug.exists()


def test_get_importers() -> None:
    target = (CSVTransactionImporter,)
    assert get_importers(None) == target


def test_get_importers_custom(data_path: Path) -> None:
    target_base = (CSVTransactionImporter,)
    target_extra = (BananaBankImporter,)
    result = get_importers(data_path)
    assert result[: len(target_base)] == target_base
    # Since importers are imported separately, can't check direct equality
    n_strip = len(data.__name__) + 1
    target_names = [f"{i.__module__[n_strip:]}.{i.__name__}" for i in target_extra]
    result_names = [f"{i.__module__}.{i.__name__}" for i in result[len(target_base) :]]
    assert result_names == target_names
