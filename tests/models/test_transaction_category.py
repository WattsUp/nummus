from __future__ import annotations

from nummus import models
from nummus.models import TransactionCategory, TransactionCategoryGroup
from tests.base import TestBase


class TestTransactionCategory(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        d = {
            "name": self.random_string(),
            "group": self._RNG.choice(TransactionCategoryGroup),
            "locked": False,
        }

        t_cat = TransactionCategory(**d)
        s.add(t_cat)
        s.commit()

        self.assertEqual(t_cat.name, d["name"])
        self.assertEqual(t_cat.group, d["group"])
        self.assertEqual(t_cat.locked, d["locked"])

        # Short strings are bad
        self.assertRaises(ValueError, setattr, t_cat, "name", "ab")

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
        self.assertEqual(query.count(), 63)
