"""Account model for storing a financial account."""

from __future__ import annotations

import sqlalchemy
from sqlalchemy import event, ForeignKey, orm
from typing_extensions import override

from nummus import custom_types as t
from nummus.models.base import Base, Decimal6, Decimal18


class TransactionSplit(Base):
    """TransactionSplit model for storing an exchange of cash for an asset (or none).

    Every Transaction has at least one TransactionSplit.

    Attributes:
        id: TransactionSplit unique identifier
        uuid: TransactionSplit unique identifier
        amount: Amount amount of cash exchanged. Positive indicated Account
            increases in value (inflow)
        payee: Name of payee (for outflow)/payer (for inflow)
        description: Description of exchange
        tag: Unique tag linked across datasets
        category: Type of Transaction
        parent: Parent Transaction
        date: Date on which Transaction occurred
        locked: True only allows manually editing, False allows automatic changes
            (namely auto labeling field based on similar Transactions)
        account: Account that owns this Transaction
        asset: Asset exchanged for cash, primarily for instrument transactions
        asset_quantity: Number of units of Asset exchanged, Positive indicates
            Account gained Assets (inflow)
    """

    amount: t.ORMReal = orm.mapped_column(
        Decimal6,
        sqlalchemy.CheckConstraint(
            "amount != 0",
            "transaction_split.amount must be non-zero",
        ),
    )
    payee: t.ORMStrOpt
    description: t.ORMStrOpt
    tag: t.ORMStrOpt

    category_id: t.ORMInt = orm.mapped_column(ForeignKey("transaction_category.id_"))

    parent_id: t.ORMInt = orm.mapped_column(ForeignKey("transaction.id_"))
    date: t.ORMDate
    locked: t.ORMBool
    account_id: t.ORMInt = orm.mapped_column(ForeignKey("account.id_"))

    asset_id: t.ORMIntOpt = orm.mapped_column(ForeignKey("asset.id_"))
    _asset_qty_int: t.ORMIntOpt
    _asset_qty_frac: t.ORMRealOpt = orm.mapped_column(Decimal18)
    _asset_qty_int_unadjusted: t.ORMIntOpt
    _asset_qty_frac_unadjusted: t.ORMRealOpt = orm.mapped_column(Decimal18)

    @orm.validates("payee", "description", "tag")
    @override
    def validate_strings(self, key: str, field: str) -> str:
        return super().validate_strings(key, field)

    @override
    def __setattr__(self, name: str, value: t.Any) -> None:
        if name in ["parent_id", "date", "locked", "account_uuid", "account_id"]:
            msg = (
                "Call TransactionSplit.parent = Transaction. "
                "Do not set parent properties directly"
            )
            raise PermissionError(msg)
        super().__setattr__(name, value)

    @property
    def asset_quantity(self) -> t.Real:
        """Number of units of Asset exchanged.

        Positive indicates Account gained Assets (inflow), adjusted for splits.
        """
        if self._asset_qty_int is None:
            return None
        return self._asset_qty_int + self._asset_qty_frac

    @property
    def asset_quantity_unadjusted(self) -> t.Real:
        """Number of units of Asset exchanged.

        Positive indicates Account gained Assets (inflow), unadjusted for splits.
        """
        if self._asset_qty_int_unadjusted is None:
            return None
        return self._asset_qty_int_unadjusted + self._asset_qty_frac_unadjusted

    @asset_quantity_unadjusted.setter
    def asset_quantity_unadjusted(self, qty: t.Real) -> None:
        if qty is None:
            self._asset_qty_int_unadjusted = None
            self._asset_qty_frac_unadjusted = None
            self._asset_qty_int = None
            self._asset_qty_frac = None
            return
        i, f = divmod(qty, 1)
        i = int(i)
        self._asset_qty_int_unadjusted = i
        self._asset_qty_frac_unadjusted = f

        # Also set the adjusted with a 1x multiplier
        self._asset_qty_int = i
        self._asset_qty_frac = f

    def adjust_asset_quantity(self, multiplier: t.Real) -> None:
        """Set adjusted asset quantity.

        Args:
            multiplier: Adjusted = unadjusted * multiplier
        """
        qty = self.asset_quantity_unadjusted
        if qty is None:
            msg = "Cannot adjust non-asset transaction"
            raise ValueError(msg)
        i, f = divmod(qty * multiplier, 1)
        i = int(i)
        self._asset_qty_int = i
        self._asset_qty_frac = f

    @property
    def parent(self) -> Transaction:
        """Parent Transaction."""
        s = orm.object_session(self)
        return s.query(Transaction).where(Transaction.id_ == self.parent_id).first()

    @parent.setter
    def parent(self, parent: Transaction) -> None:
        if not isinstance(parent, Transaction):
            msg = "TransactionSplit.parent must be of type Transaction"
            raise TypeError(msg)
        if parent.id_ is None:
            self._parent_tmp = parent
            return
        super().__setattr__("parent_id", parent.id_)
        super().__setattr__("date", parent.date)
        super().__setattr__("locked", parent.locked)
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
        uuid: Transaction unique identifier
        account: Account that owns this Transaction
        date: Date on which Transaction occurred
        amount: Amount amount of cash exchanged. Positive indicated Account
            increases in value (inflow)
        statement: Text appearing on Account statement
        locked: True only allows manually editing, False allows automatic changes
            (namely auto labeling field based on similar Transactions)
        splits: List of TransactionSplits
    """

    account_id: t.ORMInt = orm.mapped_column(ForeignKey("account.id_"))

    date: t.ORMDate
    amount: t.ORMReal = orm.mapped_column(Decimal6)
    statement: t.ORMStr
    locked: t.ORMBool = orm.mapped_column(default=False)

    splits: orm.Mapped[list[TransactionSplit]] = orm.relationship()

    @orm.validates("statement")
    @override
    def validate_strings(self, key: str, field: str) -> str:
        return super().validate_strings(key, field)
