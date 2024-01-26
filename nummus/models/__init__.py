"""Database models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.models.account import Account, AccountCategory
from nummus.models.asset import Asset, AssetCategory, AssetSplit, AssetValuation
from nummus.models.base import Base, BaseEnum, YIELD_PER
from nummus.models.base_uri import Cipher, load_cipher
from nummus.models.budget import Budget
from nummus.models.config import Config, ConfigKey
from nummus.models.credentials import Credentials
from nummus.models.health_checks import HealthCheckIgnore
from nummus.models.imported_file import ImportedFile
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import (
    TransactionCategory,
    TransactionCategoryGroup,
)
from nummus.models.utils import paginate, query_count, search

if TYPE_CHECKING:
    import sqlalchemy
    from sqlalchemy import orm

__all__ = [
    "Account",
    "AccountCategory",
    "Asset",
    "AssetCategory",
    "AssetSplit",
    "AssetValuation",
    "Base",
    "BaseEnum",
    "Budget",
    "Cipher",
    "Config",
    "ConfigKey",
    "Credentials",
    "HealthCheckIgnore",
    "ImportedFile",
    "load_cipher",
    "Transaction",
    "TransactionSplit",
    "TransactionCategory",
    "TransactionCategoryGroup",
    "YIELD_PER",
    "paginate",
    "query_count",
    "search",
    "metadata_create_all",
]

_TABLES: list[sqlalchemy.Table] = [  # type: ignore[attr-defined]
    Account.__table__,
    Asset.__table__,
    AssetSplit.__table__,
    AssetValuation.__table__,
    Budget.__table__,
    Config.__table__,
    Credentials.__table__,
    ImportedFile.__table__,
    HealthCheckIgnore.__table__,
    Transaction.__table__,
    TransactionCategory.__table__,
    TransactionSplit.__table__,
]


def metadata_create_all(s: orm.Session) -> None:
    """Create all tables for nummus models.

    Creates tables then commits

    Args:
        s: Session to create tables for
    """
    Base.metadata.create_all(s.get_bind(), _TABLES)
    s.commit()
