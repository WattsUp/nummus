from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus.controllers import base
from nummus.models import (
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Transaction,
    )
    from tests.controllers.conftest import WebClient


@pytest.mark.parametrize(
    ("category", "s", "target"),
    [
        ("uncategorized", " ", "Required"),
        ("uncategorized", "i", "2 characters required"),
        ("uncategorized", "idk", "May only add/remove emojis"),
        ("uncategorized", "Uncategorized 🤷", ""),
        ("groceries", "Food", ""),
        ("groceries", "Restaurants", "Must be unique"),
    ],
)
def test_validation(
    web_client: WebClient,
    categories: dict[str, int],
    category: str,
    s: str,
    target: str,
) -> None:
    uri = TransactionCategory.id_to_uri(categories[category])
    result, _ = web_client.GET(
        ("transaction_categories.validation", {"uri": uri, "name": s}),
    )
    assert result == target


def test_page(web_client: WebClient) -> None:
    result, _ = web_client.GET("transaction_categories.page")
    assert "Transaction categories" in result
    assert "Income" in result
    assert "Expense" in result
    assert "Transfer" in result
    assert "Other" in result


def test_new_get(web_client: WebClient) -> None:
    result, _ = web_client.GET("transaction_categories.new")
    assert "New category" in result
    assert "Save" in result
    assert "Delete" not in result


def test_new(
    web_client: WebClient,
    rand_str: str,
    session: orm.Session,
) -> None:
    form = {
        "name": rand_str,
        "group": "expense",
        "is-pnl": "on",
        "essential-spending": "on",
    }
    result, headers = web_client.POST("transaction_categories.new", data=form)
    assert "snackbar.show" in result
    assert f"Created category {rand_str}" in result
    assert headers["HX-Trigger"] == "category"

    t_cat = (
        session.query(TransactionCategory)
        .where(TransactionCategory.emoji_name == rand_str)
        .one()
    )
    assert t_cat.group == TransactionCategoryGroup.EXPENSE
    assert t_cat.is_profit_loss
    assert t_cat.essential_spending


def test_new_error(web_client: WebClient, rand_str: str) -> None:
    form = {
        "name": rand_str,
        "group": "income",
        "is-pnl": "on",
        "essential-spending": "on",
    }
    result, _ = web_client.POST("transaction_categories.new", data=form)
    assert result == base.error("Income cannot be essential spending")


def test_category_get_locked(web_client: WebClient, categories: dict[str, int]) -> None:
    uri = TransactionCategory.id_to_uri(categories["uncategorized"])
    result, _ = web_client.GET(("transaction_categories.category", {"uri": uri}))
    assert "Edit category" in result
    assert "Uncategorized" in result
    assert "Save" in result
    assert "Delete" not in result
    assert "May only add/remove emojis" in result


def test_category_get_unlocked(
    web_client: WebClient,
    categories: dict[str, int],
) -> None:
    uri = TransactionCategory.id_to_uri(categories["groceries"])
    result, _ = web_client.GET(("transaction_categories.category", {"uri": uri}))
    assert "Edit category" in result
    assert "Groceries" in result
    assert "Save" in result
    assert "Delete" in result
    assert "May only add/remove emojis" not in result


def test_category_delete_locked(
    web_client: WebClient,
    categories: dict[str, int],
) -> None:
    uri = TransactionCategory.id_to_uri(categories["uncategorized"])
    web_client.DELETE(
        ("transaction_categories.category", {"uri": uri}),
        rc=base.HTTP_CODE_FORBIDDEN,
    )


def test_category_delete_unlocked(
    web_client: WebClient,
    categories: dict[str, int],
    session: orm.Session,
    transactions_spending: list[Transaction],
) -> None:
    _ = transactions_spending
    t_split = (
        session.query(TransactionSplit)
        .where(TransactionSplit.category_id == categories["groceries"])
        .first()
    )
    assert t_split is not None
    uri = TransactionCategory.id_to_uri(categories["groceries"])

    result, headers = web_client.DELETE(
        ("transaction_categories.category", {"uri": uri}),
    )
    assert "snackbar.show" in result
    assert "Deleted category Groceries" in result
    assert headers["HX-Trigger"] == "category"

    t_cat = (
        session.query(TransactionCategory)
        .where(TransactionCategory.name == "groceries")
        .one_or_none()
    )
    assert t_cat is None

    session.refresh(t_split)
    assert t_split.category_id == categories["uncategorized"]


def test_category_edit_unlocked(
    web_client: WebClient,
    categories: dict[str, int],
    session: orm.Session,
) -> None:
    uri = TransactionCategory.id_to_uri(categories["groceries"])

    result, headers = web_client.PUT(
        ("transaction_categories.category", {"uri": uri}),
        data={"name": "Food", "group": "expense", "essential-spending": "on"},
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "category"

    t_cat = (
        session.query(TransactionCategory)
        .where(TransactionCategory.name == "food")
        .one()
    )
    assert t_cat.emoji_name == "Food"
    assert t_cat.group == TransactionCategoryGroup.EXPENSE
    assert not t_cat.is_profit_loss
    assert t_cat.essential_spending


def test_category_edit_locked(
    web_client: WebClient,
    categories: dict[str, int],
    session: orm.Session,
) -> None:
    uri = TransactionCategory.id_to_uri(categories["uncategorized"])

    result, headers = web_client.PUT(
        ("transaction_categories.category", {"uri": uri}),
        data={"name": "Uncategorized 🤷", "group": "other"},
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "category"

    t_cat = (
        session.query(TransactionCategory)
        .where(TransactionCategory.name == "uncategorized")
        .one()
    )
    assert t_cat.emoji_name == "Uncategorized 🤷"
    assert t_cat.group == TransactionCategoryGroup.OTHER
    assert not t_cat.is_profit_loss
    assert not t_cat.essential_spending


def test_category_edit_locked_error(
    web_client: WebClient,
    categories: dict[str, int],
) -> None:
    uri = TransactionCategory.id_to_uri(categories["uncategorized"])

    result, _ = web_client.PUT(
        ("transaction_categories.category", {"uri": uri}),
        data={"name": "Food", "group": "expense", "essential-spending": "on"},
    )
    assert result == base.error("May only add/remove emojis on locked category")


def test_category_edit_error(
    web_client: WebClient,
    categories: dict[str, int],
) -> None:
    uri = TransactionCategory.id_to_uri(categories["groceries"])

    result, _ = web_client.PUT(
        ("transaction_categories.category", {"uri": uri}),
        data={"name": "Food", "group": "income", "essential-spending": "on"},
    )
    assert result == base.error("Income cannot be essential spending")
