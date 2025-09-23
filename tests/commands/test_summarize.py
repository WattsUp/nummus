from __future__ import annotations

import zoneinfo
from decimal import Decimal
from typing import TYPE_CHECKING

import time_machine

from nummus.commands.summarize import Summarize

if TYPE_CHECKING:
    import datetime

    import pytest
    from sqlalchemy import orm

    from nummus.commands.summarize import _Summary
    from nummus.models import Account, Asset, AssetValuation, Transaction
    from nummus.portfolio import Portfolio


def test_empty_summary(
    empty_portfolio: Portfolio,
) -> None:
    c = Summarize(empty_portfolio.path, None, include_all=False)
    result = c._get_summary()

    target: _Summary = {
        "n_accounts": 0,
        "n_assets": 0,
        "n_transactions": 0,
        "n_valuations": 0,
        "net_worth": Decimal(),
        "accounts": [],
        "total_asset_value": Decimal(),
        "assets": [],
        "db_size": empty_portfolio.path.stat().st_size,
    }
    assert result == target


def test_non_empty_summary(
    utc: datetime.datetime,
    empty_portfolio: Portfolio,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    _ = transactions
    _ = asset_valuation

    c = Summarize(empty_portfolio.path, None, include_all=False)

    utc = utc.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
    with time_machine.travel(utc):
        result = c._get_summary()

    target: _Summary = {
        "n_accounts": 1,
        "n_assets": 1,
        "n_transactions": 4,
        "n_valuations": 1,
        "net_worth": Decimal(110),
        "accounts": [
            {
                "name": "Monkey bank checking",
                "institution": "Monkey bank",
                "category": "Cash",
                "age": "3 days",
                "profit": Decimal(10),
                "value": Decimal(110),
            },
        ],
        "total_asset_value": Decimal(20),
        "assets": [
            {
                "name": "Banana incorporated",
                "description": "Banana Incorporated makes bananas",
                "category": "Stocks",
                "profit": Decimal(10),
                "ticker": "BANANA",
                "value": Decimal(20),
            },
        ],
        "db_size": empty_portfolio.path.stat().st_size,
    }
    assert result == target


def test_exclude_empty(
    empty_portfolio: Portfolio,
    session: orm.Session,
    account: Account,
    asset: Asset,
) -> None:
    account.closed = True
    session.commit()
    _ = asset

    c = Summarize(empty_portfolio.path, None, include_all=False)
    result = c._get_summary()

    target: _Summary = {
        "n_accounts": 1,
        "n_assets": 1,
        "n_transactions": 0,
        "n_valuations": 0,
        "net_worth": Decimal(),
        "accounts": [],
        "total_asset_value": Decimal(),
        "assets": [],
        "db_size": empty_portfolio.path.stat().st_size,
    }
    assert result == target


def test_empty_print(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
) -> None:

    c = Summarize(empty_portfolio.path, None, include_all=False)
    assert c.run() == 0

    captured = capsys.readouterr()
    # big output use "" in asserts
    assert "0 accounts, 0 of which are currently open" in captured.out
    assert "0 assets, 0 of which are currently held" in captured.out
    assert "0 asset valuations" in captured.out
    assert "0 transactions" in captured.out
    assert not captured.err


def test_non_empty_print(
    capsys: pytest.CaptureFixture,
    utc: datetime.datetime,
    empty_portfolio: Portfolio,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    _ = transactions
    _ = asset_valuation

    c = Summarize(empty_portfolio.path, None, include_all=False)

    utc = utc.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
    with time_machine.travel(utc):
        assert c.run() == 0

    captured = capsys.readouterr()
    # big output use "" in asserts
    assert "1 account, 1 of which is currently open" in captured.out
    assert "1 asset, 1 of which is currently held" in captured.out
    assert "1 asset valuation" in captured.out
    assert "4 transactions" in captured.out
    assert not captured.err
