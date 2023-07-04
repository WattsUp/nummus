"""Asset model for storing an individual item with dynamic worth
"""

from __future__ import annotations
from typing import List, Optional

import datetime

import sqlalchemy
from sqlalchemy import orm

from nummus.models import base


class AssetValuation(base.Base):
  """Asset Valuation model for storing a value of an asset on a specific date

  Attributes:
    asset_uuid: Asset unique identifier
    date: Date of valuation
    value: Value of assert
    multiplier: Multiplier to mutate quantity (ex: share splits)
  """

  _PROPERTIES_DEFAULT = ["asset_uuid", "value", "multiplier", "date"]
  _PROPERTIES_HIDDEN = ["id", "uuid"]

  asset_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("asset.id"))
  asset: orm.Mapped[Asset] = orm.relationship()
  value: orm.Mapped[float]
  multiplier: orm.Mapped[float] = orm.mapped_column(default=1)
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
  description: orm.Mapped[Optional[str]]
  category: orm.Mapped[AssetCategory]
  unit: orm.Mapped[Optional[str]]
  tag: orm.Mapped[Optional[str]]
  img_suffix: orm.Mapped[Optional[str]]

  # TODO (WattsUp) Move to write only relationship if too slow
  valuations: orm.Mapped[List[AssetValuation]] = orm.relationship(
      back_populates="asset")

  @property
  def image_name(self) -> str:
    """Get name of Asset's image, None if it doesn't exist
    """
    s = self.img_suffix
    if s is None:
      return None
    return f"{self.uuid}{s}"
