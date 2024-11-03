from __future__ import annotations

import datetime
import re

from nummus import utils
from nummus.models import (
    Account,
    BudgetAssignment,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestEmergencyFund(WebTestBase):
    def test_page(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()

        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()

        # No emergency fund should not error out
        endpoint = "emergency_fund.page"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("No spending", result)
        self.assertRegex(
            result,
            r'<script>emergencyFundChart\.update\(.*"balances": \[.+\].*\)</script>',
        )

        # Add an emergency fund
        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Emergency Fund")
                .one()[0]
            )
            b = BudgetAssignment(category_id=t_cat_id, month_ord=month_ord, amount=10)
            s.add(b)

            # Mark account as budgeted
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            acct.budgeted = True

            # Mark groceries as essential
            s.query(TransactionCategory).where(
                TransactionCategory.name == "Groceries",
            ).update({"essential": True})

            # Add spending
            txn = Transaction(
                account_id=acct.id_,
                date=today,
                amount=-100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Groceries"],
            )
            s.add_all((txn, t_split))

            # Add spending >3 months ago
            txn = Transaction(
                account_id=acct.id_,
                date=today - datetime.timedelta(days=100),
                amount=-100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Groceries"],
            )
            s.add_all((txn, t_split))
            s.commit()

            # Add spending >3 months ago
            txn = Transaction(
                account_id=acct.id_,
                date=today - datetime.timedelta(days=300),
                amount=-100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Groceries"],
            )
            s.add_all((txn, t_split))
            s.commit()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("You have $10 in your emergency fund", result)
        self.assertIn("You need $39 for emergencies", result)
        self.assertIn("increasing your emergency fund by $29", result)
        self.assertRegex(
            result,
            r'<script>emergencyFundChart\.update\(.*"balances": \[.+\].*\)</script>',
        )
        self.assertIn("Groceries", result)
        m = re.search(
            r"Groceries.*\$(\d+\.\d+).*\$(\d+\.\d+).*\$(\d+\.\d+)",
            result,
            re.S,
        )
        if m is None:
            self.fail("Could not find Groceries row")
        else:
            self.assertEqualWithinError(float(m[1]), 32.97, 0.01)
            self.assertEqualWithinError(float(m[2]), 98.91, 0.01)
            self.assertEqualWithinError(float(m[3]), 197.83, 0.01)

        # Increase fund to $100
        with p.get_session() as s:
            s.query(BudgetAssignment).update({"amount": 100})
            s.commit()
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("You have $100 in your emergency fund", result)
        self.assertIn("will cover 5.5 months", result)
        self.assertIn("good shape", result)

        # Increase fund to $200
        with p.get_session() as s:
            s.query(BudgetAssignment).update({"amount": 200})
            s.commit()
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("You have $200 in your emergency fund", result)
        self.assertIn("will cover 10.7 months", result)
        self.assertIn("extra $88 could be invested", result)

    def test_dashboard(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()

        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()

        # No budget should not error out
        endpoint = "emergency_fund.dashboard"
        result, _ = self.web_get(endpoint)
        self.assertIn("No spending", result)
        self.assertRegex(
            result,
            r"<script>emergencyFundChart\.updateDashboard\("
            r'.*"balances": \[.+\].*\)</script>',
        )

        # Add an emergency fund
        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Emergency Fund")
                .one()[0]
            )
            b = BudgetAssignment(category_id=t_cat_id, month_ord=month_ord, amount=10)
            s.add(b)

            # Mark account as budgeted
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            acct.budgeted = True

            # Mark groceries as essential
            s.query(TransactionCategory).where(
                TransactionCategory.name == "Groceries",
            ).update({"essential": True})

            # Add spending
            txn = Transaction(
                account_id=acct.id_,
                date=today,
                amount=-100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Groceries"],
            )
            s.add_all((txn, t_split))

            # Add spending >3 months ago
            txn = Transaction(
                account_id=acct.id_,
                date=today - datetime.timedelta(days=100),
                amount=-100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Groceries"],
            )
            s.add_all((txn, t_split))
            s.commit()

            # Add spending >3 months ago
            txn = Transaction(
                account_id=acct.id_,
                date=today - datetime.timedelta(days=300),
                amount=-100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Groceries"],
            )
            s.add_all((txn, t_split))
            s.commit()

        result, _ = self.web_get(endpoint)
        self.assertIn("increase your fund to at least $39", result)
        self.assertRegex(
            result,
            r"<script>emergencyFundChart\.updateDashboard"
            r'\(.*"balances": \[.+\].*\)</script>',
        )

        # Increase fund to $100
        with p.get_session() as s:
            s.query(BudgetAssignment).update({"amount": 100})
            s.commit()
        result, _ = self.web_get(endpoint)
        self.assertIn("cover 5.5 months", result)

        # Increase fund to $200
        with p.get_session() as s:
            s.query(BudgetAssignment).update({"amount": 200})
            s.commit()
        result, _ = self.web_get(endpoint)
        self.assertIn("$88 could be invested", result)
