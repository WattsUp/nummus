"""Budget model for storing an allocation of expenses per month
"""

from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models.base import Base

ORMBudget = orm.Mapped["Budget"]
ORMBudgetOpt = orm.Mapped[t.Optional["Budget"]]


class Budget(Base):
  """Budget model for storing an allocation of expenses per month

  Attributes:
    uuid: Budget unique identifier
    date: Date on which Budget is effective
    total: Target limit of expense per month
  """
  date: t.ORMDate = orm.mapped_column(unique=True)
  total: t.ORMReal
