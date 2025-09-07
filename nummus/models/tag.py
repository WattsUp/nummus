"""Tag model for storing tags associated with transactions."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, orm, UniqueConstraint

from nummus.models.base import (
    Base,
    ORMInt,
    ORMStr,
    string_column_args,
)


class TagLink(Base):
    """Link between a tag and a transaction.

    Attributes:
        tag_id: Tag unique identifier
        t_split_id: TransactionSlit unique identifier
    """

    __table_id__ = None

    tag_id: ORMInt = orm.mapped_column(ForeignKey("tag.id_"))
    t_split_id: ORMInt = orm.mapped_column(ForeignKey("transaction_split.id_"))

    __table_args__ = (
        UniqueConstraint("tag_id", "t_split_id"),
        Index("tag_link_tag_id", "tag_id"),
        Index("tag_link_t_split_id", "t_split_id"),
    )


class Tag(Base):
    """Tag model for storing tags associated with transactions.

    Attributes:
        name: Name of tag
    """

    __table_id__ = 0x00000000

    name: ORMStr = orm.mapped_column(unique=True)

    __table_args__ = (*string_column_args("name"),)

    @orm.validates("name")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validates string fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field
        """
        return self.clean_strings(key, field)
