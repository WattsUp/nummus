"""Account model for storing a financial account."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import orm
from typing_extensions import override

from nummus import exceptions as exc
from nummus import utils
from nummus.models.asset import Asset
from nummus.models.base import Base, BaseEnum, ORMBool, ORMStr, ORMStrOpt, YIELD_PER
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import TransactionCategory

if TYPE_CHECKING:
    from collections.abc import Iterable


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

    name: ORMStr
    number: ORMStrOpt
    institution: ORMStr
    category: orm.Mapped[AccountCategory]
    closed: ORMBool
    budgeted: ORMBool

    @orm.validates("name", "number", "institution")
    @override
    def validate_strings(self, key: str, field: str | None) -> str | None:
        return super().validate_strings(key, field)

    @property
    def opened_on_ord(self) -> int | None:
        """Date ordinal of first Transaction."""
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError
        query = s.query(sqlalchemy.func.min(Transaction.date_ord)).where(
            Transaction.account_id == self.id_,
        )
        return query.scalar()

    @property
    def updated_on_ord(self) -> int | None:
        """Date ordinal of latest Transaction."""
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError
        query = s.query(sqlalchemy.func.max(Transaction.date_ord)).where(
            Transaction.account_id == self.id_,
        )
        return query.scalar()

    @classmethod
    def get_value_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: Iterable[int] | None = None,
    ) -> tuple[
        dict[int, list[Decimal]],
        dict[int, list[Decimal]],
        dict[int, list[Decimal]],
    ]:
        """Get the value of all Accounts from start to end date.

        Args:
            s: SQL session to use
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)
            ids: Limit results to specific Accounts by ID

        Returns:
            Also returns profit & loss for each Account
            Also returns value by Assets, Accounts holding same Assets will sum
            (
                dict{Account.id_: list[values]},
                dict{Account.id_: list[profit]},
                dict{Asset.id_: list[values]},
            )
        """
        n = end_ord - start_ord + 1

        cash_flow_accounts: dict[int, list[Decimal | None]]
        if ids is not None:
            cash_flow_accounts = {acct_id: [None] * n for acct_id in ids}
        else:
            cash_flow_accounts = {
                acct_id: [None] * n for acct_id, in s.query(Account.id_).all()
            }
        cost_basis_accounts: dict[int, list[Decimal | None]]
        cost_basis_accounts = {acct_id: [None] * n for acct_id in cash_flow_accounts}

        # Profit = Interest + dividends + rewards + change in asset value - fees
        # Dividends, fees, and change in value can be assigned to an asset
        # Change in value = current value - basis
        # Get list of transaction categories not included in cost basis
        query = s.query(TransactionCategory.id_).where(
            TransactionCategory.is_profit_loss.is_(True),
        )
        cost_basis_skip_ids = {t_cat_id for t_cat_id, in query.all()}

        # Get Account cash value on start date
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.account_id,
                sqlalchemy.func.sum(TransactionSplit.amount),
            )
            .where(TransactionSplit.date_ord <= start_ord)
            .group_by(TransactionSplit.account_id)
        )
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))
        for acct_id, iv in query.all():
            acct_id: int
            iv: Decimal
            cash_flow_accounts[acct_id][0] = iv

        # Calculate cost basis on first day
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.account_id,
                sqlalchemy.func.sum(TransactionSplit.amount),
            )
            .where(
                TransactionSplit.date_ord == start_ord,
                TransactionSplit.category_id.in_(cost_basis_skip_ids),
            )
            .group_by(TransactionSplit.account_id)
        )
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))
        for acct_id, iv in query.all():
            acct_id: int
            iv: Decimal
            cost_basis_accounts[acct_id][0] = -iv

        if start_ord != end_ord:
            # Get cash_flow on each day between start and end
            # Not Account.get_cash_flow because being categorized doesn't matter and
            # slows it down
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.account_id,
                    TransactionSplit.date_ord,
                    TransactionSplit.amount,
                    TransactionSplit.category_id,
                )
                .where(
                    TransactionSplit.date_ord <= end_ord,
                    TransactionSplit.date_ord > start_ord,
                )
            )
            if ids is not None:
                query = query.where(TransactionSplit.account_id.in_(ids))

            for acct_id, date_ord, amount, t_cat_id in query.yield_per(YIELD_PER):
                acct_id: int
                date_ord: int
                amount: Decimal
                t_cat_id: int

                i = date_ord - start_ord

                v = cash_flow_accounts[acct_id][i]
                cash_flow_accounts[acct_id][i] = amount if v is None else v + amount

                if t_cat_id not in cost_basis_skip_ids:
                    v = cost_basis_accounts[acct_id][i]
                    cost_basis_accounts[acct_id][i] = (
                        amount if v is None else v + amount
                    )

        # Get assets for all Accounts
        assets_accounts = cls.get_asset_qty_all(
            s,
            start_ord,
            end_ord,
            list(cash_flow_accounts.keys()),
        )

        # Get day one asset transactions to add to profit & loss
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.account_id,
                TransactionSplit.asset_id,
                TransactionSplit.asset_quantity,
            )
            .where(
                TransactionSplit.asset_id.isnot(None),
                TransactionSplit.date_ord == start_ord,
            )
        )
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))
        assets_day_zero: dict[int, dict[int, Decimal]] = {
            acct_id: {} for acct_id in cash_flow_accounts
        }
        for acct_id, a_id, qty in query.yield_per(YIELD_PER):
            acct_id: int
            a_id: int
            qty: Decimal
            try:
                assets_day_zero[acct_id][a_id] += qty
            except KeyError:
                assets_day_zero[acct_id][a_id] = qty

        # Skip assets with zero quantity
        a_ids: set[int] = set()
        for assets in assets_accounts.values():
            for a_id, quantities in list(assets.items()):
                if not any(quantities):
                    # Remove asset from account
                    assets.pop(a_id)
                else:
                    a_ids.add(a_id)
        for assets in assets_day_zero.values():
            for a_id, qty in list(assets.items()):
                if qty == 0:
                    assets.pop(a_id)
                else:
                    a_ids.add(a_id)

        asset_prices = Asset.get_value_all(s, start_ord, end_ord, a_ids)

        acct_values: dict[int, list[Decimal]] = {}
        asset_values: dict[int, list[Decimal]] = {
            a_id: [Decimal(0)] * n for a_id in a_ids
        }
        for acct_id, cash_flow in cash_flow_accounts.items():
            assets = assets_accounts[acct_id]
            cash = utils.integrate(cash_flow)

            if len(assets) == 0:
                acct_values[acct_id] = cash

                continue

            summed = cash
            for a_id, quantities in assets.items():
                price = asset_prices[a_id]
                asset_value = asset_values[a_id]
                for i, qty in enumerate(quantities):
                    if qty:
                        v = price[i] * qty
                        asset_value[i] += v
                        summed[i] += v

            acct_values[acct_id] = summed

        acct_profit: dict[int, list[Decimal]] = {}
        for acct_id, values in acct_values.items():
            cost_basis_flow = cost_basis_accounts[acct_id]
            v = cost_basis_flow[0]
            v = values[0] if v is None else v + values[0]

            # Reduce the cost basis on day one to add the asset value to profit
            for a_id, qty in assets_day_zero[acct_id].items():
                v -= qty * asset_prices[a_id][0]

            cost_basis_flow[0] = v

            cost_basis = utils.integrate(cost_basis_flow)
            profit = [v - cb for v, cb in zip(values, cost_basis, strict=True)]
            acct_profit[acct_id] = profit

        return acct_values, acct_profit, asset_values

    def get_value(
        self,
        start_ord: int,
        end_ord: int,
    ) -> tuple[list[Decimal], list[Decimal], dict[int, list[Decimal]]]:
        """Get the value of Account from start to end date.

        Args:
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            Also returns profit & loss
            Also returns value by Asset
            (list[values], list[profit], dict{Asset.id_: list[values]})

        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        # Not reusing get_value_all is faster by ~2ms,
        # not worth maintaining two almost identical implementations

        accts, profit, assets = self.get_value_all(s, start_ord, end_ord, [self.id_])
        return accts[self.id_], profit[self.id_], assets

    @classmethod
    def get_cash_flow_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: Iterable[int] | None = None,
    ) -> dict[int, list[Decimal]]:
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

        categories: dict[int, list[Decimal]] = {
            cat_id: [Decimal(0)] * n
            for cat_id, in s.query(TransactionCategory.id_).all()
        }

        # Transactions between start and end
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.date_ord,
                TransactionSplit.amount,
                TransactionSplit.category_id,
            )
            .where(
                TransactionSplit.date_ord <= end_ord,
                TransactionSplit.date_ord >= start_ord,
            )
        )
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))

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
    ) -> dict[int, list[Decimal]]:
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
        ids: Iterable[int] | None = None,
    ) -> dict[int, dict[int, list[Decimal]]]:
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

        iv_accounts: dict[int, dict[int, Decimal]] = {}
        if ids is not None:
            iv_accounts = {acct_id: {} for acct_id in ids}
        else:
            iv_accounts = {acct_id: {} for acct_id, in s.query(Account.id_).all()}

        # Get Asset quantities on start date
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.account_id,
                TransactionSplit.asset_id,
                sqlalchemy.func.sum(TransactionSplit.asset_quantity),
            )
            .where(
                TransactionSplit.asset_id.is_not(None),
                TransactionSplit.date_ord <= start_ord,
            )
            .group_by(
                TransactionSplit.account_id,
                TransactionSplit.asset_id,
            )
        )
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))

        for acct_id, a_id, qty in query.yield_per(YIELD_PER):
            acct_id: int
            a_id: int
            qty: Decimal
            try:
                iv_accounts[acct_id][a_id] = qty
            except KeyError:  # pragma: no cover
                # All accounts already created in iv_accounts
                iv_accounts[acct_id] = {a_id: qty}

        # Daily delta in qty
        deltas_accounts: dict[int, dict[int, list[Decimal | None]]] = {}
        for acct_id, iv in iv_accounts.items():
            deltas: dict[int, list[Decimal | None]] = {}
            for a_id, v in iv.items():
                deltas[a_id] = [None] * n
                deltas[a_id][0] = v
            deltas_accounts[acct_id] = deltas

        if start_ord != end_ord:
            # Transactions between start and end
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.date_ord,
                    TransactionSplit.account_id,
                    TransactionSplit.asset_id,
                    TransactionSplit.asset_quantity,
                )
                .where(
                    TransactionSplit.date_ord <= end_ord,
                    TransactionSplit.date_ord > start_ord,
                    TransactionSplit.asset_id.is_not(None),
                )
                .order_by(TransactionSplit.account_id)
            )
            if ids is not None:
                query = query.where(TransactionSplit.account_id.in_(ids))

            current_acct_id = None
            deltas = {}

            for date_ord, acct_id, a_id, qty in query.yield_per(YIELD_PER):
                date_ord: int
                acct_id: int
                a_id: int
                qty: Decimal

                i = date_ord - start_ord

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
        qty_accounts: dict[int, dict[int, list[Decimal]]] = {}
        for acct_id, deltas in deltas_accounts.items():
            qty_assets: dict[int, list[Decimal]] = {}
            for a_id, delta in deltas.items():
                qty_assets[a_id] = utils.integrate(delta)
            qty_accounts[acct_id] = qty_assets

        return qty_accounts

    def get_asset_qty(
        self,
        start_ord: int,
        end_ord: int,
    ) -> dict[int, list[Decimal]]:
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

    @classmethod
    def get_profit_by_asset_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: Iterable[int] | None = None,
    ) -> dict[int, Decimal]:
        """Get the profit of Assets on end_date since start_ord.

        Args:
            s: SQL session to use
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)
            ids: Limit results to specific Accounts by ID

        Returns:
            dict{Asset.id_: profit}
        """
        # Get Asset quantities on start date
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.asset_id,
                sqlalchemy.func.sum(TransactionSplit.asset_quantity),
            )
            .where(
                TransactionSplit.asset_id.is_not(None),
                TransactionSplit.date_ord < start_ord,
            )
            .group_by(TransactionSplit.asset_id)
        )
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))

        initial_qty: dict[int, Decimal] = {
            a_id: qty for a_id, qty in query.yield_per(YIELD_PER) if qty != 0
        }

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.asset_id,
                TransactionSplit.asset_quantity,
                TransactionSplit.amount,
            )
            .where(
                TransactionSplit.asset_id.is_not(None),
                TransactionSplit.date_ord >= start_ord,
                TransactionSplit.date_ord <= end_ord,
            )
        )
        if ids is not None:
            query = query.where(TransactionSplit.account_id.in_(ids))

        cost_basis: dict[int, Decimal] = {a_id: Decimal(0) for a_id in initial_qty}
        end_qty: dict[int, Decimal] = dict(initial_qty)
        for a_id, qty, amount in query.yield_per(YIELD_PER):
            a_id: int
            qty: Decimal
            amount: Decimal
            try:
                end_qty[a_id] += qty
                cost_basis[a_id] += amount
            except KeyError:
                end_qty[a_id] = qty
                cost_basis[a_id] = amount
        a_ids = set(end_qty)

        initial_price = Asset.get_value_all(s, start_ord, start_ord, ids=a_ids)
        end_price = Asset.get_value_all(s, end_ord, end_ord, ids=a_ids)

        profits: dict[int, Decimal] = {}
        for a_id in a_ids:
            i_value = initial_qty.get(a_id, 0) * initial_price[a_id][0]
            e_value = end_qty[a_id] * end_price[a_id][0]

            profit = e_value - i_value + cost_basis[a_id]
            profits[a_id] = profit

        return profits

    def get_profit_by_asset(
        self,
        start_ord: int,
        end_ord: int,
    ) -> dict[int, Decimal]:
        """Get the profit of Assets on end_date since start_ord.

        Args:
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            dict{Asset.id_: profit}
        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        return self.get_profit_by_asset_all(s, start_ord, end_ord, [self.id_])

    @classmethod
    def ids(cls, s: orm.Session, category: AccountCategory) -> set[int]:
        """Get Account ids for a specific category.

        Args:
            s: SQL session to use
            category: AccountCategory to filter

        Returns:
            set{Account.id_}
        """
        query = s.query(Account.id_).where(Account.category == category)
        return {acct_id for acct_id, in query.all()}
