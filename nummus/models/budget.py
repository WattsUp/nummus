"""Budget model for storing an allocation of cash flow transactions by
categories

All number are annual allocations
"""

import typing as t

import datetime
import decimal

from sqlalchemy import orm

from nummus.models import base


class Budget(base.Base):
  """Budget model for storing an allocation of cash flow transactions by
  categories

  All numbers are annual allocations

  Attributes:
    uuid: Budget unique identifier
    date: Date on which Budget is effective
    total: Total limit of Budget
    categories: Categorical breakdown of total, all amounts <= 0
  """

  _PROPERTIES_DEFAULT = ["uuid", "date", "total", "categories"]

  date: orm.Mapped[datetime.date] = orm.mapped_column(unique=True)
  home: orm.Mapped[decimal.Decimal] = orm.mapped_column(base.Decimal6,
                                                        default=0)
  food: orm.Mapped[decimal.Decimal] = orm.mapped_column(base.Decimal6,
                                                        default=0)
  shopping: orm.Mapped[decimal.Decimal] = orm.mapped_column(base.Decimal6,
                                                            default=0)
  hobbies: orm.Mapped[decimal.Decimal] = orm.mapped_column(base.Decimal6,
                                                           default=0)
  services: orm.Mapped[decimal.Decimal] = orm.mapped_column(base.Decimal6,
                                                            default=0)
  travel: orm.Mapped[decimal.Decimal] = orm.mapped_column(base.Decimal6,
                                                          default=0)

  @property
  def categories(self) -> t.Dict[str, float]:
    """Categorical breakdown of total
    """
    return {
        "home": self.home,
        "food": self.food,
        "shopping": self.shopping,
        "hobbies": self.hobbies,
        "services": self.services,
        "travel": self.travel
    }

  @orm.validates("home", "food", "shopping", "hobbies", "services", "travel")
  def validate_category(self, key: str, field: float) -> float:
    """Validate budget amounts are <= 0

    Args:
      key: Field being updated
      field: Updated value

    Returns:
      field

    Raises:
      ValueError if budget amount > 0
    """
    if field > 0:
      raise ValueError(f"Budget.{key} must be <= 0")
    return field

  @categories.setter
  def categories(self, data: t.Dict[str, float]) -> None:
    keys = self.categories.keys()
    if keys != data.keys():
      raise KeyError(f"Categories must have these keys: {keys}")
    for k, v in data.items():
      setattr(self, f"{k}", v)

  @property
  def total(self) -> float:
    """Total budget
    """
    return sum(self.categories.values())
