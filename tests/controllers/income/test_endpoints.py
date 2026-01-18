from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from nummus.models.account import Account
    from nummus.models.transaction import Transaction
    from tests.controllers.conftest import WebClient


def test_page(
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.GET(("income.page", {"period": "all"}))
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
    result, _ = web_client.GET(("income.chart", {"period": "all"}))
    assert "Income" in result
    assert account.name in result
    assert "Other Income" in result
    assert "engineer" in result


def test_dashboard(
    today: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    transactions[0].date = today
    transactions[0].splits[0].parent = transactions[0]
    session.commit()

    result, _ = web_client.GET("income.dashboard")
    assert "Income" in result
    assert account.name in result
    assert "Other Income" in result
    assert "engineer" in result
