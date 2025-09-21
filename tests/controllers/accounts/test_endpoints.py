from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus.controllers import base
from nummus.models import Account, AccountCategory

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Asset, Transaction
    from tests.controllers.conftest import WebClient


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


def test_new_get(web_client: WebClient) -> None:
    result, _ = web_client.GET("accounts.new")
    assert "New account" in result
    assert "Save" in result
    assert "Delete" not in result


def test_new(
    web_client: WebClient,
    session: orm.Session,
) -> None:
    result, headers = web_client.POST(
        "accounts.new",
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

    account = session.query(Account).one()
    assert account.name == "New name"
    assert account.category == AccountCategory.INVESTMENT
    assert account.institution == "Nothing to see"
    assert account.number == "1234"
    assert not account.closed


def test_new_error(web_client: WebClient) -> None:
    result, _ = web_client.POST(
        "accounts.new",
        data={
            "name": "a",
            "category": "INVESTMENT",
            "institution": "Nothing to see",
            "number": "1234",
            "closed": "on",
        },
    )
    assert result == base.error("Account name must be at least 2 characters long")


def test_account_get_empty(web_client: WebClient, account: Account) -> None:
    result, _ = web_client.GET(("accounts.account", {"uri": account.uri}))
    assert account.name in result
    assert account.institution in result
    assert account.number is not None
    assert account.number in result
    assert "Edit account" in result
    assert "Save" in result
    assert "Delete" in result


def test_account_get(
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
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


def test_account_delete(web_client: WebClient, account: Account) -> None:
    result, headers = web_client.DELETE(("accounts.account", {"uri": account.uri}))
    assert not result
    assert headers["HX-Redirect"] == web_client.url_for("accounts.page_all")


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
