"""Asset controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import flask
from sqlalchemy import orm

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common, transactions
from nummus.models import Account, Asset, AssetCategory, paginate
from nummus.models.asset import AssetValuation

if TYPE_CHECKING:
    from decimal import Decimal

    from nummus.controllers.base import Routes

DEFAULT_PERIOD = "90-days"
PREVIOUS_PERIOD: dict[str, datetime.date | None] = {"start": None, "end": None}


def page(uri: str) -> str:
    """GET /assets/<uri>.

    Args:
        uri: Asset URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        a = web_utils.find(s, Asset, uri)
        val_table, title = ctx_valuations(a)
        title = f"Asset {a.name}"
        return common.page(
            "assets/index-content.jinja",
            title=title,
            asset=ctx_asset(a),
            chart=ctx_chart(a),
            val_table=val_table,
            url_args={"uri": uri},
        )


def page_transactions() -> str:
    """GET /assets/transactions.

    Returns:
        string HTML response
    """
    txn_table, title = transactions.ctx_table(asset_transactions=True)
    return common.page(
        "transactions/index-content.jinja",
        title=title,
        txn_table=txn_table,
        endpoint="assets.txns",
        asset_transactions=True,
    )


def txns() -> flask.Response:
    """GET /h/assets/transactions.

    Returns:
        HTML response with url set
    """
    txn_table, title = transactions.ctx_table(asset_transactions=True)
    html_title = f"<title>{title}</title>\n"
    html = html_title + flask.render_template(
        "transactions/table.jinja",
        txn_table=txn_table,
        include_oob=True,
        endpoint="assets.txns",
        asset_transactions=True,
    )
    response = flask.make_response(html)
    args = dict(flask.request.args.lists())
    response.headers["HX-Push-Url"] = flask.url_for(
        "assets.page_transactions",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **args,
    )
    return response


def txns_options(field: str) -> str:
    """GET /h/assets/txns-options/<field>.

    Args:
        uri: Account URI
        field: Name of field to get options for

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        args = flask.request.args

        id_mapping = None
        if field == "account":
            id_mapping = Account.map_name(s)
        elif field == "asset":
            id_mapping = Asset.map_name(s)
        else:
            msg = f"Unexpected txns options: {field}"
            raise exc.http.BadRequest(msg)

        query, _, _, _ = transactions.table_unfiltered_query(s, asset_transactions=True)

        search_str = args.get(f"search-{field}")

        return flask.render_template(
            "transactions/table-options.jinja",
            options=transactions.ctx_options(
                query,
                field,
                id_mapping,
                search_str=search_str,
            ),
            name=field,
            search_str=search_str,
            endpoint="assets.txns",
        )


def asset(uri: str) -> str | flask.Response:
    """GET & POST /h/assets/a/<uri>.

    Args:
        uri: Asset URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        a = web_utils.find(s, Asset, uri)

        if flask.request.method == "GET":
            return flask.render_template(
                "assets/edit.jinja",
                asset=ctx_asset(a),
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
            # Make the changes
            a.name = name
            a.description = description
            a.ticker = ticker
            a.category = category
            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.overlay_swap(event="update-asset")


def valuation(uri: str) -> str | flask.Response:
    """GET, PUT, & DELETE /h/assets/v/<uri>.

    Args:
        uri: AssetValuation URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        v = web_utils.find(s, AssetValuation, uri)

        if flask.request.method == "GET":
            return flask.render_template(
                "assets/valuations-edit.jinja",
                valuation=ctx_valuation(v),
            )
        if flask.request.method == "DELETE":
            s.delete(v)
            s.commit()
            return common.overlay_swap(event="update-valuation")

        form = flask.request.form
        date = utils.parse_date(form.get("date"))
        if date is None:
            return common.error("Asset valuation date must not be empty")
        value = utils.parse_real(form.get("value"), precision=6)
        if value is None:
            return common.error("Asset valuation value must not be empty")

        try:
            # Make the changes
            v.date_ord = date.toordinal()
            v.value = value
            s.commit()
        except exc.IntegrityError as e:
            # Get the line that starts with (...IntegrityError)
            orig = str(e.orig)
            if "UNIQUE" in orig and "asset_id" in orig and "date_ord" in orig:
                return common.error(
                    "Asset valuation date must be unique for each asset",
                )
            return common.error(e)

        return common.overlay_swap(event="update-valuation")


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
    value = utils.parse_real(form.get("value"), precision=6)
    if value is None:
        return common.error("Asset valuation value must not be empty")

    try:
        with flask.current_app.app_context():
            p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
        with p.get_session() as s:
            a = web_utils.find(s, Asset, uri)
            v = AssetValuation(
                asset_id=a.id_,
                date_ord=date.toordinal(),
                value=value,
            )
            s.add(v)
            s.commit()
    except exc.IntegrityError as e:
        # Get the line that starts with (...IntegrityError)
        orig = str(e.orig)
        if "UNIQUE" in orig and "asset_id" in orig and "date_ord" in orig:
            return common.error(
                "Asset valuation date must be unique for each asset",
            )
        return common.error(e)

    return common.overlay_swap(event="update-valuation")


def ctx_asset(a: Asset) -> dict[str, object]:
    """Get the context to build the asset details.

    Args:
        a: Asset to generate context for

    Returns:
        Dictionary HTML context
    """
    s = orm.object_session(a)
    if s is None:
        raise exc.UnboundExecutionError
    valuation = (
        s.query(AssetValuation)
        .where(AssetValuation.asset_id == a.id_)
        .order_by(AssetValuation.date_ord.desc())
        .first()
    )
    if valuation is None:
        current_value = 0
        current_date = None
    else:
        current_value = valuation.value
        current_date = datetime.date.fromordinal(valuation.date_ord)

    return {
        "uri": a.uri,
        "name": a.name,
        "description": a.description,
        "category": a.category,
        "category_type": AssetCategory,
        "value": current_value,
        "value_date": current_date,
        "ticker": a.ticker,
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

    with p.get_session() as s:
        a = web_utils.find(s, Asset, uri)

        args = flask.request.args
        period = args.get("period", DEFAULT_PERIOD)
        start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))
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
        if not (
            PREVIOUS_PERIOD["start"] == start
            and PREVIOUS_PERIOD["end"] == end
            and flask.request.headers.get("Hx-Trigger") != "val-table"
        ):
            # If same period and not being updated via update_valuations:
            # don't update the chart
            # aka if just the table changed pages or column filters
            html += flask.render_template(
                "assets/chart-data.jinja",
                oob=True,
                chart=ctx_chart(a),
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


def ctx_chart(a: Asset) -> dict[str, object]:
    """Get the context to build the asset chart.

    Args:
        a: Asset to generate context for

    Returns:
        Dictionary HTML context
    """
    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))
    if start is None:
        s = orm.object_session(a)
        if s is None:
            raise exc.UnboundExecutionError
        start_ord = (
            s.query(AssetValuation.date_ord)
            .where(AssetValuation.asset_id == a.id_)
            .order_by(AssetValuation.date_ord)
            .first()
        )
        start = end if start_ord is None else datetime.date.fromordinal(start_ord[0])

    PREVIOUS_PERIOD["start"] = start
    PREVIOUS_PERIOD["end"] = end

    start_ord = start.toordinal()
    end_ord = end.toordinal()
    n = end_ord - start_ord + 1

    values = a.get_value(start_ord, end_ord)

    labels: list[str] = []
    values_min: list[Decimal] | None = None
    values_max: list[Decimal] | None = None
    date_mode: str | None = None

    if n > web_utils.LIMIT_DOWNSAMPLE:
        # Downsample to min/avg/max by month
        labels, values_min, values, values_max = utils.downsample(
            start_ord,
            end_ord,
            values,
        )
        date_mode = "years"
    else:
        labels = [d.isoformat() for d in utils.range_date(start_ord, end_ord)]
        if n > web_utils.LIMIT_TICKS_MONTHS:
            date_mode = "months"
        elif n > web_utils.LIMIT_TICKS_WEEKS:
            date_mode = "weeks"
        else:
            date_mode = "days"

    return {
        "start": start,
        "end": end,
        "period": period,
        "data": {
            "labels": labels,
            "date_mode": date_mode,
            "values": values,
            "min": values_min,
            "max": values_max,
        },
    }


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

    with p.get_session() as s:
        args = flask.request.args
        page_len = 25
        offset = int(args.get("offset", 0))
        period = args.get("period", DEFAULT_PERIOD)
        start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))
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


ROUTES: Routes = {
    "/assets/<path:uri>": (page, ["GET"]),
    "/assets/transactions": (page_transactions, ["GET"]),
    "/h/assets/txns": (txns, ["GET"]),
    "/h/assets/txns-options/<path:field>": (txns_options, ["GET"]),
    "/h/assets/a/<path:uri>": (asset, ["GET", "PUT"]),
    "/h/assets/a/<path:uri>/new-valuation": (new_valuation, ["GET", "POST"]),
    "/h/assets/a/<path:uri>/valuations": (valuations, ["GET"]),
    "/h/assets/v/<path:uri>": (valuation, ["GET", "PUT", "DELETE"]),
}
