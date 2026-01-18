"""Checks for transactions that should be linked to an asset that aren't."""

from __future__ import annotations

import datetime
from typing import override, TYPE_CHECKING

from nummus.health_checks.base import HealthCheck
from nummus.models.account import Account
from nummus.models.base import YIELD_PER
from nummus.models.currency import CURRENCY_FORMATS
from nummus.models.transaction import TransactionSplit
from nummus.models.transaction_category import TransactionCategory

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy import orm

    from nummus.models.currency import Currency


class MissingAssetLink(HealthCheck):
    """Checks for transactions that should be linked to an asset that aren't."""

    _DESC = "Checks for transactions that should be linked to an asset that aren't."
    _SEVERE = False

    @override
    def test(self, s: orm.Session) -> None:
        query = s.query(Account).with_entities(
            Account.id_,
            Account.name,
            Account.currency,
        )
        accounts: dict[int, tuple[str, Currency]] = {
            r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
        }
        if len(accounts) == 0:
            self._commit_issues(s, {})
            return
        acct_len = max(len(acct[0]) for acct in accounts.values())
        issues: dict[str, str] = {}

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

            acct_name, currency = accounts[acct_id]
            cf = CURRENCY_FORMATS[currency]

            msg = (
                f"{datetime.date.fromordinal(date_ord)} -"
                f" {acct_name:{acct_len}}:"
                f" {cf(amount)} {categories[cat_id]} "
                "does not have an asset"
            )
            issues[uri] = msg

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

            acct_name, currency = accounts[acct_id]
            cf = CURRENCY_FORMATS[currency]

            msg = (
                f"{datetime.date.fromordinal(date_ord)} -"
                f" {acct_name:{acct_len}}:"
                f" {cf(amount)} {categories[cat_id]} "
                "has an asset"
            )
            issues[uri] = msg

        self._commit_issues(s, issues)
