"""Portfolio health checks."""

from __future__ import annotations

from nummus.health_checks.base import Base
from nummus.health_checks.database_integrity import DatabaseIntegrity
from nummus.health_checks.duplicate_transactions import DuplicateTransactions
from nummus.health_checks.empty_fields import EmptyFields
from nummus.health_checks.missing_asset_link import MissingAssetLink
from nummus.health_checks.missing_valuations import MissingAssetValuations
from nummus.health_checks.outlier_asset_price import OutlierAssetPrice
from nummus.health_checks.overdrawn_accounts import OverdrawnAccounts
from nummus.health_checks.typos import Typos
from nummus.health_checks.unbalanced_transfers import (
    UnbalancedCreditCardPayments,
    UnbalancedTransfers,
)
from nummus.health_checks.unlocked_transactions import UnlockedTransactions

__all__ = [
    "Base",
    "DatabaseIntegrity",
    "DuplicateTransactions",
    "EmptyFields",
    "MissingAssetLink",
    "MissingAssetValuations",
    "OutlierAssetPrice",
    "OverdrawnAccounts",
    "Typos",
    "UnbalancedCreditCardPayments",
    "UnbalancedTransfers",
    "UnlockedTransactions",
    "CHECKS",
]

CHECKS: list[type[Base]] = [
    DatabaseIntegrity,
    DuplicateTransactions,
    UnbalancedTransfers,
    UnbalancedCreditCardPayments,
    MissingAssetValuations,
    OutlierAssetPrice,
    OverdrawnAccounts,
    # Not severe below
    Typos,
    UnlockedTransactions,
    EmptyFields,
    MissingAssetLink,
]