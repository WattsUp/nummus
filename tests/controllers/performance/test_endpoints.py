from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.models import AccountCategory

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Account, AssetValuation, Transaction
    from tests.controllers.conftest import WebClient


def test_page_empty(web_client: WebClient, account: Account) -> None:
    result, _ = web_client.GET("performance.page")
    assert "Investing performance" in result
    assert "Accounts" in result
    assert "About S&P 500" in result
    assert account.name not in result


def test_page(
    session: orm.Session,
    web_client: WebClient,
    account: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    account.category = AccountCategory.INVESTMENT
    session.commit()
    _ = asset_valuation
    _ = transactions

    result, _ = web_client.GET(
        ("performance.page", {"index": "Dow Jones Industrial Average"}),
    )
    assert "Investing performance" in result
    assert "Accounts" in result
    assert "About Dow Jones" in result
    assert account.name in result


def test_chart(
    session: orm.Session,
    web_client: WebClient,
    account: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    account.category = AccountCategory.INVESTMENT
    session.commit()
    _ = asset_valuation
    _ = transactions

    result, headers = web_client.GET("performance.chart")
    assert headers["HX-Push-URL"] == web_client.url_for(
        "performance.page",
        period="6m",
        index="S&P 500",
    )
    assert "JSON.parse" in result


def test_dashboard(
    session: orm.Session,
    web_client: WebClient,
    account: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    account.category = AccountCategory.INVESTMENT
    session.commit()
    _ = asset_valuation
    _ = transactions

    result, _ = web_client.GET("performance.dashboard")
    assert "Investing performance" in result
    assert "Portfolio" in result
    assert "S&P 500" in result
    assert "Dow Jones" in result
