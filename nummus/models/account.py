"""Account model for storing a financial account
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import sqlalchemy
from sqlalchemy import ForeignKey, event, orm

from nummus import custom_types as t
from nummus.models.base import Base, BaseEnum, Decimal6, Decimal18
from nummus.models.asset import Asset, DictStrAsset

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
  parent_uuid: t.ORMStr
  date: t.ORMDate
  locked: t.ORMBool
  account_id: t.ORMInt = orm.mapped_column(ForeignKey("account.id"))
  account_uuid: t.ORMStr

  asset_id: t.ORMIntOpt = orm.mapped_column(ForeignKey("asset.id"))
  asset_uuid: t.ORMStrOpt
  _asset_qty_int: t.ORMIntOpt
  _asset_qty_frac: t.ORMRealOpt = orm.mapped_column(Decimal18)

  def __setattr__(self, name: str, value: t.Any) -> None:
    if name in [
        "parent_id", "parent_uuid", "date", "locked", "account_uuid",
        "account_id"
    ]:
      raise PermissionError("Call TransactionSplit.parent = Transaction. "
                            "Do not set parent properties directly")
    if name in ["asset_id", "asset_uuid"]:
      raise PermissionError("Call TransactionSplit.asset = Asset. "
                            "Do not set asset properties directly")
    super().__setattr__(name, value)

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
    super().__setattr__("parent_uuid", parent.uuid)
    super().__setattr__("date", parent.date)
    super().__setattr__("locked", parent.locked)
    super().__setattr__("account_id", parent.account_id)
    super().__setattr__("account_uuid", parent.account_uuid)

  @property
  def asset(self) -> Asset:
    """Asset exchanged for cash, primarily for instrument transactions
    """
    if self.asset_id is None:
      return None
    s = orm.object_session(self)
    return s.query(Asset).where(Asset.id == self.asset_id).first()

  @asset.setter
  def asset(self, asset: Asset) -> None:
    if asset is None:
      super().__setattr__("asset_id", None)
      super().__setattr__("asset_uuid", None)
      return
    if not isinstance(asset, Asset):
      raise TypeError("TransactionSplit.asset must be of type Asset")
    if asset.id is None:
      raise ValueError("Commit Asset before adding to split")
    super().__setattr__("asset_id", asset.id)
    super().__setattr__("asset_uuid", asset.uuid)


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
  account_uuid: t.ORMStr

  date: t.ORMDate
  total: t.ORMReal = orm.mapped_column(Decimal6)
  statement: t.ORMStr
  locked: t.ORMBool = orm.mapped_column(default=False)

  splits: ORMTxnSplitList = orm.relationship()

  def __setattr__(self, name: str, value: t.Any) -> None:
    if name in ["account_id", "account_uuid"]:
      raise PermissionError("Call Transaction.account = Account. "
                            "Do not set account properties directly")
    super().__setattr__(name, value)

  @property
  def account(self) -> Account:
    """Account that owns this Transaction
    """
    s = orm.object_session(self)
    return s.query(Account).where(Account.id == self.account_id).first()

  @account.setter
  def account(self, acct: Account) -> None:
    if not isinstance(acct, Account):
      raise TypeError("Transaction.account must be of type Account")
    if acct.id is None:
      raise ValueError("Commit Account before adding Transaction")
    super().__setattr__("account_id", acct.id)
    super().__setattr__("account_uuid", acct.uuid)


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

  @property
  def opened_on(self) -> t.Date:
    """Date of first Transaction
    """
    s = orm.object_session(self)
    query = s.query(Transaction.date).where(Transaction.account_id == self.id)
    date = query.order_by(Transaction.date).first()
    if date is None:
      return None
    return date[0]

  @property
  def updated_on(self) -> t.Date:
    """Date of latest Transaction
    """
    s = orm.object_session(self)
    query = s.query(Transaction.date).where(Transaction.account_id == self.id)
    date = query.order_by(Transaction.date.desc()).first()
    if date is None:
      return None
    return date[0]

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

    current_qty_assets: t.DictReal = {}

    s = orm.object_session(self)

    # Get Account value on start date
    # It is callable, sum returns a generator type
    query_iv = s.query(sqlalchemy.func.sum(TransactionSplit.total))  # pylint: disable=not-callable
    query_iv = query_iv.where(TransactionSplit.account_id == self.id)
    query_iv = query_iv.where(TransactionSplit.date < start)
    iv = query_iv.scalar()
    if iv is None:
      current_cash = Decimal(0)
    else:
      current_cash = iv

    # Get Asset quantities on start date
    query_assets = s.query(TransactionSplit.asset_id).distinct()
    query_assets = query_assets.where(TransactionSplit.account_id == self.id)
    for asset_id, in query_assets.all():
      if asset_id is None:
        continue
      a: Asset = s.query(Asset).where(Asset.id == asset_id).first()
      a_uuid = a.uuid
      assets[a_uuid] = a
      qty_assets[a_uuid] = []
      current_qty_assets[a_uuid] = Decimal(0)

      # Get initial value for each Asset
      query_iv = s.query(sqlalchemy.func.sum(TransactionSplit._asset_qty_int))  # pylint: disable=not-callable, protected-access
      query_iv = query_iv.where(TransactionSplit.account_id == self.id)
      query_iv = query_iv.where(TransactionSplit.asset_id == asset_id)
      query_iv = query_iv.where(TransactionSplit.date < start)
      iv_int = query_iv.scalar()
      if iv_int is None:
        continue

      # Can't use SQL SUM on fractional since overflow possible at 8 rows...
      query_iv = s.query(TransactionSplit._asset_qty_frac)  # pylint: disable=protected-access
      query_iv = query_iv.where(TransactionSplit.account_id == self.id)
      query_iv = query_iv.where(TransactionSplit.asset_id == asset_id)
      query_iv = query_iv.where(TransactionSplit.date < start)
      iv_frac = sum(v for v, in query_iv.all())

      current_qty_assets[a_uuid] = iv_int + iv_frac

    # Transactions between start and end
    query = s.query(TransactionSplit)
    query = query.where(TransactionSplit.account_id == self.id)
    query = query.where(TransactionSplit.date <= end)
    query = query.where(TransactionSplit.date >= start)
    query = query.order_by(TransactionSplit.date)

    for t_split in query.all():
      t_split: TransactionSplit
      # Don't need thanks SQL filters
      # if t_split.date > end:
      #   continue
      while date < t_split.date:
        for k, v in current_qty_assets.items():
          qty_assets[k].append(v)
        dates.append(date)
        cash.append(current_cash)
        date += datetime.timedelta(days=1)

      current_cash += t_split.total
      a_uuid = t_split.asset_uuid
      if a_uuid is None:
        continue
      current_qty_assets[a_uuid] += t_split.asset_quantity

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
      # Value = quantity * price
      values = [p * q for q, p in zip(qty, a.get_value(start, end)[1])]
      value_assets[asset_uuid] = values

    # Sum with cash
    values = [round(sum(x), 6) for x in zip(cash, *value_assets.values())]

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

    s = orm.object_session(self)

    # Transactions between start and end
    query = s.query(TransactionSplit)
    query = query.where(TransactionSplit.account_id == self.id)
    query = query.where(TransactionSplit.date <= end)
    query = query.where(TransactionSplit.date >= start)
    query = query.order_by(TransactionSplit.date)

    for t_split in query.all():
      t_split: TransactionSplit
      # Don't need thanks SQL filters
      # if t_split.date > end:
      #   continue
      while date < t_split.date:
        dates.append(date)
        # Append and clear daily
        for k, v in daily_categories.items():
          categories[k].append(v)
          daily_categories[k] = 0
        date += datetime.timedelta(days=1)

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

    s = orm.object_session(self)

    # Get Asset quantities on start date
    query_assets = s.query(TransactionSplit.asset_id).distinct()
    query_assets = query_assets.where(TransactionSplit.account_id == self.id)
    for asset_id, in query_assets.all():
      if asset_id is None:
        continue
      a: Asset = s.query(Asset).where(Asset.id == asset_id).first()
      a_uuid = a.uuid
      qty_assets[a_uuid] = []
      current_qty_assets[a_uuid] = Decimal(0)

      # Get initial value for each Asset
      query_iv = s.query(sqlalchemy.func.sum(TransactionSplit._asset_qty_int))  # pylint: disable=not-callable, protected-access
      query_iv = query_iv.where(TransactionSplit.account_id == self.id)
      query_iv = query_iv.where(TransactionSplit.asset_id == asset_id)
      query_iv = query_iv.where(TransactionSplit.date < start)
      iv_int = query_iv.scalar()
      if iv_int is None:
        continue

      # Can't use SQL SUM on fractional since overflow possible at 8 rows...
      query_iv = s.query(TransactionSplit._asset_qty_frac)  # pylint: disable=protected-access
      query_iv = query_iv.where(TransactionSplit.account_id == self.id)
      query_iv = query_iv.where(TransactionSplit.asset_id == asset_id)
      query_iv = query_iv.where(TransactionSplit.date < start)
      iv_frac = sum(v for v, in query_iv.all())

      current_qty_assets[a_uuid] = iv_int + iv_frac

    # Transactions between start and end
    query = s.query(TransactionSplit)
    query = query.where(TransactionSplit.account_id == self.id)
    query = query.where(TransactionSplit.date <= end)
    query = query.where(TransactionSplit.date >= start)
    query = query.where(TransactionSplit.asset_id.is_not(None))
    query = query.order_by(TransactionSplit.date)

    for t_split in query.all():
      t_split: TransactionSplit
      # Don't need thanks SQL filters
      # if t_split.date > end:
      #   continue
      while date < t_split.date:
        for k, v in current_qty_assets.items():
          qty_assets[k].append(v)
        dates.append(date)
        date += datetime.timedelta(days=1)

      a_uuid = t_split.asset_uuid
      current_qty_assets[a_uuid] += t_split.asset_quantity

    while date <= end:
      for k, v in current_qty_assets.items():
        qty_assets[k].append(v)
      dates.append(date)
      date += datetime.timedelta(days=1)

    return dates, qty_assets
