from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore

from nummus.commands.export import Export
from nummus.models.currency import CURRENCY_FORMATS, DEFAULT_CURRENCY

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from nummus.models.account import Account
    from nummus.models.transaction import Transaction
    from nummus.portfolio import Portfolio


def test_export_empty(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    tmp_path: Path,
) -> None:
    path_csv = tmp_path / "out.csv"

    c = Export(empty_portfolio.path, None, path_csv, None, None, no_bars=True)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = (
        f"{Fore.GREEN}Portfolio is unlocked\n"
        f"{Fore.GREEN}0 transactions exported to {path_csv}\n"
    )
    assert captured.out == target
    assert not captured.err

    buf = path_csv.read_text("utf-8").splitlines()
    target = [
        "Date,Account,Payee,Memo,Category,Amount",
    ]
    assert buf == target


def test_export(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    account: Account,
    transactions: list[Transaction],
    tmp_path: Path,
) -> None:
    txn = transactions[0]
    t_split = txn.splits[0]
    path_csv = tmp_path / "out.csv"

    c = Export(empty_portfolio.path, None, path_csv, txn.date, txn.date, no_bars=True)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = (
        f"{Fore.GREEN}Portfolio is unlocked\n"
        f"{Fore.GREEN}1 transactions exported to {path_csv}\n"
    )
    assert captured.out == target
    assert not captured.err

    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    buf = path_csv.read_text("utf-8").splitlines()
    target = [
        "Date,Account,Payee,Memo,Category,Amount",
        (
            f"{txn.date},{account.name},{txn.payee or ''},{t_split.memo or ''},"
            f"Other Income,{cf(txn.amount)}"
        ),
    ]
    assert buf == target
