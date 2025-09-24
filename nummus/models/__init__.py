"""Database models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.models import base_uri
from nummus.models.account import Account, AccountCategory
from nummus.models.asset import (
    Asset,
    AssetCategory,
    AssetSector,
    AssetSplit,
    AssetValuation,
    USSector,
)
from nummus.models.base import Base, BaseEnum, YIELD_PER
from nummus.models.base_uri import Cipher, load_cipher
from nummus.models.budget import (
    BudgetAssignment,
    BudgetAvailable,
    BudgetAvailableCategory,
    BudgetGroup,
    Target,
    TargetPeriod,
    TargetType,
)
from nummus.models.config import Config, ConfigKey
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.imported_file import ImportedFile
from nummus.models.label import Label, LabelLink
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import (
    TransactionCategory,
    TransactionCategoryGroup,
)
from nummus.models.utils import (
    dump_table_configs,
    get_constraints,
    obj_session,
    one_or_none,
    paginate,
    query_count,
    query_to_dict,
    update_rows,
    update_rows_list,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

__all__ = [
    "YIELD_PER",
    "Account",
    "AccountCategory",
    "Asset",
    "AssetCategory",
    "AssetSector",
    "AssetSplit",
    "AssetValuation",
    "Base",
    "BaseEnum",
    "BudgetAssignment",
    "BudgetAvailable",
    "BudgetAvailableCategory",
    "BudgetGroup",
    "Cipher",
    "Config",
    "ConfigKey",
    "HealthCheckIssue",
    "ImportedFile",
    "Label",
    "LabelLink",
    "Target",
    "TargetPeriod",
    "TargetType",
    "Transaction",
    "TransactionCategory",
    "TransactionCategoryGroup",
    "TransactionSplit",
    "USSector",
    "dump_table_configs",
    "get_constraints",
    "load_cipher",
    "metadata_create_all",
    "obj_session",
    "one_or_none",
    "paginate",
    "query_count",
    "query_to_dict",
    "update_rows",
    "update_rows_list",
]

_MODELS: list[type[Base]] = [
    Account,
    Asset,
    AssetSector,
    AssetSplit,
    AssetValuation,
    BudgetAssignment,
    BudgetGroup,
    Config,
    ImportedFile,
    HealthCheckIssue,
    Label,
    LabelLink,
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
    Base.metadata.create_all(s.get_bind(), [m.sql_table() for m in _MODELS])
    s.commit()


set_table_uris()
