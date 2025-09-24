"""Migrator to v0.13.0."""

from __future__ import annotations

from collections import defaultdict
from typing import override, TYPE_CHECKING

import sqlalchemy

from nummus.migrations.base import Migrator
from nummus.models import Base, Label, LabelLink, TransactionSplit

if TYPE_CHECKING:
    from nummus import portfolio


class MigratorV0_13(Migrator):
    """Migrator to v0.13.0."""

    _VERSION = "0.13.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> list[str]:
        _ = p

        comments: list[str] = []

        with p.begin_session() as s:
            Base.metadata.create_all(
                s.get_bind(),
                [Label.sql_table(), LabelLink.sql_table()],
            )

        # Move existing tags to Label & LabelLink
        with p.begin_session() as s:
            stmt = "SELECT id_, tag FROM transaction_split WHERE tag is not null"
            tag_mapping: dict[str, set[int]] = defaultdict(set)
            for t_split_id, name in s.execute(sqlalchemy.text(stmt)):
                tag_mapping[name].add(t_split_id)

            labels = [Label(name=name) for name in tag_mapping]
            s.add_all(labels)
            s.flush()

            for label in labels:
                for t_split_id in tag_mapping[label.name]:
                    s.add(LabelLink(label_id=label.id_, t_split_id=t_split_id))

        with p.begin_session() as s:
            self.drop_column(s, TransactionSplit, "tag")

        return comments
