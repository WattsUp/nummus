from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import TransactionCategory, TransactionCategoryGroup

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import BudgetGroup


def test_init_properties(
    session: orm.Session,
    rand_str: str,
    budget_group: BudgetGroup,
) -> None:
    d = {
        "emoji_name": f"😀{rand_str}😀",
        "group": TransactionCategoryGroup.INCOME,
        "locked": False,
        "is_profit_loss": False,
        "asset_linked": False,
        "essential_spending": False,
        "budget_group_id": budget_group.id_,
        "budget_position": 0,
    }

    t_cat = TransactionCategory(**d)
    session.add(t_cat)
    session.commit()

    assert t_cat.name == rand_str.lower()
    assert t_cat.emoji_name == d["emoji_name"]
    assert t_cat.group == d["group"]
    assert t_cat.locked == d["locked"]
    assert t_cat.is_profit_loss == d["is_profit_loss"]
    assert t_cat.asset_linked == d["asset_linked"]
    assert t_cat.essential_spending == d["essential_spending"]
    assert t_cat.budget_group_id == d["budget_group_id"]
    assert t_cat.budget_group_id == d["budget_group_id"]


def test_empty() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        TransactionCategory(emoji_name="😀")


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        TransactionCategory(emoji_name="a")


def test_name_direct() -> None:
    with pytest.raises(exc.ParentAttributeError):
        TransactionCategory(name="a")


def test_name_no_position(session: orm.Session, budget_group: BudgetGroup) -> None:
    with pytest.raises(exc.IntegrityError):
        session.query(TransactionCategory).where(
            TransactionCategory.name == "transfers",
        ).update({TransactionCategory.budget_group_id: budget_group.id_})


def test_name_no_group(session: orm.Session) -> None:
    with pytest.raises(exc.IntegrityError):
        session.query(TransactionCategory).where(
            TransactionCategory.name == "transfers",
        ).update({TransactionCategory.budget_position: 0})


def test_essential_income() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        TransactionCategory(
            group=TransactionCategoryGroup.INCOME,
            essential_spending=True,
        )


def test_essential_income_update(session: orm.Session) -> None:
    with pytest.raises(exc.IntegrityError):
        session.query(TransactionCategory).where(
            TransactionCategory.name == "other income",
        ).update({TransactionCategory.essential_spending: True})


def test_essential_expense(session: orm.Session) -> None:
    session.query(TransactionCategory).where(
        TransactionCategory.name == "groceries",
    ).update({TransactionCategory.essential_spending: True})
    session.commit()


def test_essential_none() -> None:
    with pytest.raises(TypeError):
        TransactionCategory(essential_spending=None)


def test_emergency_fund_missing(session: orm.Session) -> None:
    session.query(TransactionCategory).delete()
    with pytest.raises(exc.ProtectedObjectNotFoundError):
        TransactionCategory.emergency_fund(session)


def test_emergency_fund(session: orm.Session, categories: dict[str, int]) -> None:
    result = TransactionCategory.emergency_fund(session)
    t_cat_id = categories["emergency fund"]
    assert result == (t_cat_id, TransactionCategory.id_to_uri(t_cat_id))


def test_uncategorized(session: orm.Session, categories: dict[str, int]) -> None:
    result = TransactionCategory.uncategorized(session)
    t_cat_id = categories["uncategorized"]
    assert result == (t_cat_id, TransactionCategory.id_to_uri(t_cat_id))


def test_securities_traded(session: orm.Session, categories: dict[str, int]) -> None:
    result = TransactionCategory.securities_traded(session)
    t_cat_id = categories["securities traded"]
    assert result == (t_cat_id, TransactionCategory.id_to_uri(t_cat_id))


def test_map_name(
    session: orm.Session,
    categories: dict[str, int],
) -> None:
    result = TransactionCategory.map_name(session)
    assert result[categories["uncategorized"]] == "uncategorized"
    assert result[categories["securities traded"]] == "securities traded"


def test_map_name_no_asset_linked(
    session: orm.Session,
    categories: dict[str, int],
) -> None:
    result = TransactionCategory.map_name(session, no_asset_linked=True)
    assert result[categories["uncategorized"]] == "uncategorized"
    assert categories["securities traded"] not in result


def test_map_name_emoji(
    session: orm.Session,
    categories: dict[str, int],
) -> None:
    session.query(TransactionCategory).where(
        TransactionCategory.name == "uncategorized",
    ).update(
        {TransactionCategory.emoji_name: "🤷 Uncategorized 🤷"},
    )
    result = TransactionCategory.map_name_emoji(session)
    assert result[categories["uncategorized"]] == "🤷 Uncategorized 🤷"
    assert result[categories["securities traded"]] == "Securities Traded"


def test_map_name_emoji_no_asset_linked(
    session: orm.Session,
    categories: dict[str, int],
) -> None:
    session.query(TransactionCategory).where(
        TransactionCategory.name == "uncategorized",
    ).update(
        {TransactionCategory.emoji_name: "🤷 Uncategorized 🤷"},
    )
    result = TransactionCategory.map_name_emoji(session, no_asset_linked=True)
    assert result[categories["uncategorized"]] == "🤷 Uncategorized 🤷"
    assert categories["securities traded"] not in result
