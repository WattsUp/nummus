"""Budget model for storing an allocation of expenses per month
"""

from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models.base import Base, Decimal6

ORMBudget = orm.Mapped["Budget"]
ORMBudgetOpt = orm.Mapped[t.Optional["Budget"]]


class Budget(Base):
  """Budget model for storing an allocation of expenses per month

  Attributes:
    uuid: Budget unique identifier
    date: Date on which Budget is effective
    amount: Target limit of expense per month, zero or negative
  """
  date: t.ORMDate = orm.mapped_column(unique=True)
  amount: t.ORMReal = orm.mapped_column(Decimal6)

  @orm.validates("amount")
  def validate_total(
      self,
      key: str,  # pylint: disable=unused-argument
      field: t.Real) -> t.Real:
    """Validates amount constraints are met

    Args:
      key: Field being updated
      field: Updated value

    Returns:
      field

    Raises:
      ValueError if amount is positive
    """
    if field > 0:
      raise ValueError("Budget amount must be zero or negative")
    return field
