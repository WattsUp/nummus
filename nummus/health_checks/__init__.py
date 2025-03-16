"""Portfolio health checks."""

from __future__ import annotations

from nummus.health_checks.base import Base
from nummus.health_checks.category_direction import CategoryDirection
from nummus.health_checks.database_integrity import DatabaseIntegrity
from nummus.health_checks.duplicate_transactions import DuplicateTransactions
from nummus.health_checks.empty_fields import EmptyFields
from nummus.health_checks.missing_asset_link import MissingAssetLink
from nummus.health_checks.missing_valuations import MissingAssetValuations
from nummus.health_checks.outlier_asset_price import OutlierAssetPrice
from nummus.health_checks.overdrawn_accounts import OverdrawnAccounts
from nummus.health_checks.typos import Typos
from nummus.health_checks.unbalanced_transfers import UnbalancedTransfers
from nummus.health_checks.uncleared_transactions import UnclearedTransactions
from nummus.health_checks.unnecessary_slits import UnnecessarySplits
from nummus.health_checks.unused_categories import UnusedCategories

__all__ = [
    "CHECKS",
    "Base",
    "CategoryDirection",
    "DatabaseIntegrity",
    "DuplicateTransactions",
    "EmptyFields",
    "MissingAssetLink",
    "MissingAssetValuations",
    "OutlierAssetPrice",
    "OverdrawnAccounts",
    "Typos",
    "UnbalancedTransfers",
    "UnclearedTransactions",
    "UnnecessarySplits",
    "UnusedCategories",
]

CHECKS: list[type[Base]] = [
    DatabaseIntegrity,
    CategoryDirection,
    DuplicateTransactions,
    UnbalancedTransfers,
    MissingAssetValuations,
    OutlierAssetPrice,
    OverdrawnAccounts,
    # Not severe below
    Typos,
    UnclearedTransactions,
    EmptyFields,
    MissingAssetLink,
    UnusedCategories,
    UnnecessarySplits,
]
