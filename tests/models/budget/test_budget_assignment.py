from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus import utils
from nummus.models import (
    BudgetAssignment,
    BudgetAvailableCategory,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Account,
    )


def test_init_properties(
    month_ord: int,
    session: orm.Session,
    categories: dict[str, int],
    rand_real: Decimal,
) -> None:
    d = {
        "month_ord": month_ord,
        "amount": rand_real,
        "category_id": categories["uncategorized"],
    }

    b = BudgetAssignment(**d)
    session.add(b)
    session.commit()

    assert b.month_ord == d["month_ord"]
    assert b.amount == d["amount"]
    assert b.category_id == d["category_id"]


def test_duplicate_months(
    month_ord: int,
    session: orm.Session,
    categories: dict[str, int],
    rand_real: Decimal,
) -> None:
    b = BudgetAssignment(
        month_ord=month_ord,
        amount=rand_real,
        category_id=categories["uncategorized"],
    )
    session.add(b)
    b = BudgetAssignment(
        month_ord=month_ord,
        amount=rand_real,
        category_id=categories["uncategorized"],
    )
    session.add(b)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_get_monthly_available_empty(
    month: datetime.date,
    session: orm.Session,
    categories: dict[str, int],
) -> None:
    availables, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        session,
        month,
    )
    assert set(availables.keys()) == set(categories.values())
    non_zero = {k: v for k, v in availables.items() if any(vv != 0 for vv in v)}
    assert non_zero == {}
    assert assignable == 0
    assert future_assigned == 0


def test_get_monthly_available(
    month: datetime.date,
    session: orm.Session,
    categories: dict[str, int],
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    availables, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        session,
        month,
    )
    availables.pop(categories["other income"])
    target = BudgetAvailableCategory(
        Decimal(50),
        Decimal(-20),
        Decimal(30),
        Decimal(),
    )
    assert availables.pop(categories["groceries"]) == target
    target = BudgetAvailableCategory(
        Decimal(),
        Decimal(-50),
        Decimal(-50),
        Decimal(),
    )
    assert availables.pop(categories["rent"]) == target
    target = BudgetAvailableCategory(
        Decimal(100),
        Decimal(),
        Decimal(100),
        Decimal(),
    )
    assert availables.pop(categories["emergency fund"]) == target
    target = BudgetAvailableCategory(
        Decimal(),
        Decimal(-50),
        Decimal(-50),
        Decimal(),
    )
    assert availables.pop(categories["securities traded"]) == target
    # Remaining all zero
    non_zero = {k: v for k, v in availables.items() if any(vv != 0 for vv in v)}
    assert non_zero == {}
    assert assignable == Decimal(1170)
    assert future_assigned == Decimal(2000)


def test_get_monthly_available_next_month(
    month: datetime.date,
    session: orm.Session,
    categories: dict[str, int],
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    availables, assignable, future_assigned = BudgetAssignment.get_monthly_available(
        session,
        utils.date_add_months(month, 1),
    )
    availables.pop(categories["other income"])
    target = BudgetAvailableCategory(
        Decimal(),
        Decimal(),
        Decimal(30),
        Decimal(30),
    )
    assert availables.pop(categories["groceries"]) == target
    target = BudgetAvailableCategory(
        Decimal(2000),
        Decimal(),
        Decimal(2000),
        Decimal(),
    )
    assert availables.pop(categories["rent"]) == target
    target = BudgetAvailableCategory(
        Decimal(),
        Decimal(),
        Decimal(100),
        Decimal(100),
    )
    assert availables.pop(categories["emergency fund"]) == target
    # Remaining all zero
    non_zero = {k: v for k, v in availables.items() if any(vv != 0 for vv in v)}
    assert non_zero == {}
    assert assignable == Decimal(1200 - 30 - 2000 - 100)
    assert future_assigned == 0


def test_get_emergency_fund_empty(
    today_ord: int,
    session: orm.Session,
) -> None:
    start_ord = today_ord - 3
    end_ord = today_ord + 3

    n_lower = 20
    n_upper = 40
    result = BudgetAssignment.get_emergency_fund(
        session,
        start_ord,
        end_ord,
        n_lower,
        n_upper,
    )
    assert result.spending_lower == [Decimal()] * 7
    assert result.spending_upper == [Decimal()] * 7
    assert result.balances == [Decimal()] * 7
    assert result.categories == {}
    assert result.categories_total == {}


def test_get_emergency_fund(
    today: datetime.date,
    today_ord: int,
    session: orm.Session,
    account: Account,
    categories: dict[str, int],
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
    rand_str: str,
) -> None:
    session.query(TransactionCategory).where(
        TransactionCategory.name == "groceries",
    ).update({"essential_spending": True})
    # Add a transaction 30 days ago
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=30),
        amount=-50,
        statement=rand_str,
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        category_id=categories["groceries"],
    )
    session.add_all((txn, t_split))
    session.commit()

    _ = transactions_spending
    _ = budget_assignments
    start_ord = today_ord - 3
    end_ord = today_ord + 3

    n_smoothing = 15
    n_lower = 20
    n_upper = 40
    result = BudgetAssignment.get_emergency_fund(
        session,
        start_ord,
        end_ord,
        n_lower,
        n_upper,
    )

    n_target = 7 + n_lower + n_smoothing + 1
    target = [
        *([Decimal()] * 9),
        *([Decimal(50)] * n_lower),
        *([Decimal()] * (n_target - n_lower - 4 - 9)),
        *([Decimal(20)] * 4),
    ]
    assert len(target) == n_target
    target = utils.low_pass(target, n_smoothing)[-7:]
    assert result.spending_lower == target

    n_target = 7 + n_smoothing + 1
    target = [
        *([Decimal(50)] * (n_target - 4)),
        *([Decimal(70)] * 4),
    ]
    assert len(target) == n_target
    target = utils.low_pass(target, n_smoothing)[-7:]
    assert result.spending_upper == target

    assert result.balances[-1] == Decimal(100)

    target = {
        categories["groceries"]: ("groceries", "Groceries"),
    }
    assert result.categories == target
    target = {
        categories["groceries"]: Decimal(-20),
    }
    assert result.categories_total == target


def test_get_emergency_fund_balance(
    month_ord: int,
    session: orm.Session,
    budget_assignments: list[BudgetAssignment],
) -> None:
    _ = budget_assignments
    start_ord = month_ord - 3
    end_ord = month_ord + 3

    n_lower = 20
    n_upper = 40
    result = BudgetAssignment.get_emergency_fund(
        session,
        start_ord,
        end_ord,
        n_lower,
        n_upper,
    )
    target = [
        *([Decimal()] * 3),
        *([Decimal(100)] * 4),
    ]
    assert result.balances == target


def test_move_from_income(
    month_ord: int,
    session: orm.Session,
    categories: dict[str, int],
) -> None:
    src_cat_id = None
    dest_cat_id = categories["groceries"]
    BudgetAssignment.move(session, month_ord, src_cat_id, dest_cat_id, Decimal(100))
    session.commit()

    a = session.query(BudgetAssignment).one()
    assert a.category_id == dest_cat_id
    assert a.month_ord == month_ord
    assert a.amount == 100


@pytest.mark.parametrize(
    ("src", "dest", "to_move", "target_src", "target_dest"),
    [
        (None, "rent", Decimal(100), None, Decimal(100)),
        (None, "groceries", Decimal(100), None, Decimal(150)),
        ("groceries", None, Decimal(20), Decimal(30), None),
        ("groceries", None, Decimal(50), None, None),
        ("groceries", "rent", Decimal(20), Decimal(30), Decimal(20)),
        ("rent", "groceries", Decimal(20), Decimal(-20), Decimal(70)),
    ],
)
def test_move_to_income_partial(
    month_ord: int,
    session: orm.Session,
    categories: dict[str, int],
    budget_assignments: list[BudgetAssignment],
    src: str | None,
    dest: str | None,
    to_move: Decimal,
    target_src: Decimal | None,
    target_dest: Decimal | None,
) -> None:
    _ = budget_assignments
    src_cat_id = None if src is None else categories[src]
    dest_cat_id = None if dest is None else categories[dest]
    BudgetAssignment.move(session, month_ord, src_cat_id, dest_cat_id, to_move)
    session.commit()

    a = (
        session.query(BudgetAssignment)
        .where(
            BudgetAssignment.category_id == src_cat_id,
            BudgetAssignment.month_ord == month_ord,
        )
        .one_or_none()
    )
    if target_src is None:
        assert a is None
    else:
        assert a is not None
        assert a.month_ord == month_ord
        assert a.amount == target_src

    a = (
        session.query(BudgetAssignment)
        .where(
            BudgetAssignment.category_id == dest_cat_id,
            BudgetAssignment.month_ord == month_ord,
        )
        .one_or_none()
    )
    if target_dest is None:
        assert a is None
    else:
        assert a is not None
        assert a.month_ord == month_ord
        assert a.amount == target_dest
