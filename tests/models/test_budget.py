from __future__ import annotations

import datetime
from decimal import Decimal

from nummus import exceptions as exc
from nummus import models, utils
from nummus.models import (
    Account,
    AccountCategory,
    BudgetAssignment,
    BudgetGroup,
    Target,
    TargetPeriod,
    TargetType,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from tests.base import TestBase


class TestBudgetGroup(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        d = {
            "name": self.random_string(),
            "position": 0,
        }

        g = BudgetGroup(**d)
        s.add(g)
        s.commit()

        self.assertEqual(g.name, d["name"])
        self.assertEqual(g.position, d["position"])

        # Short strings are bad
        self.assertRaises(exc.InvalidORMValueError, setattr, g, "name", "b")

        # No strings are bad
        g.name = ""
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # Duplicate names are bad
        g = BudgetGroup(name=d["name"], position=1)
        s.add(g)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # Duplicate positions are bad
        g = BudgetGroup(name=self.random_string(), position=0)
        s.add(g)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()


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


class TestTarget(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)
        TransactionCategory.add_default(s)
        names = TransactionCategory.map_name(s)
        names_rev = {v: k for k, v in names.items()}

        today = datetime.date.today()
        today_ord = today.toordinal()

        d = {
            "category_id": names_rev["General Merchandise"],
            "amount": self.random_decimal(1, 10),
            "type_": TargetType.BALANCE,
            "period": TargetPeriod.ONCE,
            "due_date_ord": today_ord,
            "repeat_every": 0,
        }

        t = Target(**d)
        s.add(t)
        s.commit()

        self.assertEqual(t.category_id, d["category_id"])
        self.assertEqual(t.amount, d["amount"])
        self.assertEqual(t.type_, d["type_"])
        self.assertEqual(t.period, d["period"])
        self.assertEqual(t.due_date_ord, d["due_date_ord"])
        self.assertEqual(t.repeat_every, d["repeat_every"])

        # ONCE cannot be REFILL
        t.type_ = TargetType.REFILL
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # ONCE cannot be ACCUMULATE
        t.type_ = TargetType.ACCUMULATE
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # ONCE cannot repeat
        t.repeat_every = 2
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # BALANCE cannot have a due date
        t.due_date_ord = None
        s.commit()

        # But not ONCE can be those things
        t.period = TargetPeriod.WEEK
        t.type_ = TargetType.ACCUMULATE
        t.repeat_every = 1
        t.due_date_ord = today_ord
        s.commit()

        # WEEK must repeat
        t.repeat_every = 0
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # WEEK can only repeat every week
        t.repeat_every = 2
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # MONTH and YEAR can repeat every other
        t.period = TargetPeriod.MONTH
        t.repeat_every = 2
        s.commit()

        # !ONCE cannot be BALANCE
        t.type_ = TargetType.BALANCE
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # ACCUMULATE must have a due date
        t.due_date_ord = None
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # Duplicate category_id are bad
        t = Target(**d)
        s.add(t)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

    def test_get_expected_assigned(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)
        t_cat = TransactionCategory(
            name=self.random_string(),
            group=TransactionCategoryGroup.EXPENSE,
            locked=False,
            is_profit_loss=False,
            asset_linked=False,
            essential=False,
        )
        s.add(t_cat)
        s.commit()
        t_cat_id = t_cat.id_

        date = datetime.date(2024, 11, 12)

        # There are 5 months so need to add 2k each month
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("25e3"),
            type_=TargetType.BALANCE,
            period=TargetPeriod.ONCE,
            due_date_ord=datetime.date(2025, 3, 31).toordinal(),
            repeat_every=0,
        )
        result = t.get_expected_assigned(date, Decimal("15e3"))
        target = Decimal("2e3")
        self.assertEqual(result, target)

        # Target is end of month so need to add 10k more
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("25e3"),
            type_=TargetType.BALANCE,
            period=TargetPeriod.ONCE,
            due_date_ord=datetime.date(2024, 11, 30).toordinal(),
            repeat_every=0,
        )
        result = t.get_expected_assigned(date, Decimal("15e3"))
        target = Decimal("10e3")
        self.assertEqual(result, target)

        # Target is end of last month so need to add 10k more
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("25e3"),
            type_=TargetType.BALANCE,
            period=TargetPeriod.ONCE,
            due_date_ord=datetime.date(2024, 10, 31).toordinal(),
            repeat_every=0,
        )
        result = t.get_expected_assigned(date, Decimal("15e3"))
        target = Decimal("10e3")
        self.assertEqual(result, target)

        # Target is end of next month so need to add 5k more
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("25e3"),
            type_=TargetType.BALANCE,
            period=TargetPeriod.ONCE,
            due_date_ord=datetime.date(2024, 12, 31).toordinal(),
            repeat_every=0,
        )
        result = t.get_expected_assigned(date, Decimal("15e3"))
        target = Decimal("5e3")
        self.assertEqual(result, target)

        # Target has no due date so need to add 10k more
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("25e3"),
            type_=TargetType.BALANCE,
            period=TargetPeriod.ONCE,
            due_date_ord=None,
            repeat_every=0,
        )
        result = t.get_expected_assigned(date, Decimal("15e3"))
        target = Decimal("10e3")
        self.assertEqual(result, target)

        # Target is to ACCUMULATE 5k each month so always need 5k
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.ACCUMULATE,
            period=TargetPeriod.MONTH,
            due_date_ord=datetime.date(2023, 12, 1).toordinal(),
            repeat_every=6,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("2e3")
        self.assertEqual(result, target)

        # Target is due in a few days, need remaining
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.ACCUMULATE,
            period=TargetPeriod.MONTH,
            due_date_ord=datetime.date(2023, 11, 15).toordinal(),
            repeat_every=6,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("4e3")
        self.assertEqual(result, target)

        # Target was due a few days ago, need remaining
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.ACCUMULATE,
            period=TargetPeriod.MONTH,
            due_date_ord=datetime.date(2023, 11, 1).toordinal(),
            repeat_every=6,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("4e3")
        self.assertEqual(result, target)

        # Target was due a few days ago, need remaining
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.ACCUMULATE,
            period=TargetPeriod.MONTH,
            due_date_ord=datetime.date(2023, 11, 1).toordinal(),
            repeat_every=6,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("4e3")
        self.assertEqual(result, target)

        # Target is ACCUMULATE every month, need full amount always
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.ACCUMULATE,
            period=TargetPeriod.MONTH,
            due_date_ord=datetime.date(2023, 11, 1).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("5e3")
        self.assertEqual(result, target)

        # Target is ACCUMULATE every year, and ends this month
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.ACCUMULATE,
            period=TargetPeriod.YEAR,
            due_date_ord=datetime.date(2023, 11, 1).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("4e3")
        self.assertEqual(result, target)

        # Target is ACCUMULATE every year, and ended last month
        # So ignore balance
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.ACCUMULATE,
            period=TargetPeriod.YEAR,
            due_date_ord=datetime.date(2023, 10, 1).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("5e3") / 12
        self.assertEqual(result, target)

        # Target is REFILL every month, need deficient amount always
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.REFILL,
            period=TargetPeriod.MONTH,
            due_date_ord=datetime.date(2023, 11, 1).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("4e3")
        self.assertEqual(result, target)

        # Target is REFILL every year, and ends this month
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.REFILL,
            period=TargetPeriod.YEAR,
            due_date_ord=datetime.date(2023, 11, 1).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("4e3")
        self.assertEqual(result, target)

        # Target is REFILL every year, and ended last month
        # So include balance
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("5e3"),
            type_=TargetType.REFILL,
            period=TargetPeriod.YEAR,
            due_date_ord=datetime.date(2023, 10, 1).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("1e3"))
        target = Decimal("4e3") / 12
        self.assertEqual(result, target)

        # Target is ACCUMULATE every week due Friday
        # With 5 Fridays in November 2024, need 500
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("100"),
            type_=TargetType.ACCUMULATE,
            period=TargetPeriod.WEEK,
            due_date_ord=datetime.date(2024, 10, 4).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("50"))
        target = Decimal("500")
        self.assertEqual(result, target)

        # Target is ACCUMULATE every week due Sunday
        # With 4 Sundays in November 2024, need 400
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("100"),
            type_=TargetType.ACCUMULATE,
            period=TargetPeriod.WEEK,
            due_date_ord=datetime.date(2024, 10, 6).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("50"))
        target = Decimal("400")
        self.assertEqual(result, target)

        # Target is REFILL every week due Friday
        # With 5 Fridays in November 2024, need 450
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("100"),
            type_=TargetType.REFILL,
            period=TargetPeriod.WEEK,
            due_date_ord=datetime.date(2024, 10, 4).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("50"))
        target = Decimal("450")
        self.assertEqual(result, target)

        # Target is REFILL every week due Sunday
        # With 4 Sundays in November 2024, need 350
        t = Target(
            category_id=t_cat_id,
            amount=Decimal("100"),
            type_=TargetType.REFILL,
            period=TargetPeriod.WEEK,
            due_date_ord=datetime.date(2024, 10, 6).toordinal(),
            repeat_every=1,
        )
        result = t.get_expected_assigned(date, Decimal("50"))
        target = Decimal("350")
        self.assertEqual(result, target)
