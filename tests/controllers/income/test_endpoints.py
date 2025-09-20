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
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.GET("income.page")
    assert "Income" in result
    assert account.name in result
    assert "Other Income" in result
    assert "engineer" in result


def test_chart(
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.GET("income.chart")
    assert "Income" in result
    assert account.name in result
    assert "Other Income" in result
    assert "engineer" in result


def test_dashboard(
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.GET("income.dashboard")
    assert "Income" in result
    assert account.name in result
    assert "Other Income" in result
    assert "engineer" in result
