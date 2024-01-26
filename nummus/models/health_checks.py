"""Health check models."""

from __future__ import annotations

from nummus import custom_types as t
from nummus.models.base import Base


class HealthCheckSilence(Base):
    """Health check issue suppression model.

    Attributes:
        check: Name of check being silenced
        value: Value of failure being silenced
    """

    # No __table_id__ because this is not user accessible

    check: t.ORMStr
    value: t.ORMStr
