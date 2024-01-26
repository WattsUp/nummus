"""Health check models."""

from __future__ import annotations

from nummus import custom_types as t
from nummus.models.base import Base


class HealthCheckIgnore(Base):
    """Health check issue suppression model.

    Attributes:
        check: Name of check being ignored
        value: Value of failure being ignored
    """

    # No __table_id__ because this is not user accessible

    check: t.ORMStr
    value: t.ORMStr
