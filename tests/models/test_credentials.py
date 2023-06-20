"""Test module nummus.models.credentials
"""

import datetime

from nummus import models
from nummus.models import credentials

from tests import base


class TestCredentials(base.TestBase):
  """Test AnnualBudget class
  """

  def test_init_properties(self):
    session = self._get_session()
    models.metadata_create_all(session)

    d = {
        "site": self.random_string(),
        "user": self.random_string(),
        "password": self.random_string()
    }

    c = credentials.Credentials(**d)
    session.add(c)
    session.commit()

    self.assertEqual(d["site"], c.site)
    self.assertEqual(d["user"], c.user)
    self.assertEqual(d["password"], c.password)

    d.pop("password")
    d["id"] = c.id
    result = c.to_dict()
    self.assertDictEqual(d, result)