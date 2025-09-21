"""Tag model for storing tags associated with transactions."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, orm, UniqueConstraint

from nummus.models.base import (
    Base,
    ORMInt,
    ORMStr,
    string_column_args,
    YIELD_PER,
)
from nummus.models.utils import update_rows


class TagLink(Base):
    """Link between a tag and a transaction.

    Attributes:
        tag_id: Tag unique identifier
        t_split_id: TransactionSplit unique identifier

    """

    __table_id__ = None

    tag_id: ORMInt = orm.mapped_column(ForeignKey("tag.id_"))
    t_split_id: ORMInt = orm.mapped_column(ForeignKey("transaction_split.id_"))

    __table_args__ = (
        UniqueConstraint("tag_id", "t_split_id"),
        Index("tag_link_tag_id", "tag_id"),
        Index("tag_link_t_split_id", "t_split_id"),
    )

    @staticmethod
    def add_links(s: orm.Session, split_tags: dict[int, set[str]]) -> None:
        """Add links between TransactionSplits and Tags.

        Args:
            s: SQL session to use
            split_tags: dict {TransactionSplit: {tag names to link}

        """
        split_tags = {
            t_split_id: {tag for tag in tags if tag.strip()}
            for t_split_id, tags in split_tags.items()
        }
        tag_names: set[str] = set()
        for tags in split_tags.values():
            tag_names.update(tags)

        query = (
            s.query(Tag).with_entities(Tag.name, Tag.id_).where(Tag.name.in_(tag_names))
        )
        mapping: dict[str, int] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

        to_add = [Tag(name=name) for name in tag_names if name not in mapping]
        if to_add:
            s.add_all(to_add)
            s.flush()
            mapping.update({t.name: t.id_ for t in to_add})

        for t_split_id, tags in split_tags.items():
            query = s.query(TagLink).where(TagLink.t_split_id == t_split_id)
            update_rows(
                s,
                TagLink,
                query,
                "tag_id",
                {mapping[tag]: {"t_split_id": t_split_id} for tag in tags},
            )

        # Prune danglers
        sub_query = s.query(TagLink.tag_id).distinct()
        s.query(Tag).where(Tag.id_.not_in(sub_query)).delete()


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
        """Validate string fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_strings(key, field)
