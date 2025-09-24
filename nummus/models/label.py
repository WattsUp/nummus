"""Label model for storing labeling transactions."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, orm, UniqueConstraint

from nummus.models.base import (
    Base,
    ORMInt,
    ORMStr,
    string_column_args,
)
from nummus.models.utils import query_to_dict, update_rows


class LabelLink(Base):
    """Link between a label and a transaction.

    Attributes:
        label_id: Label unique identifier
        t_split_id: TransactionSplit unique identifier

    """

    __tablename__ = "label_link"
    __table_id__ = None

    label_id: ORMInt = orm.mapped_column(ForeignKey("label.id_"))
    t_split_id: ORMInt = orm.mapped_column(ForeignKey("transaction_split.id_"))

    __table_args__ = (
        UniqueConstraint("label_id", "t_split_id"),
        Index("label_link_label_id", "label_id"),
        Index("label_link_t_split_id", "t_split_id"),
    )

    @staticmethod
    def add_links(s: orm.Session, split_labels: dict[int, set[str]]) -> None:
        """Add links between TransactionSplits and Labels.

        Args:
            s: SQL session to use
            split_labels: dict {TransactionSplit: {label names to link}

        """
        split_labels = {
            t_split_id: {label.strip() for label in labels if label.strip()}
            for t_split_id, labels in split_labels.items()
        }
        label_names: set[str] = set()
        for labels in split_labels.values():
            label_names.update(labels)

        query = (
            s.query(Label)
            .with_entities(Label.name, Label.id_)
            .where(Label.name.in_(label_names))
        )
        mapping: dict[str, int] = query_to_dict(query)

        to_add = [Label(name=name) for name in label_names if name not in mapping]
        if to_add:
            s.add_all(to_add)
            s.flush()
            mapping.update({label.name: label.id_ for label in to_add})

        for t_split_id, labels in split_labels.items():
            query = s.query(LabelLink).where(LabelLink.t_split_id == t_split_id)
            update_rows(
                s,
                LabelLink,
                query,
                "label_id",
                {mapping[label]: {"t_split_id": t_split_id} for label in labels},
            )


class Label(Base):
    """Label model for storing labeling transactions.

    Attributes:
        name: Name of label

    """

    __tablename__ = "label"
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
