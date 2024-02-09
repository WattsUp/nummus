"""Health check models."""

from __future__ import annotations

from nummus.models.base import Base, ORMBool, ORMStr


class HealthCheckIssue(Base):
    """Health check issue model.

    Attributes:
        check: Name of check
        value: Identifier of failure
        ignore: True will ignore this issue
    """

    __table_id__ = 0x20000000

    check: ORMStr
    value: ORMStr
    ignore: ORMBool
