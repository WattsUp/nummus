from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from nummus.controllers import base, net_worth
from nummus.models import (
    Transaction,
    TransactionSplit,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Account,
        AssetValuation,
    )
    from tests.conftest import RandomStringGenerator


def test_ctx_chart_empty(
    today: datetime.date,
    account: Account,
    session: orm.Session,
) -> None:
    _ = account
    ctx = net_worth.ctx_chart(session, today, "max")

    chart: base.ChartData = {
        "labels": [today.isoformat()],
        "mode": "days",
        "avg": [Decimal()],
        "min": None,
        "max": None,
    }

    target: net_worth.Context = {
        "start": today,
        "end": today,
        "period": "max",
        "period_options": base.PERIOD_OPTIONS,
        "chart": chart,
        "accounts": [],
        "net_worth": Decimal(),
        "assets": Decimal(),
        "liabilities": Decimal(),
        "assets_w": Decimal(),
        "liabilities_w": Decimal(),
    }
    assert ctx == target


def test_ctx_chart_this_year(
    today: datetime.date,
    session: orm.Session,
) -> None:
    ctx = net_worth.ctx_chart(session, today, "ytd")

    assert ctx["start"] == today.replace(month=1, day=1)
    assert ctx["end"] == today


def test_ctx_chart(
    today: datetime.date,
    rand_str_generator: RandomStringGenerator,
    account: Account,
    account_investments: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
    session: orm.Session,
    categories: dict[str, int],
) -> None:
    _ = asset_valuation
    _ = transactions
    # Make account_investments negative
    txn = Transaction(
        account_id=account_investments.id_,
        date=today,
        amount=-100,
        statement=rand_str_generator(),
        payee="Monkey Bank",
        cleared=True,
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        category_id=categories["groceries"],
    )
    session.add_all((txn, t_split))
    session.commit()

    start = today - datetime.timedelta(days=3)
    end = today + datetime.timedelta(days=3)
    ctx = net_worth.ctx_chart(session, end, "max")

    chart: base.ChartData = {
        "labels": base.date_labels(start.toordinal(), end.toordinal())[0],
        "mode": "days",
        "avg": [
            Decimal(100),
            Decimal(90),
            Decimal(90),
            Decimal(10),
            Decimal(50),
            Decimal(50),
            Decimal(50),
        ],
        "min": None,
        "max": None,
    }

    accounts: list[net_worth.AccountContext] = [
        {
            "name": account.name,
            "uri": account.uri,
            "avg": [
                Decimal(100),
                Decimal(90),
                Decimal(90),
                Decimal(110),
                Decimal(150),
                Decimal(150),
                Decimal(150),
            ],
            "min": None,
            "max": None,
        },
        {
            "name": account_investments.name,
            "uri": account_investments.uri,
            "avg": [
                Decimal(),
                Decimal(),
                Decimal(),
                Decimal(-100),
                Decimal(-100),
                Decimal(-100),
                Decimal(-100),
            ],
            "min": None,
            "max": None,
        },
    ]

    target: net_worth.Context = {
        "start": start,
        "end": end,
        "period": "max",
        "period_options": base.PERIOD_OPTIONS,
        "chart": chart,
        "accounts": accounts,
        "net_worth": Decimal(50),
        "assets": Decimal(150),
        "liabilities": Decimal(-100),
        "assets_w": Decimal(60),
        "liabilities_w": Decimal(40),
    }
    assert ctx == target
