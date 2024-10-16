from __future__ import annotations

import datetime
from decimal import Decimal

from nummus import exceptions as exc
from nummus import models, utils
from nummus.models import (
    Account,
    AccountCategory,
    BudgetAssignment,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from tests.base import TestBase


class TestBudgetAssignment(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        t_cat = TransactionCategory(
            name="Securities Traded",
            group=TransactionCategoryGroup.OTHER,
            locked=False,
            is_profit_loss=False,
            asset_linked=True,
            essential=False,
        )
        s.add(t_cat)
        s.commit()
        t_cat_id = t_cat.id_

        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()

        d = {
            "month_ord": month_ord,
            "amount": self.random_decimal(-1, 0),
            "category_id": t_cat_id,
        }

        b = BudgetAssignment(**d)
        s.add(b)
        s.commit()

        self.assertEqual(b.month_ord, d["month_ord"])
        self.assertEqual(b.amount, d["amount"])
        self.assertEqual(b.category_id, d["category_id"])

        # Duplicate dates are bad
        b = BudgetAssignment(month_ord=month_ord, amount=0, category_id=t_cat_id)
        s.add(b)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

    def test_get_monthly_available(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)
        TransactionCategory.add_default(s)
        names = TransactionCategory.map_name(s)
        names_rev = {v: k for k, v in names.items()}

        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        self.assertEqual(categories.keys(), names.keys())
        non_zero = {k: v for k, v in categories.items() if any(vv != 0 for vv in v)}
        self.assertEqual(non_zero, {})
        self.assertEqual(assignable, 0)
        self.assertEqual(future_assigned, 0)

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
            budgeted=False,
        )
        s.add(acct)
        s.commit()

        t_cat_id = names_rev["General Merchandise"]
        txn = Transaction(
            account_id=acct.id_,
            date=today,
            amount=Decimal(-10),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=t_cat_id,
        )
        s.add_all((txn, t_split))
        s.commit()

        # Account not budgeted won't show up
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        non_zero = {k: v for k, v in categories.items() if any(vv != 0 for vv in v)}
        self.assertEqual(non_zero, {})
        self.assertEqual(assignable, 0)
        self.assertEqual(future_assigned, 0)

        # Show up with a budgeted account
        acct.budgeted = True
        s.commit()

        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        self.assertEqual(categories[t_cat_id], (Decimal(0), Decimal(-10), Decimal(-10)))
        self.assertEqual(assignable, 0)
        self.assertEqual(future_assigned, 0)

        # Add income
        txn = Transaction(
            account_id=acct.id_,
            date=today,
            amount=Decimal(100),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=names_rev["Other Income"],
        )
        s.add_all((txn, t_split))
        s.commit()
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        self.assertEqual(categories[t_cat_id], (Decimal(0), Decimal(-10), Decimal(-10)))
        self.assertEqual(
            categories[names_rev["Other Income"]],
            (Decimal(0), Decimal(100), Decimal(0)),
        )
        self.assertEqual(assignable, Decimal(100))
        self.assertEqual(future_assigned, 0)

        # Add assignment
        a = BudgetAssignment(
            month_ord=month_ord,
            amount=Decimal(10),
            category_id=t_cat_id,
        )
        s.add(a)
        s.commit()
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        self.assertEqual(categories[t_cat_id], (Decimal(10), Decimal(-10), Decimal(0)))
        self.assertEqual(assignable, Decimal(90))
        self.assertEqual(future_assigned, 0)

        # Add assignment to last month and more income
        month_last = utils.date_add_months(month, -1)
        a = BudgetAssignment(
            month_ord=month_last.toordinal(),
            amount=Decimal(10),
            category_id=t_cat_id,
        )
        s.add(a)
        txn = Transaction(
            account_id=acct.id_,
            date=month_last,
            amount=Decimal(100),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=names_rev["Other Income"],
        )
        s.add_all((txn, t_split))
        s.commit()
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        self.assertEqual(categories[t_cat_id], (Decimal(10), Decimal(-10), Decimal(10)))
        self.assertEqual(assignable, Decimal(180))
        self.assertEqual(future_assigned, 0)
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month_last)
        )
        self.assertEqual(categories[t_cat_id], (Decimal(10), Decimal(0), Decimal(10)))
        self.assertEqual(assignable, Decimal(80))
        self.assertEqual(future_assigned, Decimal(10))

        # Add prior activity with leftovers
        txn = Transaction(
            account_id=acct.id_,
            date=month_last,
            amount=Decimal(-5),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=t_cat_id,
        )
        s.add_all((txn, t_split))
        s.commit()
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        self.assertEqual(categories[t_cat_id], (Decimal(10), Decimal(-10), Decimal(5)))
        self.assertEqual(assignable, Decimal(180))
        self.assertEqual(future_assigned, 0)

        # Remove prior assignment
        a.amount = Decimal(0)
        s.commit()
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        self.assertEqual(categories[t_cat_id], (Decimal(10), Decimal(-10), Decimal(0)))
        self.assertEqual(assignable, Decimal(185))
        self.assertEqual(future_assigned, 0)

        # Increase funding
        a.amount = Decimal(90)
        s.commit()
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month_last)
        )
        self.assertEqual(categories[t_cat_id], (Decimal(90), Decimal(-5), Decimal(85)))
        self.assertEqual(assignable, Decimal(0))
        self.assertEqual(future_assigned, Decimal(10))

        # Increase funding
        a.amount = Decimal(150)
        s.commit()
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month_last)
        )
        self.assertEqual(
            categories[t_cat_id],
            (Decimal(150), Decimal(-5), Decimal(145)),
        )
        self.assertEqual(assignable, Decimal(-50))
        self.assertEqual(future_assigned, Decimal(0))

        # Close account, but still included cause it has transactions this month
        txn = Transaction(
            account_id=acct.id_,
            date=today,
            amount=Decimal(-185),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=t_cat_id,
        )
        s.add_all((txn, t_split))
        acct.closed = True
        s.commit()
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        self.assertEqual(
            categories[t_cat_id],
            (Decimal(10), Decimal(-195), Decimal(-40)),
        )
        self.assertEqual(assignable, Decimal(40))
        self.assertEqual(future_assigned, 0)
