from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore

from nummus import utils
from nummus.commands.export import Export

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from nummus.models import Account, Transaction
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

    with path_csv.open("r", encoding="utf-8") as file:
        buf = file.read().splitlines()
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

    with path_csv.open("r", encoding="utf-8") as file:
        buf = file.read().splitlines()
    target = [
        "Date,Account,Payee,Memo,Category,Amount",
        f"{txn.date},{account.name},{txn.payee or ''},{t_split.memo or ''},"
        f"Other Income,{utils.format_financial(txn.amount)}",
    ]
    assert buf == target
