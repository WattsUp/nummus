from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.importers.raw_csv import CSVTransactionImporter

if TYPE_CHECKING:
    from pathlib import Path

    from nummus.importers.base import TxnDicts


# Other unit tests use the files, share target
TRANSACTIONS_REQUIRED = [
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 1),
        "amount": Decimal("1000.0"),
        "statement": "Paycheck",
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-12.34"),
        "statement": "Banana",
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-900.0"),
        "statement": "Account Transfer",
    },
    {
        "account": "Monkey Bank Investments",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("900.0"),
        "statement": "Account Transfer",
    },
]

TRANSACTIONS_EXTRAS: TxnDicts = [
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 1),
        "amount": Decimal("1000.0"),
        "statement": "Paycheck",
        "payee": "Employer",
        "memo": "Paycheck",
        "category": "Paychecks/Salary",
        "asset": None,
        "asset_quantity": None,
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-12.34"),
        "statement": "Banana",
        "payee": "Monkey Store",
        "memo": "Banana",
        "category": "Groceries",
        "asset": None,
        "asset_quantity": None,
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-900.0"),
        "statement": "Account Transfer",
        "payee": "Monkey Investments",
        "memo": "Account Transfer",
        "category": "Transfers",
        "asset": None,
        "asset_quantity": None,
    },
    {
        "account": "Monkey Bank Investments",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("900.0"),
        "statement": "Account Transfer",
        "payee": "Monkey Investments",
        "memo": "Account Transfer",
        "category": "Transfers",
        "asset": None,
        "asset_quantity": None,
    },
    {
        "account": "Monkey Bank Investments",
        "date": datetime.date(2023, 1, 3),
        "amount": Decimal("-900.0"),
        "statement": "",
        "payee": "Monkey Investments",
        "memo": None,
        "category": "Securities Traded",
        "asset": "BANANA",
        "asset_quantity": Decimal("32.1234"),
    },
    {
        "account": "Monkey Bank Investments",
        "date": datetime.date(2023, 2, 1),
        "amount": Decimal("1234.56"),
        "statement": "Profit Maker",
        "payee": "Monkey Investments",
        "memo": "Profit Maker",
        "category": "Securities Traded",
        "asset": "BANANA",
        "asset_quantity": Decimal("-32.1234"),
    },
]


def test_is_importable_none() -> None:
    with pytest.raises(exc.WrongImporterBufferError):
        CSVTransactionImporter.is_importable(".csv", None, None)


@pytest.mark.parametrize(
    ("suffix", "data", "target"),
    [
        ("", b"", False),
        (".csv", "transactions_required.csv", True),
        (".csv", "transactions_extras.csv", True),
        (".csv", "transactions_lacking.csv", False),
    ],
)
def test_is_importable(
    data_path: Path,
    suffix: str,
    data: str | bytes | None,
    target: bool,
) -> None:
    if isinstance(data, str):
        path = data_path / data
        with path.open("rb") as file:
            buf = file.read()
    else:
        buf = data

    assert CSVTransactionImporter.is_importable(suffix, buf, None) == target


def test_run_none() -> None:
    i = CSVTransactionImporter(None, [""])
    with pytest.raises(exc.WrongImporterBufferError):
        i.run()


def test_run_lacking(data_path: Path) -> None:
    path = data_path / "transactions_lacking.csv"
    with path.open("rb") as file:
        buf = file.read()
    i = CSVTransactionImporter(buf=buf)
    with pytest.raises(KeyError):
        i.run()


def test_run_bad_value() -> None:
    buf = b"Account,Date,Amount,Statement\nMonkey Bank Checking,2023-01-01,,Paycheck"
    i = CSVTransactionImporter(buf=buf)
    with pytest.raises(ValueError, match="Amount column did not import a number"):
        i.run()


@pytest.mark.parametrize(
    ("name", "target"),
    [
        ("transactions_required.csv", TRANSACTIONS_REQUIRED),
        ("transactions_extras.csv", TRANSACTIONS_EXTRAS),
    ],
)
def test_run(data_path: Path, name: str, target: TxnDicts) -> None:
    path = data_path / name
    with path.open("rb") as file:
        buf = file.read()
    result = CSVTransactionImporter(buf=buf).run()
    assert len(result) == len(target)
    for r, t in zip(result, target, strict=True):
        r_dict = r.copy()
        for k, t_v in t.items():
            r_v = r_dict.pop(k)
            assert r_v == t_v
        # Remaining should be none
        assert all(v is None for v in r_dict.values())
