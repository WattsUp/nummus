"""Asset controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import flask

from nummus import exceptions as exc
from nummus import portfolio, web_utils
from nummus.controllers import common, transactions
from nummus.models import Account, Asset, AssetCategory, TransactionCategory
from nummus.models.asset import AssetValuation

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.controllers.base import Routes

DEFAULT_PERIOD = "90-days"
PREVIOUS_PERIOD: dict[str, datetime.date | None] = {"start": None, "end": None}


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
        no_recent=True,
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
        no_recent=True,
        asset_transactions=True,
    )
    response = flask.make_response(html)
    args = dict(flask.request.args)
    response.headers["HX-Push-Url"] = flask.url_for(
        "assets.page_transactions",
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
        elif field == "category":
            id_mapping = TransactionCategory.map_name(s)
        elif field == "asset":
            id_mapping = Asset.map_name(s)

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


def edit(uri: str) -> str | flask.Response:
    """GET & POST /h/assets/a/<uri>/edit.

    Args:
        uri: Asset URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        asset: Asset = web_utils.find(s, Asset, uri)  # type: ignore[attr-defined]

        if flask.request.method == "GET":
            return flask.render_template(
                "assets/edit.jinja",
                asset=ctx_asset(s, asset),
            )

        form = flask.request.form
        name = form["name"].strip()
        description = form["description"].strip()
        ticker = form["ticker"].strip()
        category_s = form.get("category")
        category = AssetCategory(category_s) if category_s else None
        interpolate = "interpolate" in form

        if category is None:
            return common.error("Asset category must not be None")

        try:
            # Make the changes
            asset.name = name
            asset.description = description
            asset.ticker = ticker
            asset.category = category
            asset.interpolate = interpolate
            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.overlay_swap(event="update-asset")


def ctx_asset(s: orm.Session, asset: Asset) -> dict[str, object]:
    """Get the context to build the asset details.

    Args:
        s: SQL session to use
        asset: Asset to generate context for

    Returns:
        Dictionary HTML context
    """
    valuation = (
        s.query(AssetValuation)
        .where(AssetValuation.asset_id == asset.id_)
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
        "uri": asset.uri,
        "name": asset.name,
        "description": asset.description,
        "category": asset.category,
        "category_type": AssetCategory,
        "value": current_value,
        "value_date": current_date,
        "ticker": asset.ticker,
        "interpolate": asset.interpolate,
    }


ROUTES: Routes = {
    "/assets/transactions": (page_transactions, ["GET"]),
    "/h/assets/txns": (txns, ["GET"]),
    "/h/assets/txns-options/<path:field>": (txns_options, ["GET"]),
    "/h/assets/a/<path:uri>/edit": (edit, ["GET", "POST"]),
}
