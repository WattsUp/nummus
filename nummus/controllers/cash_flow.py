"""Cash Flow controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import flask
import sqlalchemy
from sqlalchemy import orm

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
        incomes_categorized: list[t.DictAny] = []
        expenses_categorized: list[t.DictAny] = []
        total_income = Decimal(0)
        total_expense = Decimal(0)
        for cat_id, amount in query.all():
            cat_id: int
            amount: t.Real
            if cat_id in categories_incomes:
                incomes_categorized.append(
                    {
                        "name": categories_incomes[cat_id],
                        "amount": amount,
                    },
                )
                total_income += amount
            elif cat_id in categories_expenses:
                expenses_categorized.append(
                    {
                        "name": categories_expenses[cat_id],
                        "amount": amount,
                    },
                )
                total_expense += amount

        # For the timeseries,
        # If n > 400, sum by years and make bars
        # elif n > 80, sum by months and make bars
        # else make daily
        # TODO (WattsUp): Add a previous dailys when period is months
        labels: t.Strings = []
        incomes: t.Reals = []
        expenses: t.Reals = []
        chart_bars = False

        periods: dict[str, tuple[int, int]] | None = None
        if n > web_utils.LIMIT_PLOT_YEARS:
            # Sum for each year in period
            periods = utils.period_years(start_ord, end_ord)

        elif n > web_utils.LIMIT_PLOT_MONTHS:
            periods = utils.period_months(start_ord, end_ord)
        else:
            # Daily amounts
            labels = [date.isoformat() for date in utils.range_date(start_ord, end_ord)]
            cash_flow = Account.get_cash_flow_all(s, start_ord, end_ord, ids=ids)
            incomes_daily: t.Reals = [Decimal(0)] * n
            expenses_daily: t.Reals = [Decimal(0)] * n
            for cat_id, dailys in cash_flow.items():
                add_to: t.Reals | None = None
                if cat_id in categories_incomes:
                    add_to = incomes_daily
                elif cat_id in categories_expenses:
                    add_to = expenses_daily
                else:
                    continue
                for i, amount in enumerate(dailys):
                    add_to[i] += amount
            incomes = utils.integrate(incomes_daily)
            expenses = utils.integrate(expenses_daily)

        if periods is not None:
            chart_bars = True
            for label, limits in periods.items():
                labels.append(label)
                i, e = sum_income_expenses(
                    s,
                    limits[0],
                    limits[1],
                    ids,
                    set(categories_incomes),
                    set(categories_expenses),
                )
                incomes.append(i)
                expenses.append(e)

        totals = [i + e for i, e in zip(incomes, expenses, strict=True)]

    return {
        "start": start,
        "end": end,
        "period": period,
        "data": {
            "total_income": total_income,
            "total_expense": total_expense,
            "incomes_categorized": incomes_categorized,
            "expenses_categorized": expenses_categorized,
            "chart_bars": chart_bars,
            "labels": labels,
            "totals": totals,
            "incomes": incomes,
            "expenses": expenses,
        },
        "category": category,
        "category_type": AccountCategory,
    }


def sum_income_expenses(
    s: orm.Session,
    start_ord: int,
    end_ord: int,
    ids: t.Ints | set[int],
    categories_incomes: set[int],
    categories_expenses: set[int],
) -> tuple[t.Real, t.Real]:
    """Sum income and expenses from start to end.

    Args:
        s: SQL session to use
        start_ord: First date ordinal to evaluate
        end_ord: Last date ordinal to evaluate (inclusive)
        ids: Limit results to specific Accounts by ID
        categories_incomes: Set of TransactionCategory.id_ for incomes
        categories_expenses: Set of TransactionCategory.id_ for expenses

    Returns:
        income, expenses
    """
    income = Decimal(0)
    expenses = Decimal(0)

    query = s.query(TransactionSplit)
    query = query.with_entities(
        TransactionSplit.category_id,
        sqlalchemy.func.sum(TransactionSplit.amount),
    )
    query = query.where(TransactionSplit.account_id.in_(ids))
    query = query.where(TransactionSplit.date_ord >= start_ord)
    query = query.where(TransactionSplit.date_ord <= end_ord)
    query = query.group_by(TransactionSplit.category_id)
    for cat_id, amount in query.all():
        if cat_id in categories_incomes:
            income += amount
        elif cat_id in categories_expenses:
            expenses += amount

    return income, expenses


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
