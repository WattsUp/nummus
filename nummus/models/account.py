"""Account model for storing a financial account
"""

from __future__ import annotations
from typing import List, Optional

import datetime

import sqlalchemy
from sqlalchemy import orm

from nummus.models import base, asset


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
    total: Total amount of cash exchanged. Positive indicated Account
      increases in value (ingress)
    sales_tax: Amount of sales tax paid on Transaction, always negative
    payee: Name of payee (for egress)/payer (for ingress)
    description: Description of exchange
    category: Type of Transaction
    subcategory: Subcategory of Transaction type
    tag: Unique tag linked across datasets
    parent: Parent Transaction
    asset: Asset exchanged for cash, primarily for instrument transactions
    asset_quantity: Number of units of Asset exchanged, Positive indicates
      Account gained Assets (ingress)
  """

  _PROPERTIES_DEFAULT = [
      "uuid", "total", "sales_tax", "payee", "description", "category",
      "subcategory", "tag", "parent_uuid", "asset_uuid", "asset_quantity"
  ]

  total: orm.Mapped[float]
  sales_tax: orm.Mapped[Optional[float]]
  payee: orm.Mapped[Optional[str]]
  description: orm.Mapped[Optional[str]]
  category: orm.Mapped[Optional[TransactionCategory]]
  subcategory: orm.Mapped[Optional[str]]
  tag: orm.Mapped[Optional[str]]

  parent_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("transaction.id"))
  parent: orm.Mapped[Transaction] = orm.relationship(back_populates="splits")

  asset_id: orm.Mapped[Optional[int]] = orm.mapped_column(
      sqlalchemy.ForeignKey("asset.id"))
  asset: orm.Mapped[asset.Asset] = orm.relationship()

  asset_quantity: orm.Mapped[Optional[float]]

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


class Transaction(base.Base):
  """Transaction model for storing an exchange of cash for an asset (or none)

  Every Transaction has at least one TransactionSplit.

  Attributes:
    uuid: Transaction unique identifier
    account: Account that owns this Transaction
    date: Date on which Transaction occurred
    total: Total amount of cash exchanged. Positive indicated Account
      increases in value (ingress)
    statement: Text appearing on Account statement
    locked: True only allows manually editing, False allows automatic changes
      (namely auto labeling field based on similar Transactions)
    splits: List of TransactionSplits
  """

  _PROPERTIES_DEFAULT = [
      "uuid", "account_uuid", "date", "total", "statement", "locked", "splits"
  ]

  account_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("account.id"))
  account: orm.Mapped[Account] = orm.relationship(back_populates="transactions")

  date: orm.Mapped[datetime.date]
  total: orm.Mapped[float]
  statement: orm.Mapped[str]
  locked: orm.Mapped[bool] = orm.mapped_column(default=False)

  splits: orm.Mapped[List[TransactionSplit]] = orm.relationship(
      back_populates="parent")

  @property
  def account_uuid(self) -> str:
    """UUID of account
    """
    return self.account.uuid


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

  transactions: orm.Mapped[List[Transaction]] = orm.relationship(
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
