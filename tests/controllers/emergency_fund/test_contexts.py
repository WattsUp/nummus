from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import utils
from nummus.controllers import emergency_fund
from nummus.models import (
    Transaction,
    TransactionCategory,
    TransactionSplit,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Account,
        BudgetAssignment,
    )


def test_empty(today: datetime.date, session: orm.Session) -> None:
    start = today - datetime.timedelta(days=utils.DAYS_IN_QUARTER * 2)
    dates = utils.range_date(start.toordinal(), today.toordinal())
    n = len(dates)

    ctx = emergency_fund.ctx_page(session, today)

    target: emergency_fund.EFundContext = {
        "chart": {
            "labels": [d.isoformat() for d in dates],
            "date_mode": "months",
            "balances": [Decimal(0)] * n,
            "spending_lower": [Decimal(0)] * n,
            "spending_upper": [Decimal(0)] * n,
        },
        "current": Decimal(),
        "target_lower": Decimal(),
        "target_upper": Decimal(),
        "days": None,
        "delta_lower": Decimal(),
        "delta_upper": Decimal(),
        "categories": [],
    }
    assert ctx == target


def test_ctx_underfunded(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    categories: dict[str, int],
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
    rand_str: str,
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    session.query(TransactionCategory).where(
        TransactionCategory.name == "groceries",
    ).update({"essential_spending": True})
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=100),
        amount=-1000,
        statement=rand_str,
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        category_id=categories["groceries"],
    )
    session.add_all((txn, t_split))
    session.commit()

    ctx = emergency_fund.ctx_page(session, today)

    assert ctx["current"] == Decimal(100)
    assert ctx["days"] == pytest.approx(Decimal(34), abs=Decimal(1))
    assert ctx["target_upper"] > ctx["target_lower"]
    assert ctx["delta_upper"] < 0
    assert ctx["delta_lower"] > 0
    ctx_categories = ctx["categories"]
    assert len(ctx_categories) == 1
    assert ctx_categories[0]["emoji_name"] == "Groceries"
    assert ctx_categories[0]["name"] == "groceries"
    assert ctx_categories[0]["monthly"] == pytest.approx(Decimal(170), abs=Decimal(2))


def test_ctx_overfunded(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    categories: dict[str, int],
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
    rand_str: str,
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    session.query(TransactionCategory).where(
        TransactionCategory.name == "groceries",
    ).update({"essential_spending": True})
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=100),
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

    ctx = emergency_fund.ctx_page(session, today)

    assert ctx["current"] == Decimal(100)
    assert ctx["days"] == pytest.approx(Decimal(347), abs=Decimal(1))
    assert ctx["target_upper"] > ctx["target_lower"]
    assert ctx["delta_upper"] > 0
    assert ctx["delta_lower"] < 0
    ctx_categories = ctx["categories"]
    assert len(ctx_categories) == 1
    assert ctx_categories[0]["emoji_name"] == "Groceries"
    assert ctx_categories[0]["name"] == "groceries"
    assert ctx_categories[0]["monthly"] == pytest.approx(Decimal(11), abs=Decimal(1))


def test_ctx(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    categories: dict[str, int],
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
    rand_str: str,
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    session.query(TransactionCategory).where(
        TransactionCategory.name == "groceries",
    ).update({"essential_spending": True})
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=100),
        amount=-200,
        statement=rand_str,
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        category_id=categories["groceries"],
    )
    session.add_all((txn, t_split))
    session.commit()

    ctx = emergency_fund.ctx_page(session, today)

    assert ctx["current"] == Decimal(100)
    assert ctx["days"] == pytest.approx(Decimal(119), abs=Decimal(1))
    assert ctx["target_upper"] > ctx["target_lower"]
    assert ctx["delta_upper"] < 0
    assert ctx["delta_lower"] < 0
    ctx_categories = ctx["categories"]
    assert len(ctx_categories) == 1
    assert ctx_categories[0]["emoji_name"] == "Groceries"
    assert ctx_categories[0]["name"] == "groceries"
    assert ctx_categories[0]["monthly"] == pytest.approx(Decimal(37), abs=Decimal(1))
