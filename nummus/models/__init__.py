"""Database models
"""

import enum
import json

from sqlalchemy import exc, orm

from nummus.models.base import Base

from nummus.models.account import (AccountCategory, Account,
                                   TransactionCategory, Transaction,
                                   TransactionSplit)
from nummus.models.asset import AssetValuation, AssetCategory, Asset
from nummus.models.budget import AnnualBudget
from nummus.models.credentials import Credentials


def metadata_create_all(session: orm.Session) -> None:
  """Create all tables for nummus models

  Creates tables then commits

  Args:
    session: Session to create tables for
  """
  tables = [
      Account.__table__, AssetValuation.__table__, Asset.__table__,
      AnnualBudget.__table__, Credentials.__table__, Transaction.__table__,
      TransactionSplit.__table__
  ]
  Base.metadata.create_all(session.get_bind(), tables)
  session.commit()


class NummusJSONEncoder(json.JSONEncoder):
  """Custom JSON Encoder for nummus models
  """

  def default(self, o: object) -> object:
    if isinstance(o, Base):
      return o.to_dict()
    if isinstance(o, enum.Enum):
      return o.name.lower()
    return super().default(o)
