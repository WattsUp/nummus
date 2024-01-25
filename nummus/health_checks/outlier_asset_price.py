"""Checks if an asset was bought/sold at an outlier price."""

from __future__ import annotations

import datetime
import textwrap
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy
from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Asset, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from nummus import custom_types as t
    from nummus import portfolio


class OutlierAssetPrice(Base):
    """Checks if an asset was bought/sold at an outlier price."""

    _NAME = "Outlier asset price"
    _DESC = textwrap.dedent("""\
        Checks if an asset was bought/sold at an outlier price.
        Most likely an issue with asset splits.""")
    _SEVERE = True

    # 50% would miss 2:1 or 1:2 splits
    _RANGE = Decimal("0.4")

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        today = datetime.date.today()
        today_ord = today.toordinal()
        with p.get_session() as s:
            assets = Asset.map_name(s)
            asset_len = max(len(a) for a in assets.values())

            start_ord = (
                s.query(sqlalchemy.func.min(TransactionSplit.date_ord))
                .where(TransactionSplit.asset_id.isnot(None))
                .scalar()
            )
            if start_ord is None:
                # No asset transactions at all
                return
            asset_valuations = Asset.get_value_all(s, start_ord, today_ord)

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.date_ord,
                    TransactionSplit.asset_id,
                    TransactionSplit.amount,
                    TransactionSplit._asset_qty_int,  # noqa: SLF001
                    TransactionSplit._asset_qty_frac,  # noqa:SLF001
                )
                .where(TransactionSplit.asset_id.isnot(None))
            )
            for date_ord, a_id, amount, qty_i, qty_f in query.yield_per(YIELD_PER):
                date_ord: int
                a_id: int
                amount: t.Real
                qty_i: int
                qty_f: t.Real
                qty = qty_i + qty_f
                if qty == 0:
                    continue

                # Transaction asset price
                t_price = -amount / qty

                v_price = asset_valuations[a_id][date_ord - start_ord]
                v_price_low = v_price * (1 - self._RANGE)
                v_price_high = v_price * (1 + self._RANGE)
                if v_price is None:
                    msg = (
                        f"{datetime.date.fromordinal(date_ord)}:"
                        f" {assets[a_id]:{asset_len}} has no valuations before"
                        " transaction on"
                    )
                    self._issues.append(msg)
                elif t_price < v_price_low:
                    msg = (
                        f"{datetime.date.fromordinal(date_ord)}:"
                        f" {assets[a_id]:{asset_len}} was traded at"
                        f" {utils.format_financial(t_price)} which is below valuation"
                        f" of {utils.format_financial(v_price)}"
                    )
                    self._issues.append(msg)
                elif t_price > v_price_high:
                    msg = (
                        f"{datetime.date.fromordinal(date_ord)}:"
                        f" {assets[a_id]:{asset_len}} was bought at"
                        f" {utils.format_financial(t_price)} which is above valuation"
                        f" of {utils.format_financial(v_price)}"
                    )
                    self._issues.append(msg)
