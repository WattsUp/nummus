"""Budget model for storing an allocation of cash flow transactions by
categories

All number are annual allocations
"""

from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models.base import Base, Decimal6

ORMBudget = orm.Mapped["Budget"]
ORMBudgetOpt = orm.Mapped[t.Optional["Budget"]]


class Budget(Base):
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

  date: t.ORMDate = orm.mapped_column(unique=True)
  home: t.ORMReal = orm.mapped_column(Decimal6, default=0)
  food: t.ORMReal = orm.mapped_column(Decimal6, default=0)
  shopping: t.ORMReal = orm.mapped_column(Decimal6, default=0)
  hobbies: t.ORMReal = orm.mapped_column(Decimal6, default=0)
  services: t.ORMReal = orm.mapped_column(Decimal6, default=0)
  travel: t.ORMReal = orm.mapped_column(Decimal6, default=0)

  @property
  def categories(self) -> t.DictReal:
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
  def validate_category(self, key: str, field: t.Real) -> t.Real:
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
  def categories(self, data: t.DictReal) -> None:
    keys = self.categories.keys()
    if keys != data.keys():
      raise KeyError(f"Categories must have these keys: {keys}")
    for k, v in data.items():
      setattr(self, f"{k}", v)

  @property
  def total(self) -> t.Real:
    """Total budget
    """
    return sum(self.categories.values())
