"""Account model for storing a financial account."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import event, ForeignKey, orm
from typing_extensions import override

from nummus import exceptions as exc
from nummus.models.base import (
    Base,
    Decimal6,
    Decimal9,
    ORMBool,
    ORMInt,
    ORMIntOpt,
    ORMReal,
    ORMRealOpt,
    ORMStr,
    ORMStrOpt,
)

if TYPE_CHECKING:
    from decimal import Decimal


class TransactionSplit(Base):
    """TransactionSplit model for storing an exchange of cash for an asset (or none).

    Every Transaction has at least one TransactionSplit.

    Attributes:
        id: TransactionSplit unique identifier
        uri: TransactionSplit unique identifier
        amount: Amount amount of cash exchanged. Positive indicated Account
            increases in value (inflow)
        payee: Name of payee (for outflow)/payer (for inflow)
        description: Description of exchange
        tag: Unique tag linked across datasets
        category: Type of Transaction
        parent: Parent Transaction
        date_ord: Date ordinal on which Transaction occurred
        locked: True only allows manually editing, False allows automatic changes
            (namely auto labeling field based on similar Transactions)
        linked: True when transaction has been imported from a bank source, False
            indicates transaction was manually created
        account: Account that owns this Transaction
        asset: Asset exchanged for cash, primarily for instrument transactions
        asset_quantity: Number of units of Asset exchanged, Positive indicates
            Account gained Assets (inflow)
    """

    __table_id__ = 0x80000000

    amount: ORMReal = orm.mapped_column(
        Decimal6,
        sqlalchemy.CheckConstraint(
            "amount != 0",
            "transaction_split.amount must be non-zero",
        ),
    )
    payee: ORMStrOpt
    description: ORMStrOpt
    tag: ORMStrOpt

    category_id: ORMInt = orm.mapped_column(ForeignKey("transaction_category.id_"))

    parent_id: ORMInt = orm.mapped_column(ForeignKey("transaction.id_"))
    date_ord: ORMInt
    locked: ORMBool
    linked: ORMBool
    account_id: ORMInt = orm.mapped_column(ForeignKey("account.id_"))

    asset_id: ORMIntOpt = orm.mapped_column(ForeignKey("asset.id_"))
    asset_quantity: ORMRealOpt = orm.mapped_column(Decimal9)
    _asset_qty_unadjusted: ORMRealOpt = orm.mapped_column(Decimal9)

    @orm.validates("payee", "description", "tag")
    @override
    def validate_strings(self, key: str, field: str | None) -> str | None:
        return super().validate_strings(key, field)

    @orm.validates("amount", "asset_quantity", "_asset_qty_unadjusted")
    @override
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        return super().validate_decimals(key, field)

    @override
    def __setattr__(self, name: str, value: object) -> None:
        if name in ["parent_id", "date", "locked", "linked", "account_id"]:
            msg = (
                "Call TransactionSplit.parent = Transaction. "
                "Do not set parent properties directly"
            )
            raise exc.ParentAttributeError(msg)
        super().__setattr__(name, value)

    @property
    def asset_quantity_unadjusted(self) -> Decimal | None:
        """Number of units of Asset exchanged.

        Positive indicates Account gained Assets (inflow), unadjusted for splits.
        """
        return self._asset_qty_unadjusted

    @asset_quantity_unadjusted.setter
    def asset_quantity_unadjusted(self, qty: Decimal | None) -> None:
        if qty is None:
            self._asset_qty_unadjusted = None
            self.asset_quantity = None
            return
        self._asset_qty_unadjusted = qty

        # Also set adjusted quantity with 1x multiplier
        self.asset_quantity = qty

    def adjust_asset_quantity(self, multiplier: Decimal) -> None:
        """Set adjusted asset quantity.

        Args:
            multiplier: Adjusted = unadjusted * multiplier
        """
        qty = self.asset_quantity_unadjusted
        if qty is None:
            raise exc.NonAssetTransactionError
        self.asset_quantity = qty * multiplier

    @property
    def parent(self) -> Transaction:
        """Parent Transaction."""
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError
        query = s.query(Transaction).where(Transaction.id_ == self.parent_id)
        return query.one()

    @parent.setter
    def parent(self, parent: Transaction) -> None:
        if not isinstance(parent, Transaction):
            msg = "TransactionSplit.parent must be of type Transaction"
            raise TypeError(msg)
        if parent.id_ is None:
            self._parent_tmp = parent
            return
        super().__setattr__("parent_id", parent.id_)
        super().__setattr__("date_ord", parent.date_ord)
        super().__setattr__("locked", parent.locked)
        super().__setattr__("linked", parent.linked)
        super().__setattr__("account_id", parent.account_id)


@event.listens_for(TransactionSplit, "before_insert")
def before_insert_transaction_split(
    mapper: orm.Mapper,  # noqa: ARG001
    connection: sqlalchemy.Connection,  # noqa: ARG001
    target: TransactionSplit,
) -> None:
    """Handle event before insert of TransactionSplit.

    Args:
        mapper: Unused
        connection: Unused
        target: TransactionSplit being inserted
    """
    # If TransactionSplit has parent_tmp set, move it to real parent
    if hasattr(target, "_parent_tmp"):
        target.parent = target._parent_tmp  # noqa: SLF001
        delattr(target, "_parent_tmp")


class Transaction(Base):
    """Transaction model for storing an exchange of cash for an asset (or none).

    Every Transaction has at least one TransactionSplit.

    Attributes:
        id: Transaction unique identifier
        uri: Transaction unique identifier
        account: Account that owns this Transaction
        date_ord: Date ordinal on which Transaction occurred
        amount: Amount amount of cash exchanged. Positive indicated Account
            increases in value (inflow)
        statement: Text appearing on Account statement
        locked: True only allows manually editing, False allows automatic changes
            (namely auto labeling field based on similar Transactions)
        linked: True when transaction has been imported from a bank source, False
            indicates transaction was manually created
        splits: List of TransactionSplits
    """

    __table_id__ = 0x90000000

    account_id: ORMInt = orm.mapped_column(ForeignKey("account.id_"))

    date_ord: ORMInt
    amount: ORMReal = orm.mapped_column(Decimal6)
    statement: ORMStr
    locked: ORMBool = orm.mapped_column(default=False)
    linked: ORMBool = orm.mapped_column(default=False)

    similar_txn_id: ORMIntOpt = orm.mapped_column(ForeignKey("transaction.id_"))

    splits: orm.Mapped[list[TransactionSplit]] = orm.relationship()

    # TODO (WattsUp): Add a constraint so unlinked transactions cannot be locked

    @orm.validates("statement")
    @override
    def validate_strings(self, key: str, field: str | None) -> str | None:
        return super().validate_strings(key, field)

    @orm.validates("amount")
    @override
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        return super().validate_decimals(key, field)
