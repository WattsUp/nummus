"""Health check models."""

from __future__ import annotations

from sqlalchemy import orm, UniqueConstraint

from nummus.models.base import Base, ORMBool, ORMStr, string_column_args


class HealthCheckIssue(Base):
    """Health check issue model.

    Attributes:
        check: Name of check
        value: Identifier of failure
        msg: User message of failure
        ignore: True will ignore this issue

    """

    __tablename__ = "health_check_issue"
    __table_id__ = 0x00000000

    check: ORMStr
    value: ORMStr
    msg: ORMStr
    ignore: ORMBool

    __table_args__ = (
        UniqueConstraint("check", "value"),
        *string_column_args("check"),
        *string_column_args("value", short_check=False),
    )

    @orm.validates("check", "value")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validate string fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_strings(key, field, short_check=key != "value")
