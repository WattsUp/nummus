"""Account model for storing a financial account."""

from __future__ import annotations

import datetime
from decimal import Decimal

import sqlalchemy
from sqlalchemy import orm
from typing_extensions import override

from nummus import custom_types as t
from nummus.models.asset import Asset
from nummus.models.base import Base, BaseEnum
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
        uuid: Account unique identifier
        name: Account name
        institution: Account holding institution
        category: Type of Account
        closed: True if Account is closed, will hide from view and not update
        opened_on: Date of first Transaction
        updated_on: Date of latest Transaction
    """

    name: t.ORMStr = orm.mapped_column()
    institution: t.ORMStr
    category: orm.Mapped[AccountCategory]
    closed: t.ORMBool

    @orm.validates("name", "institution")
    @override
    def validate_strings(self, key: str, field: str) -> str:
        return super().validate_strings(key, field)

    @property
    def opened_on(self) -> t.Date:
        """Date of first Transaction."""
        s = orm.object_session(self)
        query = s.query(Transaction)
        query = query.with_entities(sqlalchemy.func.min(Transaction.date))
        query = query.where(Transaction.account_id == self.id_)
        return query.scalar()

    @property
    def updated_on(self) -> t.Date:
        """Date of latest Transaction."""
        s = orm.object_session(self)
        query = s.query(Transaction)
        query = query.with_entities(sqlalchemy.func.max(Transaction.date))
        query = query.where(Transaction.account_id == self.id_)
        return query.scalar()

    def get_value(
        self,
        start: t.Date,
        end: t.Date,
    ) -> tuple[t.Dates, t.Reals, t.DictIntReals]:
        """Get the value of Account from start to end date.

        Args:
            start: First date to evaluate
            end: Last date to evaluate (inclusive)

        Returns:
            Also returns value by Asset (possibly empty for non-investment accounts)
            List[dates], list[values], dict{Asset.id_: list[values]}
        """
        s = orm.object_session(self)

        # Get Account value on start date
        # It is callable, sum returns a generator type
        query = s.query(sqlalchemy.func.sum(TransactionSplit.amount))
        query = query.where(TransactionSplit.account_id == self.id_)
        query = query.where(TransactionSplit.date <= start)
        iv = query.scalar()
        current_cash = iv or Decimal(0)

        date = start + datetime.timedelta(days=1)
        dates: t.Dates = [start]
        cash: t.Reals = [current_cash]

        # Get Asset quantities on start date
        current_qty_assets: t.DictReal = {}
        query = s.query(TransactionSplit)
        query = query.with_entities(
            TransactionSplit.asset_id,
            TransactionSplit._asset_qty_int,  # noqa: SLF001
            TransactionSplit._asset_qty_frac,  # noqa: SLF001
        )
        query = query.where(TransactionSplit.account_id == self.id_)
        query = query.where(TransactionSplit.asset_id.is_not(None))
        query = query.where(TransactionSplit.date <= start)
        for a_id, qty_int, qty_frac in query.all():
            a_id: int
            qty_int: int
            qty_frac: Decimal
            if a_id not in current_qty_assets:
                current_qty_assets[a_id] = Decimal(0)
            current_qty_assets[a_id] += qty_int + qty_frac

        qty_assets: t.DictReals = {}
        for a_id, qty in current_qty_assets.items():
            qty_assets[a_id] = [qty]

        if start != end:

            def next_day(current: datetime.date) -> datetime.date:
                """Push currents into the lists."""
                for k, v in current_qty_assets.items():
                    qty_assets[k].append(v)
                cash.append(current_cash)
                dates.append(current)
                return current + datetime.timedelta(days=1)

            # Transactions between start and end
            query = s.query(TransactionSplit)
            query = query.with_entities(
                TransactionSplit.date,
                TransactionSplit.amount,
                TransactionSplit.asset_id,
                TransactionSplit._asset_qty_int,  # noqa: SLF001
                TransactionSplit._asset_qty_frac,  # noqa: SLF001
            )
            query = query.where(TransactionSplit.account_id == self.id_)
            query = query.where(TransactionSplit.date <= end)
            query = query.where(TransactionSplit.date > start)
            query = query.order_by(TransactionSplit.date)

            for t_date, amount, a_id, qty_int, qty_frac in query.all():
                t_date: datetime.date
                amount: Decimal
                a_id: int
                qty_int: int
                qty_frac: Decimal

                while date < t_date:
                    date = next_day(date)

                current_cash += amount
                if a_id is None:
                    continue
                if a_id not in current_qty_assets:
                    # Asset not added during initial value
                    qty_assets[a_id] = [Decimal(0)] * len(dates)
                    current_qty_assets[a_id] = Decimal(0)
                current_qty_assets[a_id] += qty_int + qty_frac

            while date <= end:
                date = next_day(date)

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
            _, price = a.get_value(start, end)
            a_values = [round(p * q, 6) for p, q in zip(price, qty, strict=True)]
            value_assets[a.id_] = a_values

        # Sum with cash
        values = [sum(x) for x in zip(cash, *value_assets.values(), strict=True)]

        return dates, values, value_assets

    @classmethod
    def get_value_all(
        cls,
        s: orm.Session,
        start: t.Date,
        end: t.Date,
        uuids: t.Strings = None,
        ids: t.Ints = None,
    ) -> tuple[t.Dates, t.DictReals]:
        """Get the value of all Accounts from start to end date.

        Args:
            s: SQL session to use
            start: First date to evaluate
            end: Last date to evaluate (inclusive)
            uuids: Limit results to specific Assets by UUID
            ids: Limit results to specific Assets by ID

        Returns:
            (List[dates], dict{Account.id_: list[values]})
        """
        accounts = Account.map_uuid(s)
        current_cash: t.DictIntReal = {acct_id: Decimal(0) for acct_id in accounts}

        if uuids is not None:
            ids = [
                acct_id for acct_id, acct_uuid in accounts.items() if acct_uuid in uuids
            ]
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
        query = query.where(TransactionSplit.date <= start)
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))
        query = query.group_by(TransactionSplit.account_id)

        for acct_id, iv in query.all():
            acct_id: int
            iv: Decimal
            current_cash[acct_id] = iv

        date = start + datetime.timedelta(days=1)
        dates: t.Dates = [start]
        cash: t.DictReals = {acct_id: [v] for acct_id, v in current_cash.items()}

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
        query = query.where(TransactionSplit.date <= start)
        for acct_id, a_id, qty_int, qty_frac in query.all():
            acct_id: int
            a_id: int
            qty_int: int
            qty_frac: Decimal
            acct_current_qty_assets = current_qty_assets[acct_id]
            if a_id not in acct_current_qty_assets:
                acct_current_qty_assets[a_id] = Decimal(0)
            acct_current_qty_assets[a_id] += qty_int + qty_frac

        qty_assets: dict[int, t.DictReals] = {acct_id: {} for acct_id in current_cash}
        for acct_id, assets in current_qty_assets.items():
            for a_id, qty in assets.items():
                qty_assets[acct_id][a_id] = [qty]

        if start != end:

            def next_day(current: datetime.date) -> datetime.date:
                """Push currents into the lists."""
                for acct_id, assets in current_qty_assets.items():
                    for a_id, qty in assets.items():
                        qty_assets[acct_id][a_id].append(qty)
                    cash[acct_id].append(current_cash[acct_id])
                dates.append(current)
                return current + datetime.timedelta(days=1)

            # Transactions between start and end
            query = s.query(TransactionSplit)
            query = query.with_entities(
                TransactionSplit.account_id,
                TransactionSplit.date,
                TransactionSplit.amount,
                TransactionSplit.asset_id,
                TransactionSplit._asset_qty_int,  # noqa: SLF001
                TransactionSplit._asset_qty_frac,  # noqa: SLF001
            )
            query = query.where(TransactionSplit.date <= end)
            query = query.where(TransactionSplit.date > start)
            query = query.order_by(TransactionSplit.date)

            for acct_id, t_date, amount, a_id, qty_int, qty_frac in query.all():
                acct_id: int
                t_date: datetime.date
                amount: Decimal
                a_id: int
                qty_int: int
                qty_frac: Decimal

                while date < t_date:
                    date = next_day(date)

                current_cash[acct_id] += amount
                if a_id is None:
                    continue
                acct_current_qty_assets = current_qty_assets[acct_id]
                if a_id not in acct_current_qty_assets:
                    # Asset not added during initial value
                    qty_assets[acct_id][a_id] = [Decimal(0)] * len(dates)
                    acct_current_qty_assets[a_id] = Decimal(0)
                acct_current_qty_assets[a_id] += qty_int + qty_frac

            while date <= end:
                date = next_day(date)

        # Skip assets with zero quantity
        acct_values: t.DictReals = {}
        a_ids: t.Ints = []
        for assets in qty_assets.values():
            for a_id, qty in list(assets.items()):
                if all(q == 0 for q in qty):
                    assets.pop(a_id)
                else:
                    a_ids.append(a_id)
        _, assets_values = Asset.get_value_all(s, start, end, ids=a_ids)
        for acct_id, assets in qty_assets.items():
            if len(assets) == 0:
                acct_values[acct_id] = cash[acct_id]
            else:
                # Get Asset objects and convert qty to value
                to_sum: list[t.Reals] = [cash[acct_id]]
                for a_id, qty in assets.items():
                    price = assets_values[a_id]
                    a_values = [
                        round(p * q, 6) for p, q in zip(price, qty, strict=True)
                    ]
                    to_sum.append(a_values)

                # Sum with cash
                acct_values[acct_id] = [sum(x) for x in zip(*to_sum, strict=True)]

        return dates, acct_values

    def get_cash_flow(
        self,
        start: t.Date,
        end: t.Date,
    ) -> tuple[t.Dates, t.DictIntReal]:
        """Get the cash_flow of Account from start to end date.

        Results are not integrated, i.e. inflow[3] = 10 means $10 was made on the
        third day; inflow[4] may be zero

        Args:
            start: First date to evaluate
            end: Last date to evaluate (inclusive)

        Returns:
            List[dates], dict{Category: list[values]}
            Includes None in categories
        """
        s = orm.object_session(self)

        date = start

        dates: t.Dates = []
        categories: t.DictIntReals = {
            cat_id: [] for cat_id, in s.query(TransactionCategory.id_).all()
        }

        daily_categories: t.DictIntReal = {cat_id: 0 for cat_id in categories}

        # Transactions between start and end
        query = s.query(TransactionSplit)
        query = query.with_entities(
            TransactionSplit.date,
            TransactionSplit.amount,
            TransactionSplit.category_id,
        )
        query = query.where(TransactionSplit.account_id == self.id_)
        query = query.where(TransactionSplit.date <= end)
        query = query.where(TransactionSplit.date >= start)
        query = query.order_by(TransactionSplit.date)

        for t_date, amount, category_id in query.all():
            t_date: datetime.date
            amount: Decimal
            category_id: int

            while date < t_date:
                dates.append(date)
                # Append and clear daily
                for k, v in daily_categories.items():
                    categories[k].append(v)
                    daily_categories[k] = 0
                date += datetime.timedelta(days=1)

            daily_categories[category_id] += amount

        while date <= end:
            dates.append(date)
            # Append and clear daily
            for k, v in daily_categories.items():
                categories[k].append(v)
                daily_categories[k] = 0
            date += datetime.timedelta(days=1)

        return dates, categories

    def get_asset_qty(
        self,
        start: t.Date,
        end: t.Date,
    ) -> tuple[t.Dates, t.DictIntReals]:
        """Get the quantity of Assets held from start to end date.

        Args:
            start: First date to evaluate
            end: Last date to evaluate (inclusive)

        Returns:
            List[dates], dict{Asset.id_: list[values]}
        """
        s = orm.object_session(self)

        date = start + datetime.timedelta(days=1)
        dates: t.Dates = [start]

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
        query = query.where(TransactionSplit.date <= start)
        for a_id, qty_int, qty_frac in query.all():
            a_id: int
            qty_int: int
            qty_frac: Decimal
            if a_id not in current_qty_assets:
                current_qty_assets[a_id] = Decimal(0)
            current_qty_assets[a_id] += qty_int + qty_frac

        qty_assets: t.DictReals = {}
        for a_id, qty in current_qty_assets.items():
            qty_assets[a_id] = [qty]

        if start == end:
            return dates, qty_assets

        # Transactions between start and end
        query = s.query(TransactionSplit)
        query = query.with_entities(
            TransactionSplit.date,
            TransactionSplit.asset_id,
            TransactionSplit._asset_qty_int,  # noqa: SLF001
            TransactionSplit._asset_qty_frac,  # noqa: SLF001
        )
        query = query.where(TransactionSplit.account_id == self.id_)
        query = query.where(TransactionSplit.date <= end)
        query = query.where(TransactionSplit.date > start)
        query = query.where(TransactionSplit.asset_id.is_not(None))
        query = query.order_by(TransactionSplit.date)

        for t_date, a_id, qty_int, qty_frac in query.all():
            t_date: datetime.date
            a_id: int
            qty_int: int
            qty_frac: Decimal

            while date < t_date:
                for k, v in current_qty_assets.items():
                    qty_assets[k].append(v)
                dates.append(date)
                date += datetime.timedelta(days=1)

            if a_id not in current_qty_assets:
                # Asset not added during initial value
                qty_assets[a_id] = [Decimal(0)] * len(dates)
                current_qty_assets[a_id] = qty_int + qty_frac
            else:
                current_qty_assets[a_id] += qty_int + qty_frac

        while date <= end:
            for k, v in current_qty_assets.items():
                qty_assets[k].append(v)
            dates.append(date)
            date += datetime.timedelta(days=1)

        return dates, qty_assets
