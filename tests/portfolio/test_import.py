from __future__ import annotations

import datetime
import operator
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import Account, Asset, query_count, Transaction
from nummus.models.transaction import TransactionSplit
from nummus.portfolio import Portfolio
from tests.importers.test_raw_csv import TRANSACTIONS_REQUIRED

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from nummus.models import Base


def test_import_file(
    data_path: Path,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
    categories: dict[str, int],
) -> None:
    _ = account_investments
    _ = asset
    path = data_path / "transactions_required.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")

    # Create first txn to be cleared
    with empty_portfolio.begin_session() as s:
        d = TRANSACTIONS_REQUIRED[0]
        txn = Transaction(
            account_id=account.id_,
            date=d["date"],
            amount=d["amount"],
            statement="Manually imported",
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=categories["uncategorized"],
        )
        s.add_all((txn, t_split))

    empty_portfolio.import_file(path, path_debug)

    assert not path_debug.exists()

    with empty_portfolio.begin_session() as s:
        assert query_count(s.query(Transaction)) == len(TRANSACTIONS_REQUIRED)


def test_import_file_duplicate(
    data_path: Path,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
) -> None:
    _ = account
    _ = account_investments
    _ = asset
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
    _ = account
    _ = account_investments
    _ = asset
    path = data_path / "transactions_required.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")

    empty_portfolio.import_file(path, path_debug)
    empty_portfolio.import_file(path, path_debug, force=True)

    assert not path_debug.exists()

    with empty_portfolio.begin_session() as s:
        assert query_count(s.query(Transaction)) == len(TRANSACTIONS_REQUIRED) * 2


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
    _ = account
    _ = account_investments
    _ = asset
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
    _ = account
    _ = account_investments
    path = data_path / "transactions_investments.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")

    empty_portfolio.import_file(path, path_debug)

    assert not path_debug.exists()

    with empty_portfolio.begin_session() as s:
        assert query_count(s.query(Transaction)) == 4

        txn = (
            s.query(Transaction)
            .where(Transaction.date_ord == datetime.date(2023, 1, 3).toordinal())
            .one()
        )
        assert txn.statement == f"Asset Transaction {asset.name}"


def test_import_file_bad_category(
    data_path: Path,
    empty_portfolio: Portfolio,
    account: Account,
    categories: dict[str, int],
) -> None:
    _ = account
    path = data_path / "transactions_bad_category.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer-debug")

    empty_portfolio.import_file(path, path_debug)

    assert not path_debug.exists()

    with empty_portfolio.begin_session() as s:
        t_split = s.query(TransactionSplit).one()
        assert t_split.category_id == categories["uncategorized"]


@pytest.mark.parametrize(
    ("type_", "prop", "value_adjuster"),
    [
        (Account, "uri", lambda s: s),
        (Account, "number", lambda s: s),
        (Account, "number", operator.itemgetter(slice(-4, None))),
        (Account, "institution", lambda s: s),
        (Account, "name", lambda s: s),
        (Account, "name", lambda s: s.lower()),
        (Account, "name", lambda s: s.upper()),
        (Asset, "uri", lambda s: s),
        (Asset, "ticker", lambda s: s),
        (Asset, "name", lambda s: s),
    ],
)
def test_find(
    empty_portfolio: Portfolio,
    account: Account,
    asset: Asset,
    type_: type[Base],
    prop: str,
    value_adjuster: Callable[[str], str],
) -> None:
    obj = {
        Account: account,
        Asset: asset,
    }[type_]
    query = value_adjuster(getattr(obj, prop))

    cache: dict[str, tuple[int, str | None]] = {}
    with empty_portfolio.begin_session() as s:
        a_id, a_name = Portfolio.find(s, type_, query, cache)
    assert a_id == obj.id_
    assert a_name == obj.name

    assert cache == {query: (a_id, a_name)}


def test_find_missing(
    empty_portfolio: Portfolio,
    account: Account,
) -> None:
    query = Account.id_to_uri(account.id_ + 1)

    cache: dict[str, tuple[int, str | None]] = {}
    with empty_portfolio.begin_session() as s, pytest.raises(exc.NoResultFound):
        Portfolio.find(s, Account, query, cache)

    assert not cache
