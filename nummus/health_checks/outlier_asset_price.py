"""Checks if an asset was bought/sold at an outlier price."""

from __future__ import annotations

import datetime
import textwrap
from decimal import Decimal
from typing import override, TYPE_CHECKING

from sqlalchemy import func

from nummus import sql, utils
from nummus.health_checks.base import HealthCheck
from nummus.models.account import Account
from nummus.models.asset import Asset
from nummus.models.currency import CURRENCY_FORMATS
from nummus.models.transaction import TransactionSplit

if TYPE_CHECKING:

    from nummus.models.currency import Currency


class OutlierAssetPrice(HealthCheck):
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
        today = datetime.datetime.now(datetime.UTC).date()
        today_ord = today.toordinal()
        start_ord = sql.scalar(
            TransactionSplit.query(func.min(TransactionSplit.date_ord)).where(
                TransactionSplit.asset_id.isnot(None),
            ),
        )
        if start_ord is None:
            # No asset transactions at all
            self._commit_issues({})
            return

        # List of (uri, source, field)
        issues: list[tuple[str, str, str]] = []

        assets = Asset.map_name()

        asset_valuations = Asset.get_value_all(
            start_ord,
            today_ord + utils.DAYS_IN_WEEK,
        )

        query = Account.query(
            Account.id_,
            Account.currency,
        )
        accounts: dict[int, Currency] = sql.to_dict(query)

        query = (
            TransactionSplit.query(
                TransactionSplit.id_,
                TransactionSplit.account_id,
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
        for t_id, acct_id, date_ord, a_id, amount, qty in sql.yield_(query):
            uri = TransactionSplit.id_to_uri(t_id)

            if not qty:
                continue
            if TYPE_CHECKING:
                # Enforced by query and SQL constraints
                assert a_id is not None

            # Transaction asset price
            t_price = -amount / qty

            v_price = asset_valuations[a_id][date_ord - start_ord]
            v_price_low = v_price * (1 - self._RANGE)
            v_price_high = v_price * (1 + self._RANGE)
            if t_price < v_price_low:
                cf = CURRENCY_FORMATS[accounts[acct_id]]
                issues.append(
                    (
                        uri,
                        f"{datetime.date.fromordinal(date_ord)}: {assets[a_id]}",
                        (
                            f"was traded at {cf(t_price)} which is "
                            f"below valuation of {cf(v_price)}"
                        ),
                    ),
                )
            elif t_price > v_price_high:
                cf = CURRENCY_FORMATS[accounts[acct_id]]
                issues.append(
                    (
                        uri,
                        f"{datetime.date.fromordinal(date_ord)}: {assets[a_id]}",
                        (
                            f"was traded at {cf(t_price)} which is "
                            f"above valuation of {cf(v_price)}"
                        ),
                    ),
                )
        source_len = max(len(item[1]) for item in issues) if issues else 0

        self._commit_issues(
            {uri: f"{source:{source_len}} {field}" for uri, source, field in issues},
        )
