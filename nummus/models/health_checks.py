"""Health check models."""

from __future__ import annotations

from nummus import custom_types as t
from nummus.models.base import Base


class HealthCheckIssue(Base):
    """Health check issue model.

    Attributes:
        check: Name of check
        value: Identifier of failure
        ignore: True will ignore this issue
    """

    __table_id__ = 0x20000000

    check: t.ORMStr
    value: t.ORMStr
    ignore: t.ORMBool
