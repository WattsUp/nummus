"""Checks for transactions that should be linked to an asset that aren't."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, TransactionCategory, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from decimal import Decimal


class MissingAssetLink(Base):
    """Checks for transactions that should be linked to an asset that aren't."""

    _DESC = "Checks for transactions that should be linked to an asset that aren't."
    _SEVERE = False

    @override
    def test(self) -> None:
        with self._p.begin_session() as s:
            accounts = Account.map_name(s)
            if len(accounts) == 0:
                self._commit_issues()
                return
            acct_len = max(len(acct) for acct in accounts.values())

            categories = TransactionCategory.map_name_emoji(s)

            # These categories should be linked to an asset
            query = s.query(TransactionCategory.id_).where(
                TransactionCategory.asset_linked.is_(True),
            )
            categories_assets_id = {r for r, in query.all()}

            # Get transactions in these categories that do not have an asset
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.id_,
                    TransactionSplit.date_ord,
                    TransactionSplit.account_id,
                    TransactionSplit.category_id,
                    TransactionSplit.amount,
                )
                .where(
                    TransactionSplit.category_id.in_(categories_assets_id),
                    TransactionSplit.asset_id.is_(None),
                )
            )
            for t_id, date_ord, acct_id, cat_id, amount in query.yield_per(YIELD_PER):
                t_id: int
                date_ord: int
                acct_id: int
                cat_id: int
                amount: Decimal
                uri = TransactionSplit.id_to_uri(t_id)

                msg = (
                    f"{datetime.date.fromordinal(date_ord)} -"
                    f" {accounts[acct_id]:{acct_len}}:"
                    f" {utils.format_financial(amount)} {categories[cat_id]} "
                    "does not have an asset"
                )
                self._issues_raw[uri] = msg

            # Get transactions not in these categories that do have an asset
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.id_,
                    TransactionSplit.date_ord,
                    TransactionSplit.account_id,
                    TransactionSplit.category_id,
                    TransactionSplit.amount,
                )
                .where(
                    TransactionSplit.category_id.not_in(categories_assets_id),
                    TransactionSplit.asset_id.is_not(None),
                )
            )
            for t_id, date_ord, acct_id, cat_id, amount in query.yield_per(YIELD_PER):
                t_id: int
                date_ord: int
                acct_id: int
                cat_id: int
                amount: Decimal
                uri = TransactionSplit.id_to_uri(t_id)

                msg = (
                    f"{datetime.date.fromordinal(date_ord)} -"
                    f" {accounts[acct_id]:{acct_len}}:"
                    f" {utils.format_financial(amount)} {categories[cat_id]} "
                    "has an asset"
                )
                self._issues_raw[uri] = msg

        self._commit_issues()
