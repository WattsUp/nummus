import datetime
import uuid

import flask

from nummus import models, web_utils
from nummus.models import Account, AccountCategory
from tests.base import TestBase


class TestWebUtils(TestBase):
    def test_find(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        # Create accounts
        acct = Account(
            name="Monkey Bank Checking",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
        )
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

    def test_parse_period(self) -> None:
        today = datetime.date.today()

        result = web_utils.parse_period("custom", None, None)
        self.assertEqual(result, (today, today))

        start = datetime.date(today.year, today.month, 4)
        end = datetime.date(today.year, today.month, 10)
        result = web_utils.parse_period("custom", start, end)
        self.assertEqual(result, (start, end))
        result = web_utils.parse_period("custom", end, start)
        self.assertEqual(result, (end, end))

        start = datetime.date(today.year, today.month, 1)
        end = today
        result = web_utils.parse_period("this-month", None, None)
        self.assertEqual(result, (start, end))

        end = datetime.date(today.year, today.month, 1) - datetime.timedelta(days=1)
        start = datetime.date(end.year, end.month, 1)
        result = web_utils.parse_period("last-month", None, None)
        self.assertEqual(result, (start, end))

        start = today - datetime.timedelta(days=30)
        end = today
        result = web_utils.parse_period("30-days", None, None)
        self.assertEqual(result, (start, end))

        start = today - datetime.timedelta(days=90)
        end = today
        result = web_utils.parse_period("90-days", None, None)
        self.assertEqual(result, (start, end))

        start = datetime.date(today.year - 1, today.month, 1)
        end = today
        result = web_utils.parse_period("1-year", None, None)
        self.assertEqual(result, (start, end))

        start = datetime.date(today.year - 5, today.month, 1)
        end = today
        result = web_utils.parse_period("5-years", None, None)
        self.assertEqual(result, (start, end))

        start = datetime.date(today.year, 1, 1)
        end = today
        result = web_utils.parse_period("this-year", None, None)
        self.assertEqual(result, (start, end))

        start = datetime.date(today.year - 1, 1, 1)
        end = datetime.date(today.year - 1, 12, 31)
        result = web_utils.parse_period("last-year", None, None)
        self.assertEqual(result, (start, end))

        result = web_utils.parse_period("all", None, None)
        self.assertEqual(result, (None, today))

        self.assertHTTPRaises(
            400, web_utils.parse_period, self.random_string(), None, None
        )

    def test_validate_image_upload(self) -> None:
        # Missing length
        req = flask.Request({})
        self.assertHTTPRaises(411, web_utils.validate_image_upload, req)

        # Still missing type
        req = flask.Request({"CONTENT_LENGTH": "1000001"})
        self.assertHTTPRaises(422, web_utils.validate_image_upload, req)

        # Still bad type
        req = flask.Request(
            {"CONTENT_TYPE": "application/pdf", "CONTENT_LENGTH": "1000001"}
        )
        self.assertHTTPRaises(415, web_utils.validate_image_upload, req)

        # Still bad type
        req = flask.Request({"CONTENT_TYPE": "image/pdf", "CONTENT_LENGTH": "1000001"})
        self.assertHTTPRaises(415, web_utils.validate_image_upload, req)

        # Still too long
        req = flask.Request({"CONTENT_TYPE": "image/png", "CONTENT_LENGTH": "1000001"})
        self.assertHTTPRaises(413, web_utils.validate_image_upload, req)

        # All good
        req = flask.Request({"CONTENT_TYPE": "image/png", "CONTENT_LENGTH": "1000000"})
        suffix = web_utils.validate_image_upload(req)
        self.assertEqual(".png", suffix)
