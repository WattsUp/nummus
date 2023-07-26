"""Asset model for storing an individual item with dynamic worth
"""

from __future__ import annotations
import typing as t

import datetime
import decimal

import sqlalchemy
from sqlalchemy import orm

from nummus.models import base

Dates = t.List[datetime.date]
Values = t.List[decimal.Decimal]

# TODO (WattsUp) Add AssetSplits


class AssetValuation(base.Base):
  """Asset Valuation model for storing a value of an asset on a specific date

  Attributes:
    asset_uuid: Asset unique identifier
    date: Date of valuation
    value: Value of assert
  """

  _PROPERTIES_DEFAULT = ["asset_uuid", "value", "multiplier", "date"]
  _PROPERTIES_HIDDEN = ["id", "uuid"]

  asset_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("asset.id"))
  asset: orm.Mapped[Asset] = orm.relationship()
  value: orm.Mapped[decimal.Decimal] = orm.mapped_column(base.Decimal6)
  date: orm.Mapped[datetime.date]

  @property
  def asset_uuid(self) -> str:
    """UUID of asset
    """
    return self.asset.uuid


class AssetCategory(base.BaseEnum):
  """Categories of Assets
  """
  CASH = 1
  SECURITY = 2
  REAL_ESTATE = 3
  VEHICLE = 4
  ITEM = 5


class Asset(base.Base):
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

  name: orm.Mapped[str]
  description: orm.Mapped[t.Optional[str]]
  category: orm.Mapped[AssetCategory]
  unit: orm.Mapped[t.Optional[str]]
  tag: orm.Mapped[t.Optional[str]]
  img_suffix: orm.Mapped[t.Optional[str]]

  # TODO (WattsUp) Move to write only relationship if too slow
  valuations: orm.Mapped[t.List[AssetValuation]] = orm.relationship(
      back_populates="asset", order_by=AssetValuation.date)

  @property
  def image_name(self) -> str:
    """Get name of Asset's image, None if it doesn't exist
    """
    s = self.img_suffix
    if s is None:
      return None
    return f"{self.uuid}{s}"

  def get_value(self, start: datetime.date,
                end: datetime.date) -> t.Tuple[Dates, Values]:
    """Get the value of Asset from start to end date

    Args:
      start: First date to evaluate
      end: Last date to evaluate (inclusive)

    Returns:
      List[dates], list[values]
    """
    date = start

    dates: Dates = []
    values: Values = []

    value = 0
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
