"""Account model for storing a financial account."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy
from sqlalchemy import orm
from typing_extensions import override

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus import utils
from nummus.models.asset import Asset
from nummus.models.base import Base, BaseEnum, YIELD_PER
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import TransactionCategory


class AccountCategory(BaseEnum):
    """Categories of Accounts."""

    CASH = 1
    CREDIT = 2
    INVESTMENT = 3
    MORTGAGE = 4
    LOAN = 5
    FIXED = 6
    OTHER = 7


class Account(Base):
    """Account model for storing a financial account.

    Attributes:
        uri: Account unique identifier
        name: Account name
        number: Account number
        institution: Account holding institution
        category: Type of Account
        closed: True if Account is closed, will hide from view and not update
        emergency: True if Account is included in emergency fund
        opened_on: Date of first Transaction
        updated_on: Date of latest Transaction
    """

    __table_id__ = 0x10000000

    name: t.ORMStr
    number: t.ORMStrOpt
    institution: t.ORMStr
    category: orm.Mapped[AccountCategory]
    closed: t.ORMBool
    emergency: t.ORMBool

    @orm.validates("name", "number", "institution")
    @override
    def validate_strings(self, key: str, field: str | None) -> str | None:
        return super().validate_strings(key, field)

    @property
    def opened_on_ord(self) -> int:
        """Date ordinal of first Transaction."""
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError
        query = s.query(Transaction)
        query = query.with_entities(sqlalchemy.func.min(Transaction.date_ord))
        query = query.where(Transaction.account_id == self.id_)
        return query.scalar()

    @property
    def updated_on_ord(self) -> int:
        """Date ordinal of latest Transaction."""
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError
        query = s.query(Transaction)
        query = query.with_entities(sqlalchemy.func.max(Transaction.date_ord))
        query = query.where(Transaction.account_id == self.id_)
        return query.scalar()

    @classmethod
    def get_value_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: t.Ints | set[int] | None = None,
    ) -> tuple[t.DictIntReals, t.DictIntReals]:
        """Get the value of all Accounts from start to end date.

        Args:
            s: SQL session to use
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)
            ids: Limit results to specific Accounts by ID

        Returns:
            Also returns value by Assets, Accounts holding same Assets will sum
            (dict{Account.id_: list[values]}, dict{Asset.id_: list[values]}
        """
        n = end_ord - start_ord + 1

        cash_flow_accounts: dict[int, list[t.Real | None]] = {}
        if ids is not None:
            cash_flow_accounts = {acct_id: [None] * n for acct_id in ids}
        else:
            cash_flow_accounts = {
                acct_id: [None] * n for acct_id, in s.query(Account.id_).all()
            }

        # Get Account cash value on start date
        query = s.query(TransactionSplit)
        query = query.with_entities(
            TransactionSplit.account_id,
            sqlalchemy.func.sum(TransactionSplit.amount),
        )
        query = query.where(TransactionSplit.date_ord <= start_ord)
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))
        query = query.group_by(TransactionSplit.account_id)
        for acct_id, iv in query.all():
            acct_id: int
            iv: Decimal
            cash_flow_accounts[acct_id][0] = iv

        if start_ord != end_ord:
            # Get cash_flow on each day between start and end
            # Not Account.get_cash_flow because being categorized doesn't matter and
            # slows it down
            query = s.query(TransactionSplit)
            query = query.with_entities(
                TransactionSplit.account_id,
                TransactionSplit.date_ord,
                TransactionSplit.amount,
            )
            query = query.where(TransactionSplit.date_ord <= end_ord)
            query = query.where(TransactionSplit.date_ord > start_ord)
            if ids is not None:
                query = query.where(TransactionSplit.account_id.in_(ids))

            for acct_id, date_ord, amount in query.yield_per(YIELD_PER):
                acct_id: int
                date_ord: int
                amount: Decimal

                i = date_ord - start_ord

                v = cash_flow_accounts[acct_id][i]
                cash_flow_accounts[acct_id][i] = amount if v is None else v + amount

        # Get assets for all Accounts
        assets_accounts = cls.get_asset_qty_all(
            s,
            start_ord,
            end_ord,
            list(cash_flow_accounts.keys()),
        )

        # Skip assets with zero quantity
        a_ids: set[int] = set()
        for assets in assets_accounts.values():
            for a_id, qty in list(assets.items()):
                if not any(qty):
                    # Remove asset from account
                    assets.pop(a_id)
                else:
                    a_ids.add(a_id)

        asset_prices = Asset.get_value_all(s, start_ord, end_ord, a_ids)

        acct_values: t.DictIntReals = {}
        asset_values: t.DictIntReals = {a_id: [Decimal(0)] * n for a_id in a_ids}
        for acct_id, cash_flow in cash_flow_accounts.items():
            assets = assets_accounts[acct_id]
            cash = utils.integrate(cash_flow)

            if len(assets) == 0:
                acct_values[acct_id] = cash
                continue

            summed = cash
            for a_id, qty in assets.items():
                price = asset_prices[a_id]
                asset_value = asset_values[a_id]
                for i, q in enumerate(qty):
                    if q:
                        v = price[i] * q
                        asset_value[i] += v
                        summed[i] += v

            acct_values[acct_id] = summed

        return acct_values, asset_values

    def get_value(self, start_ord: int, end_ord: int) -> tuple[t.Reals, t.DictIntReals]:
        """Get the value of Account from start to end date.

        Args:
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            Also returns value by Asset
            (list[values], dict{Asset.id_: list[values]})
        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        # Not reusing get_value_all is faster by ~2ms,
        # not worth maintaining two almost identical implementations

        accts, assets = self.get_value_all(s, start_ord, end_ord, [self.id_])
        return accts[self.id_], assets

    @classmethod
    def get_cash_flow_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: t.Ints | set[int] | None = None,
    ) -> t.DictIntReals:
        """Get the cash flow of all Accounts from start to end date by category.

        Does not separate results by account.

        Args:
            s: SQL session to use
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)
            ids: Limit results to specific Accounts by ID

        Returns:
            dict{TransactionCategory: list[values]}
        """
        n = end_ord - start_ord + 1

        categories: t.DictIntReals = {
            cat_id: [Decimal(0)] * n
            for cat_id, in s.query(TransactionCategory.id_).all()
        }

        # Transactions between start and end
        query = s.query(TransactionSplit)
        query = query.with_entities(
            TransactionSplit.date_ord,
            TransactionSplit.amount,
            TransactionSplit.category_id,
        )
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))
        query = query.where(TransactionSplit.date_ord <= end_ord)
        query = query.where(TransactionSplit.date_ord >= start_ord)

        for t_date_ord, amount, category_id in query.yield_per(YIELD_PER):
            t_date_ord: int
            amount: Decimal
            category_id: int

            categories[category_id][t_date_ord - start_ord] += amount

        return categories

    def get_cash_flow(
        self,
        start_ord: int,
        end_ord: int,
    ) -> t.DictIntReals:
        """Get the cash flow of Account from start to end date by category.

        Results are not integrated, i.e. inflow[3] = 10 means $10 was made on the
        third day; inflow[4] may be zero

        Args:
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            dict{TransactionCategory: list[values]}
            Includes None in categories
        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        return self.get_cash_flow_all(s, start_ord, end_ord, [self.id_])

    @classmethod
    def get_asset_qty_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: t.Ints | set[int] | None = None,
    ) -> dict[int, t.DictIntReals]:
        """Get the quantity of Assets held from start to end date.

        Args:
            s: SQL session to use
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)
            ids: Limit results to specific Accounts by ID

        Returns:
            dict{Account.id_: dict{Asset.id_: list[values]}}
        """
        n = end_ord - start_ord + 1

        iv_accounts: dict[int, t.DictIntReal] = {}
        if ids is not None:
            iv_accounts = {acct_id: {} for acct_id in ids}
        else:
            iv_accounts = {acct_id: {} for acct_id, in s.query(Account.id_).all()}

        # Get Asset quantities on start date
        # Cannot do sql sum due to overflow fractional part
        query = s.query(TransactionSplit)
        query = query.with_entities(
            TransactionSplit.account_id,
            TransactionSplit.asset_id,
            TransactionSplit._asset_qty_int,  # noqa: SLF001
            TransactionSplit._asset_qty_frac,  # noqa: SLF001
        )
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))
        query = query.where(TransactionSplit.asset_id.is_not(None))
        query = query.where(TransactionSplit.date_ord <= start_ord)
        query = query.order_by(TransactionSplit.account_id)

        current_acct_id: int | None = None
        iv: t.DictIntReal = {}
        for acct_id, a_id, qty_i, qty_f in query.yield_per(YIELD_PER):
            acct_id: int
            a_id: int
            qty_i: int
            qty_f: Decimal
            if acct_id != current_acct_id:
                current_acct_id = acct_id
                try:
                    iv = iv_accounts[acct_id]
                except KeyError:  # pragma: no cover
                    # Should not happen cause iv_accounts is initialized with all
                    iv = {}
                    iv_accounts[acct_id] = iv
            try:
                iv[a_id] += qty_i + qty_f
            except KeyError:
                iv[a_id] = qty_i + qty_f

        # Daily delta in qty
        deltas_accounts: dict[int, dict[int, list[t.Real | None]]] = {}
        for acct_id, iv in iv_accounts.items():
            deltas: dict[int, list[t.Real | None]] = {}
            for a_id, v in iv.items():
                deltas[a_id] = [None] * n
                deltas[a_id][0] = v
            deltas_accounts[acct_id] = deltas

        if start_ord != end_ord:
            # Transactions between start and end
            query = s.query(TransactionSplit)
            query = query.with_entities(
                TransactionSplit.date_ord,
                TransactionSplit.account_id,
                TransactionSplit.asset_id,
                TransactionSplit._asset_qty_int,  # noqa: SLF001
                TransactionSplit._asset_qty_frac,  # noqa: SLF001
            )
            if ids is not None:
                query = query.where(TransactionSplit.account_id.in_(ids))
            query = query.where(TransactionSplit.date_ord <= end_ord)
            query = query.where(TransactionSplit.date_ord > start_ord)
            query = query.where(TransactionSplit.asset_id.is_not(None))
            query = query.order_by(TransactionSplit.account_id)

            current_acct_id = None
            deltas = {}

            for date_ord, acct_id, a_id, qty_i, qty_f in query.yield_per(YIELD_PER):
                date_ord: int
                acct_id: int
                a_id: int
                qty_i: int
                qty_f: Decimal

                i = date_ord - start_ord
                qty = qty_i + qty_f

                if acct_id != current_acct_id:
                    current_acct_id = acct_id
                    try:
                        deltas = deltas_accounts[acct_id]
                    except KeyError:  # pragma: no cover
                        # Should not happen cause delta_accounts is initialized with all
                        deltas = {}
                        deltas_accounts[acct_id] = deltas
                try:
                    v = deltas[a_id][i]
                    deltas[a_id][i] = qty if v is None else v + qty
                except KeyError:
                    deltas[a_id] = [None] * n
                    deltas[a_id][i] = qty

        # Integrate deltas
        qty_accounts: dict[int, t.DictIntReals] = {}
        for acct_id, deltas in deltas_accounts.items():
            qty_assets: t.DictIntReals = {}
            for a_id, delta in deltas.items():
                qty_assets[a_id] = utils.integrate(delta)
            qty_accounts[acct_id] = qty_assets

        return qty_accounts

    def get_asset_qty(
        self,
        start_ord: int,
        end_ord: int,
    ) -> t.DictIntReals:
        """Get the quantity of Assets held from start to end date.

        Args:
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            dict{Asset.id_: list[values]}
        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        return self.get_asset_qty_all(s, start_ord, end_ord, [self.id_])[self.id_]
