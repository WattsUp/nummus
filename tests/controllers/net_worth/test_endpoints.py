from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nummus.models import Account, AssetValuation, Transaction
    from tests.controllers.conftest import WebClient


def test_page_empty(web_client: WebClient, account: Account) -> None:
    result, _ = web_client.GET("net_worth.page")
    assert "Net worth" in result
    assert "Assets" in result
    assert "Liabilities" in result
    assert account.name not in result


def test_page(
    web_client: WebClient,
    account: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    _ = asset_valuation
    _ = transactions

    result, _ = web_client.GET("net_worth.page")
    assert "Net worth" in result
    assert "Assets" in result
    assert "Liabilities" in result
    assert account.name in result


def test_chart(
    web_client: WebClient,
    account: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    _ = account
    _ = asset_valuation
    _ = transactions

    result, headers = web_client.GET("net_worth.chart")
    assert headers["HX-Push-URL"] == web_client.url_for(
        "net_worth.page",
        period="6m",
    )
    assert "JSON.parse" in result


def test_dashboard(
    web_client: WebClient,
    account: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    _ = account
    _ = asset_valuation
    _ = transactions

    result, _ = web_client.GET("net_worth.dashboard")
    assert "Net worth" in result
    assert "JSON.parse" in result
