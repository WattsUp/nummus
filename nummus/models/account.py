"""Account model for storing a financial account
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, orm

from nummus import custom_types as t
from nummus.models.base import Base, BaseEnum, Decimal6, Decimal18
from nummus.models.asset import ORMAsset, DictStrAsset

ORMTxn = orm.Mapped["Transaction"]
ORMTxnList = orm.Mapped[t.List["Transaction"]]
ORMTxnOpt = orm.Mapped[t.Optional["Transaction"]]
ORMTxnSplit = orm.Mapped["TransactionSplit"]
ORMTxnSplitList = orm.Mapped[t.List["TransactionSplit"]]
ORMTxnSplitOpt = orm.Mapped[t.Optional["TransactionSplit"]]
ORMTxnCat = orm.Mapped["TransactionCategory"]
ORMTxnCatOpt = orm.Mapped[t.Optional["TransactionCategory"]]
ORMAcct = orm.Mapped["Account"]
ORMAcctOpt = orm.Mapped[t.Optional["Account"]]
ORMAcctCat = orm.Mapped["AccountCategory"]
ORMAcctCatOpt = orm.Mapped[t.Optional["AccountCategory"]]

RealOrTxnCat = t.Union[t.Real, "TransactionCategory"]

DictTxnCatReal = t.Dict["TransactionCategory", t.Real]
DictTxnCatReals = t.Dict["TransactionCategory", t.Reals]


class TransactionCategory(BaseEnum):
  """Categories of Transactions
  """
  # Outflow, checked TransactionSplit.total < 0
  HOME = 1
  FOOD = 2
  SHOPPING = 3
  HOBBIES = 4
  SERVICES = 5
  TRAVEL = 6

  # Inflow, checked TransactionSplit.total < 0
  INCOME = 7

  # Outflow/inflow, no check
  INSTRUMENT = 8
  TRANSFER = 9

  def is_valid_amount(self, amount: t.Real) -> bool:
    """Test amount is valid sign for the Category

    Args:
      amount: Amount of TransactionSplit to test

    Returns:
      True if sign(amount) matches the proper category, False otherwise
    """
    if (self in [
        self.HOME, self.FOOD, self.SHOPPING, self.HOBBIES, self.SERVICES,
        self.TRAVEL
    ]):
      return amount <= 0
    elif self == self.INCOME:
      return amount >= 0
    # Other categories are bidirectional
    return True


class TransactionSplit(Base):
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
  """

  _PROPERTIES_DEFAULT = [
      "uuid", "account_uuid", "date", "total", "sales_tax", "payee",
      "description", "category", "subcategory", "tag", "parent_uuid",
      "asset_uuid", "asset_quantity", "locked"
  ]

  total: t.ORMReal = orm.mapped_column(Decimal6)
  sales_tax: t.ORMRealOpt = orm.mapped_column(Decimal6)
  payee: t.ORMStrOpt
  description: t.ORMStrOpt
  category: ORMTxnCatOpt
  subcategory: t.ORMStrOpt
  tag: t.ORMStrOpt

  parent_id: t.ORMInt = orm.mapped_column(ForeignKey("transaction.id"))
  parent: ORMTxn = orm.relationship(back_populates="splits")

  asset_id: t.ORMIntOpt = orm.mapped_column(ForeignKey("asset.id"))
  asset: ORMAsset = orm.relationship()

  _asset_qty_int: t.ORMIntOpt
  _asset_qty_frac: t.ORMRealOpt = orm.mapped_column(Decimal18)

  @orm.validates("total", "category")
  def validate_category(self, key: str, field: RealOrTxnCat) -> RealOrTxnCat:
    """Validate inflow/outflow constraints are met

    Args:
      key: Field being updated
      field: Updated value

    Returns:
      field

    Raises:
      ValueError if category and sign(total) do not agree
    """
    total = self.total
    category = self.category
    if key == "total":
      total: t.Real = field
    else:
      category: TransactionCategory = field
    if category is None:
      # It's fine
      return field

    if not category.is_valid_amount(total):
      raise ValueError(f"{category} does not match sign({total})")
    return field

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
  def date(self) -> t.Date:
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
  def asset_quantity(self) -> t.Real:
    """Number of units of Asset exchanged, Positive indicates
    Account gained Assets (inflow)
    """
    if self._asset_qty_int is None:
      return None
    return self._asset_qty_int + self._asset_qty_frac

  @asset_quantity.setter
  def asset_quantity(self, qty: t.Real) -> None:
    if qty is None:
      self._asset_qty_int = None
      self._asset_qty_frac = None
      return
    i, f = divmod(qty, 1)
    self._asset_qty_int = int(i)
    self._asset_qty_frac = f


class Transaction(Base):
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
  """

  _PROPERTIES_DEFAULT = [
      "uuid", "account_uuid", "date", "total", "statement", "locked", "splits"
  ]

  account_id: t.ORMInt = orm.mapped_column(ForeignKey("account.id"))
  account: ORMAcct = orm.relationship(back_populates="transactions")

  date: t.ORMDate
  total: t.ORMReal = orm.mapped_column(Decimal6)
  statement: t.ORMStr
  locked: t.ORMBool = orm.mapped_column(default=False)

  splits: ORMTxnSplitList = orm.relationship(back_populates="parent")

  @property
  def account_uuid(self) -> str:
    """UUID of account
    """
    return self.account.uuid


class AccountCategory(BaseEnum):
  """Categories of Accounts
  """
  CASH = 1
  CREDIT = 2
  INVESTMENT = 3
  MORTGAGE = 4
  LOAN = 5
  FIXED = 6
  OTHER = 7


class Account(Base):
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

  name: t.ORMStr
  institution: t.ORMStr
  category: ORMAcctCat

  transactions: ORMTxnList = orm.relationship(back_populates="account",
                                              order_by=Transaction.date)

  @property
  def opened_on(self) -> t.Date:
    """Date of first Transaction
    """
    if len(self.transactions) < 1:
      return None
    return self.transactions[0].date

  @property
  def updated_on(self) -> t.Date:
    """Date of latest Transaction
    """
    if len(self.transactions) < 1:
      return None
    return self.transactions[-1].date

  def get_value(self, start: t.Date,
                end: t.Date) -> t.Tuple[t.Dates, t.Reals, t.DictReals]:
    """Get the value of Account from start to end date

    Args:
      start: First date to evaluate
      end: Last date to evaluate (inclusive)

    Returns:
      Also returns value by Asset (possibly empty for non-investment accounts)
      List[dates], list[values], dict{Asset.uuid: list[values]}
    """
    date = start

    dates: t.Dates = []
    cash: t.Reals = []
    qty_assets: t.DictReals = {}
    assets: DictStrAsset = {}

    current_cash = Decimal(0)
    current_qty_assets: t.DictReal = {}

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
    value_assets: t.DictReals = {}
    for asset_uuid, a in assets.items():
      qty = qty_assets[asset_uuid]
      # Value = quantity * price * multiplier
      values = [p * q for p, q in zip(qty, *a.get_value(start, end)[1:])]
      value_assets[asset_uuid] = values

    # Sum with cash
    values = [sum(x) for x in zip(cash, *value_assets.values())]

    return dates, values, value_assets

  def get_cash_flow(self, start: t.Date,
                    end: t.Date) -> t.Tuple[t.Dates, DictTxnCatReals]:
    """Get the cash_flow of Account from start to end date

    Results are not integrated, i.e. inflow[3] = 10 means $10 was made on the
    third day; inflow[4] may be zero

    Args:
      start: First date to evaluate
      end: Last date to evaluate (inclusive)

    Returns:
      List[dates], dict{Category: list[values]}
      Includes None in categories
    """
    date = start

    dates: t.Dates = []
    categories: DictTxnCatReals = {cat: [] for cat in TransactionCategory}
    categories["unknown-inflow"] = []  # Category is nullable
    categories["unknown-outflow"] = []  # Category is nullable

    daily_categories: DictTxnCatReal = {cat: 0 for cat in TransactionCategory}
    daily_categories["unknown-inflow"] = 0
    daily_categories["unknown-outflow"] = 0

    for transaction in self.transactions:
      if transaction.date > end:
        continue
      while date < transaction.date:
        dates.append(date)
        # Append and clear daily
        for k, v in daily_categories.items():
          categories[k].append(v)
          daily_categories[k] = 0
        date += datetime.timedelta(days=1)

      if date == transaction.date:
        for t_split in transaction.splits:
          if t_split.category is None:
            if t_split.total > 0:
              daily_categories["unknown-inflow"] += t_split.total
            else:
              daily_categories["unknown-outflow"] += t_split.total
          else:
            daily_categories[t_split.category] += t_split.total

    while date <= end:
      dates.append(date)
      # Append and clear daily
      for k, v in daily_categories.items():
        categories[k].append(v)
        daily_categories[k] = 0
      date += datetime.timedelta(days=1)

    return dates, categories

  def get_asset_qty(self, start: t.Date,
                    end: t.Date) -> t.Tuple[t.Dates, t.DictReals]:
    """Get the quantity of Assets held from start to end date

    Args:
      start: First date to evaluate
      end: Last date to evaluate (inclusive)

    Returns:
      List[dates], dict{Asset.uuid: list[values]}
    """
    date = start

    dates: t.Dates = []
    qty_assets: t.DictReals = {}

    current_qty_assets: t.DictReal = {}

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
