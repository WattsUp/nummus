from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus import sql
from nummus.models.transaction import Transaction, TransactionSplit
from tests.importers.test_raw_csv import TRANSACTIONS_REQUIRED

if TYPE_CHECKING:
    from pathlib import Path

    from nummus.models.account import Account
    from nummus.models.asset import Asset
    from nummus.portfolio import Portfolio


def test_import_file(
    data_path: Path,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
    categories: dict[str, int],
) -> None:
    path = data_path / "transactions_required.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")

    # Create first txn to be cleared
    with empty_portfolio.begin_session():
        d = TRANSACTIONS_REQUIRED[0]
        txn = Transaction.create(
            account_id=account.id_,
            date=d["date"],
            amount=d["amount"],
            statement="Manually imported",
        )
        TransactionSplit.create(
            parent=txn,
            amount=txn.amount,
            category_id=categories["uncategorized"],
        )

    empty_portfolio.import_file(path, path_debug)

    assert not path_debug.exists()

    with empty_portfolio.begin_session():
        assert sql.count(Transaction.query()) == len(TRANSACTIONS_REQUIRED)


def test_import_file_duplicate(
    data_path: Path,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
) -> None:
    path = data_path / "transactions_required.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")

    empty_portfolio.import_file(path, path_debug)

    with pytest.raises(exc.FileAlreadyImportedError):
        empty_portfolio.import_file(path, path_debug)

    assert not path_debug.exists()


def test_import_file_force(
    data_path: Path,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
) -> None:
    path = data_path / "transactions_required.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")

    empty_portfolio.import_file(path, path_debug)
    empty_portfolio.import_file(path, path_debug, force=True)

    assert not path_debug.exists()

    with empty_portfolio.begin_session():
        assert sql.count(Transaction.query()) == len(TRANSACTIONS_REQUIRED) * 2


@pytest.mark.parametrize(
    ("files", "target", "debug_exists"),
    [
        (
            ("transactions_required.csv", "transactions_required.csv"),
            exc.FileAlreadyImportedError,
            False,
        ),
        (("transactions_corrupt.csv",), exc.FailedImportError, True),
        (("transactions_empty.csv",), exc.EmptyImportError, True),
        (("transactions_future.csv",), exc.FutureTransactionError, True),
        (
            ("transactions_investments_bad_category.csv",),
            exc.InvalidAssetTransactionCategoryError,
            True,
        ),
        (("transactions_investments_missing0.csv",), exc.MissingAssetError, True),
        (("transactions_investments_missing1.csv",), exc.MissingAssetError, True),
    ],
)
def test_import_file_error(
    data_path: Path,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
    files: tuple[str, ...],
    target: type[Exception],
    debug_exists: bool,
) -> None:
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")
    for f in files[:-1]:
        path = data_path / f
        empty_portfolio.import_file(path, path_debug)

    path = data_path / files[-1]
    with pytest.raises(target):
        empty_portfolio.import_file(path, path_debug)

    assert path_debug.exists() == debug_exists


def test_import_file_investments(
    data_path: Path,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
) -> None:
    path = data_path / "transactions_investments.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")

    empty_portfolio.import_file(path, path_debug)

    assert not path_debug.exists()

    with empty_portfolio.begin_session():
        assert sql.count(Transaction.query()) == 4

        query = Transaction.query().where(
            Transaction.date_ord == datetime.date(2023, 1, 3).toordinal(),
        )
        txn = sql.one(query)
        assert txn.statement == f"Asset Transaction {asset.name}"


def test_import_file_bad_category(
    data_path: Path,
    empty_portfolio: Portfolio,
    account: Account,
    categories: dict[str, int],
) -> None:
    path = data_path / "transactions_bad_category.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")

    empty_portfolio.import_file(path, path_debug)

    assert not path_debug.exists()

    with empty_portfolio.begin_session():
        t_split = TransactionSplit.one()
        assert t_split.category_id == categories["uncategorized"]
