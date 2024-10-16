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
    def test_search(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        # Create accounts
        acct_checking = Account(
            name="Monkey Bank Checking",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
            emergency=False,
            budgeted=False,
        )
        acct_invest = Account(
            name="Gorilla Investments",
            institution="Ape Trading",
            category=AccountCategory.INVESTMENT,
            closed=False,
            emergency=False,
            budgeted=False,
        )
        s.add_all((acct_checking, acct_invest))
        s.commit()

        query = s.query(Account)

        # No results return all
        result = utils.search(query, Account, None).all()  # type: ignore[attr-defined]
        self.assertEqual(result, [acct_checking, acct_invest])

        # Short query return all
        result = utils.search(query, Account, "ab").all()  # type: ignore[attr-defined]
        self.assertEqual(result, [acct_checking, acct_invest])

        # No matches return first 5
        result = utils.search(query, Account, "crazy unrelated words").all()  # type: ignore[attr-defined]
        self.assertEqual(result, [acct_checking, acct_invest])

        result = utils.search(query, Account, "checking").all()  # type: ignore[attr-defined]
        self.assertEqual(result, [acct_checking])

        result = utils.search(query, Account, "Monkey Bank").all()  # type: ignore[attr-defined]
        self.assertEqual(result, [acct_checking])

        result = utils.search(query, Account, "monkey gorilla").all()  # type: ignore[attr-defined]
        self.assertEqual(result, [acct_checking, acct_invest])

        result = utils.search(query, Account, "trading").all()  # type: ignore[attr-defined]
        self.assertEqual(result, [acct_invest])

    def test_paginate(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        n_transactions = 10
        today = datetime.date.today()

        # Create accounts
        acct = Account(
            name="Monkey Bank Checking",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
            emergency=False,
            budgeted=False,
        )
        s.add(acct)
        s.commit()

        t_cat = TransactionCategory(
            name="Uncategorized",
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
