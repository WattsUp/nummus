from __future__ import annotations

import datetime

from nummus import models
from nummus.models import (
    Account,
    AccountCategory,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
    utils,
)
from tests.base import TestBase


class TestUtils(TestBase):

    def test_paginate(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        n_transactions = 10
        today = datetime.datetime.now().astimezone().date()

        # Create accounts
        acct = Account(
            name="Monkey Bank Checking",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
            budgeted=False,
        )
        s.add(acct)
        s.commit()

        t_cat = TransactionCategory(
            emoji_name="Uncategorized",
            group=TransactionCategoryGroup.OTHER,
            locked=False,
            is_profit_loss=False,
            asset_linked=False,
            essential=False,
        )
        s.add(t_cat)
        s.commit()

        for _ in range(n_transactions):
            txn = Transaction(
                account_id=acct.id_,
                date=today,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(amount=100, parent=txn, category_id=t_cat.id_)
            s.add_all((txn, t_split))
        s.commit()

        query = s.query(Transaction)
        transactions = query.all()
        query = s.query(Transaction)

        page, count, next_offset = utils.paginate(query, 50, 0)  # type: ignore[attr-defined]
        self.assertEqual(page, transactions)
        self.assertEqual(count, n_transactions)
        self.assertIsNone(next_offset)

        page, count, next_offset = utils.paginate(query, 3, 0)  # type: ignore[attr-defined]
        self.assertEqual(page, transactions[0:3])
        self.assertEqual(count, n_transactions)
        self.assertEqual(next_offset, 3)

        page, count, next_offset = utils.paginate(query, 3, 3)  # type: ignore[attr-defined]
        self.assertEqual(page, transactions[3:6])
        self.assertEqual(count, n_transactions)
        self.assertEqual(next_offset, 6)

        page, count, next_offset = utils.paginate(query, 3, 6)  # type: ignore[attr-defined]
        self.assertEqual(page, transactions[6:9])
        self.assertEqual(count, n_transactions)
        self.assertEqual(next_offset, 9)

        page, count, next_offset = utils.paginate(query, 3, 9)  # type: ignore[attr-defined]
        self.assertEqual(page, transactions[9:])
        self.assertEqual(count, n_transactions)
        self.assertIsNone(next_offset)

        page, count, next_offset = utils.paginate(query, 3, 1000)  # type: ignore[attr-defined]
        self.assertEqual(page, [])
        self.assertEqual(count, n_transactions)
        self.assertIsNone(next_offset)

        page, count, next_offset = utils.paginate(query, 3, -1000)  # type: ignore[attr-defined]
        self.assertEqual(page, transactions[0:3])
        self.assertEqual(count, n_transactions)
        self.assertEqual(next_offset, 3)
