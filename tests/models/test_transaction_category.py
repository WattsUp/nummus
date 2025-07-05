from __future__ import annotations

from nummus import exceptions as exc
from nummus import models
from nummus.models import (
    BudgetGroup,
    query_count,
    TransactionCategory,
    TransactionCategoryGroup,
)


def test_init_properties() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    g = BudgetGroup(name=self.random_string(), position=0)
    s.add(g)
    s.commit()
    g_id = g.id_

    name = self.random_string()
    d = {
        "emoji_name": f"😀{name}😀",
        "group": TransactionCategoryGroup.INCOME,
        "locked": False,
        "is_profit_loss": False,
        "asset_linked": False,
        "essential": False,
    }

    t_cat = TransactionCategory(**d)
    s.add(t_cat)
    s.commit()

    self.assertEqual(t_cat.name, name.lower())
    self.assertEqual(t_cat.emoji_name, d["emoji_name"])
    self.assertEqual(t_cat.group, d["group"])
    self.assertEqual(t_cat.locked, d["locked"])
    self.assertEqual(t_cat.is_profit_loss, d["is_profit_loss"])
    self.assertEqual(t_cat.asset_linked, d["asset_linked"])
    self.assertEqual(t_cat.essential, d["essential"])

    # Setting name directly is bad
    self.assertRaises(
        exc.ParentAttributeError,
        setattr,
        t_cat,
        "name",
        self.random_string(),
    )

    # Short strings are bad
    self.assertRaises(exc.InvalidORMValueError, setattr, t_cat, "emoji_name", "b")

    # No strings are bad
    self.assertRaises(
        exc.InvalidORMValueError,
        setattr,
        t_cat,
        "emoji_name",
        "😀",
    )

    # Just budget_group bad
    t_cat.budget_group_id = g_id
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # Just budget_position bad
    t_cat.budget_position = 10
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # Both okay
    t_cat.budget_group_id = g_id
    t_cat.budget_position = 10
    s.commit()

    # INCOME cannot be essential
    self.assertRaises(
        exc.InvalidORMValueError,
        setattr,
        t_cat,
        "essential",
        True,  # noqa: FBT003
    )

    # INCOME cannot be non-bool
    self.assertRaises(
        TypeError,
        setattr,
        t_cat,
        "essential",
        None,
    )

    # EXPENSE okay
    t_cat.group = TransactionCategoryGroup.EXPENSE
    t_cat.essential = True
    s.commit()


def test_add_default() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    self.assertRaises(
        exc.ProtectedObjectNotFoundError,
        TransactionCategory.emergency_fund,
        s,
    )

    result = TransactionCategory.add_default(s)
    s.commit()
    self.assertIsInstance(result, dict)

    cat = result["emergency fund"]
    target = (cat.id_, cat.uri)
    self.assertEqual(TransactionCategory.emergency_fund(s), target)

    cat = result["uncategorized"]
    target = (cat.id_, cat.uri)
    self.assertEqual(TransactionCategory.uncategorized(s), target)

    n_income = 0
    n_expense = 0
    n_transfer = 0
    n_other = 0
    for cat in result.values():
        if cat.group == TransactionCategoryGroup.INCOME:
            n_income += 1
        elif cat.group == TransactionCategoryGroup.EXPENSE:
            n_expense += 1
        elif cat.group == TransactionCategoryGroup.TRANSFER:
            n_transfer += 1
        elif cat.group == TransactionCategoryGroup.OTHER:
            n_other += 1

    query = s.query(TransactionCategory).where(
        TransactionCategory.group == TransactionCategoryGroup.INCOME,
    )
    self.assertEqual(query_count(query), n_income)

    query = s.query(TransactionCategory).where(
        TransactionCategory.group == TransactionCategoryGroup.EXPENSE,
    )
    self.assertEqual(query_count(query), n_expense)

    query = s.query(TransactionCategory).where(
        TransactionCategory.group == TransactionCategoryGroup.TRANSFER,
    )
    self.assertEqual(query_count(query), n_transfer)

    query = s.query(TransactionCategory).where(
        TransactionCategory.group == TransactionCategoryGroup.OTHER,
    )
    self.assertEqual(query_count(query), n_other)

    query = s.query(TransactionCategory)
    self.assertEqual(
        query_count(query),
        n_income + n_expense + n_transfer + n_other,
    )
    self.assertEqual(query_count(query), 62)


def test_map_name_emoji() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    TransactionCategory.add_default(s)

    t_cat_id = (
        s.query(TransactionCategory.id_)
        .where(TransactionCategory.name == "uncategorized")
        .one()[0]
    )
    s.query(TransactionCategory).where(TransactionCategory.id_ == t_cat_id).update(
        {"emoji_name": "🤷 Uncategorized 🤷"},
    )

    target = TransactionCategory.map_name(s)
    target[t_cat_id] = "🤷 uncategorized 🤷"
    result = TransactionCategory.map_name_emoji(s)
    self.assertEqual({k: v.lower() for k, v in result.items()}, target)

    asset_linked = ("securities traded", "dividends received", "investment fees")
    target = {
        t_cat_id: name for t_cat_id, name in target.items() if name not in asset_linked
    }
    result = TransactionCategory.map_name_emoji(s, no_asset_linked=True)
    self.assertEqual({k: v.lower() for k, v in result.items()}, target)
    target[t_cat_id] = "uncategorized"
    result = TransactionCategory.map_name(s, no_asset_linked=True)
    self.assertEqual({k: v.lower() for k, v in result.items()}, target)
