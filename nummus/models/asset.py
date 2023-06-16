"""Asset model for storing an individual item with dynamic worth
"""

from typing import List, Optional

import datetime
import enum

import sqlalchemy
from sqlalchemy import orm

from nummus.models import base


class AssetValuation(base.Base):
  """Asset Valuation model for storing a value of an asset on a specific date

  Attributes:
    asset: Asset unique identifier
    date: Date of valuation
    value: Value of assert
    multiplier: Multiplier to mutate quantity (ex: share splits)
  """

  _PROPERTIES_DEFAULT = ["asset_id", "value", "multiplier", "date"]
  _PROPERTIES_HIDDEN = ["id"]

  asset_id: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String(36), sqlalchemy.ForeignKey("asset.id"))
  value: orm.Mapped[float]
  multiplier: orm.Mapped[float] = orm.mapped_column(default=1)
  date: orm.Mapped[datetime.date]


class AssetCategory(enum.Enum):
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
    id: Asset unique identifier
    name: Name of Asset
    description: Description of Asset
    category: Type of Asset
    unit: Unit name for an individual Asset (ex: shares)
    tag: Unique tag linked across datasets
  """

  _PROPERTIES_DEFAULT = ["id", "name", "description", "category", "unit", "tag"]

  name: orm.Mapped[str]
  description: orm.Mapped[Optional[str]]
  category: orm.Mapped[AssetCategory]
  unit: orm.Mapped[Optional[str]]
  tag: orm.Mapped[Optional[str]]

  # TODO (WattsUp) Move to write only relationship if too slow
  valuations: orm.Mapped[List[AssetValuation]] = orm.relationship()
