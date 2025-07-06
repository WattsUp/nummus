from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

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


@pytest.mark.xfail
def test_init_properties() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    t_cat = TransactionCategory(
        emoji_name="Securities Traded",
        group=TransactionCategoryGroup.OTHER,
        locked=False,
        is_profit_loss=False,
        asset_linked=True,
        essential=False,
    )
    s.add(t_cat)
    s.commit()
    t_cat_id = t_cat.id_

    today = datetime.datetime.now().astimezone().date()
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

    assert b.month_ord == d["month_ord"]
    assert b.amount == d["amount"]
    assert b.category_id == d["category_id"]

    # Duplicate dates are bad
    b = BudgetAssignment(month_ord=month_ord, amount=0, category_id=t_cat_id)
    s.add(b)
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()


@pytest.mark.xfail
def test_get_monthly_available() -> None:
    s = self.get_session()
    models.metadata_create_all(s)
    TransactionCategory.add_default(s)
    names = TransactionCategory.map_name(s)
    names_rev = {v: k for k, v in names.items()}

    today = datetime.datetime.now().astimezone().date()
    month = utils.start_of_month(today)
    month_ord = month.toordinal()
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month,
    )
    assert categories.keys() == names.keys()
    non_zero = {k: v for k, v in categories.items() if any(vv != 0 for vv in v)}
    assert non_zero == {}
    assert assignable == 0
    assert future_assigned == 0

    acct = Account(
        name=self.random_string(),
        institution=self.random_string(),
        category=AccountCategory.INVESTMENT,
        closed=False,
        budgeted=False,
    )
    s.add(acct)
    s.commit()

    t_cat_id = names_rev["general merchandise"]
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
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month,
    )
    non_zero = {k: v for k, v in categories.items() if any(vv != 0 for vv in v)}
    assert non_zero == {}
    assert assignable == 0
    assert future_assigned == 0

    # Show up with a budgeted account
    acct.budgeted = True
    s.commit()

    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(0), Decimal(-10), Decimal(-10), Decimal(0)),
    )
    assert assignable == 0
    assert future_assigned == 0

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
        category_id=names_rev["other income"],
    )
    s.add_all((txn, t_split))
    s.commit()
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(0), Decimal(-10), Decimal(-10), Decimal(0)),
    )
    self.assertEqual(
        categories[names_rev["other income"]],
        (Decimal(0), Decimal(100), Decimal(0), Decimal(0)),
    )
    assert assignable == Decimal(100)
    assert future_assigned == 0

    # Add assignment
    a = BudgetAssignment(
        month_ord=month_ord,
        amount=Decimal(10),
        category_id=t_cat_id,
    )
    s.add(a)
    s.commit()
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(10), Decimal(-10), Decimal(0), Decimal(0)),
    )
    assert assignable == Decimal(90)
    assert future_assigned == 0

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
        category_id=names_rev["other income"],
    )
    s.add_all((txn, t_split))
    s.commit()
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(10), Decimal(-10), Decimal(10), Decimal(10)),
    )
    assert assignable == Decimal(180)
    assert future_assigned == 0
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month_last,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(10), Decimal(0), Decimal(10), Decimal(0)),
    )
    assert assignable == Decimal(80)
    assert future_assigned == Decimal(10)

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
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(10), Decimal(-10), Decimal(5), Decimal(5)),
    )
    assert assignable == Decimal(180)
    assert future_assigned == 0

    # Remove prior assignment
    a.amount = Decimal(0)
    s.commit()
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(10), Decimal(-10), Decimal(0), Decimal(0)),
    )
    assert assignable == Decimal(185)
    assert future_assigned == 0

    # Increase funding
    a.amount = Decimal(90)
    s.commit()
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month_last,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(90), Decimal(-5), Decimal(85), Decimal(0)),
    )
    assert assignable == Decimal(0)
    assert future_assigned == Decimal(10)

    # Increase funding
    a.amount = Decimal(150)
    s.commit()
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month_last,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(150), Decimal(-5), Decimal(145), Decimal(0)),
    )
    assert assignable == Decimal(-50)
    assert future_assigned == Decimal(0)

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
    categories, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        s,
        month,
    )
    self.assertEqual(
        categories[t_cat_id],
        (Decimal(10), Decimal(-195), Decimal(-40), Decimal(145)),
    )
    assert assignable == Decimal(40)
    assert future_assigned == 0


@pytest.mark.xfail
def test_get_emergency_fund() -> None:
    s = self.get_session()
    models.metadata_create_all(s)
    TransactionCategory.add_default(s)
    categories = TransactionCategory.map_name(s)
    # Reverse categories for LUT
    categories = {v: k for k, v in categories.items()}

    today = datetime.datetime.now().astimezone().date()
    month = utils.start_of_month(today)
    month_ord = month.toordinal()
    end_ord = month_ord + 1
    start_ord = month_ord - 8

    n_smoothing = 15
    n_lower = 20
    n_upper = 40

    # Empty if fine
    r_lowers, r_uppers, r_balances, r_categories, r_categories_total = (
        BudgetAssignment.get_emergency_fund(s, start_ord, end_ord, n_lower, n_upper)
    )
    assert r_lowers == [Decimal(0)] * 10
    assert r_uppers == [Decimal(0)] * 10
    assert r_balances == [Decimal(0)] * 10
    assert r_categories == {}
    assert r_categories_total == {}

    # Prepare portfolio
    acct = Account(
        name="Monkey Bank Checking",
        institution="Monkey Bank",
        category=AccountCategory.CASH,
        closed=False,
        budgeted=True,
    )
    s.add(acct)
    b = BudgetAssignment(
        category_id=TransactionCategory.emergency_fund(s)[0],
        month_ord=month_ord,
        amount=10,
    )
    s.add(b)
    s.commit()

    # Mark groceries as essential
    s.query(TransactionCategory).where(
        TransactionCategory.name == "groceries",
    ).update({"essential": True})

    # Add spending
    txn = Transaction(
        account_id=acct.id_,
        date=month,
        amount=-100,
        statement=self.random_string(),
    )
    t_split = TransactionSplit(
        amount=txn.amount,
        parent=txn,
        category_id=categories["groceries"],
    )
    s.add_all((txn, t_split))

    # Add spending >3 months ago
    txn = Transaction(
        account_id=acct.id_,
        date=month - datetime.timedelta(days=30),
        amount=-100,
        statement=self.random_string(),
    )
    t_split = TransactionSplit(
        amount=txn.amount,
        parent=txn,
        category_id=categories["groceries"],
    )
    s.add_all((txn, t_split))

    # Add spending >3 months ago
    txn = Transaction(
        account_id=acct.id_,
        date=month - datetime.timedelta(days=300),
        amount=-100,
        statement=self.random_string(),
    )
    t_split = TransactionSplit(
        amount=txn.amount,
        parent=txn,
        category_id=categories["groceries"],
    )
    s.add_all((txn, t_split))

    s.commit()

    r_lowers, r_uppers, r_balances, r_categories, r_categories_total = (
        BudgetAssignment.get_emergency_fund(s, start_ord, end_ord, n_lower, n_upper)
    )
    n_target = 10 + n_lower + n_smoothing + 1
    target = [
        *([Decimal(0)] * 14),
        *([Decimal(100)] * n_lower),
        *([Decimal(0)] * (n_target - n_lower - 2 - 14)),
        *([Decimal(100)] * 2),
    ]
    target = utils.low_pass(target, n_smoothing)[-10:]
    assert r_lowers == target
    n_target = 10 + n_smoothing + 1
    target = [
        *([Decimal(100)] * (n_target - 2)),
        *([Decimal(200)] * 2),
    ]
    target = utils.low_pass(target, n_smoothing)[-10:]
    assert r_uppers == target
    target = [Decimal(0)] * 8 + [Decimal(10), Decimal(10)]
    assert r_balances == target
    target = {
        categories["groceries"]: ("groceries", "Groceries"),
    }
    assert r_categories == target
    target = {
        categories["groceries"]: Decimal(-100),
    }
    assert r_categories_total == target


@pytest.mark.xfail
def test_budget() -> None:
    s = self.get_session()
    models.metadata_create_all(s)
    TransactionCategory.add_default(s)
    categories = TransactionCategory.map_name(s)
    # Reverse categories for LUT
    categories = {v: k for k, v in categories.items()}

    today = datetime.datetime.now().astimezone().date()
    month = utils.start_of_month(today)
    month_ord = month.toordinal()

    src_cat_id = None
    dest_cat_id = categories["groceries"]
    BudgetAssignment.move(s, month_ord, src_cat_id, dest_cat_id, Decimal(100))
    s.commit()

    a = s.query(BudgetAssignment).one()
    assert a.category_id == dest_cat_id
    assert a.month_ord == month_ord
    assert a.amount == 100

    src_cat_id = None
    dest_cat_id = categories["groceries"]
    BudgetAssignment.move(s, month_ord, src_cat_id, dest_cat_id, Decimal(100))
    s.commit()

    a = s.query(BudgetAssignment).one()
    assert a.category_id == dest_cat_id
    assert a.month_ord == month_ord
    assert a.amount == 200

    src_cat_id = categories["groceries"]
    dest_cat_id = None
    BudgetAssignment.move(s, month_ord, src_cat_id, dest_cat_id, Decimal(100))
    s.commit()

    a = s.query(BudgetAssignment).one()
    assert a.category_id == src_cat_id
    assert a.month_ord == month_ord
    assert a.amount == 100

    src_cat_id = categories["groceries"]
    dest_cat_id = None
    BudgetAssignment.move(s, month_ord, src_cat_id, dest_cat_id, Decimal(100))
    s.commit()

    a = s.query(BudgetAssignment).one_or_none()
    self.assertIsNone(a)

    src_cat_id = categories["groceries"]
    dest_cat_id = None
    BudgetAssignment.move(s, month_ord, src_cat_id, dest_cat_id, Decimal(100))
    s.commit()

    a = s.query(BudgetAssignment).one()
    assert a.category_id == src_cat_id
    assert a.month_ord == month_ord
    assert a.amount == -100
