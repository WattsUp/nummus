from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from nummus.controllers import allocation

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from nummus.models import Asset, AssetSector, AssetValuation, Transaction


def test_ctx_empty(today: datetime.date, session: orm.Session) -> None:
    ctx = allocation.ctx_allocation(session, today)

    target: allocation.AllocationContext = {
        "chart": {"categories": {}, "sectors": {}},
        "categories": [],
        "sectors": [],
    }
    assert ctx == target


def test_ctx(
    today: datetime.date,
    session: orm.Session,
    asset: Asset,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
    asset_sectors: tuple[AssetSector, AssetSector],
) -> None:
    _ = transactions
    _ = asset_valuation
    _ = asset_sectors

    ctx = allocation.ctx_allocation(session, today)

    target: allocation.AllocationContext = {
        "chart": {
            "categories": {
                "Stocks": [
                    {
                        "name": asset.name,
                        "ticker": asset.ticker,
                        "value": Decimal(20),
                        "weight": Decimal(1),
                    },
                ],
            },
            "sectors": {
                "Basic Materials": [
                    {
                        "name": asset.name,
                        "ticker": asset.ticker,
                        "value": Decimal(4),
                        "weight": Decimal("0.2"),
                    },
                ],
                "Technology": [
                    {
                        "name": asset.name,
                        "ticker": asset.ticker,
                        "value": Decimal(16),
                        "weight": Decimal("0.8"),
                    },
                ],
            },
        },
        "categories": [
            {
                "assets": [
                    {
                        "name": asset.name,
                        "uri": asset.uri,
                        "ticker": asset.ticker,
                        "qty": Decimal(10),
                        "price": Decimal(2),
                        "value": Decimal(20),
                        "weight": Decimal(1),
                    },
                ],
                "name": "Stocks",
                "value": Decimal(20),
            },
        ],
        "sectors": [
            {
                "assets": [
                    {
                        "name": asset.name,
                        "uri": asset.uri,
                        "ticker": asset.ticker,
                        "qty": Decimal(2),
                        "price": Decimal(2),
                        "value": Decimal(4),
                        "weight": Decimal("0.2"),
                    },
                ],
                "name": "Basic Materials",
                "value": Decimal(4),
            },
            {
                "assets": [
                    {
                        "name": asset.name,
                        "uri": asset.uri,
                        "ticker": asset.ticker,
                        "qty": Decimal(8),
                        "price": Decimal(2),
                        "value": Decimal(16),
                        "weight": Decimal("0.8"),
                    },
                ],
                "name": "Technology",
                "value": Decimal(16),
            },
        ],
    }
    assert ctx == target
