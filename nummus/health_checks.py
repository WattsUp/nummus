"""Portfolio health checks."""

from __future__ import annotations

import datetime
import textwrap
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy
from typing_extensions import override

from nummus import exceptions as exc
from nummus import utils
from nummus.models import (
    Account,
    Asset,
    AssetValuation,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from nummus import custom_types as t
    from nummus import portfolio

# TODO (WattsUp): Add a silence mechanism to hush false positives


class Base(ABC):
    """Base health check class."""

    _NAME: str = ""
    _DESC: str = ""
    _SEVERE: bool = False

    def __init__(self) -> None:
        """Initialize Base health check."""
        super().__init__()
        self._issues: t.Strings = []

    @property
    def name(self) -> str:
        """Health check name."""
        return self._NAME

    @property
    def description(self) -> str:
        """Health check description."""
        return self._DESC

    @property
    def issues(self) -> t.Strings:
        """List of issues this check found."""
        return self._issues

    @property
    def any_issues(self) -> bool:
        """True if check found any issues."""
        return len(self._issues) != 0

    @property
    def is_severe(self) -> bool:
        """True if issues are severe."""
        return self._SEVERE

    @abstractmethod
    def test(self, p: portfolio.Portfolio) -> None:
        """Run the health check on a portfolio.

        Args:
            p: Portfolio to test
        """
        raise NotImplementedError


class DatabaseIntegrity(Base):
    """Checks for issues in the underlying SQL database."""

    _NAME = "Database integrity"
    _DESC = "Checks for issues in the underlying SQL database."
    _SEVERE = True

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        with p.get_session() as s:
            result = s.execute(sqlalchemy.text("PRAGMA integrity_check"))
            rows = [row for row, in result.all()]
            if len(rows) != 1 or rows[0] != "ok":
                self._issues.extend(rows)


class UnbalancedTransfers(Base):
    """Checks for non-zero net transfers."""

    _NAME = "Unbalanced transfers"
    _DESC = textwrap.dedent("""\
        Transfers move money between accounts so none should be lost.
        If there are transfer fees, add that as a separate transaction.""")
    _SEVERE = True

    _CATEGORY_NAME = "Transfers"

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        with p.get_session() as s:
            try:
                cat_transfers_id: int = (
                    s.query(TransactionCategory.id_)
                    .where(TransactionCategory.name == self._CATEGORY_NAME)
                    .one()[0]
                )
            except exc.NoResultFound as e:
                msg = f"Category {self._CATEGORY_NAME} not found"
                raise exc.ProtectedObjectNotFoundError(msg) from e

            accounts = Account.map_name(s)
            acct_len = max(len(acct) for acct in accounts.values())
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.account_id,
                    TransactionSplit.date_ord,
                    TransactionSplit.amount,
                )
                .where(TransactionSplit.category_id == cat_transfers_id)
                .order_by(TransactionSplit.date_ord)
            )
            current_date_ord = 0
            total = Decimal(0)
            current_splits: list[tuple[str, Decimal]] = []
            for a_id, date_ord, amount in query.yield_per(YIELD_PER):
                a_id: int
                date_ord: int
                amount: Decimal
                if date_ord != current_date_ord:
                    if total != 0:
                        date = datetime.date.fromordinal(current_date_ord)
                        self._issues.append(
                            f"{date}: Sum of transfers on this day are non-zero",
                        )

                        # Remove any that are exactly equal since those are probably
                        # balanced amongst themselves
                        i = 0
                        # Do need to run len(current_splits) every time since it will
                        # change length during iteration
                        while i < len(current_splits):
                            # Look for inverse amount in remaining splits
                            v_search = -current_splits[i][1]
                            found_any = False
                            for ii in range(i + 1, len(current_splits)):
                                if v_search == current_splits[ii][1]:
                                    # If found, pop both positive and negative ones
                                    current_splits.pop(ii)
                                    current_splits.pop(i)
                                    found_any = True
                                    break
                            # Don't increase iterator if popped any since there is a new
                            # value at i
                            if not found_any:
                                i += 1

                        current_splits = sorted(
                            current_splits,
                            key=lambda item: (item[0], item[1]),
                        )
                        self._issues.extend(
                            f"  {acct:{acct_len}}: "
                            f"{utils.format_financial(amount, plus=True):>14}"
                            for acct, amount in current_splits
                        )

                    current_date_ord = date_ord
                    total = Decimal(0)
                    current_splits = []

                total += amount
                current_splits.append((accounts[a_id], amount))


class UnbalancedCreditCardPayments(UnbalancedTransfers):
    """Checks for non-zero net credit card payments."""

    _NAME = "Unbalanced credit card payments"
    _DESC = textwrap.dedent("""\
        Credit card payments are transfers so none should be lost.
        If there interest incurred, add that as a separate transaction.""")
    _SEVERE = True

    _CATEGORY_NAME = "Credit Card Payments"


class MissingAssetValuations(Base):
    """Checks if an asset is held without any valuations."""

    _NAME = "Missing asset valuations"
    _DESC = "Checks if an asset is held without any valuations"
    _SEVERE = True

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        with p.get_session() as s:
            assets = Asset.map_name(s)

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.asset_id,
                    sqlalchemy.func.min(TransactionSplit.date_ord),
                )
                .where(TransactionSplit.asset_id.isnot(None))
                .group_by(TransactionSplit.asset_id)
            )
            first_date_ords: dict[int, int] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

            query = (
                s.query(AssetValuation)
                .with_entities(
                    AssetValuation.asset_id,
                    sqlalchemy.func.min(AssetValuation.date_ord),
                )
                .group_by(AssetValuation.asset_id)
            )
            first_valuations: dict[int, int] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

            for a_id, date_ord in first_date_ords.items():
                date_ord_v = first_valuations.get(a_id)
                if date_ord_v is None:
                    msg = f"{assets[a_id]} has no valuations"
                    self._issues.append(msg)
                elif date_ord < date_ord_v:
                    msg = (
                        f"{assets[a_id]} has first transaction on"
                        f" {datetime.date.fromordinal(date_ord)} before first valuation"
                        f" on {datetime.date.fromordinal(date_ord_v)}"
                    )
                    self._issues.append(msg)


class OutlierAssetPrice(Base):
    """Checks if an asset was bought/sold at an outlier price."""

    _NAME = "Outlier asset price"
    _DESC = textwrap.dedent("""\
        Checks if an asset was bought/sold at an outlier price.
        Most likely an issue with asset splits.""")
    _SEVERE = True

    # 50% would miss 2:1 or 1:2 splits
    _RANGE = Decimal("0.4")

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        today = datetime.date.today()
        today_ord = today.toordinal()
        with p.get_session() as s:
            assets = Asset.map_name(s)
            asset_len = max(len(a) for a in assets.values())

            start_ord = (
                s.query(sqlalchemy.func.min(TransactionSplit.date_ord))
                .where(TransactionSplit.asset_id.isnot(None))
                .scalar()
            )
            if start_ord is None:
                # No asset transactions at all
                return
            asset_valuations = Asset.get_value_all(s, start_ord, today_ord)

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.date_ord,
                    TransactionSplit.asset_id,
                    TransactionSplit.amount,
                    TransactionSplit._asset_qty_int,  # noqa: SLF001
                    TransactionSplit._asset_qty_frac,  # noqa:SLF001
                )
                .where(TransactionSplit.asset_id.isnot(None))
            )
            for date_ord, a_id, amount, qty_i, qty_f in query.yield_per(YIELD_PER):
                date_ord: int
                a_id: int
                amount: t.Real
                qty_i: int
                qty_f: t.Real
                qty = qty_i + qty_f
                if qty == 0:
                    continue

                # Transaction asset price
                t_price = -amount / qty

                v_price = asset_valuations[a_id][date_ord - start_ord]
                v_price_low = v_price * (1 - self._RANGE)
                v_price_high = v_price * (1 + self._RANGE)
                if v_price is None:
                    msg = (
                        f"{datetime.date.fromordinal(date_ord)}:"
                        f" {assets[a_id]:{asset_len}} has no valuations before"
                        " transaction on"
                    )
                    self._issues.append(msg)
                elif t_price < v_price_low:
                    msg = (
                        f"{datetime.date.fromordinal(date_ord)}:"
                        f" {assets[a_id]:{asset_len}} was traded at"
                        f" {utils.format_financial(t_price)} which is below valuation"
                        f" of {utils.format_financial(v_price)}"
                    )
                    self._issues.append(msg)
                elif t_price > v_price_high:
                    msg = (
                        f"{datetime.date.fromordinal(date_ord)}:"
                        f" {assets[a_id]:{asset_len}} was bought at"
                        f" {utils.format_financial(t_price)} which is above valuation"
                        f" of {utils.format_financial(v_price)}"
                    )
                    self._issues.append(msg)


class Typos(Base):
    """Checks for very similar fields and common typos."""

    _NAME = "Typos"
    _DESC = "Checks for very similar fields and common typos."
    _SEVERE = False

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        self._issues = []
        raise NotImplementedError


class UnlockedTransactions(Base):
    """Checks for unlocked transactions."""

    _NAME = "Unlocked transactions"
    _DESC = textwrap.dedent("""\
        Locked transactions have been manually verified.
        Any unlocked transactions should be validated and locked.""")
    _SEVERE = False

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        with p.get_session() as s:
            accounts = Account.map_name(s)
            acct_len = max(len(acct) for acct in accounts.values())

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.date_ord,
                    TransactionSplit.account_id,
                    TransactionSplit.payee,
                    TransactionSplit.amount,
                )
                .where(TransactionSplit.locked.is_(False))
            )
            for date_ord, acct_id, payee, amount in query.yield_per(YIELD_PER):
                date_ord: int
                acct_id: int
                payee: str
                amount: t.Real

                msg = (
                    f"{datetime.date.fromordinal(date_ord)} -"
                    f" {accounts[acct_id]:{acct_len}}:"
                    f" {utils.format_financial(amount)} to {payee} is unlocked"
                )
                self._issues.append(msg)


# List of all checks to test
CHECKS: list[type[Base]] = [
    DatabaseIntegrity,
    UnbalancedTransfers,
    UnbalancedCreditCardPayments,
    MissingAssetValuations,
    OutlierAssetPrice,
    # Typos,
    UnlockedTransactions,
    # Negative cash when buying assets, buying on margin needs a silence
    # Dividends and investment fees not assigned to an asset
    # Interest assigned to an asset
    # null payee or description or uncategorized
]
