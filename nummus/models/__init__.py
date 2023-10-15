"""Database models
"""

from sqlalchemy import exc, orm

from nummus.models.account import Account, AccountCategory
from nummus.models.asset import Asset, AssetCategory, AssetSplit, AssetValuation
from nummus.models.base import Base, BaseEnum
from nummus.models.budget import Budget
from nummus.models.credentials import Credentials
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import (
    TransactionCategory,
    TransactionCategoryGroup,
)
from nummus.models.utils import paginate, query_count, search


def metadata_create_all(s: orm.Session) -> None:
    """Create all tables for nummus models

    Creates tables then commits

    Args:
        s: Session to create tables for
    """
    tables = [
        Account.__table__,
        Asset.__table__,
        AssetSplit.__table__,
        AssetValuation.__table__,
        Budget.__table__,
        Credentials.__table__,
        Transaction.__table__,
        TransactionCategory.__table__,
        TransactionSplit.__table__,
    ]
    Base.metadata.create_all(s.get_bind(), tables)
    s.commit()
