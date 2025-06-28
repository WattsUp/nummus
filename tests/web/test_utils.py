from __future__ import annotations

import datetime
from decimal import Decimal

from nummus import models, utils
from nummus.models import Account, AccountCategory, base_uri
from nummus.web import utils as web_utils
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
            budgeted=True,
        )
        s.add(acct)
        s.commit()

        acct_uri = acct.uri
        result = web_utils.find(s, Account, acct_uri)
        self.assertEqual(result, acct)

        # Account does not exist
        mising_uri = Account.id_to_uri(acct.id_ + 1)
        self.assertHTTPRaises(404, web_utils.find, s, Account, mising_uri)

        # Bad URI
        bad_uri = base_uri.id_to_uri(0)
        self.assertHTTPRaises(400, web_utils.find, s, Account, bad_uri)

    def test_parse_period(self) -> None:
        today = datetime.date.today()

        start = utils.date_add_months(today, -1)
        end = today
        result = web_utils.parse_period("1m")
        self.assertEqual(result, (start, end))

        start = utils.date_add_months(today, -6)
        end = today
        result = web_utils.parse_period("6m")
        self.assertEqual(result, (start, end))

        start = datetime.date(today.year - 1, today.month, today.day)
        end = today
        result = web_utils.parse_period("1yr")
        self.assertEqual(result, (start, end))

        start = datetime.date(today.year, 1, 1)
        end = today
        result = web_utils.parse_period("ytd")
        self.assertEqual(result, (start, end))

        start = None
        end = today
        result = web_utils.parse_period("max")
        self.assertEqual(result, (start, end))

        self.assertHTTPRaises(400, web_utils.parse_period, self.random_string())

    def test_date_labels(self) -> None:
        today = datetime.date.today()

        start = today - datetime.timedelta(days=utils.DAYS_IN_WEEK)
        end = today
        result, result_date_mode = web_utils.date_labels(
            start.toordinal(),
            end.toordinal(),
        )
        self.assertEqual(result[0], start.isoformat())
        self.assertEqual(result[-1], end.isoformat())
        self.assertEqual(result_date_mode, "days")

        start = utils.date_add_months(today, -1)
        end = today
        result, result_date_mode = web_utils.date_labels(
            start.toordinal(),
            end.toordinal(),
        )
        self.assertEqual(result[0], start.isoformat())
        self.assertEqual(result[-1], end.isoformat())
        self.assertEqual(result_date_mode, "weeks")

        start = utils.date_add_months(today, -3)
        end = today
        result, result_date_mode = web_utils.date_labels(
            start.toordinal(),
            end.toordinal(),
        )
        self.assertEqual(result[0], start.isoformat())
        self.assertEqual(result[-1], end.isoformat())
        self.assertEqual(result_date_mode, "months")

        start = utils.date_add_months(today, -24)
        end = today
        result, result_date_mode = web_utils.date_labels(
            start.toordinal(),
            end.toordinal(),
        )
        self.assertEqual(result[0], start.isoformat())
        self.assertEqual(result[-1], end.isoformat())
        self.assertEqual(result_date_mode, "years")

    def test_ctx_to_json(self) -> None:
        ctx: dict[str, object] = {"number": Decimal("1234.1234")}
        result = web_utils.ctx_to_json(ctx)
        target = '{"number":1234.12}'
        self.assertEqual(result, target)

        class Fake:
            pass

        ctx = {"fake": Fake()}
        self.assertRaises(TypeError, web_utils.ctx_to_json, ctx)
