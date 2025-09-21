"""Allocation controllers."""

from __future__ import annotations

import operator
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

from nummus import web
from nummus.controllers import base
from nummus.models import (
    Account,
    Asset,
    AssetSector,
    YIELD_PER,
)

if TYPE_CHECKING:
    import datetime

    import flask
    from sqlalchemy import orm

    from nummus.models import (
        AssetCategory,
        USSector,
    )


class ChartAssetContext(TypedDict):
    """Type definition for asset context."""

    name: str
    ticker: str | None
    value: Decimal
    weight: Decimal


class AssetContext(ChartAssetContext):
    """Type definition for asset context."""

    uri: str
    qty: Decimal
    price: Decimal


class GroupContext(TypedDict):
    """Type definition for category or sector context."""

    name: str
    value: Decimal
    assets: list[AssetContext]


class ChartContext(TypedDict):
    """Type definition for allocation chart context."""

    categories: dict[str, list[ChartAssetContext]]
    sectors: dict[str, list[ChartAssetContext]]


class AllocationContext(TypedDict):
    """Type definition for allocation context."""

    categories: list[GroupContext]
    sectors: list[GroupContext]
    chart: ChartContext


def page() -> flask.Response:
    """GET /allocation.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        return base.page(
            "allocation/page.jinja",
            title="Asset allocation",
            allocation=ctx_allocation(s, base.today_client()),
        )


def ctx_allocation(s: orm.Session, today: datetime.date) -> AllocationContext:
    """Get the context to build the allocation chart.

    Args:
        s: SQL session to use
        today: Today's date

    Returns:
        Dictionary HTML context

    """
    today_ord = today.toordinal()

    asset_qtys: dict[int, Decimal] = defaultdict(Decimal)
    acct_qtys = Account.get_asset_qty_all(s, today_ord, today_ord)
    for acct_qty in acct_qtys.values():
        for a_id, values in acct_qty.items():
            asset_qtys[a_id] += values[0]
    asset_qtys = {a_id: v for a_id, v in asset_qtys.items() if v}

    asset_prices = {
        a_id: values[0]
        for a_id, values in Asset.get_value_all(
            s,
            today_ord,
            today_ord,
            ids=set(asset_qtys),
        ).items()
    }

    asset_values = {a_id: qty * asset_prices[a_id] for a_id, qty in asset_qtys.items()}

    asset_sectors: dict[int, dict[USSector, Decimal]] = defaultdict(dict)
    for a_sector in s.query(AssetSector).yield_per(YIELD_PER):
        asset_sectors[a_sector.asset_id][a_sector.sector] = a_sector.weight

    assets_by_category: dict[AssetCategory, list[AssetContext]] = defaultdict(list)
    assets_by_sector: dict[USSector, list[AssetContext]] = defaultdict(list)
    query = (
        s.query(Asset)
        .with_entities(Asset.id_, Asset.name, Asset.category, Asset.ticker)
        .where(Asset.id_.in_(asset_qtys))
        .order_by(Asset.name)
    )
    for a_id, name, category, ticker in query.yield_per(YIELD_PER):
        a_id: int
        name: str
        category: AssetCategory
        ticker: str | None
        qty = asset_qtys[a_id]
        value = asset_values[a_id]
        a_uri = Asset.id_to_uri(a_id)

        asset_ctx: AssetContext = {
            "uri": a_uri,
            "name": name,
            "ticker": ticker,
            "qty": qty,
            "price": asset_prices[a_id],
            "value": value,
            "weight": Decimal(1),
        }
        assets_by_category[category].append(asset_ctx)

        for sector, weight in asset_sectors[a_id].items():
            asset_sector_ctx = asset_ctx.copy()
            asset_sector_ctx["weight"] = weight
            asset_sector_ctx["qty"] = qty * weight
            asset_sector_ctx["value"] = value * weight
            assets_by_sector[sector].append(asset_sector_ctx)

    categories: list[GroupContext] = [
        {
            "name": cat.pretty,
            "value": sum(a["value"] for a in assets) or Decimal(),
            "assets": sorted(assets, key=operator.itemgetter("name")),
        }
        for cat, assets in assets_by_category.items()
    ]
    sectors: list[GroupContext] = [
        {
            "name": sector.pretty,
            "value": sum(a["value"] for a in assets) or Decimal(),
            "assets": sorted(assets, key=operator.itemgetter("name")),
        }
        for sector, assets in assets_by_sector.items()
    ]

    def chart_assets(assets: list[AssetContext]) -> list[ChartAssetContext]:
        return [
            {
                "name": a["name"],
                "ticker": a["ticker"],
                "value": a["value"],
                "weight": a["weight"],
            }
            for a in assets
        ]

    return {
        "categories": sorted(categories, key=operator.itemgetter("name")),
        "sectors": sorted(sectors, key=operator.itemgetter("name")),
        "chart": {
            "categories": {
                item["name"]: chart_assets(item["assets"]) for item in categories
            },
            "sectors": {item["name"]: chart_assets(item["assets"]) for item in sectors},
        },
    }


ROUTES: base.Routes = {
    "/allocation": (page, ["GET"]),
}
