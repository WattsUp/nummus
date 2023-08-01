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

# TODO (WattsUp) Add AssetSplits


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

  # TODO (WattsUp) Move to write only relationship if too slow
  valuations: ORMAssetValList = orm.relationship(order_by=AssetValuation.date)

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
    for valuation in self.valuations:
      if valuation.date > end:
        continue
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
