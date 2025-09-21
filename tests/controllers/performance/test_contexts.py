from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from nummus.controllers import base, performance
from nummus.models import (
    AccountCategory,
    Asset,
    AssetCategory,
    YIELD_PER,
)

if TYPE_CHECKING:

    from sqlalchemy import orm

    from nummus.models import (
        Account,
        AssetValuation,
        Transaction,
    )


def test_ctx_chart_empty(
    today: datetime.date,
    account: Account,
    session: orm.Session,
) -> None:
    _ = account
    ctx = performance.ctx_chart(session, today, "max", "S&P 500", set())

    chart: performance.ChartData = {
        "labels": [today.isoformat()],
        "mode": "days",
        "avg": [Decimal()],
        "min": None,
        "max": None,
        "index": [Decimal()],
        "index_name": "S&P 500",
        "index_min": None,
        "index_max": None,
        "mwrr": [Decimal()],
    }

    accounts: performance.AccountsContext = {
        "initial": Decimal(),
        "end": Decimal(),
        "cash_flow": Decimal(),
        "pnl": Decimal(),
        "mwrr": Decimal(),
        "accounts": [],
        "options": [],
    }

    query = session.query(Asset.name).order_by(Asset.name)
    indices: list[str] = [r[0] for r in query.yield_per(YIELD_PER)]

    desc = session.query(Asset.description).where(Asset.name == "S&P 500").one()[0]

    target: performance.Context = {
        "start": today,
        "end": today,
        "period": "max",
        "period_options": base.PERIOD_OPTIONS,
        "chart": chart,
        "accounts": accounts,
        "index": "S&P 500",
        "indices": indices,
        "index_description": desc,
    }
    assert ctx == target


def test_ctx_chart_this_year(
    today: datetime.date,
    session: orm.Session,
    account: Account,
) -> None:
    account.category = AccountCategory.INVESTMENT
    account.closed = True
    session.commit()

    ctx = performance.ctx_chart(session, today, "ytd", "S&P 500", set())

    assert ctx["start"] == today.replace(month=1, day=1)
    assert ctx["end"] == today
    assert ctx["accounts"]["accounts"] == []


def test_ctx_chart(
    today: datetime.date,
    account: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
    session: orm.Session,
) -> None:
    account.category = AccountCategory.INVESTMENT
    session.commit()
    _ = asset_valuation
    _ = transactions

    start = today - datetime.timedelta(days=3)
    end = today + datetime.timedelta(days=3)
    ctx = performance.ctx_chart(session, end, "max", "S&P 500", set())

    chart: performance.ChartData = {
        "labels": base.date_labels(start.toordinal(), end.toordinal())[0],
        "mode": "days",
        "avg": [
            Decimal(),
            Decimal("-0.1"),
            Decimal("-0.1"),
            Decimal("0.1"),
            Decimal("0.5"),
            Decimal("0.5"),
            Decimal("0.5"),
        ],
        "min": None,
        "max": None,
        "index": [Decimal()] * 7,
        "index_name": "S&P 500",
        "index_min": None,
        "index_max": None,
        "mwrr": None,
    }

    accounts: performance.AccountsContext = {
        "initial": Decimal(100),
        "end": Decimal(150),
        "cash_flow": Decimal(),
        "pnl": Decimal(50),
        "mwrr": None,
        "accounts": [
            {
                "name": account.name,
                "uri": account.uri,
                "initial": Decimal(100),
                "end": Decimal(150),
                "pnl": Decimal(50),
                "cash_flow": Decimal(),
                "mwrr": None,
            },
        ],
        "options": [
            base.NamePairState(account.name, account.uri, state=False),
        ],
    }

    query = (
        session.query(Asset.name)
        .where(Asset.category == AssetCategory.INDEX)
        .order_by(Asset.name)
    )
    indices: list[str] = [r[0] for r in query.yield_per(YIELD_PER)]

    desc = session.query(Asset.description).where(Asset.name == "S&P 500").one()[0]

    target: performance.Context = {
        "start": start,
        "end": end,
        "period": "max",
        "period_options": base.PERIOD_OPTIONS,
        "chart": chart,
        "accounts": accounts,
        "index": "S&P 500",
        "indices": indices,
        "index_description": desc,
    }
    assert ctx == target


def test_ctx_chart_exclude(
    today: datetime.date,
    account: Account,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
    session: orm.Session,
) -> None:
    account.category = AccountCategory.INVESTMENT
    session.commit()
    _ = asset_valuation
    _ = transactions

    start = today - datetime.timedelta(days=3)
    end = today + datetime.timedelta(days=3)
    ctx = performance.ctx_chart(session, end, "max", "S&P 500", {account.id_})

    chart: performance.ChartData = {
        "labels": base.date_labels(start.toordinal(), end.toordinal())[0],
        "mode": "days",
        "avg": [Decimal()] * 7,
        "min": None,
        "max": None,
        "index": [Decimal()] * 7,
        "index_name": "S&P 500",
        "index_min": None,
        "index_max": None,
        "mwrr": [Decimal()] * 7,
    }

    accounts: performance.AccountsContext = {
        "initial": Decimal(),
        "end": Decimal(),
        "cash_flow": Decimal(),
        "pnl": Decimal(),
        "mwrr": Decimal(),
        "accounts": [],
        "options": [
            base.NamePairState(account.name, account.uri, state=True),
        ],
    }

    query = (
        session.query(Asset.name)
        .where(Asset.category == AssetCategory.INDEX)
        .order_by(Asset.name)
    )
    indices: list[str] = [r[0] for r in query.yield_per(YIELD_PER)]

    desc = session.query(Asset.description).where(Asset.name == "S&P 500").one()[0]

    target: performance.Context = {
        "start": start,
        "end": end,
        "period": "max",
        "period_options": base.PERIOD_OPTIONS,
        "chart": chart,
        "accounts": accounts,
        "index": "S&P 500",
        "indices": indices,
        "index_description": desc,
    }
    assert ctx == target
