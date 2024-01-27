from __future__ import annotations

import datetime
from decimal import Decimal

import sqlalchemy.exc

from nummus import controllers
from nummus.controllers import common
from nummus.models import (
    Account,
    AccountCategory,
    Budget,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestCommon(WebTestBase):
    def test_sidebar(self) -> None:
        endpoint = "/h/sidebar"
        result, _ = self.web_get(endpoint)
        self.assertIn("Click to show", result)

        result, _ = self.web_get(endpoint, queries={"closed": "included"})
        self.assertIn("Click to hide", result)

    def test_ctx_sidebar(self) -> None:
        p = self._portfolio

        today = datetime.date.today()
        today_ord = today.toordinal()

        with self._flask_app.app_context():
            result = common.ctx_sidebar()
        target = {
            "net-worth": Decimal(0),
            "assets": Decimal(0),
            "liabilities": Decimal(0),
            "assets-w": 0,
            "liabilities-w": 0,
            "include_closed": False,
            "n_closed": 0,
            "categories": {},
        }
        self.assertDictEqual(result, target)

        with p.get_session() as s:
            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                emergency=False,
            )
            acct_savings = Account(
                name="Monkey Bank Savings",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=True,
                emergency=False,
            )
            s.add_all((acct_checking, acct_savings))
            s.commit()

            acct_uri_checking = acct_checking.uri
            acct_uri_savings = acct_savings.uri

            categories: dict[str, TransactionCategory] = {
                cat.name: cat for cat in s.query(TransactionCategory).all()
            }
            t_cat = categories["Uncategorized"]

            txn = Transaction(
                account_id=acct_savings.id_,
                date_ord=today_ord,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat.id_,
            )
            s.add_all((txn, t_split))

            txn = Transaction(
                account_id=acct_checking.id_,
                date_ord=today_ord,
                amount=-50,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat.id_,
            )
            s.add_all((txn, t_split))

            s.commit()

        target_accounts = [
            {
                "institution": "Monkey Bank",
                "name": "Monkey Bank Checking",
                "updated_days_ago": 0,
                "value": Decimal("-50.000000"),
                "category": AccountCategory.CASH,
                "closed": False,
                "uri": acct_uri_checking,
            },
            {
                "institution": "Monkey Bank",
                "name": "Monkey Bank Savings",
                "updated_days_ago": 0,
                "value": Decimal("100.000000"),
                "category": AccountCategory.CASH,
                "closed": True,
                "uri": acct_uri_savings,
            },
        ]
        target = {
            "net-worth": Decimal("50.000000"),
            "assets": Decimal("100.000000"),
            "liabilities": Decimal("-50.000000"),
            "assets-w": Decimal("66.67"),
            "liabilities-w": Decimal("33.33"),
            "include_closed": True,
            "n_closed": 1,
            "categories": {
                AccountCategory.CASH: (Decimal("50.000000"), target_accounts),
            },
        }
        with self._flask_app.app_context():
            result = common.ctx_sidebar(include_closed=True)
        self.assertDictEqual(result, target)

        target_accounts = [target_accounts[0]]
        target = {
            "net-worth": Decimal("50.000000"),
            "assets": Decimal("100.000000"),
            "liabilities": Decimal("-50.000000"),
            "assets-w": Decimal("66.67"),
            "liabilities-w": Decimal("33.33"),
            "include_closed": False,
            "n_closed": 1,
            "categories": {
                AccountCategory.CASH: (Decimal("50.000000"), target_accounts),
            },
        }
        with self._flask_app.app_context():
            result = common.ctx_sidebar(include_closed=False)
        self.assertDictEqual(result, target)

    def test_empty(self) -> None:
        self.assertEqual(common.empty(), "")

    def test_overlay_swap(self) -> None:
        with self._flask_app.app_context():
            content = self.random_string()
            event_0 = self.random_string()
            event_1 = self.random_string()

            response = common.overlay_swap()
            data: bytes = response.data
            html = data.decode()
            self.assertValidHTML(html)
            self.assertNotIn(content, html)
            self.assertNotIn("HX-Trigger", response.headers)

            response = common.overlay_swap(content, event_0)
            data: bytes = response.data
            html = data.decode()
            self.assertValidHTML(html)
            self.assertIn(content, html)
            self.assertEqual(response.headers["HX-Trigger"], event_0)

            response = common.overlay_swap(content, [event_0, event_1])
            data: bytes = response.data
            html = data.decode()
            self.assertValidHTML(html)
            self.assertIn(content, html)
            self.assertEqual(response.headers["HX-Trigger"], f"{event_0},{event_1}")

    def test_error(self) -> None:
        p = self._portfolio

        today = datetime.date.today()
        today_ord = today.toordinal()

        with self._flask_app.app_context():
            e_str = self.random_string()
            html = common.error(e_str)
            self.assertValidHTML(html)
            self.assertIn(e_str, html)

            with p.get_session() as s:
                t_cat = TransactionCategory()
                t_cat.group = TransactionCategoryGroup.OTHER
                t_cat.locked = False
                t_cat.is_profit_loss = False

                with self.assertRaises(sqlalchemy.exc.IntegrityError) as cm:
                    s.add(t_cat)
                    s.commit()
                e: sqlalchemy.exc.IntegrityError = cm.exception
                e_str = "Transaction category name must not be empty"
                html = common.error(e)
                self.assertValidHTML(html)
                self.assertIn(e_str, html)
                s.rollback()

                name = self.random_string()
                t_cat.name = name
                s.add(t_cat)
                s.commit()

                t_cat = TransactionCategory()
                t_cat.name = name
                t_cat.group = TransactionCategoryGroup.OTHER
                t_cat.locked = False
                t_cat.is_profit_loss = False
                with self.assertRaises(sqlalchemy.exc.IntegrityError) as cm:
                    s.add(t_cat)
                    s.commit()
                e: sqlalchemy.exc.IntegrityError = cm.exception
                e_str = "Transaction category name must be unique"
                html = common.error(e)
                self.assertValidHTML(html)
                self.assertIn(e_str, html)
                s.rollback()

                b = Budget()
                b.date_ord = today_ord
                b.amount = Decimal(1)
                with self.assertRaises(sqlalchemy.exc.IntegrityError) as cm:
                    s.add(b)
                    s.commit()
                e: sqlalchemy.exc.IntegrityError = cm.exception
                e_str = "Budget amount must be zero or negative"
                html = common.error(e)
                self.assertValidHTML(html)
                self.assertIn(e_str, html)
                s.rollback()

    def test_add_routes(self) -> None:
        controllers.add_routes(self._flask_app)
        routes = self._flask_app.url_map
        for rule in routes.iter_rules():
            self.assertFalse(rule.endpoint.startswith("nummus.controllers."))
            self.assertFalse(rule.endpoint.startswith("."))
            self.assertTrue(rule.rule.startswith("/"))
            self.assertFalse(rule.rule != "/" and rule.rule.endswith("/"))
