"""Checks if an asset is held without any valuations."""

from __future__ import annotations

import datetime
from typing import override

from sqlalchemy import func

from nummus import sql
from nummus.health_checks.base import HealthCheck
from nummus.models.asset import (
    Asset,
    AssetValuation,
)
from nummus.models.transaction import TransactionSplit


class MissingAssetValuations(HealthCheck):
    """Checks if an asset is held without any valuations."""

    _DESC = "Checks if an asset is held without any valuations."
    _SEVERE = True

    @override
    def test(self) -> None:
        assets = Asset.map_name()
        issues: dict[str, str] = {}

        query = (
            TransactionSplit.query(
                TransactionSplit.asset_id,
                func.min(TransactionSplit.date_ord),
            )
            .where(TransactionSplit.asset_id.isnot(None))
            .group_by(TransactionSplit.asset_id)
        )
        first_date_ords: dict[int | None, int] = sql.to_dict(query)

        query = AssetValuation.query(
            AssetValuation.asset_id,
            func.min(AssetValuation.date_ord),
        ).group_by(AssetValuation.asset_id)
        first_valuations: dict[int, int] = sql.to_dict(query)

        for a_id, date_ord in first_date_ords.items():
            if a_id is None:
                raise TypeError
            uri = Asset.id_to_uri(a_id)

            date_ord_v = first_valuations.get(a_id)
            if date_ord_v is None:
                msg = f"{assets[a_id]} has no valuations"
                issues[uri] = msg
            elif date_ord < date_ord_v:
                msg = (
                    f"{assets[a_id]} has first transaction on"
                    f" {datetime.date.fromordinal(date_ord)} before first valuation"
                    f" on {datetime.date.fromordinal(date_ord_v)}"
                )
                issues[uri] = msg

        self._commit_issues(issues)
