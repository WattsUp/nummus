"""Account model for storing a financial account
"""

from __future__ import annotations

import sqlalchemy
from sqlalchemy import ForeignKey, event, orm

from nummus import custom_types as t
from nummus.models.base import Base, Decimal6, Decimal18

ORMTxn = orm.Mapped["Transaction"]
ORMTxnList = orm.Mapped[t.List["Transaction"]]
ORMTxnOpt = orm.Mapped[t.Optional["Transaction"]]
ORMTxnSplit = orm.Mapped["TransactionSplit"]
ORMTxnSplitList = orm.Mapped[t.List["TransactionSplit"]]
ORMTxnSplitOpt = orm.Mapped[t.Optional["TransactionSplit"]]


class TransactionSplit(Base):
  """TransactionSplit model for storing an exchange of cash for an asset
  (or none)

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
      sqlalchemy.CheckConstraint("amount != 0",
                                 "transaction_split.amount must be non-zero"))
  payee: t.ORMStrOpt
  description: t.ORMStrOpt
  tag: t.ORMStrOpt

  category_id: t.ORMInt = orm.mapped_column(
      ForeignKey("transaction_category.id"))

  parent_id: t.ORMInt = orm.mapped_column(ForeignKey("transaction.id"))
  date: t.ORMDate
  locked: t.ORMBool
  account_id: t.ORMInt = orm.mapped_column(ForeignKey("account.id"))

  asset_id: t.ORMIntOpt = orm.mapped_column(ForeignKey("asset.id"))
  _asset_qty_int: t.ORMIntOpt
  _asset_qty_frac: t.ORMRealOpt = orm.mapped_column(Decimal18)
  _asset_qty_int_unadjusted: t.ORMIntOpt
  _asset_qty_frac_unadjusted: t.ORMRealOpt = orm.mapped_column(Decimal18)

  @orm.validates("payee", "description", "tag")
  def validate_strings(self, key: str, field: str) -> str:
    return super().validate_strings(key, field)

  def __setattr__(self, name: str, value: t.Any) -> None:
    if name in ["parent_id", "date", "locked", "account_uuid", "account_id"]:
      raise PermissionError("Call TransactionSplit.parent = Transaction. "
                            "Do not set parent properties directly")
    super().__setattr__(name, value)

  @property
  def asset_quantity(self) -> t.Real:
    """Number of units of Asset exchanged, Positive indicates
    Account gained Assets (inflow), adjusted for splits
    """
    if self._asset_qty_int is None:
      return None
    return self._asset_qty_int + self._asset_qty_frac

  @property
  def asset_quantity_unadjusted(self) -> t.Real:
    """Number of units of Asset exchanged, Positive indicates
    Account gained Assets (inflow), unadjusted for splits
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
    """Set adjusted asset quantity

    Args:
      multiplier: Adjusted = unadjusted * multiplier
    """
    qty = self.asset_quantity_unadjusted
    if qty is None:
      raise ValueError("Cannot adjust non-asset transaction")
    i, f = divmod(qty * multiplier, 1)
    i = int(i)
    self._asset_qty_int = i
    self._asset_qty_frac = f

  @property
  def parent(self) -> Transaction:
    """Parent Transaction
    """
    s = orm.object_session(self)
    return s.query(Transaction).where(Transaction.id == self.parent_id).first()

  @parent.setter
  def parent(self, parent: Transaction) -> None:
    if not isinstance(parent, Transaction):
      raise TypeError("TransactionSplit.parent must be of type Transaction")
    if parent.id is None:
      self._parent_tmp = parent
      return
    super().__setattr__("parent_id", parent.id)
    super().__setattr__("date", parent.date)
    super().__setattr__("locked", parent.locked)
    super().__setattr__("account_id", parent.account_id)


@event.listens_for(TransactionSplit, "before_insert")
def before_insert_transaction_split(
    mapper: orm.Mapper,  # pylint: disable=unused-argument
    connection: sqlalchemy.Connection,  # pylint: disable=unused-argument
    target: TransactionSplit) -> None:
  """Handle event before insert of TransactionSplit

  Args:
    target: TransactionSplit being inserted
  """
  # If TransactionSplit has parent_tmp set, move it to real parent
  if hasattr(target, "_parent_tmp"):
    target.parent = target._parent_tmp  # pylint: disable=protected-access
    delattr(target, "_parent_tmp")


class Transaction(Base):
  """Transaction model for storing an exchange of cash for an asset (or none)

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
  account_id: t.ORMInt = orm.mapped_column(ForeignKey("account.id"))

  date: t.ORMDate
  amount: t.ORMReal = orm.mapped_column(Decimal6)
  statement: t.ORMStr
  locked: t.ORMBool = orm.mapped_column(default=False)

  splits: ORMTxnSplitList = orm.relationship()

  @orm.validates("statement")
  def validate_strings(self, key: str, field: str) -> str:
    return super().validate_strings(key, field)
