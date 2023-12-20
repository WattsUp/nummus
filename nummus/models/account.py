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

    def get_value(
        self,
        start_ord: int,
        end_ord: int,
    ) -> tuple[t.Ints, t.Reals, t.DictIntReals]:
        """Get the value of Account from start to end date.

        Args:
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            Also returns value by Asset (possibly empty for non-investment accounts)
            List[date ordinals], list[values], dict{Asset.id_: list[values]}
        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        # Get Account value on start date
        # It is callable, sum returns a generator type
        query = s.query(sqlalchemy.func.sum(TransactionSplit.amount))
        query = query.where(TransactionSplit.account_id == self.id_)
        query = query.where(TransactionSplit.date_ord <= start_ord)
        iv = query.scalar()
        current_cash = iv or Decimal(0)

        date_ord = start_ord + 1
        date_ords: t.Ints = [start_ord]
        cash: t.Reals = [current_cash]

        # Get Asset quantities on start date
        current_qty_assets: t.DictIntReal = {}
        query = s.query(TransactionSplit)
        query = query.with_entities(
            TransactionSplit.asset_id,
            TransactionSplit._asset_qty_int,  # noqa: SLF001
            TransactionSplit._asset_qty_frac,  # noqa: SLF001
        )
        query = query.where(TransactionSplit.account_id == self.id_)
        query = query.where(TransactionSplit.asset_id.is_not(None))
        query = query.where(TransactionSplit.date_ord <= start_ord)
        for a_id, qty_int, qty_frac in query.all():
            a_id: int
            qty_int: int
            qty_frac: Decimal
            if a_id not in current_qty_assets:
                current_qty_assets[a_id] = Decimal(0)
            current_qty_assets[a_id] += qty_int + qty_frac

        qty_assets: t.DictIntReals = {}
        for a_id, qty in current_qty_assets.items():
            qty_assets[a_id] = [qty]

        if start_ord != end_ord:

            def next_day(current: int) -> int:
                """Push currents into the lists."""
                for k, v in current_qty_assets.items():
                    qty_assets[k].append(v)
                cash.append(current_cash)
                date_ords.append(current)
                return current + 1

            # Transactions between start and end
            query = s.query(TransactionSplit)
            query = query.with_entities(
                TransactionSplit.date_ord,
                TransactionSplit.amount,
                TransactionSplit.asset_id,
                TransactionSplit._asset_qty_int,  # noqa: SLF001
                TransactionSplit._asset_qty_frac,  # noqa: SLF001
            )
            query = query.where(TransactionSplit.account_id == self.id_)
            query = query.where(TransactionSplit.date_ord <= end_ord)
            query = query.where(TransactionSplit.date_ord > start_ord)
            query = query.order_by(TransactionSplit.date_ord)

            for t_date_ord, amount, a_id, qty_int, qty_frac in query.all():
                t_date_ord: int
                amount: Decimal
                a_id: int
                qty_int: int
                qty_frac: Decimal

                while date_ord < t_date_ord:
                    date_ord = next_day(date_ord)

                current_cash += amount
                if a_id is None:
                    continue
                if a_id not in current_qty_assets:
                    # Asset not added during initial value
                    qty_assets[a_id] = [Decimal(0)] * len(date_ords)
                    current_qty_assets[a_id] = Decimal(0)
                current_qty_assets[a_id] += qty_int + qty_frac

            while date_ord <= end_ord:
                date_ord = next_day(date_ord)

        # Skip assets with zero quantity
        for a_id, qty in list(qty_assets.items()):
            if all(q == 0 for q in qty):
                qty_assets.pop(a_id)

        # Get Asset objects and convert qty to value
        value_assets: t.DictIntReals = {}
        query = s.query(Asset)
        query = query.where(Asset.id_.in_(qty_assets.keys()))
        for a in query.all():
            qty = qty_assets[a.id_]
            price = a.get_value(start_ord, end_ord)
            a_values = [round(p * q, 6) for p, q in zip(price, qty, strict=True)]
            value_assets[a.id_] = a_values

        # Sum with cash
        values: t.Reals = [  # type: ignore[attr-defined]
            sum(x) for x in zip(cash, *value_assets.values(), strict=True)
        ]

        return date_ords, values, value_assets

    @classmethod
    def get_value_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: t.Ints | None = None,
    ) -> tuple[t.Ints, t.DictIntReals]:
        """Get the value of all Accounts from start to end date.

        Args:
            s: SQL session to use
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)
            ids: Limit results to specific Accounts by ID

        Returns:
            (List[date ordinals], dict{Account.id_: list[values]})
        """
        current_cash: t.DictIntReal = {
            acct_id: Decimal(0) for acct_id, in s.query(Account.id_).all()
        }

        if ids is not None:
            current_cash = {
                acct_id: v for acct_id, v in current_cash.items() if acct_id in ids
            }

        # Get Account value on start date
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
            current_cash[acct_id] = iv

        date_ord = start_ord + 1
        date_ords: t.Ints = [start_ord]
        cash: t.DictIntReals = {acct_id: [v] for acct_id, v in current_cash.items()}

        # Get Asset quantities on start date
        current_qty_assets: dict[int, t.DictIntReal] = {
            acct_id: {} for acct_id in current_cash
        }
        query = s.query(TransactionSplit)
        query = query.with_entities(
            TransactionSplit.account_id,
            TransactionSplit.asset_id,
            TransactionSplit._asset_qty_int,  # noqa: SLF001
            TransactionSplit._asset_qty_frac,  # noqa: SLF001
        )
        query = query.where(TransactionSplit.asset_id.is_not(None))
        query = query.where(TransactionSplit.date_ord <= start_ord)
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))
        for acct_id, a_id, qty_int, qty_frac in query.yield_per(YIELD_PER):
            acct_id: int
            a_id: int
            qty_int: int
            qty_frac: Decimal
            acct_current_qty_assets = current_qty_assets[acct_id]
            if a_id not in acct_current_qty_assets:
                acct_current_qty_assets[a_id] = Decimal(0)
            acct_current_qty_assets[a_id] += qty_int + qty_frac

        qty_assets: dict[int, t.DictIntReals] = {
            acct_id: {} for acct_id in current_cash
        }
        for acct_id, assets in current_qty_assets.items():
            for a_id, qty in assets.items():
                qty_assets[acct_id][a_id] = [qty]

        if start_ord != end_ord:

            def next_day(current: int) -> int:
                """Push currents into the lists."""
                for acct_id, assets in current_qty_assets.items():
                    for a_id, qty in assets.items():
                        qty_assets[acct_id][a_id].append(qty)
                    cash[acct_id].append(current_cash[acct_id])
                date_ords.append(current)
                return current + 1

            # Transactions between start and end
            query = s.query(TransactionSplit)
            query = query.with_entities(
                TransactionSplit.account_id,
                TransactionSplit.date_ord,
                TransactionSplit.amount,
                TransactionSplit.asset_id,
                TransactionSplit._asset_qty_int,  # noqa: SLF001
                TransactionSplit._asset_qty_frac,  # noqa: SLF001
            )
            query = query.where(TransactionSplit.date_ord <= end_ord)
            query = query.where(TransactionSplit.date_ord > start_ord)
            query = query.order_by(TransactionSplit.date_ord)
            if ids is not None:
                query = query.where(TransactionSplit.account_id.in_(ids))

            for acct_id, t_date_ord, amount, a_id, qty_int, qty_frac in query.yield_per(
                YIELD_PER,
            ):
                acct_id: int
                t_date_ord: int
                amount: Decimal
                a_id: int
                qty_int: int
                qty_frac: Decimal

                while date_ord < t_date_ord:
                    date_ord = next_day(date_ord)

                current_cash[acct_id] += amount
                if a_id is None:
                    continue
                acct_current_qty_assets = current_qty_assets[acct_id]
                if a_id not in acct_current_qty_assets:
                    # Asset not added during initial value
                    qty_assets[acct_id][a_id] = [Decimal(0)] * len(date_ords)
                    acct_current_qty_assets[a_id] = Decimal(0)
                acct_current_qty_assets[a_id] += qty_int + qty_frac

            while date_ord <= end_ord:
                date_ord = next_day(date_ord)

        # Skip assets with zero quantity
        acct_values: t.DictIntReals = {}
        a_ids: t.Ints = []
        for assets in qty_assets.values():
            for a_id, qty in list(assets.items()):
                if all(q == 0 for q in qty):
                    assets.pop(a_id)
                else:
                    a_ids.append(a_id)
        assets_values = Asset.get_value_all(s, start_ord, end_ord, ids=a_ids)
        n = len(date_ords)
        for acct_id, assets in qty_assets.items():
            if len(assets) == 0:
                acct_values[acct_id] = cash[acct_id]
            else:
                # Get Asset objects and convert qty to value
                summed = cash[acct_id]
                for a_id, qty in assets.items():
                    price = assets_values[a_id]
                    for i in range(n):
                        q = qty[i]
                        if q == 0:
                            continue
                        summed[i] += price[i] * q
                acct_values[acct_id] = [round(v, 6) for v in summed]

        return date_ords, acct_values

    @classmethod
    def get_cash_flow_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: t.Ints | None = None,
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
        ids: t.Ints | None = None,
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
        # Cannot do sql sum due to overflow fracional part
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
