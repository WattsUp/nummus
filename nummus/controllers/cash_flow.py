"""Cash Flow controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import flask
import sqlalchemy

from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import (
    Account,
    AccountCategory,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)

if TYPE_CHECKING:
    from nummus import custom_types as t

DEFAULT_PERIOD = "90-days"


def ctx_chart() -> t.DictAny:
    """Get the context to build the net worth chart.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(
        period,
        args.get("start", type=datetime.date.fromisoformat),
        args.get("end", type=datetime.date.fromisoformat),
    )
    category = args.get("category", None, type=AccountCategory)

    with p.get_session() as s:
        if start is None:
            query = s.query(TransactionSplit)
            query = query.where(TransactionSplit.asset_id.is_(None))
            query = query.with_entities(sqlalchemy.func.min(TransactionSplit.date_ord))
            start_ord = query.scalar()
            start = (
                datetime.date.fromordinal(start_ord)
                if start_ord
                else datetime.date(1970, 1, 1)
            )
        start_ord = start.toordinal()
        end_ord = end.toordinal()
        n = end_ord - start_ord + 1

        query = s.query(Account)
        if category is not None:
            query = query.where(Account.category == category)
        # Include account if not closed
        # Include account if most recent transaction is in period
        ids = [
            acct.id_
            for acct in query.all()
            if (not acct.closed or acct.updated_on_ord > start_ord)
        ]

        # Categorize whole period
        query = s.query(TransactionCategory)
        query = query.with_entities(
            TransactionCategory.id_,
            TransactionCategory.name,
            TransactionCategory.group,
        )
        categories_incomes: t.DictIntStr = {}
        categories_expenses: t.DictIntStr = {}
        for cat_id, name, group in query.all():
            if group == TransactionCategoryGroup.INCOME:
                categories_incomes[cat_id] = name
            elif group == TransactionCategoryGroup.EXPENSE:
                categories_expenses[cat_id] = name

        query = s.query(TransactionSplit)
        query = query.with_entities(
            TransactionSplit.category_id,
            sqlalchemy.func.sum(TransactionSplit.amount),
        )
        query = query.where(TransactionSplit.account_id.in_(ids))
        query = query.where(TransactionSplit.date_ord >= start_ord)
        query = query.where(TransactionSplit.date_ord <= end_ord)
        query = query.group_by(TransactionSplit.category_id)
        incomes: list[t.DictAny] = []
        expenses: list[t.DictAny] = []
        total_income = Decimal(0)
        total_expense = Decimal(0)
        for cat_id, amount in query.all():
            cat_id: int
            amount: t.Real
            if cat_id in categories_incomes:
                incomes.append(
                    {
                        "name": categories_incomes[cat_id],
                        "amount": amount,
                    },
                )
                total_income += amount
            elif cat_id in categories_expenses:
                expenses.append(
                    {
                        "name": categories_expenses[cat_id],
                        "amount": -amount,  # Flip the sign
                    },
                )
                total_expense += amount
        data: t.DictAny = {
            "total_income": total_income,
            "total_expense": -total_expense,  # Flip the sign
            "incomes_categorized": sorted(incomes, key=lambda item: -item["amount"]),
            "expenses_categorized": sorted(expenses, key=lambda item: -item["amount"]),
        }

        # For the timeseries,
        # If n > 400, sum by years and make bars
        # elif n > 80, sum by months and make bars
        # else make daily; and if period = this month or last month include previous
        # period

        data["dates"] = [d.isoformat() for d in utils.range_date(start_ord, end_ord)]
        data["total"] = [Decimal(0)] * n

    return {
        "start": start,
        "end": end,
        "period": period,
        "data": data,
        "category": category,
        "category_type": AccountCategory,
    }


def page() -> str:
    """GET /cash-flow.

    Returns:
        string HTML response
    """
    return common.page(
        "cash-flow/index-content.jinja",
        chart=ctx_chart(),
    )


def chart() -> str:
    """GET /h/cash-flow/chart.

    Returns:
        string HTML response
    """
    return flask.render_template(
        "cash-flow/chart-data.jinja",
        chart=ctx_chart(),
        include_oob=True,
    )


def dashboard() -> str:
    """GET /h/dashboard/cash-flow.

    Returns:
        string HTML response
    """
    raise NotImplementedError
    return flask.render_template(
        "cash-flow/dashboard.jinja",
    )


ROUTES: t.Routes = {
    "/cash-flow": (page, ["GET"]),
    "/h/cash-flow/chart": (chart, ["GET"]),
    "/h/dashboard/cash-flow": (dashboard, ["GET"]),
}
