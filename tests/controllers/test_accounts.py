from __future__ import annotations

import datetime
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
    TransactionSplit,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from tests.conftest import RandomStringGenerator
    from tests.controllers.conftest import WebClient


@pytest.fixture
def transactions(
    today: datetime.date,
    rand_str_generator: RandomStringGenerator,
    session: orm.Session,
    account: Account,
    asset: Asset,
    categories: dict[str, int],
    transactions: list[Transaction],
) -> list[Transaction]:
    _ = transactions
    # Add dividends yesterday
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=1),
        amount=0,
        statement=rand_str_generator(),
        payee="Monkey Bank",
        cleared=True,
    )
    t_split_0 = TransactionSplit(
        parent=txn,
        amount=-1,
        asset_id=asset.id_,
        asset_quantity_unadjusted=1,
        category_id=categories["securities traded"],
    )
    t_split_1 = TransactionSplit(
        parent=txn,
        amount=1,
        asset_id=asset.id_,
        asset_quantity_unadjusted=0,
        category_id=categories["dividends received"],
    )
    session.add_all((txn, t_split_0, t_split_1))

    # Add fee today
    txn = Transaction(
        account_id=account.id_,
        date=today,
        amount=0,
        statement=rand_str_generator(),
        payee="Monkey Bank",
        cleared=True,
    )
    t_split_0 = TransactionSplit(
        parent=txn,
        amount=2,
        asset_id=asset.id_,
        asset_quantity_unadjusted=-2,
        category_id=categories["securities traded"],
    )
    t_split_1 = TransactionSplit(
        parent=txn,
        amount=-2,
        asset_id=asset.id_,
        asset_quantity_unadjusted=0,
        category_id=categories["investment fees"],
    )
    session.add_all((txn, t_split_0, t_split_1))

    session.commit()
    return session.query(Transaction).order_by(Transaction.date_ord).all()


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


def test_txns(web_client: WebClient, account: Account) -> None:
    result, headers = web_client.GET(("accounts.txns", {"uri": account.uri}))
    assert "no transactions match query" in result
    assert headers["HX-Push-URL"] == web_client.url_for(
        "accounts.page",
        uri=account.uri,
    )


def test_txns_second_page(
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    result, headers = web_client.GET(
        (
            "accounts.txns",
            {"uri": account.uri, "page": transactions[0].date.isoformat()},
        ),
    )
    assert "no more transactions match query" in result
    assert "HX-Push-URL" not in headers


def test_txns_options(
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.GET(("accounts.txns_options", {"uri": account.uri}))
    assert 'name="period"' in result
    assert 'name="category"' in result
    assert 'name="start"' in result
    assert 'name="end"' in result
    assert 'name="account"' not in result
    assert "Other Income" in result
    assert "Securities Traded" in result
    assert account.name not in result


def test_page_all(web_client: WebClient, account: Account) -> None:
    result, _ = web_client.GET("accounts.page_all")
    assert "Accounts" in result
    assert "Cash" in result
    assert account.name in result


def test_page_empty(web_client: WebClient, account: Account) -> None:
    result, _ = web_client.GET(("accounts.page", {"uri": account.uri}))
    assert "Transactions" in result
    assert "Balance" in result
    assert "Performance" not in result
    assert "Assets" not in result
    assert account.name in result


def test_page(
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.GET(("accounts.page", {"uri": account.uri}))
    assert "Transactions" in result
    assert "Balance" in result
    assert "Performance" not in result
    assert "Assets" in result
    assert "Investments" not in result
    assert account.name in result


def test_page_performance(
    session: orm.Session,
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    account.category = AccountCategory.INVESTMENT
    session.commit()

    result, _ = web_client.GET(("accounts.page", {"uri": account.uri}))
    assert "Transactions" in result
    assert "Balance" in result
    assert "Performance" in result
    assert "Assets" not in result
    assert "Investments" in result
    assert account.name in result


@pytest.mark.xfail
def test_new(web_client: WebClient) -> None:
    web_client.GET("accounts.new")


def test_account_get(web_client: WebClient, account: Account) -> None:
    result, _ = web_client.GET(("accounts.account", {"uri": account.uri}))
    assert account.name in result
    assert account.institution in result
    assert account.number is not None
    assert account.number in result
    assert "Edit account" in result
    assert "Save" in result
    assert "Delete" not in result


def test_account_edit(
    web_client: WebClient,
    session: orm.Session,
    account: Account,
) -> None:
    result, headers = web_client.PUT(
        ("accounts.account", {"uri": account.uri}),
        data={
            "name": "New name",
            "category": "INVESTMENT",
            "institution": "Nothing to see",
            "number": "1234",
            "closed": "on",
        },
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "account"

    session.refresh(account)
    assert account.name == "New name"
    assert account.category == AccountCategory.INVESTMENT
    assert account.institution == "Nothing to see"
    assert account.number == "1234"


@pytest.mark.parametrize(
    ("name", "closed", "target"),
    [
        ("a", False, "Account name must be at least 2 characters long"),
        ("New name", True, "Cannot close Account with non-zero balance"),
    ],
)
def test_account_edit_error(
    web_client: WebClient,
    account: Account,
    name: str,
    closed: bool,
    target: str,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    form = {
        "name": name,
        "category": "INVESTMENT",
        "institution": "Nothing to see",
        "number": "1234",
    }
    if closed:
        form["closed"] = "on"
    result, _ = web_client.PUT(("accounts.account", {"uri": account.uri}), data=form)
    assert result == base.error(target)


def test_performance(
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, headers = web_client.GET(("accounts.performance", {"uri": account.uri}))
    assert headers["HX-Push-URL"] == web_client.url_for(
        "accounts.page",
        uri=account.uri,
    )

    assert "Performance" in result


@pytest.mark.parametrize(
    ("prop", "value", "target"),
    [
        ("name", "New Name", ""),
        ("name", " ", "Required"),
        ("name", "a", "2 characters required"),
        ("name", "Monkey bank investments", "Must be unique"),
        ("institution", "Monkey bank", ""),
        ("number", "1234", ""),
        ("number", " ", ""),
        ("number", "1", "2 characters required"),
        ("number", "1235", "Must be unique"),
    ],
)
def test_validation(
    web_client: WebClient,
    account: Asset,
    account_investments: Asset,
    prop: str,
    value: str,
    target: str,
) -> None:
    _ = account_investments
    result, _ = web_client.GET(
        (
            "accounts.validation",
            {"uri": account.uri, prop: value},
        ),
    )
    assert result == target
