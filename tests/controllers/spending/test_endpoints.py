from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nummus.models import (
        Account,
        Transaction,
    )
    from tests.controllers.conftest import WebClient


def test_page(
    web_client: WebClient,
    account: Account,
    transactions_spending: list[Transaction],
) -> None:
    _ = transactions_spending
    result, _ = web_client.GET("spending.page")
    assert "Spending" in result
    assert account.name in result
    assert "Rent" in result
    assert "Groceries" in result
    assert "apartments 4 U" in result


def test_chart(
    web_client: WebClient,
    account: Account,
    transactions_spending: list[Transaction],
) -> None:
    _ = transactions_spending
    result, _ = web_client.GET("spending.chart")
    assert "Spending" in result
    assert account.name in result
    assert "Rent" in result
    assert "Groceries" in result
    assert "apartments 4 U" in result


def test_dashboard(
    web_client: WebClient,
    account: Account,
    transactions_spending: list[Transaction],
) -> None:
    _ = transactions_spending
    result, _ = web_client.GET("spending.dashboard")
    assert "Spending" in result
    assert account.name in result
    assert "Rent" in result
    assert "Groceries" in result
    assert "apartments 4 U" in result
