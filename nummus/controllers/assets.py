"""Asset controllers."""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func, orm

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import Account, Asset, AssetCategory, AssetValuation, YIELD_PER

if TYPE_CHECKING:
    from nummus.controllers.base import Routes

PAGE_LEN = 50


class _AssetContext(TypedDict):
    """Context for asset page."""

    uri: str
    name: str
    description: str | None
    ticker: str | None
    category: AssetCategory
    category_type: type[AssetCategory]
    value: Decimal
    value_date: datetime.date | None

    table: _TableContext

    performance: _PerformanceContext


class _TableContext(TypedDict):
    """Context for valuations table."""

    uri: str
    first_page: bool
    editable: bool
    valuations: list[_ValuationContext]
    no_matches: bool
    next_page: datetime.date | None
    any_filters: bool
    selected_period: str | None
    options_period: list[tuple[str, str]]
    start: str | None
    end: str | None


class _ValuationContext(TypedDict):
    """Context for a valuation."""

    uri: str | None
    asset_uri: str
    date: datetime.date
    date_max: datetime.date | None
    value: Decimal | None


class _PerformanceContext(TypedDict):
    """Context for performance metrics."""

    labels: list[str]
    date_mode: str
    values: list[Decimal]

    period: str
    period_options: dict[str, str]


class _RowContext(TypedDict):
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
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    include_unheld = "include-unheld" in flask.request.args

    with p.begin_session() as s:
        categories: dict[AssetCategory, list[_RowContext]] = defaultdict(list)

        today = datetime.date.today()
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

    return common.page(
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
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        a = web_utils.find(s, Asset, uri)
        title = f"Asset {a.name}"
        ctx = ctx_asset(s, a)
        return common.page(
            "assets/page.jinja",
            title=title,
            asset=ctx,
        )


def new() -> str:
    """GET & POST /h/accounts/new.

    Returns:
        HTML response
    """
    raise NotImplementedError


def asset(uri: str) -> str | flask.Response:
    """GET & POST /h/assets/a/<uri>.

    Args:
        uri: Asset URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        a = web_utils.find(s, Asset, uri)

        if flask.request.method == "GET":
            return flask.render_template(
                "assets/edit.jinja",
                asset=ctx_asset(s, a),
            )

        form = flask.request.form
        name = form["name"].strip()
        description = form["description"].strip()
        ticker = form["ticker"].strip()
        category_s = form.get("category")
        category = AssetCategory(category_s) if category_s else None

        if category is None:
            return common.error("Asset category must not be None")

        try:
            with s.begin_nested():
                # Make the changes
                a.name = name
                a.description = description
                a.ticker = ticker
                a.category = category
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.dialog_swap(event="asset", snackbar="All changes saved")


def performance(uri: str) -> flask.Response:
    """GET /h/assets/a/<uri>/performance.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        a = web_utils.find(s, Asset, uri)
        html = flask.render_template(
            "assets/performance.jinja",
            asset={
                "uri": uri,
                "performance": ctx_performance(s, a),
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
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        a = web_utils.find(s, Asset, uri)
        val_table = ctx_table(s, a)

    args = flask.request.args
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


def validation(uri: str) -> str:
    """GET /h/assets/a/<uri>/validation.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    # dict{key: (required, prop if unique required)}
    properties: dict[str, tuple[bool, orm.QueryableAttribute | None]] = {
        "name": (True, Asset.name),
        "description": (False, None),
        "ticker": (False, Asset.ticker),
    }

    args = flask.request.args
    for key, (required, prop) in properties.items():
        if key not in args:
            continue
        value = args[key].strip()
        if value == "":
            return "Required" if required else ""
        if key != "ticker" and len(value) < utils.MIN_STR_LEN:
            # Ticker can be short
            return f"{utils.MIN_STR_LEN} characters required"
        if prop is not None:
            with p.begin_session() as s:
                n = (
                    s.query(Asset)
                    .where(
                        prop == value,
                        Asset.id_ != Asset.uri_to_id(uri),
                    )
                    .count()
                )
                if n != 0:
                    return "Must be unique"
        return ""

    if "date" in args:
        value = args["date"].strip()
        if value == "":
            return "Required"
        try:
            date = utils.parse_date(value)
        except ValueError:
            return "Unable to parse"
        if date is None:  # pragma: no cover
            # Type guard, should not be called
            return "Unable to parse"
        if date > (datetime.date.today() + datetime.timedelta(days=utils.DAYS_IN_WEEK)):
            return "Only up to a week in advance"
        with p.begin_session() as s:
            n = (
                s.query(AssetValuation)
                .where(
                    AssetValuation.date_ord == date.toordinal(),
                    AssetValuation.asset_id == Asset.uri_to_id(uri),
                    AssetValuation.id_ != AssetValuation.uri_to_id(args["v"]),
                )
                .count()
            )
            if n != 0:
                return "Must be unique"
        return ""

    if "value" in args:
        value = args["value"].strip()
        if value == "":
            return "Required"
        amount = utils.evaluate_real_statement(value)
        if amount is None:
            return "Unable to parse"
        return ""

    raise NotImplementedError


def new_valuation(uri: str) -> str | flask.Response:
    """GET & POST /h/assets/a/<uri>/new-valuation.

    Returns:
        string HTML response
    """
    today = datetime.date.today()
    date_max = today + datetime.timedelta(days=utils.DAYS_IN_WEEK)
    if flask.request.method == "GET":
        ctx: _ValuationContext = {
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
    date = utils.parse_date(form.get("date"))
    if date is None:
        return common.error("Date must not be empty")
    if date > date_max:
        return common.error("Date can only be up to a week in the future")
    value = utils.evaluate_real_statement(form.get("value"), precision=6)
    if value is None:
        return common.error("Value must not be empty")
    if value < 0:
        return common.error("Value must not be negative")

    try:
        with flask.current_app.app_context():
            p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
        with p.begin_session() as s:
            a = web_utils.find(s, Asset, uri)
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
        return common.error(msg)

    return common.dialog_swap(event="valuation", snackbar="All changes saved")


def valuation(uri: str) -> str | flask.Response:
    """GET, PUT, & DELETE /h/assets/v/<uri>.

    Args:
        uri: AssetValuation URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        v = web_utils.find(s, AssetValuation, uri)

        today = datetime.date.today()
        date_max = today + datetime.timedelta(days=utils.DAYS_IN_WEEK)
        if flask.request.method == "GET":
            return flask.render_template(
                "assets/edit-valuation.jinja",
                valuation={
                    "asset_uri": Asset.id_to_uri(v.asset_id),
                    "uri": uri,
                    "date": datetime.date.fromordinal(v.date_ord),
                    "date_max": date_max,
                    "value": v.value,
                },
            )
        if flask.request.method == "DELETE":
            date = datetime.date.fromordinal(v.date_ord)
            s.delete(v)
            return common.dialog_swap(
                event="valuation",
                snackbar=f"{date} valuation deleted",
            )

        form = flask.request.form
        date = utils.parse_date(form.get("date"))
        if date is None:
            return common.error("Date must not be empty")
        if date > date_max:
            return common.error("Date can only be up to a week in the future")
        value = utils.evaluate_real_statement(form.get("value"), precision=6)
        if value is None:
            return common.error("Value must not be empty")
        if value < 0:
            return common.error("Value must not be negative")

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
            return common.error(msg)

        return common.dialog_swap(event="valuation", snackbar="All changes saved")


def update() -> str | flask.Response:
    """GET & POST /h/assets/update.

    Returns:
        HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        n = s.query(Asset).where(Asset.ticker.is_not(None)).count()
    if flask.request.method == "GET":
        return flask.render_template(
            "assets/update.jinja",
            n_to_update=n,
        )

    updated = p.update_assets(no_bars=True)

    if len(updated) == 0:
        return flask.render_template(
            "assets/update.jinja",
            n_to_update=n,
            error=common.error("No assets were updated"),
        )

    updated = sorted(updated, key=lambda item: item[0].lower())  # sort by name
    failed_tickers: dict[str, str] = {}
    successful_tickers: list[str] = []
    for _, ticker, _, _, error in updated:
        if error is not None:
            failed_tickers[ticker] = error
        else:
            successful_tickers.append(ticker)
    html = flask.render_template(
        "assets/update.jinja",
        failed_tickers=failed_tickers,
        successful_tickers=sorted(successful_tickers),
    )
    response = flask.make_response(html)
    response.headers["HX-Trigger"] = "valuation"
    return response


def ctx_asset(s: orm.Session, a: Asset) -> _AssetContext:
    """Get the context to build the asset details.

    Args:
        s: SQL session to use
        a: Asset to generate context for

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
        current_value = Decimal(0)
        current_date = None
    else:
        current_value = valuation.value
        current_date = datetime.date.fromordinal(valuation.date_ord)

    return {
        "uri": a.uri,
        "name": a.name,
        "description": a.description,
        "ticker": a.ticker,
        "category": a.category,
        "category_type": AssetCategory,
        "value": current_value,
        "value_date": current_date,
        "performance": ctx_performance(s, a),
        "table": ctx_table(s, a),
    }


def ctx_performance(s: orm.Session, a: Asset) -> _PerformanceContext:
    """Get the context to build the asset performance details.

    Args:
        s: SQL session to use
        a: Asset to generate context for

    Returns:
        Dictionary HTML context
    """
    period = flask.request.args.get("chart-period", "1yr")
    start, end = web_utils.parse_period(period)
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
    labels, date_mode = web_utils.date_labels(start_ord, end_ord)

    values = a.get_value(start_ord, end_ord)

    return {
        "labels": labels,
        "date_mode": date_mode,
        "values": values,
        "period": period,
        "period_options": web_utils.PERIOD_OPTIONS,
    }


def ctx_table(s: orm.Session, a: Asset) -> _TableContext:
    """Get the context to build the valuations table.

    Args:
        s: SQL session to use
        a: Asset to get valuations for

    Returns:
        Dictionary HTML context, title of page
    """
    args = flask.request.args
    selected_period = args.get("period")
    selected_start = args.get("start")
    selected_end = args.get("end")

    page_start_str = args.get("page")
    if page_start_str is None:
        page_start = None
    else:
        try:
            page_start = int(page_start_str)
        except ValueError:
            page_start = datetime.date.fromisoformat(page_start_str).toordinal()

    query = (
        s.query(AssetValuation)
        .where(AssetValuation.asset_id == a.id_)
        .order_by(AssetValuation.date_ord.desc())
    )

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
            query = query.where(AssetValuation.date_ord >= start.toordinal())
        if end:
            query = query.where(AssetValuation.date_ord <= end.toordinal())

    if page_start:
        query = query.where(AssetValuation.date_ord <= page_start)

    valuations: list[_ValuationContext] = [
        {
            "uri": v.uri,
            "asset_uri": a.uri,
            "date": datetime.date.fromordinal(v.date_ord),
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

    today = datetime.date.today()
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
        "selected_period": selected_period,
        "options_period": options_period,
        "start": selected_start,
        "end": selected_end,
    }


ROUTES: Routes = {
    "/assets": (page_all, ["GET"]),
    "/assets/<path:uri>": (page, ["GET"]),
    "/h/assets/new": (new, ["GET", "POST"]),
    "/h/assets/a/<path:uri>": (asset, ["GET", "PUT"]),
    "/h/assets/a/<path:uri>/performance": (performance, ["GET"]),
    "/h/assets/a/<path:uri>/table": (table, ["GET"]),
    "/h/assets/a/<path:uri>/validation": (validation, ["GET"]),
    "/h/assets/a/<path:uri>/new-valuation": (new_valuation, ["GET", "POST"]),
    "/h/assets/v/<path:uri>": (valuation, ["GET", "PUT", "DELETE"]),
    "/h/assets/update": (update, ["GET", "POST"]),
}
