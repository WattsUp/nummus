"""Asset controllers."""

from __future__ import annotations

import datetime
import operator
from collections import defaultdict
from decimal import Decimal
from typing import NamedTuple, TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func

from nummus import exceptions as exc
from nummus import utils, web
from nummus.controllers import base
from nummus.models import (
    Account,
    Asset,
    AssetCategory,
    AssetSector,
    AssetValuation,
    query_count,
    YIELD_PER,
)
from nummus.models.asset import AssetSplit
from nummus.models.transaction import TransactionSplit

if TYPE_CHECKING:
    import sqlalchemy
    import werkzeug
    from sqlalchemy import orm


PAGE_LEN = 50


class AccountHoldings(NamedTuple):
    """Context for account holdings."""

    uri: str
    name: str
    qty: Decimal
    value: Decimal


class AssetContext(TypedDict):
    """Context for asset page."""

    uri: str | None
    name: str
    description: str | None
    ticker: str | None
    category: AssetCategory
    category_type: type[AssetCategory]
    value: Decimal
    value_date: datetime.date | None
    deletable: bool

    table: TableContext | None
    holdings: list[AccountHoldings]

    performance: PerformanceContext | None


class TableContext(TypedDict):
    """Context for valuations table."""

    uri: str
    first_page: bool
    editable: bool
    valuations: list[ValuationContext]
    no_matches: bool
    next_page: datetime.date | None
    any_filters: bool
    selected_period: str | None
    options_period: list[tuple[str, str]]
    start: str | None
    end: str | None


class ValuationContext(TypedDict):
    """Context for a valuation."""

    uri: str | None
    asset_uri: str
    date: datetime.date
    date_max: datetime.date | None
    value: Decimal | None


class PerformanceContext(base.ChartData):
    """Context for performance metrics."""

    labels: list[str]

    period: str
    period_options: dict[str, str]


class RowContext(TypedDict):
    """Context for asset row."""

    uri: str
    name: str
    ticker: str | None
    qty: Decimal
    price: Decimal
    value: Decimal


def page_all() -> flask.Response:
    """GET /assets.

    Returns:
        string HTML response

    """
    p = web.portfolio
    include_unheld = "include-unheld" in flask.request.args

    with p.begin_session() as s:
        categories = ctx_rows(s, base.today_client(), include_unheld=include_unheld)

    return base.page(
        "assets/page-all.jinja",
        title="Assets",
        ctx={
            "categories": {
                cat: sorted(assets, key=lambda asset: asset["name"].lower())
                for cat, assets in categories.items()
            },
            "include_unheld": include_unheld,
        },
    )


def page(uri: str) -> flask.Response:
    """GET /assets/<uri>.

    Args:
        uri: Asset URI

    Returns:
        string HTML response

    """
    p = web.portfolio
    args = flask.request.args
    with p.begin_session() as s:
        a = base.find(s, Asset, uri)
        ctx = ctx_asset(
            s,
            a,
            base.today_client(),
            args.get("period"),
            args.get("start"),
            args.get("end"),
            args.get("page"),
            args.get("chart-period"),
        )
        return base.page(
            "assets/page.jinja",
            title=a.name,
            asset=ctx,
        )


def new() -> str | flask.Response:
    """GET & POST /h/assets/new.

    Returns:
        HTML response

    """
    if flask.request.method == "GET":
        ctx: AssetContext = {
            "uri": None,
            "name": "",
            "description": None,
            "ticker": "",
            "category": AssetCategory.STOCKS,
            "category_type": AssetCategory,
            "value": Decimal(),
            "value_date": None,
            "table": None,
            "holdings": [],
            "performance": None,
            "deletable": False,
        }
        return flask.render_template(
            "assets/edit.jinja",
            asset=ctx,
        )

    p = web.portfolio

    with p.begin_session() as s:
        form = flask.request.form
        name = form["name"].strip()
        description = form["description"].strip()
        ticker = form["ticker"].strip()
        category = AssetCategory(form["category"])

        try:
            with s.begin_nested():
                a = Asset(
                    name=name,
                    description=description,
                    category=category,
                    ticker=ticker,
                )
                s.add(a)
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return base.error(e)

        return base.dialog_swap(event="asset", snackbar="All changes saved")


def asset(uri: str) -> str | werkzeug.Response:
    """GET & POST /h/assets/a/<uri>.

    Args:
        uri: Asset URI

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        a = base.find(s, Asset, uri)

        if flask.request.method == "GET":
            args = flask.request.args
            return flask.render_template(
                "assets/edit.jinja",
                asset=ctx_asset(
                    s,
                    a,
                    base.today_client(),
                    args.get("period"),
                    args.get("start"),
                    args.get("end"),
                    args.get("page"),
                    args.get("chart-period"),
                ),
            )
        if flask.request.method == "DELETE":
            with s.begin_nested():
                s.query(AssetSector).where(AssetSector.asset_id == a.id_).delete()
                s.query(AssetSplit).where(AssetSplit.asset_id == a.id_).delete()
                s.query(AssetValuation).where(AssetValuation.asset_id == a.id_).delete()
                s.delete(a)
            return flask.redirect(flask.url_for("assets.page_all"))

        form = flask.request.form
        name = form["name"].strip()
        description = form["description"].strip()
        ticker = form["ticker"].strip()
        category = AssetCategory(form["category"])

        try:
            with s.begin_nested():
                # Make the changes
                a.name = name
                a.description = description
                a.ticker = ticker
                a.category = category
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return base.error(e)

        return base.dialog_swap(event="asset", snackbar="All changes saved")


def performance(uri: str) -> flask.Response:
    """GET /h/assets/a/<uri>/performance.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        a = base.find(s, Asset, uri)
        period = flask.request.args.get("chart-period")
        html = flask.render_template(
            "assets/performance.jinja",
            asset={
                "uri": uri,
                "performance": ctx_performance(s, a, base.today_client(), period),
            },
        )
    response = flask.make_response(html)
    response.headers["HX-Push-URL"] = flask.url_for(
        "assets.page",
        uri=uri,
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **flask.request.args,
    )
    return response


def table(uri: str) -> str | flask.Response:
    """GET /h/assets/a/<uri>/table.

    Args:
        uri: Asset URI

    Returns:
        HTML response with url set

    """
    p = web.portfolio
    args = flask.request.args
    with p.begin_session() as s:
        a = base.find(s, Asset, uri)
        val_table = ctx_table(
            s,
            a,
            base.today_client(),
            args.get("period"),
            args.get("start"),
            args.get("end"),
            args.get("page"),
        )

    first_page = "page" not in args
    html = flask.render_template(
        "assets/table-rows.jinja",
        ctx=val_table,
        include_oob=first_page,
    )
    if not first_page:
        # Don't push URL for following pages
        return html
    response = flask.make_response(html)
    response.headers["HX-Push-URL"] = flask.url_for(
        "assets.page",
        uri=uri,
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **flask.request.args,
    )
    return response


def validation() -> str:
    """GET /h/assets/validation.

    Returns:
        string HTML response

    """
    p = web.portfolio
    # dict{key: (required, prop if unique required)}
    properties: dict[str, tuple[bool, orm.QueryableAttribute | None]] = {
        "name": (True, Asset.name),
        "description": (False, None),
        "ticker": (False, Asset.ticker),
    }

    with p.begin_session() as s:
        args = flask.request.args
        uri = args.get("uri")
        for key, (required, prop) in properties.items():
            if key not in args:
                continue
            return base.validate_string(
                args[key],
                is_required=required,
                check_length=key != "ticker",
                session=s,
                no_duplicates=prop,
                no_duplicate_wheres=(
                    None if uri is None else [Asset.id_ != Asset.uri_to_id(uri)]
                ),
            )

        if "date" in args:
            wheres: list[sqlalchemy.ColumnExpressionArgument] = []
            if uri:
                wheres.append(
                    AssetValuation.asset_id == Asset.uri_to_id(uri),
                )
            if "v" in args:
                wheres.append(
                    AssetValuation.id_ != AssetValuation.uri_to_id(args["v"]),
                )

            return base.validate_date(
                args["date"],
                base.today_client(),
                is_required=True,
                session=s,
                no_duplicates=AssetValuation.date_ord,
                no_duplicate_wheres=wheres,
            )

        if "value" in args:
            return base.validate_real(
                args["value"],
                is_required=True,
            )

    raise NotImplementedError


def new_valuation(uri: str) -> str | flask.Response:
    """GET & POST /h/assets/a/<uri>/new-valuation.

    Returns:
        string HTML response

    """
    today = base.today_client()
    date_max = today + datetime.timedelta(days=utils.DAYS_IN_WEEK)
    if flask.request.method == "GET":
        ctx: ValuationContext = {
            "uri": None,
            "asset_uri": uri,
            "date": today,
            "date_max": date_max,
            "value": None,
        }

        return flask.render_template(
            "assets/edit-valuation.jinja",
            valuation=ctx,
        )

    form = flask.request.form
    try:
        date = base.parse_date(form["date"], today)
    except ValueError as e:
        return base.error(str(e))
    value = utils.evaluate_real_statement(form["value"], precision=6)
    if value is None:
        return base.error("Value must not be empty")
    if value < 0:
        return base.error("Value must not be negative")

    try:
        p = web.portfolio
        with p.begin_session() as s:
            a = base.find(s, Asset, uri)
            v = AssetValuation(
                asset_id=a.id_,
                date_ord=date.toordinal(),
                value=value,
            )
            s.add(v)
    except exc.IntegrityError as e:
        # Get the line that starts with (...IntegrityError)
        orig = str(e.orig)
        msg = (
            "Date must be unique for each asset"
            if "UNIQUE" in orig and "asset_id" in orig and "date_ord" in orig
            else e
        )
        return base.error(msg)

    return base.dialog_swap(event="valuation", snackbar="All changes saved")


def valuation(uri: str) -> str | flask.Response:
    """GET, PUT, & DELETE /h/assets/v/<uri>.

    Args:
        uri: AssetValuation URI

    Returns:
        string HTML response

    """
    p = web.portfolio
    today = base.today_client()

    with p.begin_session() as s:
        v = base.find(s, AssetValuation, uri)

        date_max = today + datetime.timedelta(days=utils.DAYS_IN_WEEK)
        if flask.request.method == "GET":
            return flask.render_template(
                "assets/edit-valuation.jinja",
                valuation={
                    "asset_uri": Asset.id_to_uri(v.asset_id),
                    "uri": uri,
                    "date": v.date,
                    "date_max": date_max,
                    "value": v.value,
                },
            )
        if flask.request.method == "DELETE":
            date = v.date
            s.delete(v)
            return base.dialog_swap(
                event="valuation",
                snackbar=f"{date} valuation deleted",
            )

        form = flask.request.form
        try:
            date = base.parse_date(form["date"], today)
        except ValueError as e:
            return base.error(str(e))
        value = utils.evaluate_real_statement(form["value"], precision=6)
        if value is None:
            return base.error("Value must not be empty")
        if value < 0:
            return base.error("Value must not be negative")

        try:
            with s.begin_nested():
                # Make the changes
                v.date_ord = date.toordinal()
                v.value = value
        except exc.IntegrityError as e:
            # Get the line that starts with (...IntegrityError)
            orig = str(e.orig)
            msg = (
                "Date must be unique for each asset"
                if "UNIQUE" in orig and "asset_id" in orig and "date_ord" in orig
                else e
            )
            return base.error(msg)

        return base.dialog_swap(event="valuation", snackbar="All changes saved")


def update() -> str | flask.Response:
    """GET & POST /h/assets/update.

    Returns:
        HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        n = query_count(s.query(Asset).where(Asset.ticker.is_not(None)))
    if flask.request.method == "GET":
        return flask.render_template(
            "assets/update.jinja",
            n_to_update=n,
        )

    updated = p.update_assets(no_bars=True)

    if len(updated) == 0:
        return "No assets were updated"

    updated = sorted(updated, key=lambda item: item[0].lower())  # sort by name
    failed_tickers: dict[str, str] = {}
    successful_tickers: list[str] = []
    for _, ticker, _, _, error in updated:
        if error is not None:
            failed_tickers[ticker] = error
        else:
            successful_tickers.append(ticker)
    if not failed_tickers:
        n = len(successful_tickers)
        return base.dialog_swap(
            event="valuation",
            snackbar=f"{n} asset{'' if n == 1 else 's'} updated",
        )
    html = "Failed to update: " + ", ".join(
        f"{ticker}: {e}" for ticker, e in sorted(failed_tickers.items())
    )
    response = flask.make_response(html)
    response.headers["HX-Trigger"] = "valuation"
    return response


def ctx_rows(
    s: orm.Session,
    today: datetime.date,
    *,
    include_unheld: bool,
) -> dict[AssetCategory, list[RowContext]]:
    """Get the context to build the page all rows.

    Args:
        s: SQL session to use
        today: Today's date
        include_unheld: True will include assets with zero current quantity

    Returns:
        dict{AssetContext, list[Assets]}

    """
    categories: dict[AssetCategory, list[RowContext]] = defaultdict(list)

    today_ord = today.toordinal()

    accounts = Account.get_asset_qty_all(s, today_ord, today_ord)
    qtys: dict[int, Decimal] = defaultdict(Decimal)
    for acct_qtys in accounts.values():
        for a_id, values in acct_qtys.items():
            qtys[a_id] += values[0]
    held_ids = {a_id for a_id, qty in qtys.items() if qty}

    query = (
        s.query(Asset)
        .with_entities(Asset.id_, Asset.name, Asset.category, Asset.ticker)
        .where(Asset.category != AssetCategory.INDEX)
        .order_by(Asset.category)
    )
    if not include_unheld:
        query = query.where(Asset.id_.in_(held_ids))
    prices = Asset.get_value_all(s, today_ord, today_ord, held_ids)
    for a_id, name, category, ticker in query.yield_per(YIELD_PER):
        qty = qtys[a_id]
        price = prices[a_id][0]
        value = qty * price

        categories[category].append(
            {
                "uri": Asset.id_to_uri(a_id),
                "name": name,
                "ticker": ticker,
                "qty": qty,
                "price": price,
                "value": value,
            },
        )
    return categories


def ctx_asset(
    s: orm.Session,
    a: Asset,
    today: datetime.date,
    period: str | None,
    start: str | None,
    end: str | None,
    page: str | None,
    period_chart: str | None,
) -> AssetContext:
    """Get the context to build the asset details.

    Args:
        s: SQL session to use
        a: Asset to generate context for
        today: Today's date
        period: Period to get table for
        start: Start of custom period
        end: End of custom period
        page: Page offset
        period_chart: Chart-period to fetch performance for

    Returns:
        Dictionary HTML context

    """
    valuation = (
        s.query(AssetValuation)
        .where(AssetValuation.asset_id == a.id_)
        .order_by(AssetValuation.date_ord.desc())
        .first()
    )
    if valuation is None:
        current_value = Decimal()
        current_date = None
    else:
        current_value = valuation.value
        current_date = valuation.date
    deletable = (
        s.query(TransactionSplit.id_)
        .where(TransactionSplit.asset_id == a.id_)
        .limit(1)
        .scalar()
        is None
    )

    accounts = Account.map_name(s)
    query = (
        s.query(TransactionSplit)
        .with_entities(
            TransactionSplit.account_id,
            func.sum(TransactionSplit.asset_quantity),
        )
        .where(
            TransactionSplit.asset_id == a.id_,
            TransactionSplit.date_ord <= today.toordinal(),
        )
        .group_by(
            TransactionSplit.account_id,
        )
    )
    holdings: list[AccountHoldings] = [
        AccountHoldings(
            Account.id_to_uri(acct_id),
            accounts[acct_id],
            qty,
            qty * current_value,
        )
        for acct_id, qty in query.yield_per(YIELD_PER)
        if qty
    ]

    return {
        "uri": a.uri,
        "name": a.name,
        "description": a.description,
        "ticker": a.ticker,
        "category": a.category,
        "category_type": AssetCategory,
        "value": current_value,
        "value_date": current_date,
        "performance": ctx_performance(s, a, today, period_chart),
        "table": ctx_table(s, a, today, period, start, end, page),
        "holdings": sorted(holdings, key=operator.itemgetter(2), reverse=True),
        "deletable": deletable,
    }


def ctx_performance(
    s: orm.Session,
    a: Asset,
    today: datetime.date,
    period: str | None,
) -> PerformanceContext:
    """Get the context to build the asset performance details.

    Args:
        s: SQL session to use
        a: Asset to generate context for
        today: Today's date
        period: Chart-period to fetch performance for

    Returns:
        Dictionary HTML context

    """
    period = period or "1yr"
    start, end = base.parse_period(period, today)
    end_ord = end.toordinal()
    if start is None:
        start_ord = (
            s.query(func.min(AssetValuation.date_ord))
            .where(AssetValuation.asset_id == a.id_)
            .scalar()
            or end_ord
        )
    else:
        start_ord = start.toordinal()

    values = a.get_value(start_ord, end_ord)

    return {
        **base.chart_data(start_ord, end_ord, values),
        "period": period,
        "period_options": base.PERIOD_OPTIONS,
    }


def ctx_table(
    s: orm.Session,
    a: Asset,
    today: datetime.date,
    period: str | None,
    start: str | None,
    end: str | None,
    page: str | None,
) -> TableContext:
    """Get the context to build the valuations table.

    Args:
        s: SQL session to use
        a: Asset to get valuations for
        today: Today's date
        period: Period to get table for
        start: Start of custom period
        end: End of custom period
        page: Page start date

    Returns:
        Dictionary HTML context, title of page

    """
    page_start = None if page is None else datetime.date.fromisoformat(page).toordinal()

    query = (
        s.query(AssetValuation)
        .where(AssetValuation.asset_id == a.id_)
        .order_by(AssetValuation.date_ord.desc())
    )

    any_filters = False

    start_ord: int | None = None
    end_ord: int | None = None
    if period and period != "all":
        any_filters = True
        if period == "custom":
            d = utils.parse_date(start)
            start_ord = d and d.toordinal()
            d = utils.parse_date(end)
            end_ord = d and d.toordinal()
        elif "-" in period:
            d = datetime.date.fromisoformat(period + "-01")
            start_ord = d.toordinal()
            end_ord = utils.end_of_month(d).toordinal()
        else:
            year = int(period)
            start_ord = datetime.date(year, 1, 1).toordinal()
            end_ord = datetime.date(year, 12, 31).toordinal()

        if start_ord:
            query = query.where(AssetValuation.date_ord >= start_ord)
        if end_ord:
            query = query.where(AssetValuation.date_ord <= end_ord)

    if page_start:
        query = query.where(AssetValuation.date_ord <= page_start)

    valuations: list[ValuationContext] = [
        {
            "uri": v.uri,
            "asset_uri": a.uri,
            "date": v.date,
            "date_max": None,
            "value": v.value,
        }
        for v in query.limit(PAGE_LEN).yield_per(YIELD_PER)
    ]

    next_page = (
        None
        if len(valuations) == 0
        else valuations[-1]["date"] - datetime.timedelta(days=1)
    )

    # There are no more if there wasn't enough for a full page
    no_more = len(valuations) < PAGE_LEN

    month = utils.start_of_month(today)
    last_months = [utils.date_add_months(month, i) for i in range(0, -3, -1)]
    options_period = [
        ("All time", "all"),
        *((f"{m:%B}", m.isoformat()[:7]) for m in last_months),
        (str(month.year), str(month.year)),
        (str(month.year - 1), str(month.year - 1)),
        ("Custom date range", "custom"),
    ]

    return {
        "uri": a.uri,
        "first_page": page_start is None,
        "editable": a.ticker is None,
        "valuations": valuations,
        "no_matches": len(valuations) == 0 and page_start is None,
        "next_page": None if no_more else next_page,
        "any_filters": any_filters,
        "selected_period": period,
        "options_period": options_period,
        "start": start,
        "end": end,
    }


ROUTES: base.Routes = {
    "/assets": (page_all, ["GET"]),
    "/assets/<path:uri>": (page, ["GET"]),
    "/h/assets/new": (new, ["GET", "POST"]),
    "/h/assets/a/<path:uri>": (asset, ["GET", "PUT", "DELETE"]),
    "/h/assets/a/<path:uri>/performance": (performance, ["GET"]),
    "/h/assets/a/<path:uri>/table": (table, ["GET"]),
    "/h/assets/a/<path:uri>/new-valuation": (new_valuation, ["GET", "POST"]),
    "/h/assets/v/<path:uri>": (valuation, ["GET", "PUT", "DELETE"]),
    "/h/assets/update": (update, ["GET", "POST"]),
    "/h/assets/validation": (validation, ["GET"]),
}
