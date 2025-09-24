"""Migrator to v0.15.0."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

import sqlalchemy

from nummus import exceptions as exc
from nummus.migrations.base import Migrator
from nummus.models import Base, dump_table_configs, Label, LabelLink

if TYPE_CHECKING:
    from nummus import portfolio


class MigratorV0_15(Migrator):
    """Migrator to v0.15.0."""

    _VERSION = "0.15.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> list[str]:
        _ = p

        comments: list[str] = []

        with p.begin_session() as s:
            # Already have Label from updated v0.13 migrator, skip this one
            try:
                dump_table_configs(s, Label)
            except exc.NoResultFound:
                pass
            else:
                return comments
            Base.metadata.create_all(
                s.get_bind(),
                [Label.sql_table(), LabelLink.sql_table()],
            )

        # Move existing tags to labels
        with p.begin_session() as s:
            stmt = "SELECT id_, name FROM tag"
            # Hand crafted SQL statement can't use query_to_dict
            tags: dict[int, str] = dict(s.execute(sqlalchemy.text(stmt)).all())  # type: ignore[attr-defined]

            labels = [Label(id_=tag_id, name=name) for tag_id, name in tags.items()]
            s.add_all(labels)
            s.flush()

            stmt = "SELECT tag_id, t_split_id FROM tag_link"
            for tag_id, t_split_id in s.execute(sqlalchemy.text(stmt)):
                s.add(LabelLink(label_id=tag_id, t_split_id=t_split_id))

        with p.begin_session() as s:
            self.drop_table(s, "tag_link")
            self.drop_table(s, "tag")

        return comments
