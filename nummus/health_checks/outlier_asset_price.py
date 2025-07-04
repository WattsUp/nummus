"""Checks if an asset was bought/sold at an outlier price."""

from __future__ import annotations

import datetime
import textwrap
from decimal import Decimal

from sqlalchemy import func
from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Asset, TransactionSplit, YIELD_PER


class OutlierAssetPrice(Base):
    """Checks if an asset was bought/sold at an outlier price."""

    _DESC = textwrap.dedent(
        """\
        Checks if an asset was bought/sold at an outlier price.
        Most likely an issue with asset splits.""",
    )
    _SEVERE = True

    # 50% would miss 2:1 or 1:2 splits
    _RANGE = Decimal("0.4")

    @override
    def test(self) -> None:
        today = datetime.datetime.now().astimezone().date()
        today_ord = today.toordinal()
        with self._p.begin_session() as s:
            start_ord = (
                s.query(func.min(TransactionSplit.date_ord))
                .where(TransactionSplit.asset_id.isnot(None))
                .scalar()
            )
            if start_ord is None:
                # No asset transactions at all
                self._commit_issues()
                return

            # List of (uri, source, field)
            issues: list[tuple[str, str, str]] = []

            assets = Asset.map_name(s)

            asset_valuations = Asset.get_value_all(s, start_ord, today_ord)

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.id_,
                    TransactionSplit.date_ord,
                    TransactionSplit.asset_id,
                    TransactionSplit.amount,
                    TransactionSplit.asset_quantity,
                )
                .order_by(
                    TransactionSplit.asset_id,
                    TransactionSplit.date_ord,
                )
                .where(TransactionSplit.asset_id.isnot(None))
            )
            for t_id, date_ord, a_id, amount, qty in query.yield_per(
                YIELD_PER,
            ):
                t_id: int
                date_ord: int
                a_id: int
                amount: Decimal
                qty: Decimal
                uri = TransactionSplit.id_to_uri(t_id)

                if qty == 0:
                    continue

                # Transaction asset price
                t_price = -amount / qty

                v_price = asset_valuations[a_id][date_ord - start_ord]
                v_price_low = v_price * (1 - self._RANGE)
                v_price_high = v_price * (1 + self._RANGE)
                if t_price < v_price_low:
                    issues.append(
                        (
                            uri,
                            f"{datetime.date.fromordinal(date_ord)}: {assets[a_id]}",
                            f"was traded at {utils.format_financial(t_price)} which is "
                            f"below valuation of {utils.format_financial(v_price)}",
                        ),
                    )
                elif t_price > v_price_high:
                    issues.append(
                        (
                            uri,
                            f"{datetime.date.fromordinal(date_ord)}: {assets[a_id]}",
                            f"was traded at {utils.format_financial(t_price)} which is "
                            f"above valuation of {utils.format_financial(v_price)}",
                        ),
                    )
            if len(issues) != 0:
                source_len = max(len(item[1]) for item in issues)
                for uri, source, field in issues:
                    msg = f"{source:{source_len}} {field}"
                    self._issues_raw[uri] = msg

        self._commit_issues()
