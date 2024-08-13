from __future__ import annotations

import datetime
from decimal import Decimal

from nummus.models import Account, AccountCategory, Budget
from tests.controllers.base import WebTestBase


class TestEmergencyFund(WebTestBase):
    def test_page(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()

        today = datetime.date.today()
        today_ord = today.toordinal()

        acct_name = d["acct"]

        # No budget should not error out
        endpoint = "emergency_fund.page"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("No budget", result)
        self.assertNotIn(acct_name, result)
        self.assertRegex(
            result,
            r'<script>emergencyFundChart\.update\(.*"balances": \[.+\].*\)</script>',
        )

        # Add a budget
        with p.get_session() as s:
            b = Budget(date_ord=today_ord, amount=-10)
            s.add(b)
            s.commit()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("You have $0 in your emergency fund", result)
        self.assertNotIn(acct_name, result)
        self.assertRegex(
            result,
            r'<script>emergencyFundChart\.update\(.*"balances": \[.+\].*\)</script>',
        )

        # Add account to emergency fund
        with p.get_session() as s:
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            acct.emergency = True
            s.commit()
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn(acct_name, result)
        self.assertIn("You have $90 in your emergency fund", result)
        self.assertIn("which will cover 9 months", result)
        self.assertIn("extra $30 could be invested", result)

        # Adjust budget to be mid and add closed account
        with p.get_session() as s:
            b = s.query(Budget).first()
            if b is None:
                self.fail("Budget is missing")
            b.amount = Decimal(-20)

            acct_name_new = self.random_string()
            acct = Account(
                name=acct_name_new,
                institution=self.random_string(),
                category=AccountCategory.CASH,
                closed=True,
                emergency=True,
            )
            s.add(acct)
            s.commit()
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn(acct_name, result)
        self.assertNotIn(acct_name_new, result)
        self.assertIn("You have $90 in your emergency fund", result)
        self.assertIn("which will cover 4 months", result)
        self.assertIn("good shape", result)

        # Adjust budget to be low
        with p.get_session() as s:
            b = s.query(Budget).first()
            if b is None:
                self.fail("Budget is missing")
            b.amount = Decimal(-40)
            s.commit()
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn(acct_name, result)
        self.assertIn("You have $90 in your emergency fund", result)
        self.assertIn("You need $120 for emergencies", result)
        self.assertIn("increasing your emergency fund by $30", result)

    def test_dashboard(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()

        today = datetime.date.today()
        today_ord = today.toordinal()

        # No budget should not error out
        endpoint = "emergency_fund.dashboard"
        result, _ = self.web_get(endpoint)
        self.assertIn("No budget", result)
        self.assertRegex(
            result,
            r"<script>emergencyFundChart\.updateDashboard\("
            r'.*"balances": \[.+\].*\)</script>',
        )

        # Add a budget
        with p.get_session() as s:
            b = Budget(date_ord=today_ord, amount=-10)
            s.add(b)
            s.commit()

        result, _ = self.web_get(endpoint)
        self.assertIn("increase your fund to at least $30.", result)
        self.assertRegex(
            result,
            r"<script>emergencyFundChart\.updateDashboard\("
            r'.*"balances": \[.+\].*\)</script>',
        )

        # Add account to emergency fund
        with p.get_session() as s:
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            acct.emergency = True
            s.commit()
        result, _ = self.web_get(endpoint)
        self.assertIn("$30 could be invested", result)

        # Adjust budget to be mid and add closed account
        with p.get_session() as s:
            b = s.query(Budget).first()
            if b is None:
                self.fail("Budget is missing")
            b.amount = Decimal(-20)

            acct = Account(
                name=self.random_string(),
                institution=self.random_string(),
                category=AccountCategory.CASH,
                closed=True,
                emergency=True,
            )
            s.add(acct)
            s.commit()
        result, _ = self.web_get(endpoint)
        self.assertIn("cover 4 months of expenses.", result)

        # Adjust budget to be low
        with p.get_session() as s:
            b = s.query(Budget).first()
            if b is None:
                self.fail("Budget is missing")
            b.amount = Decimal(-40)
            s.commit()
        result, _ = self.web_get(endpoint)
        self.assertIn("Try to increase your fund to at least $120.", result)
