"""Allocation controllers."""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

import flask

from nummus.controllers import common
from nummus.models import Account, Asset, AssetCategory, YIELD_PER

if TYPE_CHECKING:
    from nummus import portfolio
    from nummus.controllers.base import Routes


def page() -> str:
    """GET /allocation.

    Returns:
        string HTML response
    """
    return common.page(
        "allocation/index-content.jinja",
        title="Asset Allocation",
        chart=ctx_chart(),
    )


def ctx_chart() -> dict[str, object]:
    """Get the context to build the allocation chart.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    today = datetime.date.today()
    today_ord = today.toordinal()

    with p.begin_session() as s:
        asset_qtys: dict[int, Decimal] = defaultdict(Decimal)
        acct_qtys = Account.get_asset_qty_all(s, today_ord, today_ord)
        for acct_qty in acct_qtys.values():
            for a_id, values in acct_qty.items():
                if values[0] != 0:
                    asset_qtys[a_id] += values[0]

        asset_prices = {
            a_id: values[0]
            for a_id, values in Asset.get_value_all(
                s,
                today_ord,
                today_ord,
                ids=set(asset_qtys),
            ).items()
        }

        asset_values = {
            a_id: qty * asset_prices[a_id] for a_id, qty in asset_qtys.items()
        }

        categories: dict[AssetCategory, list[dict[str, object]]] = defaultdict(list)
        category_values: dict[AssetCategory, Decimal] = defaultdict(Decimal)
        query = (
            s.query(Asset)
            .with_entities(Asset.id_, Asset.name, Asset.category)
            .where(Asset.id_.in_(asset_qtys))
            .order_by(Asset.name)
        )
        for a_id, name, category in query.yield_per(YIELD_PER):
            a_id: int
            name: str
            category: AssetCategory

            ctx = {
                "uri": Asset.id_to_uri(a_id),
                "name": name,
                "qty": asset_qtys[a_id],
                "price": asset_prices[a_id],
                "value": asset_values[a_id],
            }
            categories[category].append(ctx)
            category_values[category] += asset_values[a_id]

    return {
        "categories": categories,
        "category_values": category_values,
    }


ROUTES: Routes = {
    "/allocation": (page, ["GET"]),
}
