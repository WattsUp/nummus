"""Budget model for storing an allocation of cash flow transactions by
categories

All number are annual allocations
"""

from typing import Dict

import datetime

from sqlalchemy import orm

from nummus.models import base


class AnnualBudget(base.Base):
  """Budget model for storing an allocation of cash flow transactions by
  categories

  All numbers are annual allocations

  Attributes:
    id: Budget unique identifier
    date: Date on which AnnualBudget is effective
    total: Total limit of AnnualBudget
    categories: Categorical breakdown of total
  """

  _PROPERTIES_DEFAULT = ["id", "date", "total", "categories"]

  date: orm.Mapped[datetime.date]
  home: orm.Mapped[float] = orm.mapped_column(default=0)
  food: orm.Mapped[float] = orm.mapped_column(default=0)
  shopping: orm.Mapped[float] = orm.mapped_column(default=0)
  hobbies: orm.Mapped[float] = orm.mapped_column(default=0)
  services: orm.Mapped[float] = orm.mapped_column(default=0)
  travel: orm.Mapped[float] = orm.mapped_column(default=0)

  @property
  def categories(self) -> Dict[str, float]:
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

  @categories.setter
  def categories(self, data: Dict[str, float]) -> None:
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
