"""Asset model for storing an individual item with dynamic worth
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import sqlalchemy
from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models.base import Base, BaseEnum, Decimal6

ORMAsset = orm.Mapped["Asset"]
ORMAssetOpt = orm.Mapped[t.Optional["Asset"]]
ORMAssetCat = orm.Mapped["AssetCategory"]
ORMAssetCatOpt = orm.Mapped[t.Optional["AssetCategory"]]
ORMAssetVal = orm.Mapped["AssetValuation"]
ORMAssetValList = orm.Mapped[t.List["AssetValuation"]]
ORMAssetValOpt = orm.Mapped[t.Optional["AssetValuation"]]

DictStrAsset = t.Dict[str, "Asset"]


class AssetSplit(Base):
  """Asset Split model for storing a split of an asset on a specific date

  Attributes:
    asset_uuid: Asset unique identifier
    date: Date of split
    multiplier: Multiplier of split, qty = qty_unadjusted * multiplier
  """

  _PROPERTIES_DEFAULT = ["value", "date", "multiplier"]
  _PROPERTIES_HIDDEN = ["id", "uuid"]

  asset_id: t.ORMInt = orm.mapped_column(sqlalchemy.ForeignKey("asset.id"))
  multiplier: t.ORMReal = orm.mapped_column(Decimal6)
  date: t.ORMDate

  @property
  def asset(self) -> Asset:
    """Asset for which this AssetSplit is for
    """
    s = orm.object_session(self)
    return s.query(Asset).where(Asset.id == self.asset_id).first()

  @asset.setter
  def asset(self, asset: Asset) -> None:
    if not isinstance(asset, Asset):
      raise TypeError("AssetSplit.asset must be of type Asset")
    if asset.id is None:
      raise ValueError("Commit Asset before adding to split")
    super().__setattr__("asset_id", asset.id)


class AssetValuation(Base):
  """Asset Valuation model for storing a value of an asset on a specific date

  Attributes:
    asset_uuid: Asset unique identifier
    date: Date of valuation
    value: Value of assert
  """

  _PROPERTIES_DEFAULT = ["value", "date"]
  _PROPERTIES_HIDDEN = ["id", "uuid"]

  asset_id: t.ORMInt = orm.mapped_column(sqlalchemy.ForeignKey("asset.id"))
  value: t.ORMReal = orm.mapped_column(Decimal6)
  date: t.ORMDate

  @property
  def asset(self) -> Asset:
    """Asset for which this AssetValuation is for
    """
    s = orm.object_session(self)
    return s.query(Asset).where(Asset.id == self.asset_id).first()

  @asset.setter
  def asset(self, asset: Asset) -> None:
    if not isinstance(asset, Asset):
      raise TypeError("AssetValuation.asset must be of type Asset")
    if asset.id is None:
      raise ValueError("Commit Asset before adding to split")
    super().__setattr__("asset_id", asset.id)


class AssetCategory(BaseEnum):
  """Categories of Assets
  """
  CASH = 1
  SECURITY = 2
  REAL_ESTATE = 3
  VEHICLE = 4
  ITEM = 5


class Asset(Base):
  """Asset model for storing an individual item with dynamic worth

  Attributes:
    uuid: Asset unique identifier
    name: Name of Asset
    description: Description of Asset
    category: Type of Asset
    unit: Unit name for an individual Asset (ex: shares)
    tag: Unique tag linked across datasets
  """

  _PROPERTIES_DEFAULT = [
      "uuid", "name", "description", "category", "unit", "tag"
  ]

  name: t.ORMStr
  description: t.ORMStrOpt
  category: ORMAssetCat
  unit: t.ORMStrOpt
  tag: t.ORMStrOpt
  img_suffix: t.ORMStrOpt

  @property
  def image_name(self) -> str:
    """Get name of Asset's image, None if it doesn't exist
    """
    s = self.img_suffix
    if s is None:
      return None
    return f"{self.uuid}{s}"

  def get_value(self, start: t.Date, end: t.Date) -> t.Tuple[t.Dates, t.Reals]:
    """Get the value of Asset from start to end date

    Args:
      start: First date to evaluate
      end: Last date to evaluate (inclusive)

    Returns:
      List[dates], list[values]
    """
    date = start

    dates: t.Dates = []
    values: t.Reals = []

    value = Decimal(0)

    s = orm.object_session(self)

    # Get latest Valuation before start date
    query_iv = s.query(AssetValuation.value)
    query_iv = query_iv.where(AssetValuation.asset_id == self.id)
    query_iv = query_iv.where(AssetValuation.date < start)
    query_iv = query_iv.order_by(AssetValuation.date.desc())
    iv = query_iv.first()
    if iv is None:
      value = Decimal(0)
    else:
      value = iv[0]

    # Valuations between start and end
    query = s.query(AssetValuation)
    query = query.where(AssetValuation.asset_id == self.id)
    query = query.where(AssetValuation.date <= end)
    query = query.where(AssetValuation.date >= start)
    query = query.order_by(AssetValuation.date)

    for valuation in query.all():
      valuation: AssetValuation
      # Don't need thanks SQL filters
      # if t_split.date > end:
      #   continue
      while date < valuation.date:
        values.append(value)
        dates.append(date)
        date += datetime.timedelta(days=1)
      value = valuation.value
    while date <= end:
      values.append(value)
      dates.append(date)
      date += datetime.timedelta(days=1)
    return dates, values

  def update_splits(self) -> None:
    """Recalculate adjusted TransactionSplit.asset_quantity based on all asset
    splits
    """
    # Get list of splits
    # Compound them
    # Iterate through all transactions with this asset
    # asset_quantity = asset_quantity_unadjusted * factor
    raise NotImplementedError
