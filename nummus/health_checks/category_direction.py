"""Checks for direction (inflow/outflow) of transactions match category."""

from __future__ import annotations

import datetime
import textwrap
from typing import override

from nummus import sql
from nummus.health_checks.base import HealthCheck
from nummus.models.account import Account
from nummus.models.currency import CURRENCY_FORMATS
from nummus.models.transaction import TransactionSplit
from nummus.models.transaction_category import (
    TransactionCategory,
    TransactionCategoryGroup,
)


class CategoryDirection(HealthCheck):
    """Checks for direction (inflow/outflow) of transactions match category."""

    _DESC = textwrap.dedent(
        """\
        Transactions with income group category should have a positive amount.
        Transactions with expense group category should have a negative amount.""",
    )
    _SEVERE = True

    @override
    def test(self) -> None:
        query = Account.query(
            Account.id_,
            Account.name,
            Account.currency,
        )
        accounts = sql.to_dict_tuple(query)
        if len(accounts) == 0:
            self._commit_issues({})
            return
        acct_len = max(len(acct[0]) for acct in accounts.values())
        issues: dict[str, str] = {}

        query = TransactionCategory.query(
            TransactionCategory.id_,
            TransactionCategory.emoji_name,
        ).where(
            TransactionCategory.group == TransactionCategoryGroup.INCOME,
        )
        cat_income_ids: dict[int, str] = sql.to_dict(query)
        query = TransactionCategory.query(
            TransactionCategory.id_,
            TransactionCategory.emoji_name,
        ).where(
            TransactionCategory.group == TransactionCategoryGroup.EXPENSE,
        )
        cat_expense_ids: dict[int, str] = sql.to_dict(query)

        query = (
            TransactionSplit.query(
                TransactionSplit.id_,
                TransactionSplit.account_id,
                TransactionSplit.date_ord,
                TransactionSplit.payee,
                TransactionSplit.amount,
                TransactionSplit.category_id,
            )
            .where(
                TransactionSplit.category_id.in_(cat_income_ids),
                TransactionSplit.amount <= 0,
            )
            .order_by(TransactionSplit.date_ord)
        )
        for t_id, acct_id, date_ord, payee, amount, t_cat_id in sql.yield_(query):
            uri = TransactionSplit.id_to_uri(t_id)

            acct_name, currency = accounts[acct_id]
            cf = CURRENCY_FORMATS[currency]

            msg = (
                f"{datetime.date.fromordinal(date_ord)} - "
                f"{acct_name:{acct_len}}: "
                f"{cf(amount)} to {payee or '[blank]'} "
                "has negative amount with income category "
                f"{cat_income_ids[t_cat_id]}"
            )
            issues[uri] = msg

        query = (
            TransactionSplit.query(
                TransactionSplit.id_,
                TransactionSplit.account_id,
                TransactionSplit.date_ord,
                TransactionSplit.payee,
                TransactionSplit.amount,
                TransactionSplit.category_id,
            )
            .where(
                TransactionSplit.category_id.in_(cat_expense_ids),
                TransactionSplit.amount >= 0,
            )
            .order_by(TransactionSplit.date_ord)
        )
        for t_id, acct_id, date_ord, payee, amount, t_cat_id in sql.yield_(query):
            uri = TransactionSplit.id_to_uri(t_id)

            acct_name, currency = accounts[acct_id]
            cf = CURRENCY_FORMATS[currency]

            msg = (
                f"{datetime.date.fromordinal(date_ord)} - "
                f"{acct_name:{acct_len}}: "
                f"{cf(amount)} to {payee or '[blank]'} "
                "has positive amount with expense category "
                f"{cat_expense_ids[t_cat_id]}"
            )
            issues[uri] = msg

        self._commit_issues(issues)
