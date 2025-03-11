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
from nummus.models import (
    Account,
    Asset,
    AssetCategory,
    AssetValuation,
    paginate,
    YIELD_PER,
)

if TYPE_CHECKING:
    from nummus.controllers.base import Routes

DEFAULT_PERIOD = "90-days"
PREVIOUS_PERIOD: dict[str, datetime.date | None] = {"start": None, "end": None}


class _AssetContext(TypedDict):
    """Context for asset page."""

    uri: str
    name: str
    description: str | None
    ticker: str | None
    category: AssetCategory
    value: Decimal
    value_date: datetime.date | None

    performance: _PerformanceContext | None


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
        ctx["performance"] = ctx_performance(s, a)
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

        return common.dialog_swap(event="update-asset", snackbar="All changes saved")


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


def new_valuation(uri: str) -> str | flask.Response:
    """GET & POST /h/assets/a/<uri>/new-valuation.

    Returns:
        string HTML response
    """
    if flask.request.method == "GET":
        ctx: dict[str, object] = {
            "uri": None,
            "date": None,
            "value": None,
        }

        return flask.render_template(
            "assets/valuations-edit.jinja",
            valuation=ctx,
            url_args={"uri": uri},
        )

    form = flask.request.form
    date = utils.parse_date(form.get("date"))
    if date is None:
        return common.error("Asset valuation date must not be empty")
    value = utils.evaluate_real_statement(form.get("value"), precision=6)
    if value is None:
        return common.error("Asset valuation value must not be empty")

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
        if "UNIQUE" in orig and "asset_id" in orig and "date_ord" in orig:
            return common.error(
                "Asset valuation date must be unique for each asset",
            )
        return common.error(e)

    return common.dialog_swap(event="update-valuation", snackbar="All changes saved")


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

        if flask.request.method == "GET":
            return flask.render_template(
                "assets/valuations-edit.jinja",
                valuation=ctx_valuation(v),
            )
        if flask.request.method == "DELETE":
            date = datetime.date.fromordinal(v.date_ord)
            s.delete(v)
            return common.dialog_swap(
                event="update-valuation",
                snackbar=f"{date} valuation deleted",
            )

        form = flask.request.form
        date = utils.parse_date(form.get("date"))
        if date is None:
            return common.error("Asset valuation date must not be empty")
        value = utils.evaluate_real_statement(form.get("value"), precision=6)
        if value is None:
            return common.error("Asset valuation value must not be empty")

        try:
            with s.begin_nested():
                # Make the changes
                v.date_ord = date.toordinal()
                v.value = value
        except exc.IntegrityError as e:
            # Get the line that starts with (...IntegrityError)
            orig = str(e.orig)
            if "UNIQUE" in orig and "asset_id" in orig and "date_ord" in orig:
                return common.error(
                    "Asset valuation date must be unique for each asset",
                )
            return common.error(e)

        return common.dialog_swap(
            event="update-valuation",
            snackbar="All changes saved",
        )


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
        "value": current_value,
        "value_date": current_date,
        "performance": None,
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


def valuations(uri: str) -> flask.Response:
    """GET /h/assets/a/<uri>/valuations.

    Args:
        uri: Asset URI

    Returns:
        HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        a = web_utils.find(s, Asset, uri)

        args = flask.request.args
        period = args.get("period", DEFAULT_PERIOD)
        start, end = web_utils.parse_period(period)
        if start is None:
            start_ord = (
                s.query(AssetValuation.date_ord)
                .where(AssetValuation.asset_id == a.id_)
                .order_by(AssetValuation.date_ord)
                .first()
            )
            start = (
                end if start_ord is None else datetime.date.fromordinal(start_ord[0])
            )
        val_table, title = ctx_valuations(a)
        html = f"<title>{title}</title>\n" + flask.render_template(
            "assets/valuations.jinja",
            val_table=val_table,
            include_oob=True,
            url_args={"uri": uri},
        )
        response = flask.make_response(html)
        args = dict(flask.request.args.lists())
        response.headers["HX-Push-Url"] = flask.url_for(
            "assets.page",
            _anchor=None,
            _method=None,
            _scheme=None,
            _external=False,
            uri=uri,
            **args,
        )
        return response


def ctx_valuations(
    a: Asset,
) -> tuple[dict[str, object], str]:
    """Get the context to build the valuations table.

    Args:
        a: Asset to get valuations for

    Returns:
        Dictionary HTML context, title of page
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        args = flask.request.args
        page_len = 25
        offset = int(args.get("offset", 0))
        period = args.get("period", DEFAULT_PERIOD)
        start, end = web_utils.parse_period(period)
        if start is None:
            start_ord = (
                s.query(AssetValuation.date_ord)
                .where(AssetValuation.asset_id == a.id_)
                .order_by(AssetValuation.date_ord)
                .first()
            )
            start = (
                end if start_ord is None else datetime.date.fromordinal(start_ord[0])
            )
        start_ord = start.toordinal()
        end_ord = end.toordinal()

        query = (
            s.query(AssetValuation)
            .where(
                AssetValuation.asset_id == a.id_,
                AssetValuation.date_ord <= end_ord,
                AssetValuation.date_ord >= start_ord,
            )
            .order_by(AssetValuation.date_ord)
        )

        page, count, offset_next = paginate(query, page_len, offset)  # type: ignore[attr-defined]

        valuations: list[dict[str, object]] = []
        for v in page:  # type: ignore[attr-defined]
            v: AssetValuation
            v_ctx = ctx_valuation(v)

            valuations.append(v_ctx)

        offset_last = max(0, int((count - 1) // page_len) * page_len)

        if period == "custom":
            title = f"{start} to {end}"
        else:
            title = period.replace("-", " ").title()

        title = f"Asset {a.name} {title} | nummus"

        return {
            "uri": a.uri,
            "editable": a.ticker is None,
            "valuations": valuations,
            "count": count,
            "offset": offset,
            "i_first": 0 if count == 0 else offset + 1,
            "i_last": min(offset + page_len, count),
            "page_len": page_len,
            "offset_first": 0,
            "offset_prev": max(0, offset - page_len),
            "offset_next": offset_next or offset_last,
            "offset_last": offset_last,
            "start": start,
            "end": end,
            "period": period,
        }, title


def ctx_valuation(
    v: AssetValuation,
) -> dict[str, object]:
    """Get the context to build the valuation row.

    Args:
        v: AssetValuation to build context for

    Returns:
        Dictionary HTML context
    """
    return {
        "uri": v.uri,
        "date": datetime.date.fromordinal(v.date_ord),
        "value": v.value,
    }


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
        successful_tickers=successful_tickers,
    )
    response = flask.make_response(html)
    response.headers["HX-Trigger"] = "update-asset"
    return response


ROUTES: Routes = {
    "/assets": (page_all, ["GET"]),
    "/assets/<path:uri>": (page, ["GET"]),
    "/h/assets/new": (new, ["GET", "POST"]),
    "/h/assets/a/<path:uri>": (asset, ["GET", "PUT"]),
    "/h/assets/a/<path:uri>/performance": (performance, ["GET"]),
    "/h/assets/a/<path:uri>/new-valuation": (new_valuation, ["GET", "POST"]),
    "/h/assets/a/<path:uri>/valuations": (valuations, ["GET"]),
    "/h/assets/v/<path:uri>": (valuation, ["GET", "PUT", "DELETE"]),
    "/h/assets/update": (update, ["GET", "POST"]),
}
