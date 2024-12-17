"""Database models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.models import base_uri
from nummus.models.account import Account, AccountCategory
from nummus.models.asset import Asset, AssetCategory, AssetSplit, AssetValuation
from nummus.models.base import Base, BaseEnum, YIELD_PER
from nummus.models.base_uri import Cipher, load_cipher
from nummus.models.budget import (
    BudgetAssignment,
    BudgetGroup,
    Target,
    TargetPeriod,
    TargetType,
)
from nummus.models.config import Config, ConfigKey
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.imported_file import ImportedFile
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import (
    TransactionCategory,
    TransactionCategoryGroup,
)
from nummus.models.utils import paginate, query_count, search

if TYPE_CHECKING:
    from sqlalchemy import orm

__all__ = [
    "YIELD_PER",
    "Account",
    "AccountCategory",
    "Asset",
    "AssetCategory",
    "AssetSplit",
    "AssetValuation",
    "Base",
    "BaseEnum",
    "BudgetAssignment",
    "BudgetGroup",
    "Cipher",
    "Config",
    "ConfigKey",
    "HealthCheckIssue",
    "ImportedFile",
    "Target",
    "TargetPeriod",
    "TargetType",
    "Transaction",
    "TransactionCategory",
    "TransactionCategoryGroup",
    "TransactionSplit",
    "load_cipher",
    "metadata_create_all",
    "paginate",
    "query_count",
    "search",
]

_MODELS: list[type[Base]] = [
    Account,
    Asset,
    AssetSplit,
    AssetValuation,
    BudgetAssignment,
    BudgetGroup,
    Config,
    ImportedFile,
    HealthCheckIssue,
    Target,
    Transaction,
    TransactionCategory,
    TransactionSplit,
]


def set_table_uris() -> None:
    """Set table URIs."""
    i = 1
    for m in _MODELS:
        if hasattr(m, "__table_id__") and m.__table_id__ is None:
            continue
        m.__table_id__ = i << base_uri.TABLE_OFFSET
        i += 1


def metadata_create_all(s: orm.Session) -> None:
    """Create all tables for nummus models.

    Creates tables then commits

    Args:
        s: Session to create tables for
    """
    Base.metadata.create_all(s.get_bind(), [m.__table__ for m in _MODELS])  # type: ignore[attr-defined]
    s.commit()


set_table_uris()
