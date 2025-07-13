from __future__ import annotations

import datetime
from decimal import Decimal

import flask

from nummus import utils
from nummus.controllers import emergency_fund
from nummus.models import (
    Account,
    BudgetAssignment,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)


def test_ctx(flask_app: flask.Flask) -> None:
    with flask_app.app_context():
        ctx = emergency_fund.ctx_page()

    assert ctx["current"] == Decimal()


if False:

    def test_page(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()

        today = datetime.datetime.now().astimezone().date()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()

        # No emergency fund should not error out
        endpoint = "emergency_fund.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("No spending", result)
        self.assertRegex(
            result,
            r'emergencyFund\.update\(.*"balances":\[.+\].*\)',
        )

        # Add an emergency fund
        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            b = BudgetAssignment(
                category_id=TransactionCategory.emergency_fund(s)[0],
                month_ord=month_ord,
                amount=10,
            )
            s.add(b)

            # Mark account as budgeted
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            acct.budgeted = True

            # Mark groceries as essential
            s.query(TransactionCategory).where(
                TransactionCategory.name == "groceries",
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
                category_id=categories["groceries"],
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
                category_id=categories["groceries"],
            )
            s.add_all((txn, t_split))

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
                category_id=categories["groceries"],
            )
            s.add_all((txn, t_split))

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("You have $10 in your emergency fund", result)
        self.assertIn("You need $39 for emergencies", result)
        self.assertIn("increasing your emergency fund by $29", result)
        self.assertRegex(
            result,
            r'emergencyFund\.update\(.*"balances":\[.+\].*\)',
        )
        self.assertIn("Groceries", result)

        # Increase fund to $100
        with p.begin_session() as s:
            s.query(BudgetAssignment).update({"amount": 100})
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("You have $100 in your emergency fund", result)
        self.assertIn("will cover 5 months", result)
        self.assertIn("good shape", result)

        # Increase fund to $200
        with p.begin_session() as s:
            s.query(BudgetAssignment).update({"amount": 200})
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("You have $200 in your emergency fund", result)
        self.assertIn("will cover 11 months", result)
        self.assertIn("extra $88 could be invested", result)

    def test_dashboard(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()

        today = datetime.datetime.now().astimezone().date()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()

        # No budget should not error out
        endpoint = "emergency_fund.dashboard"
        result, _ = self.web_get(endpoint)
        self.assertIn("No spending", result)
        self.assertRegex(
            result,
            r'emergencyFund\.updateDashboard\(.*"balances":\[.+\].*\)',
        )

        # Add an emergency fund
        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            b = BudgetAssignment(
                category_id=TransactionCategory.emergency_fund(s)[0],
                month_ord=month_ord,
                amount=10,
            )
            s.add(b)

            # Mark account as budgeted
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            acct.budgeted = True

            # Mark groceries as essential
            s.query(TransactionCategory).where(
                TransactionCategory.name == "groceries",
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
                category_id=categories["groceries"],
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
                category_id=categories["groceries"],
            )
            s.add_all((txn, t_split))

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
                category_id=categories["groceries"],
            )
            s.add_all((txn, t_split))

        result, _ = self.web_get(endpoint)
        self.assertIn("increase your fund to at least $39", result)
        self.assertRegex(
            result,
            r'emergencyFund\.updateDashboard\(.*"balances":\[.+\].*\)',
        )

        # Increase fund to $100
        with p.begin_session() as s:
            s.query(BudgetAssignment).update({"amount": 100})
        result, _ = self.web_get(endpoint)
        self.assertIn("cover 5 months", result)

        # Increase fund to $200
        with p.begin_session() as s:
            s.query(BudgetAssignment).update({"amount": 200})
        result, _ = self.web_get(endpoint)
        self.assertIn("$88 could be invested", result)
