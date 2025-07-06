from __future__ import annotations

import pytest

from nummus import exceptions as exc
from nummus.models import BudgetGroup


@pytest.mark.xfail
def test_init_properties() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    d = {
        "name": self.random_string(),
        "position": 0,
    }

    g = BudgetGroup(**d)
    s.add(g)
    s.commit()

    self.assertEqual(g.name, d["name"])
    self.assertEqual(g.position, d["position"])

    # Short strings are bad
    self.assertRaises(exc.InvalidORMValueError, setattr, g, "name", "b")

    # No strings are bad
    g.name = ""
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # Duplicate names are bad
    g = BudgetGroup(name=d["name"], position=1)
    s.add(g)
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # Duplicate positions are bad
    g = BudgetGroup(name=self.random_string(), position=0)
    s.add(g)
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()
