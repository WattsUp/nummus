"""Cash Flow controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func, orm

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common, transactions
from nummus.models import (
    Account,
    AccountCategory,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from nummus.controllers.base import Routes

DEFAULT_PERIOD = "1-year"
PREVIOUS_PERIOD: dict[str, datetime.date | None] = {"start": None, "end": None}


def ctx_chart() -> dict[str, object]:
    """Get the context to build the cash flow chart.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))

    with p.begin_session() as s:
        if start is None:
            query = s.query(TransactionSplit)
            query = query.where(TransactionSplit.asset_id.is_(None))
            query = query.with_entities(func.min(TransactionSplit.date_ord))
            start_ord = query.scalar()
            start = (
                datetime.date.fromordinal(start_ord)
                if start_ord
                else datetime.date(1970, 1, 1)
            )
        PREVIOUS_PERIOD["start"] = start
        PREVIOUS_PERIOD["end"] = end
        start_ord = start.toordinal()
        end_ord = end.toordinal()
        n = end_ord - start_ord + 1

        query = s.query(Account)

        # Include account if not closed
        # Include account if most recent transaction is in period
        def include_account(acct: Account) -> bool:
            if not acct.closed:
                return True
            updated_on_ord = acct.updated_on_ord
            return updated_on_ord is not None and updated_on_ord >= start_ord

        ids = [acct.id_ for acct in query.all() if include_account(acct)]

        # Categorize whole period
        query = s.query(TransactionCategory).with_entities(
            TransactionCategory.id_,
            TransactionCategory.name,
            TransactionCategory.emoji_name,
            TransactionCategory.group,
        )
        categories_income: dict[int, tuple[str, str]] = {}
        categories_expense: dict[int, tuple[str, str]] = {}
        for cat_id, name, emoji_name, group in query.all():
            if group == TransactionCategoryGroup.INCOME:
                categories_income[cat_id] = name, emoji_name
            elif group == TransactionCategoryGroup.EXPENSE:
                categories_expense[cat_id] = name, emoji_name

        class CategoryContext(TypedDict):
            """Type definition for category context."""

            name: str
            emoji_name: str
            amount: Decimal

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.category_id,
                func.sum(TransactionSplit.amount),
            )
            .where(
                TransactionSplit.account_id.in_(ids),
                TransactionSplit.date_ord >= start_ord,
                TransactionSplit.date_ord <= end_ord,
            )
            .group_by(TransactionSplit.category_id)
        )
        income_categorized: list[CategoryContext] = []
        expense_categorized: list[CategoryContext] = []
        total_income = Decimal(0)
        total_expense = Decimal(0)
        for cat_id, amount in query.yield_per(YIELD_PER):
            cat_id: int
            amount: Decimal
            if cat_id in categories_income:
                income_categorized.append(
                    {
                        "name": categories_income[cat_id][0],
                        "emoji_name": categories_income[cat_id][1],
                        "amount": amount,
                    },
                )
                total_income += amount
            elif cat_id in categories_expense:
                expense_categorized.append(
                    {
                        "name": categories_expense[cat_id][0],
                        "emoji_name": categories_expense[cat_id][1],
                        "amount": amount,
                    },
                )
                total_expense += amount
        income_categorized = sorted(
            income_categorized,
            key=lambda item: -item["amount"],
        )
        expense_categorized = sorted(
            expense_categorized,
            key=lambda item: item["amount"],
        )

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.tag,
                func.sum(TransactionSplit.amount),
            )
            .where(
                TransactionSplit.account_id.in_(ids),
                TransactionSplit.date_ord >= start_ord,
                TransactionSplit.date_ord <= end_ord,
                TransactionSplit.tag.is_not(None),
            )
            .group_by(TransactionSplit.tag)
        )
        income_tagged: list[CategoryContext] = []
        expense_tagged: list[CategoryContext] = []
        for tag, amount in query.yield_per(YIELD_PER):
            tag: str
            if amount > 0:
                income_tagged.append(
                    {
                        "name": tag,
                        "emoji_name": tag,
                        "amount": amount,
                    },
                )
            else:
                expense_tagged.append(
                    {
                        "name": tag,
                        "emoji_name": tag,
                        "amount": amount,
                    },
                )
        income_tagged = sorted(
            income_tagged,
            key=lambda item: -item["amount"],
        )
        expense_tagged = sorted(
            expense_tagged,
            key=lambda item: item["amount"],
        )

        # For the timeseries,
        # If n > 400, sum by years and make bars
        # elif n > 80, sum by months and make bars
        # else make daily
        labels: list[str] = []
        date_mode: str | None = None
        incomes: list[Decimal] = []
        expenses: list[Decimal] = []
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
            if n > web_utils.LIMIT_TICKS_MONTHS:
                date_mode = "months"
            elif n > web_utils.LIMIT_TICKS_WEEKS:
                date_mode = "weeks"
            else:
                date_mode = "days"

            cash_flow = Account.get_cash_flow_all(s, start_ord, end_ord, ids=ids)
            daily_income: list[Decimal] = [Decimal(0)] * n
            daily_expense: list[Decimal] = [Decimal(0)] * n
            for cat_id, dailys in cash_flow.items():
                add_to: list[Decimal] | None = None
                if cat_id in categories_income:
                    add_to = daily_income
                elif cat_id in categories_expense:
                    add_to = daily_expense
                else:
                    continue
                for i, amount in enumerate(dailys):
                    add_to[i] += amount
            incomes = utils.integrate(daily_income)
            expenses = utils.integrate(daily_expense)

        if periods is not None:
            chart_bars = True
            for label, limits in periods.items():
                labels.append(label)
                i, e = sum_income_expense(
                    s,
                    limits[0],
                    limits[1],
                    ids,
                    set(categories_income),
                    set(categories_expense),
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
            "income_categorized": income_categorized,
            "expense_categorized": expense_categorized,
            "income_tagged": income_tagged,
            "expense_tagged": expense_tagged,
            "chart_bars": chart_bars,
            "labels": labels,
            "date_mode": date_mode,
            "totals": totals,
            "incomes": incomes,
            "expenses": expenses,
        },
        "category_type": AccountCategory,
    }


def sum_income_expense(
    s: orm.Session,
    start_ord: int,
    end_ord: int,
    ids: Iterable[int],
    categories_income: set[int],
    categories_expense: set[int],
) -> tuple[Decimal, Decimal]:
    """Sum income and expense from start to end.

    Args:
        s: SQL session to use
        start_ord: First date ordinal to evaluate
        end_ord: Last date ordinal to evaluate (inclusive)
        ids: Limit results to specific Accounts by ID
        categories_income: Set of TransactionCategory.id_ for income
        categories_expense: Set of TransactionCategory.id_ for expense

    Returns:
        income, expense
    """
    income = Decimal(0)
    expense = Decimal(0)

    query = s.query(TransactionSplit)
    query = query.with_entities(
        TransactionSplit.category_id,
        func.sum(TransactionSplit.amount),
    )
    query = query.where(TransactionSplit.account_id.in_(ids))
    query = query.where(TransactionSplit.date_ord >= start_ord)
    query = query.where(TransactionSplit.date_ord <= end_ord)
    query = query.group_by(TransactionSplit.category_id)
    for cat_id, amount in query.yield_per(YIELD_PER):
        if cat_id in categories_income:
            income += amount
        elif cat_id in categories_expense:
            expense += amount

    return income, expense


def page() -> flask.Response:
    """GET /cash-flow.

    Returns:
        string HTML response
    """
    txn_table, title = transactions.ctx_table(None, DEFAULT_PERIOD, cash_flow=True)
    title = "Cash Flow," + title.removeprefix("Transactions")
    return common.page(
        "cash-flow/index-content.jinja",
        title=title,
        chart=ctx_chart(),
        txn_table=txn_table,
        endpoint="cash_flow.txns",
    )


def txns() -> flask.Response:
    """GET /h/cash-flow/txns.

    Returns:
        HTML response
    """
    args = flask.request.args
    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))
    txn_table, title = transactions.ctx_table(None, DEFAULT_PERIOD, cash_flow=True)
    start = txn_table["start"]
    title = "Cash Flow," + title.removeprefix("Transactions")
    html = f"<title>{title}</title>\n" + flask.render_template(
        "transactions/table.jinja",
        txn_table=txn_table,
        include_oob=True,
        endpoint="cash_flow.txns",
    )
    if not (
        PREVIOUS_PERIOD["start"] == start
        and PREVIOUS_PERIOD["end"] == end
        and flask.request.headers.get("Hx-Trigger") != "txn-table"
    ):
        # If same period and not being updated via update_transaction:
        # don't update the chart
        # aka if just the table changed pages or column filters
        html += flask.render_template(
            "cash-flow/chart-data.jinja",
            oob=True,
            chart=ctx_chart(),
        )
    response = flask.make_response(html)
    args = dict(flask.request.args.lists())
    response.headers["HX-Push-Url"] = flask.url_for(
        "cash_flow.page",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **args,
    )
    return response


def txns_options(field: str) -> str:
    """GET /h/cash-flow/txns-options/<field>.

    Args:
        field: Name of field to get options for

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        args = flask.request.args

        id_mapping = None
        label_mapping = None
        if field == "account":
            id_mapping = Account.map_name(s)
        elif field == "category":
            id_mapping = TransactionCategory.map_name(s)
            label_mapping = TransactionCategory.map_name_emoji(s)
        elif field not in {"payee", "tag"}:
            msg = f"Unexpected txns options: {field}"
            raise exc.http.BadRequest(msg)

        query, _, _, _ = transactions.table_unfiltered_query(s, cash_flow=True)

        search_str = args.get(f"search-{field}")

        return flask.render_template(
            "transactions/table-options.jinja",
            options=transactions.ctx_options(
                query,
                field,
                id_mapping,
                label_mapping=label_mapping,
                search_str=search_str,
            ),
            name=field,
            search_str=search_str,
            endpoint="cash_flow.txns",
        )


def dashboard() -> str:
    """GET /h/dashboard/cash-flow.

    Returns:
        string HTML response
    """
    return flask.render_template(
        "cash-flow/dashboard.jinja",
        chart=ctx_chart(),
    )


ROUTES: Routes = {
    "/cash-flow": (page, ["GET"]),
    "/h/cash-flow/txns": (txns, ["GET"]),
    "/h/cash-flow/txns-options/<path:field>": (txns_options, ["GET"]),
    "/h/dashboard/cash-flow": (dashboard, ["GET"]),
}
