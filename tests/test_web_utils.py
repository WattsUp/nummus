"""Test module nummus.web_utils
"""

import datetime
import uuid

import flask

from nummus import models, web_utils
from nummus.models import Account, AccountCategory

from tests.base import TestBase


class TestWebUtils(TestBase):
  """Test web utility methods
  """

  def test_find(self):
    s = self.get_session()
    models.metadata_create_all(s)

    # Create accounts
    acct = Account(name="Monkey Bank Checking",
                   institution="Monkey Bank",
                   category=AccountCategory.CASH,
                   closed=False)
    s.add(acct)
    s.commit()

    acct_uuid = str(acct.uuid)
    result = web_utils.find(s, Account, acct_uuid)
    self.assertEqual(acct, result)

    # Get by uuid without dashes
    result = web_utils.find(s, Account, acct_uuid.replace("-", ""))
    self.assertEqual(acct, result)

    # Account does not exist
    self.assertHTTPRaises(404, web_utils.find, s, Account, str(uuid.uuid4()))

  def test_parse_uuid(self):
    target = uuid.uuid4()
    s = str(target)
    result = web_utils.parse_uuid(s)
    self.assertEqual(target, result)

    s = str(target).replace("-", "")
    result = web_utils.parse_uuid(s)
    self.assertEqual(target, result)

    result = web_utils.parse_uuid(target)
    self.assertEqual(target, result)

    result = web_utils.parse_uuid(None)
    self.assertIsNone(result)

    # Bad UUID
    self.assertHTTPRaises(400, web_utils.parse_uuid, self.random_string())

  def test_parse_date(self):
    target = datetime.date.today()
    s = target.isoformat()
    result = web_utils.parse_date(s)
    self.assertEqual(target, result)

    result = web_utils.parse_date(target)
    self.assertEqual(target, result)

    result = web_utils.parse_date(None)
    self.assertIsNone(result)

    # Bad Date
    self.assertHTTPRaises(400, web_utils.parse_date, self.random_string())

  def test_parse_enum(self):
    target: AccountCategory = self._RNG.choice(AccountCategory)
    s = target.name.lower()
    result = web_utils.parse_enum(s, AccountCategory)
    self.assertEqual(target, result)

    result = web_utils.parse_enum(target, AccountCategory)
    self.assertEqual(target, result)

    result = web_utils.parse_enum(None, AccountCategory)
    self.assertIsNone(result)

    # Bad Enum
    self.assertHTTPRaises(400, web_utils.parse_enum, self.random_string(),
                          AccountCategory)

  def test_validate_image_upload(self):
    # Missing length
    req = flask.Request({})
    self.assertHTTPRaises(411, web_utils.validate_image_upload, req)

    # Still missing type
    req = flask.Request({"CONTENT_LENGTH": "1000001"})
    self.assertHTTPRaises(422, web_utils.validate_image_upload, req)

    # Still bad type
    req = flask.Request({
        "CONTENT_TYPE": "application/pdf",
        "CONTENT_LENGTH": "1000001"
    })
    self.assertHTTPRaises(415, web_utils.validate_image_upload, req)

    # Still bad type
    req = flask.Request({
        "CONTENT_TYPE": "image/pdf",
        "CONTENT_LENGTH": "1000001"
    })
    self.assertHTTPRaises(415, web_utils.validate_image_upload, req)

    # Still too long
    req = flask.Request({
        "CONTENT_TYPE": "image/png",
        "CONTENT_LENGTH": "1000001"
    })
    self.assertHTTPRaises(413, web_utils.validate_image_upload, req)

    # All good
    req = flask.Request({
        "CONTENT_TYPE": "image/png",
        "CONTENT_LENGTH": "1000000"
    })
    suffix = web_utils.validate_image_upload(req)
    self.assertEqual(".png", suffix)
