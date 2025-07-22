from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import utils
from nummus.controllers import accounts, base
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetValuation,
    Transaction,
)

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm


@pytest.mark.parametrize("skip_today", [False, True])
def test_ctx_account_empty(
    session: orm.Session,
    account: Account,
    skip_today: bool,
) -> None:
    ctx = accounts.ctx_account(session, account, skip_today=skip_today)

    target: accounts.AccountContext = {
        "uri": account.uri,
        "name": account.name,
        "number": account.number,
        "institution": account.institution,
        "category": account.category,
        "category_type": AccountCategory,
        "value": Decimal(),
        "closed": account.closed,
        "budgeted": account.budgeted,
        "updated_days_ago": 0,
        "change_today": Decimal(),
        "change_future": Decimal(),
        "n_today": 0,
        "n_future": 0,
        "performance": None,
        "assets": [],
    }
    assert ctx == target


def test_ctx_account(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    ctx = accounts.ctx_account(session, account)

    target: accounts.AccountContext = {
        "uri": account.uri,
        "name": account.name,
        "number": account.number,
        "institution": account.institution,
        "category": account.category,
        "category_type": AccountCategory,
        "value": sum(txn.amount for txn in transactions[:2]) or Decimal(),
        "closed": account.closed,
        "budgeted": account.budgeted,
        "updated_days_ago": -7,
        "change_today": Decimal(),
        "change_future": sum(txn.amount for txn in transactions[2:]) or Decimal(),
        "n_today": 1,
        "n_future": 2,
        "performance": None,
        "assets": [],
    }
    assert ctx == target


def test_ctx_performance_empty(
    today: datetime.date,
    session: orm.Session,
    account: Account,
) -> None:
    start = utils.date_add_months(today, -12)
    labels, date_mode = base.date_labels(start.toordinal(), today.toordinal())

    ctx = accounts.ctx_performance(session, account, "1yr")

    target: accounts.PerformanceContext = {
        "pnl_past_year": Decimal(),
        "pnl_total": Decimal(),
        "total_cost_basis": Decimal(),
        "dividends": Decimal(),
        "fees": Decimal(),
        "cash": Decimal(),
        "twrr": Decimal(),
        "mwrr": Decimal(),
        "labels": labels,
        "date_mode": date_mode,
        "values": [Decimal()] * len(labels),
        "cost_bases": [Decimal()] * len(labels),
        "period": "1yr",
        "period_options": base.PERIOD_OPTIONS,
    }
    assert ctx == target


def test_ctx_performance(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    asset_valuation.date_ord -= 7
    session.commit()
    labels, date_mode = base.date_labels(transactions[0].date_ord, today.toordinal())

    ctx = accounts.ctx_performance(session, account, "max")

    twrr = Decimal(8) / Decimal(100)
    twrr_per_annum = (1 + twrr) ** (utils.DAYS_IN_YEAR / len(labels)) - 1
    values = [Decimal(100), Decimal(110), Decimal(112), Decimal(108)]
    profits = [Decimal(), Decimal(10), Decimal(12), Decimal(8)]
    target: accounts.PerformanceContext = {
        "pnl_past_year": Decimal(8),
        "pnl_total": Decimal(8),
        "total_cost_basis": Decimal(100),
        "dividends": Decimal(1),
        "fees": Decimal(-2),
        "cash": Decimal(90),
        "twrr": twrr_per_annum,
        "mwrr": utils.mwrr(values, profits),
        "labels": labels,
        "date_mode": date_mode,
        "values": values,
        "cost_bases": [Decimal(100)] * len(labels),
        "period": "max",
        "period_options": base.PERIOD_OPTIONS,
    }
    assert ctx == target


def test_ctx_assets_empty(
    session: orm.Session,
    account: Account,
) -> None:
    assert accounts.ctx_assets(session, account) is None


def test_ctx_assets(
    session: orm.Session,
    account: Account,
    asset: Asset,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    asset_valuation.date_ord -= 7
    session.commit()

    ctx = accounts.ctx_assets(session, account)

    target: list[accounts.AssetContext] = [
        {
            "uri": asset.uri,
            "category": asset.category,
            "name": asset.name,
            "ticker": asset.ticker,
            "qty": Decimal(9),
            "price": asset_valuation.value,
            "value": Decimal(9) * asset_valuation.value,
            "value_ratio": Decimal(18) / Decimal(108),
            "profit": Decimal(8),
        },
        {
            "uri": None,
            "category": AssetCategory.CASH,
            "name": "Cash",
            "ticker": None,
            "qty": None,
            "price": Decimal(1),
            "value": Decimal(90),
            "value_ratio": Decimal(90) / Decimal(108),
            "profit": None,
        },
    ]
    assert ctx == target


def test_ctx_accounts_empty(session: orm.Session) -> None:
    ctx = accounts.ctx_accounts(session)

    target: accounts.AllAccountsContext = {
        "net_worth": Decimal(),
        "assets": Decimal(),
        "liabilities": Decimal(),
        "assets_w": Decimal(),
        "liabilities_w": Decimal(),
        "categories": {},
        "include_closed": False,
        "n_closed": 0,
    }
    assert ctx == target


def test_ctx_accounts(
    session: orm.Session,
    account: Account,
    account_investments: Account,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    _ = transactions
    _ = asset_valuation
    account_investments.closed = True
    session.commit()

    ctx = accounts.ctx_accounts(session, include_closed=True)

    target: accounts.AllAccountsContext = {
        "net_worth": Decimal(108),
        "assets": Decimal(108),
        "liabilities": Decimal(),
        "assets_w": Decimal(100),
        "liabilities_w": Decimal(),
        "categories": {
            account.category: (
                Decimal(108),
                [accounts.ctx_account(session, account)],
            ),
            account_investments.category: (
                Decimal(),
                [accounts.ctx_account(session, account_investments)],
            ),
        },
        "include_closed": True,
        "n_closed": 1,
    }
    assert ctx == target
