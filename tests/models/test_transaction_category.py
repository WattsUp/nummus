from __future__ import annotations

from nummus import exceptions as exc
from nummus import models
from nummus.models import TransactionCategory, TransactionCategoryGroup
from tests.base import TestBase


class TestTransactionCategory(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        d = {
            "name": self.random_string(),
            "emoji": "😀",
            "group": TransactionCategoryGroup.INCOME,
            "locked": False,
            "is_profit_loss": False,
        }

        t_cat = TransactionCategory(**d)
        s.add(t_cat)
        s.commit()

        self.assertEqual(t_cat.name, d["name"])
        self.assertEqual(t_cat.group, d["group"])
        self.assertEqual(t_cat.locked, d["locked"])
        self.assertEqual(t_cat.is_profit_loss, d["is_profit_loss"])

        # Short strings are bad
        self.assertRaises(exc.InvalidORMValueError, setattr, t_cat, "name", "b")

        # No strings are bad
        t_cat.name = ""
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # Non-emojis are bad
        self.assertRaises(
            exc.InvalidORMValueError,
            setattr,
            t_cat,
            "emoji",
            self.random_string(),
        )

        # Emojis and text not allowed
        self.assertRaises(
            exc.InvalidORMValueError,
            setattr,
            t_cat,
            "name",
            self.random_string() + "😀",
        )

        # Emojis and text not allowed
        self.assertRaises(
            exc.InvalidORMValueError,
            setattr,
            t_cat,
            "emoji",
            self.random_string() + "😀",
        )

        # No emoji okay
        t_cat.emoji = None
        s.commit()

    def test_add_default(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        result = TransactionCategory.add_default(s)
        self.assertIsInstance(result, dict)

        n_income = 0
        n_expense = 0
        n_other = 0
        for cat in result.values():
            if cat.group == TransactionCategoryGroup.INCOME:
                n_income += 1
            elif cat.group == TransactionCategoryGroup.EXPENSE:
                n_expense += 1
            elif cat.group == TransactionCategoryGroup.OTHER:
                n_other += 1

        query = s.query(TransactionCategory)
        query = query.where(
            TransactionCategory.group == TransactionCategoryGroup.INCOME,
        )
        self.assertEqual(query.count(), n_income)

        query = s.query(TransactionCategory)
        query = query.where(
            TransactionCategory.group == TransactionCategoryGroup.EXPENSE,
        )
        self.assertEqual(query.count(), n_expense)

        query = s.query(TransactionCategory)
        query = query.where(TransactionCategory.group == TransactionCategoryGroup.OTHER)
        self.assertEqual(query.count(), n_other)

        query = s.query(TransactionCategory)
        self.assertEqual(query.count(), n_income + n_expense + n_other)
        self.assertEqual(query.count(), 61)

    def test_map_name_emoji(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        TransactionCategory.add_default(s)

        t_cat_id = (
            s.query(TransactionCategory.id_)
            .where(TransactionCategory.name == "Uncategorized")
            .one()[0]
        )
        s.query(TransactionCategory).where(TransactionCategory.id_ == t_cat_id).update(
            {"emoji": "🤷"},
        )

        target = TransactionCategory.map_name(s)
        target[t_cat_id] = "🤷 Uncategorized"
        result = TransactionCategory.map_name_emoji(s, no_securities_traded=False)
        self.assertEqual(result, target)

        target = {
            t_cat_id: name
            for t_cat_id, name in target.items()
            if name != "Securities Traded"
        }
        result = TransactionCategory.map_name_emoji(s, no_securities_traded=True)
        self.assertEqual(result, target)
