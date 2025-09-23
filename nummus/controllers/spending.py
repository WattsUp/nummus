"""Spending controllers."""

from __future__ import annotations

import datetime
import operator
from typing import NamedTuple, TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func

from nummus import utils, web
from nummus.controllers import base
from nummus.models import (
    Account,
    Label,
    LabelLink,
    query_count,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from decimal import Decimal

    import sqlalchemy
    from sqlalchemy import orm


class OptionsContext(TypedDict):
    """Type definition for options context."""

    options_period: list[base.NamePair]
    options_account: list[base.NamePair]
    options_category: base.CategoryGroups
    options_label: list[base.NamePair]


class Context(OptionsContext):
    """Type definition for context."""

    no_matches: bool
    selected_period: str | None
    selected_account: str | None
    selected_category: str | None
    selected_label: str | None
    start: str | None
    end: str | None
    by_account: list[tuple[str, Decimal]]
    by_payee: list[tuple[str, Decimal]]
    by_category: list[tuple[str, Decimal]]
    by_label: list[tuple[str | None, Decimal]]


class DataQuery(NamedTuple):
    """Type definition for result of data_query()."""

    query: orm.Query[TransactionSplit]
    clauses: dict[str, sqlalchemy.ColumnElement]
    any_filters: bool

    @property
    def final_query(self) -> orm.Query[TransactionSplit]:
        """Build the final query with clauses."""
        return self.query.where(*self.clauses.values())


def page() -> flask.Response:
    """GET /spending.

    Returns:
        string HTML response

    """
    args = flask.request.args
    p = web.portfolio
    with p.begin_session() as s:
        today = base.today_client()
        ctx, title = ctx_chart(
            s,
            today,
            args.get("account"),
            args.get("category"),
            args.get("label"),
            args.get("period", str(today.year)),
            args.get("start"),
            args.get("end"),
            is_income=False,
        )
    return base.page(
        "spending/page.jinja",
        title=title,
        ctx=ctx,
        is_income=False,
        controller="spending",
    )


def chart() -> flask.Response:
    """GET /h/spending/chart.

    Returns:
        string HTML response

    """
    args = flask.request.args
    p = web.portfolio
    with p.begin_session() as s:
        today = base.today_client()
        ctx, title = ctx_chart(
            s,
            today,
            args.get("account"),
            args.get("category"),
            args.get("label"),
            args.get("period", str(today.year)),
            args.get("start"),
            args.get("end"),
            is_income=False,
        )
    html_title = f"<title>{title} - nummus</title>\n"
    html = html_title + flask.render_template(
        "spending/chart-data.jinja",
        ctx=ctx,
        is_income=False,
        controller="spending",
        include_oob=True,
    )
    response = flask.make_response(html)
    response.headers["HX-Push-Url"] = flask.url_for(
        "spending.page",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **args,
    )
    return response


def dashboard() -> str:
    """GET /h/dashboard/spending.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        today = base.today_client()
        ctx, _ = ctx_chart(
            s,
            today,
            None,
            None,
            None,
            str(today.year),
            None,
            None,
            is_income=False,
        )
    return flask.render_template(
        "spending/dashboard.jinja",
        ctx=ctx,
        is_income=False,
        controller="spending",
    )


def data_query(
    s: orm.Session,
    selected_account: str | None = None,
    selected_period: str | None = None,
    selected_start: str | None = None,
    selected_end: str | None = None,
    selected_category: str | None = None,
    selected_label: str | None = None,
    *,
    is_income: bool,
) -> DataQuery:
    """Create transactions data query.

    Args:
        s: SQL session to use
        selected_account: URI of account from args
        selected_period: Name of period from args
        selected_start: ISO date string of start from args
        selected_end: ISO date string of end from args
        selected_category: URI of category from args
        selected_label: URI of label from args
        is_income: True will select income transactions,
            False will select expense and invert amount signs

    Returns:
        DataQuery

    """
    skip_groups = {
        (
            TransactionCategoryGroup.EXPENSE
            if is_income
            else TransactionCategoryGroup.INCOME
        ),
        TransactionCategoryGroup.TRANSFER,
    }
    query = s.query(TransactionCategory.id_).where(
        (TransactionCategory.name == "securities traded")
        | TransactionCategory.group.in_(skip_groups),
    )
    skip_ids = {r[0] for r in query.yield_per(YIELD_PER)}
    query = s.query(TransactionSplit).where(
        TransactionSplit.category_id.not_in(skip_ids),
    )
    clauses: dict[str, sqlalchemy.ColumnElement] = {}

    any_filters = False

    start = None
    end = None
    if selected_period and selected_period != "all":
        any_filters = True
        if selected_period == "custom":
            start = utils.parse_date(selected_start)
            end = utils.parse_date(selected_end)
        elif "-" in selected_period:
            start = datetime.date.fromisoformat(selected_period + "-01")
            end = utils.end_of_month(start)
        else:
            year = int(selected_period)
            start = datetime.date(year, 1, 1)
            end = datetime.date(year, 12, 31)

        if start:
            clauses["start"] = TransactionSplit.date_ord >= start.toordinal()
        if end:
            clauses["end"] = TransactionSplit.date_ord <= end.toordinal()

    if selected_account:
        any_filters = True
        acct_id = Account.uri_to_id(selected_account)
        clauses["account"] = TransactionSplit.account_id == acct_id

    if selected_category:
        any_filters = True
        cat_id = TransactionCategory.uri_to_id(selected_category)
        clauses["category"] = TransactionSplit.category_id == cat_id

    if selected_label:
        any_filters = True
        label_id = Label.uri_to_id(selected_label)
        label_query = (
            query.join(LabelLink)
            .with_entities(TransactionSplit.id_)
            .where(LabelLink.label_id == label_id)
            .distinct()
        )
        t_split_ids: set[int] = {r[0] for r in label_query.yield_per(YIELD_PER)}
        clauses["label"] = TransactionSplit.id_.in_(t_split_ids)

    return DataQuery(query, clauses, any_filters)


def ctx_options(
    dat_query: DataQuery,
    today: datetime.date,
    accounts: dict[int, str],
    categories: base.CategoryGroups,
    labels: dict[int, str],
    selected_account: str | None = None,
    selected_category: str | None = None,
    selected_label: str | None = None,
) -> OptionsContext:
    """Get the context to build the options for spending chart.

    Args:
        dat_query: Query to use to get distinct values
        today: Today's date
        accounts: Account name mapping
        categories: TransactionCategory name mapping
        labels: Label name mapping
        selected_account: URI of account from args
        selected_category: URI of category from args
        selected_label: URI of label from args

    Returns:
        OptionsContext

    """
    query = dat_query.query

    month = utils.start_of_month(today)
    last_months = [utils.date_add_months(month, i) for i in range(0, -3, -1)]
    options_period = [
        base.NamePair("all", "All time"),
        *(base.NamePair(m.isoformat()[:7], f"{m:%B}") for m in last_months),
        base.NamePair(str(month.year), str(month.year)),
        base.NamePair(str(month.year - 1), str(month.year - 1)),
        base.NamePair("custom", "Custom date range"),
    ]

    clauses = dat_query.clauses.copy()
    clauses.pop("account", None)
    query_options = (
        query.with_entities(TransactionSplit.account_id)
        .where(*clauses.values())
        .distinct()
    )
    options_account = sorted(
        [
            base.NamePair(Account.id_to_uri(acct_id), accounts[acct_id])
            for acct_id, in query_options.yield_per(YIELD_PER)
        ],
        key=operator.itemgetter(0),
    )
    if len(options_account) == 0 and selected_account:
        acct_id = Account.uri_to_id(selected_account)
        options_account = [base.NamePair(selected_account, accounts[acct_id])]

    clauses = dat_query.clauses.copy()
    clauses.pop("category", None)
    query_options = (
        query.with_entities(TransactionSplit.category_id)
        .where(*clauses.values())
        .distinct()
    )
    options_uris = {
        TransactionCategory.id_to_uri(r[0]) for r in query_options.yield_per(YIELD_PER)
    }
    if selected_category:
        options_uris.add(selected_category)
    options_category = {
        group: [cat for cat in items if cat.uri in options_uris]
        for group, items in categories.items()
    }
    options_category = {
        group: sorted(items, key=operator.attrgetter("name"))
        for group, items in options_category.items()
        if items
    }

    clauses = dat_query.clauses.copy()
    clauses.pop("label", None)
    query_options = (
        query.join(LabelLink)
        .with_entities(LabelLink.label_id)
        .where(*clauses.values())
        .distinct()
    )
    options_label = sorted(
        [
            base.NamePair(Label.id_to_uri(label_id), labels[label_id])
            for label_id, in query_options.yield_per(YIELD_PER)
        ],
        key=operator.itemgetter(1),
    )
    if len(options_label) == 0 and selected_label:
        label_id = Label.uri_to_id(selected_label)
        options_label = [base.NamePair(selected_label, labels[label_id])]

    return {
        "options_period": options_period,
        "options_account": options_account,
        "options_category": options_category,
        "options_label": options_label,
    }


def ctx_chart(
    s: orm.Session,
    today: datetime.date,
    selected_account: str | None,
    selected_category: str | None,
    selected_label: str | None,
    selected_period: str | None,
    selected_start: str | None,
    selected_end: str | None,
    *,
    is_income: bool,
) -> tuple[Context, str]:
    """Get the context to build the chart data.

    Args:
        s: SQL session to use
        today: Today's date
        selected_account: Selected account for filtering
        selected_category: Selected category for filtering
        selected_period: Selected period for filtering
        selected_label: Selected label for filtering
        selected_start: Selected start date for custom period
        selected_end: Selected end date for custom period
        is_income: True will select income transactions,
            False will select expense and invert amount signs

    Returns:
        tuple(Context, title)

    """
    accounts = Account.map_name(s)
    categories_emoji = TransactionCategory.map_name_emoji(s)
    labels = Label.map_name(s)

    dat_query = data_query(
        s,
        selected_account,
        selected_period,
        selected_start,
        selected_end,
        selected_category,
        selected_label,
        is_income=is_income,
    )
    options = ctx_options(
        dat_query,
        today,
        accounts,
        base.tranaction_category_groups(s),
        labels,
        selected_account,
        selected_category,
        selected_label,
    )

    final_query = dat_query.final_query
    n_matches = query_count(final_query)

    query = final_query.with_entities(
        TransactionSplit.account_id,
        func.sum(TransactionSplit.amount),
    ).group_by(TransactionSplit.account_id)
    by_account: list[tuple[str, Decimal]] = [
        (accounts[account_id], amount if is_income else -amount)
        for account_id, amount in query.yield_per(YIELD_PER)
        if amount
    ]
    by_account = sorted(by_account, key=operator.itemgetter(1), reverse=True)

    query = final_query.with_entities(
        TransactionSplit.payee,
        func.sum(TransactionSplit.amount),
    ).group_by(TransactionSplit.payee)
    by_payee: list[tuple[str, Decimal]] = [
        (payee, amount if is_income else -amount)
        for payee, amount in query.yield_per(YIELD_PER)
        if amount
    ]
    by_payee = sorted(by_payee, key=operator.itemgetter(1), reverse=True)

    query = final_query.with_entities(
        TransactionSplit.category_id,
        func.sum(TransactionSplit.amount),
    ).group_by(TransactionSplit.category_id)
    by_category: list[tuple[str, Decimal]] = [
        (categories_emoji[cat_id], amount if is_income else -amount)
        for cat_id, amount in query.yield_per(YIELD_PER)
        if amount
    ]
    by_category = sorted(by_category, key=operator.itemgetter(1), reverse=True)

    query = (
        final_query.join(LabelLink, full=True)
        .with_entities(
            LabelLink.label_id,
            func.sum(TransactionSplit.amount),
        )
        .group_by(LabelLink.label_id)
    )
    selected_label_id = selected_label and Label.uri_to_id(selected_label)
    by_label: list[tuple[str | None, Decimal, bool]] = [
        (
            label_id and labels[label_id],
            amount if is_income else -amount,
            label_id and label_id == selected_label_id,
        )
        for label_id, amount in query.yield_per(YIELD_PER)
        if amount
    ]
    by_label = sorted(by_label, key=operator.itemgetter(1), reverse=True)

    return {
        "no_matches": n_matches == 0,
        **options,
        "selected_period": selected_period,
        "selected_account": selected_account,
        "selected_category": selected_category,
        "selected_label": selected_label,
        "start": selected_start,
        "end": selected_end,
        "by_account": by_account,
        "by_payee": by_payee,
        "by_category": by_category,
        "by_label": [
            (label, amount)
            for label, amount, is_selected in by_label
            if not is_selected or len(by_label) == 1
        ],
    }, ("Income" if is_income else "Spending")


ROUTES: base.Routes = {
    "/spending": (page, ["GET"]),
    "/h/spending/chart": (chart, ["GET"]),
    "/h/dashboard/spending": (dashboard, ["GET"]),
}
