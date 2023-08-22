"""Database models
"""

from sqlalchemy import exc, orm

from nummus import custom_types as t

from nummus.models.base import Base, BaseEnum, NummusJSONEncoder

from nummus.models.account import (Account, AccountCategory, Transaction,
                                   TransactionCategory, TransactionSplit)
from nummus.models.asset import (Asset, AssetCategory, AssetSplit,
                                 AssetValuation)
from nummus.models.budget import Budget
from nummus.models.credentials import Credentials
from nummus.models.utils import search, query_count, paginate

AssetList = t.List[Asset]
TxnList = t.List[Transaction]
TxnSplitList = t.List[TransactionSplit]


def metadata_create_all(session: orm.Session) -> None:
  """Create all tables for nummus models

  Creates tables then commits

  Args:
    session: Session to create tables for
  """
  tables = [
      Account.__table__, Asset.__table__, AssetSplit.__table__,
      AssetValuation.__table__, Budget.__table__, Credentials.__table__,
      Transaction.__table__, TransactionSplit.__table__
  ]
  Base.metadata.create_all(session.get_bind(), tables)
  session.commit()
