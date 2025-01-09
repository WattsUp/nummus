"""Allocation controllers."""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

import flask

from nummus.controllers import common
from nummus.models import (
    Account,
    Asset,
    AssetCategory,
    AssetSector,
    USSector,
    YIELD_PER,
)

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
        allocation=ctx_allocation(),
    )


def ctx_allocation() -> dict[str, object]:
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

        asset_sectors: dict[int, dict[USSector, Decimal]] = defaultdict(dict)
        for a_sector in s.query(AssetSector).yield_per(YIELD_PER):
            asset_sectors[a_sector.asset_id][a_sector.sector] = a_sector.weight

        categories: dict[AssetCategory, list[dict[str, object]]] = defaultdict(list)
        category_values: dict[AssetCategory, Decimal] = defaultdict(Decimal)
        sectors: dict[USSector, list[dict[str, object]]] = defaultdict(list)
        sector_values: dict[USSector, Decimal] = defaultdict(Decimal)
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
            value = asset_values[a_id]
            a_uri = Asset.id_to_uri(a_id)

            ctx = {
                "uri": a_uri,
                "name": name,
                "qty": asset_qtys[a_id],
                "price": asset_prices[a_id],
                "value": value,
            }
            categories[category].append(ctx)
            category_values[category] += asset_values[a_id]

            for sector, weight in asset_sectors[a_id].items():
                sector_value = weight * value
                ctx = {
                    "uri": a_uri,
                    "name": name,
                    "weight": weight,
                    "value": sector_value,
                }
                sectors[sector].append(ctx)
                sector_values[sector] += sector_value

    return {
        "categories": {cat.pretty: assets for cat, assets in categories.items()},
        "category_values": {
            cat.pretty: value for cat, value in category_values.items()
        },
        "sectors": {sector.pretty: assets for sector, assets in sectors.items()},
        "sector_values": {
            sector.pretty: value for sector, value in sector_values.items()
        },
    }


ROUTES: Routes = {
    "/allocation": (page, ["GET"]),
}
