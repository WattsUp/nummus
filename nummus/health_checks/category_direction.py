"""Checks for direction (inflow/outflow) of transactions match category."""

from __future__ import annotations

import datetime
import textwrap
from typing import TYPE_CHECKING

from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, TransactionCategory, TransactionSplit, YIELD_PER
from nummus.models.transaction_category import TransactionCategoryGroup

if TYPE_CHECKING:
    from decimal import Decimal


class CategoryDirection(Base):
    """Checks for direction (inflow/outflow) of transactions match category."""

    _DESC = textwrap.dedent(
        """\
        Transactions with income group category should have a positive amount.
        Transactions with expense group category should have a negative amount.""",
    )
    _SEVERE = True

    @override
    def test(self) -> None:
        with self._p.begin_session() as s:
            accounts = Account.map_name(s)
            if len(accounts) == 0:
                self._commit_issues()
                return
            acct_len = max(len(acct) for acct in accounts.values())

            query = s.query(
                TransactionCategory.id_,
                TransactionCategory.emoji_name,
            ).where(
                TransactionCategory.group == TransactionCategoryGroup.INCOME,
            )
            cat_income_ids: dict[int, str] = dict(query.all())  # type: ignore[attr-defined]
            query = s.query(
                TransactionCategory.id_,
                TransactionCategory.emoji_name,
            ).where(
                TransactionCategory.group == TransactionCategoryGroup.EXPENSE,
            )
            cat_expense_ids: dict[int, str] = dict(query.all())  # type: ignore[attr-defined]

            query = (
                s.query(TransactionSplit)
                .with_entities(
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
            for t_id, acct_id, date_ord, payee, amount, t_cat_id in query.yield_per(
                YIELD_PER,
            ):
                acct_id: int
                date_ord: int
                payee: str
                amount: Decimal
                uri = TransactionSplit.id_to_uri(t_id)

                msg = (
                    f"{datetime.date.fromordinal(date_ord)} - "
                    f"{accounts[acct_id]:{acct_len}}: "
                    f"{utils.format_financial(amount)} to {payee or '[blank]'} "
                    "has negative amount with income category "
                    f"{cat_income_ids[t_cat_id]}"
                )
                self._issues_raw[uri] = msg

            query = (
                s.query(TransactionSplit)
                .with_entities(
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
            for t_id, acct_id, date_ord, payee, amount, t_cat_id in query.yield_per(
                YIELD_PER,
            ):
                acct_id: int
                date_ord: int
                payee: str
                amount: Decimal
                uri = TransactionSplit.id_to_uri(t_id)

                msg = (
                    f"{datetime.date.fromordinal(date_ord)} - "
                    f"{accounts[acct_id]:{acct_len}}: "
                    f"{utils.format_financial(amount)} to {payee or '[blank]'} "
                    "has positive amount with expense category "
                    f"{cat_expense_ids[t_cat_id]}"
                )
                self._issues_raw[uri] = msg

        self._commit_issues()
