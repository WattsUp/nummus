"""Asset controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import flask

from nummus import exceptions as exc
from nummus import portfolio, web_utils
from nummus.controllers import common
from nummus.models import Asset, AssetCategory
from nummus.models.asset import AssetValuation

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.controllers.base import Routes

DEFAULT_PERIOD = "90-days"
PREVIOUS_PERIOD: dict[str, datetime.date | None] = {"start": None, "end": None}


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
        category = form.get("category", type=AssetCategory)
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
    "/h/assets/a/<path:uri>/edit": (edit, ["GET", "POST"]),
}
