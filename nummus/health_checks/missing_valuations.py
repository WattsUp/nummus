"""Checks if an asset is held without any valuations."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import sqlalchemy
from typing_extensions import override

from nummus.health_checks.base import Base
from nummus.models import Asset, AssetValuation, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from nummus import portfolio


class MissingAssetValuations(Base):
    """Checks if an asset is held without any valuations."""

    _NAME = "Missing asset valuations"
    _DESC = "Checks if an asset is held without any valuations"
    _SEVERE = True

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        ignores = self.get_ignores(p)
        with p.get_session() as s:
            assets = Asset.map_name(s)

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.asset_id,
                    sqlalchemy.func.min(TransactionSplit.date_ord),
                )
                .where(TransactionSplit.asset_id.isnot(None))
                .group_by(TransactionSplit.asset_id)
            )
            first_date_ords: dict[int, int] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

            query = (
                s.query(AssetValuation)
                .with_entities(
                    AssetValuation.asset_id,
                    sqlalchemy.func.min(AssetValuation.date_ord),
                )
                .group_by(AssetValuation.asset_id)
            )
            first_valuations: dict[int, int] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

            for a_id, date_ord in first_date_ords.items():
                uri = Asset.id_to_uri(a_id)
                if uri in ignores:
                    continue

                date_ord_v = first_valuations.get(a_id)
                if date_ord_v is None:
                    msg = f"{assets[a_id]} has no valuations"
                    self._issues_raw[uri] = msg
                elif date_ord < date_ord_v:
                    msg = (
                        f"{assets[a_id]} has first transaction on"
                        f" {datetime.date.fromordinal(date_ord)} before first valuation"
                        f" on {datetime.date.fromordinal(date_ord_v)}"
                    )
                    self._issues_raw[uri] = msg
