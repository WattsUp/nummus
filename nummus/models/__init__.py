"""Database models
"""

from sqlalchemy import exc, orm

from nummus.models.base import Base

from nummus.models.account import (AccountCategory, Account,
                                   TransactionCategory, Transaction)
from nummus.models.asset import AssetValuation, AssetCategory, Asset
from nummus.models.budget import AnnualBudget


def metadata_create_all(session: orm.Session) -> None:
  """Create all tables for nummus models

  Creates tables then commits

  Args:
    session: Session to create tables for
  """
  tables = [
      Account.__table__, AssetValuation.__table__, Asset.__table__,
      AnnualBudget.__table__, Transaction.__table__
  ]
  Base.metadata.create_all(session.get_bind(), tables)
  session.commit()
