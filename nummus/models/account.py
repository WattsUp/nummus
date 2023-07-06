"""Account model for storing a financial account
"""

from __future__ import annotations
import typing as t

import datetime

import sqlalchemy
from sqlalchemy import orm

from nummus.models import base, asset

Dates = t.List[datetime.date]
Values = t.List[float]


class TransactionCategory(base.BaseEnum):
  """Categories of Transactions
  """
  HOME = 1
  FOOD = 2
  SHOPPING = 3
  HOBBIES = 4
  SERVICES = 5
  TRAVEL = 6
  INCOME = 7
  INSTRUMENT = 8
  TRANSFER = 9


class TransactionSplit(base.Base):
  """TransactionSplit model for storing an exchange of cash for an asset
  (or none)

  Every Transaction has at least one TransactionSplit.

  Attributes:
    uuid: TransactionSplit unique identifier
    account: Account that owns this Transaction
    date: Date on which Transaction occurred
    total: Total amount of cash exchanged. Positive indicated Account
      increases in value (inflow)
    sales_tax: Amount of sales tax paid on Transaction, always negative
    payee: Name of payee (for outflow)/payer (for inflow)
    description: Description of exchange
    category: Type of Transaction
    subcategory: Subcategory of Transaction type
    tag: Unique tag linked across datasets
    parent: Parent Transaction
    asset: Asset exchanged for cash, primarily for instrument transactions
    asset_quantity: Number of units of Asset exchanged, Positive indicates
      Account gained Assets (inflow)
    locked: True only allows manually editing, False allows automatic changes
      (namely auto labeling field based on similar Transactions)
    is_split: True if part of a spit Transaction
  """

  _PROPERTIES_DEFAULT = [
      "uuid", "account_uuid", "date", "total", "sales_tax", "payee",
      "description", "category", "subcategory", "tag", "parent_uuid",
      "asset_uuid", "asset_quantity", "locked", "is_split"
  ]

  total: orm.Mapped[float]
  sales_tax: orm.Mapped[t.Optional[float]]
  payee: orm.Mapped[t.Optional[str]]
  description: orm.Mapped[t.Optional[str]]
  category: orm.Mapped[t.Optional[TransactionCategory]]
  subcategory: orm.Mapped[t.Optional[str]]
  tag: orm.Mapped[t.Optional[str]]

  parent_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("transaction.id"))
  parent: orm.Mapped[Transaction] = orm.relationship(back_populates="splits")

  asset_id: orm.Mapped[t.Optional[int]] = orm.mapped_column(
      sqlalchemy.ForeignKey("asset.id"))
  asset: orm.Mapped[asset.Asset] = orm.relationship()

  asset_quantity: orm.Mapped[t.Optional[float]]

  @property
  def parent_uuid(self) -> str:
    """UUID of parent
    """
    return self.parent.uuid

  @property
  def asset_uuid(self) -> str:
    """UUID of asset
    """
    if self.asset is None:
      return None
    return self.asset.uuid

  @property
  def account_uuid(self) -> str:
    """UUID of account
    """
    return self.parent.account_uuid

  @property
  def date(self) -> datetime.date:
    """Date on which Transaction occurred
    """
    return self.parent.date

  @property
  def locked(self) -> bool:
    """True only allows manually editing, False allows automatic changes
    (namely auto labeling field based on similar Transactions)
    """
    return self.parent.locked

  @property
  def is_split(self) -> bool:
    """True if part of a split Transaction
    """
    return self.parent.is_split


class Transaction(base.Base):
  """Transaction model for storing an exchange of cash for an asset (or none)

  Every Transaction has at least one TransactionSplit.

  Attributes:
    uuid: Transaction unique identifier
    account: Account that owns this Transaction
    date: Date on which Transaction occurred
    total: Total amount of cash exchanged. Positive indicated Account
      increases in value (inflow)
    statement: Text appearing on Account statement
    locked: True only allows manually editing, False allows automatic changes
      (namely auto labeling field based on similar Transactions)
    splits: List of TransactionSplits
    is_split: len(splits) > 1
  """

  _PROPERTIES_DEFAULT = [
      "uuid", "account_uuid", "date", "total", "statement", "locked", "splits",
      "is_split"
  ]

  account_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("account.id"))
  account: orm.Mapped[Account] = orm.relationship(back_populates="transactions")

  date: orm.Mapped[datetime.date]
  total: orm.Mapped[float]
  statement: orm.Mapped[str]
  locked: orm.Mapped[bool] = orm.mapped_column(default=False)

  splits: orm.Mapped[t.List[TransactionSplit]] = orm.relationship(
      back_populates="parent")

  @property
  def account_uuid(self) -> str:
    """UUID of account
    """
    return self.account.uuid

  @property
  def is_split(self) -> bool:
    """True if more than one TransactionSplit
    """
    return len(self.splits) > 1


class AccountCategory(base.BaseEnum):
  """Categories of Accounts
  """
  CASH = 1
  CREDIT = 2
  INVESTMENT = 3
  MORTGAGE = 4
  LOAN = 5
  FIXED = 6
  OTHER = 7


class Account(base.Base):
  """Account model for storing a financial account

  Attributes:
    uuid: Account unique identifier
    name: Account name
    institution: Account holding institution
    category: Type of Account
    opened_on: Date of first Transaction
    updated_on: Date of latest Transaction
    transactions: List of Transactions
  """

  _PROPERTIES_DEFAULT = [
      "uuid", "name", "institution", "category", "opened_on", "updated_on"
  ]

  name: orm.Mapped[str]
  institution: orm.Mapped[str]
  category: orm.Mapped[AccountCategory]

  transactions: orm.Mapped[t.List[Transaction]] = orm.relationship(
      back_populates="account", order_by=Transaction.date)

  @property
  def opened_on(self) -> datetime.date:
    """Date of first Transaction
    """
    if len(self.transactions) < 1:
      return None
    return self.transactions[0].date

  @property
  def updated_on(self) -> datetime.date:
    """Date of latest Transaction
    """
    if len(self.transactions) < 1:
      return None
    return self.transactions[-1].date

  def get_value(
      self, start: datetime.date,
      end: datetime.date) -> t.Tuple[Dates, Values, t.Dict[str, Values]]:
    """Get the value of Account from start to end date

    Args:
      start: First date to evaluate
      end: Last date to evaluate (inclusive)

    Returns:
      Also returns value by Asset (possibly empty for non-investment accounts)
      List[dates], list[values], dict{Asset.uuid: list[values]}
    """
    date = start

    dates: Dates = []
    cash: Values = []
    qty_assets: t.Dict[str, Values] = {}
    assets: t.Dict[str, asset.Asset] = {}

    current_cash = 0
    current_qty_assets: t.Dict[str, float] = {}

    for transaction in self.transactions:
      if transaction.date > end:
        continue
      while date < transaction.date:
        for k, v in current_qty_assets.items():
          qty_assets[k].append(v)
        dates.append(date)
        cash.append(current_cash)
        date += datetime.timedelta(days=1)

      for split in transaction.splits:
        a = split.asset
        if a is None:
          continue
        if a.uuid not in current_qty_assets:
          current_qty_assets[a.uuid] = 0
          qty_assets[a.uuid] = [0] * len(dates)
          assets[a.uuid] = a
        current_qty_assets[a.uuid] += split.asset_quantity
      current_cash += transaction.total

    while date <= end:
      for k, v in current_qty_assets.items():
        qty_assets[k].append(v)
      dates.append(date)
      cash.append(current_cash)
      date += datetime.timedelta(days=1)

    # Assets qty to value
    value_assets: t.Dict[str, Values] = {}
    for asset_uuid, a in assets.items():
      qty = qty_assets[asset_uuid]
      # Value = quantity * price * multiplier
      values = [p * m * q for p, m, q in zip(qty, *a.get_value(start, end)[1:])]
      value_assets[asset_uuid] = values

    # Sum with cash
    values = [sum(x) for x in zip(cash, *value_assets.values())]

    return dates, values, value_assets

  def get_asset_qty(self, start: datetime.date,
                    end: datetime.date) -> t.Tuple[Dates, t.Dict[str, Values]]:
    """Get the quantity of Assets held from start to end date

    Args:
      start: First date to evaluate
      end: Last date to evaluate (inclusive)

    Returns:
      List[dates], dict{Asset.uuid: list[values]}
    """
    date = start

    dates: Dates = []
    qty_assets: t.Dict[str, Values] = {}

    current_qty_assets: t.Dict[str, float] = {}

    for transaction in self.transactions:
      if transaction.date > end:
        continue
      while date < transaction.date:
        for k, v in current_qty_assets.items():
          qty_assets[k].append(v)
        dates.append(date)
        date += datetime.timedelta(days=1)

      for split in transaction.splits:
        a = split.asset
        if a is None:
          continue
        if a.uuid not in current_qty_assets:
          current_qty_assets[a.uuid] = 0
          qty_assets[a.uuid] = [0] * len(dates)
        current_qty_assets[a.uuid] += split.asset_quantity

    while date <= end:
      for k, v in current_qty_assets.items():
        qty_assets[k].append(v)
      dates.append(date)
      date += datetime.timedelta(days=1)

    return dates, qty_assets
