from __future__ import annotations

import datetime
from decimal import Decimal

import time_machine

from nummus import utils
from nummus.controllers import budgeting
from nummus.models import (
    BudgetAssignment,
    BudgetGroup,
    Target,
    TargetPeriod,
    TargetType,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestBudgeting(WebTestBase):
    def test_page(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        month_str = month.isoformat()[:7]
        month_last = utils.date_add_months(month, -1)

        with p.begin_session() as s:
            t_cat_id_0 = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Uncategorized")
                .one()[0]
            )
            t_cat_id_1 = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "General Merchandise")
                .one()[0]
            )

        endpoint = "budgeting.page"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("Budgeting", result)
        self.assertIn(month_str, result)
        self.assertRegex(
            result,
            r"<div.*>[ \n]+Ungrouped[ \n]+</div>[ \n]+"
            r"<div.*>\$0.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>",
        )
        self.assertRegex(result, r"hx-get=.*>-\$10.00</span>")
        self.assertNotIn("General Merchandise", result)
        self.assertRegex(
            result,
            r"<div>\$100.00</div>[ \n]+<div .*>Ready to assign</div>[ \n]+",
        )
        self.assertRegex(result, r"1[ \n]+category is[ \n]+overspent")

        # Assign to category and add a target
        with p.begin_session() as s:
            a = BudgetAssignment(month_ord=month_ord, amount=10, category_id=t_cat_id_0)
            s.add(a)

        result, _ = self.web_get((endpoint, {"month": month_str}), headers=headers)
        self.assertRegex(
            result,
            r"<div.*>[ \n]+Ungrouped[ \n]+</div>[ \n]+"
            r"<div.*>\$10.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>\$0.00</div>",
        )
        self.assertRegex(result, r"<span .*>\$0.00</span>")
        self.assertRegex(
            result,
            r"<div>\$90.00</div>[ \n]+<div .*>Ready to assign</div>",
        )
        self.assertNotIn("overspent", result)

        # Assign to other category
        with p.begin_session() as s:
            a = BudgetAssignment(
                month_ord=month_last.toordinal(),
                amount=50,
                category_id=t_cat_id_1,
            )
            s.add(a)

            tar = Target(
                category_id=t_cat_id_1,
                amount=Decimal(50),
                type_=TargetType.BALANCE,
                period=TargetPeriod.ONCE,
                repeat_every=0,
            )
            s.add(tar)

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<div.*>[ \n]+Ungrouped[ \n]+</div>[ \n]+"
            r"<div.*>\$10.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>\$50.00</div>",
        )
        self.assertRegex(result, r"<span .*>\$0.00</span>")
        self.assertRegex(result, r"hx-get=.*>\$50.00</span>")
        self.assertRegex(
            result,
            r"<div>\$40.00</div>[ \n]+<div .*>Ready to assign</div>[ \n]+",
        )
        self.assertNotIn("overspent", result)
        self.assertIn("Funded", result)
        i_uncategorized = result.find("Uncategorized")
        i_general = result.find("General Merchandise")
        self.assertLess(i_general, i_uncategorized)

        # Group General Merchandise
        with p.begin_session() as s:
            g = BudgetGroup(name="Bills", position=0)
            s.add(g)
            s.flush()
            g_bills_id = g.id_
            s.query(TransactionCategory).where(
                TransactionCategory.name == "General Merchandise",
            ).update({"budget_group_id": g_bills_id, "budget_position": 0})

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<span.*>Bills</span>[ \n]+</div>[ \n]+"
            r"<div.*>\$0.00</div>[ \n]+"
            r"<div.*>\$0.00</div>[ \n]+"
            r"<div.*>\$50.00</div>",
        )
        self.assertRegex(
            result,
            r"<div.*>[ \n]+Ungrouped[ \n]+</div>[ \n]+"
            r"<div.*>\$10.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>\$0.00</div>",
        )
        i_uncategorized = result.find("Uncategorized")
        i_general = result.find("General Merchandise")
        self.assertLess(i_general, i_uncategorized)

        # Group Uncategorized
        with p.begin_session() as s:
            s.query(BudgetGroup).where(BudgetGroup.id_ == g_bills_id).update(
                {"position": 1},
            )
            g = BudgetGroup(name="Wants", position=0)
            s.add(g)
            s.flush()
            g_wants_id = g.id_
            s.query(TransactionCategory).where(
                TransactionCategory.name == "Uncategorized",
            ).update({"budget_group_id": g_wants_id, "budget_position": 0})

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<span.*>Bills</span>[ \n]+</div>[ \n]+"
            r"<div.*>\$0.00</div>[ \n]+"
            r"<div.*>\$0.00</div>[ \n]+"
            r"<div.*>\$50.00</div>",
        )
        self.assertRegex(
            result,
            r"<span.*>Wants</span>[ \n]+</div>[ \n]+"
            r"<div.*>\$10.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>\$0.00</div>",
        )
        i_uncategorized = result.find("Uncategorized")
        i_general = result.find("General Merchandise")
        self.assertLess(i_uncategorized, i_general)
        i_bills = result.find("Bills")
        i_wants = result.find("Wants")
        self.assertLess(i_wants, i_bills)

        # Combine groups
        with p.begin_session() as s:
            s.query(TransactionCategory).where(
                TransactionCategory.name == "General Merchandise",
            ).update({"budget_group_id": g_bills_id, "budget_position": 1})
            s.query(TransactionCategory).where(
                TransactionCategory.name == "Uncategorized",
            ).update({"budget_group_id": g_bills_id, "budget_position": 0})

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<span.*>Bills</span>[ \n]+</div>[ \n]+"
            r"<div.*>\$10.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>\$50.00</div>",
        )
        i_uncategorized = result.find("Uncategorized")
        i_general = result.find("General Merchandise")
        self.assertLess(i_uncategorized, i_general)

        # Unassign other category, assign remaining
        with p.begin_session() as s:
            s.query(BudgetAssignment).where(
                BudgetAssignment.month_ord == month_ord,
            ).update({"amount": Decimal(100)})
            a = BudgetAssignment(
                month_ord=month_ord,
                amount=-50,
                category_id=t_cat_id_1,
            )
            s.add(a)
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<span.*>Bills</span>[ \n]+</div>[ \n]+"
            r"<div.*>\$50.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>\$90.00</div>",
        )
        self.assertRegex(
            result,
            r"<div>\$0.00</div>[ \n]+<div .*>All money assigned</div>",
        )

        # Over assign
        with p.begin_session() as s:
            s.query(BudgetAssignment).where(
                BudgetAssignment.month_ord == month_ord,
            ).update({"amount": Decimal(100)})
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<span.*>Bills</span>[ \n]+</div>[ \n]+"
            r"<div.*>\$200.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>\$240.00</div>",
        )
        self.assertRegex(
            result,
            r"<div>-\$150.00</div>[ \n]+<div .*>More money assigned than held</div>",
        )

        # Add unbalanced transfer
        with p.begin_session() as s:
            t_cat_id_2 = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Transfers")
                .one()[0]
            )
            s.query(TransactionSplit).where(TransactionSplit.amount > 0).update(
                {"category_id": t_cat_id_2},
            )
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<div.*>[ \n]+Ungrouped[ \n]+</div>[ \n]+"
            r"<div.*>\$0.00</div>[ \n]+"
            r"<div.*>\$100.00</div>[ \n]+"
            r"<div.*>\$100.00</div>",
        )

    def test_assign(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        month_str = month.isoformat()[:7]

        with p.begin_session() as s:
            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Uncategorized")
                .one()[0]
            )
            t_cat_uri = TransactionCategory.id_to_uri(t_cat_id)

        endpoint = "budgeting.assign"
        url = endpoint, {"uri": t_cat_uri, "month": month_str}
        form = {"amount": "5*2"}
        result, _ = self.web_put(url, data=form)
        with p.begin_session() as s:
            a = s.query(BudgetAssignment).first()
            if a is None:
                self.fail("BudgetAssignment is missing")
            self.assertEqual(a.month_ord, month_ord)
            self.assertEqual(a.category_id, t_cat_id)
            self.assertEqual(a.amount, Decimal(10))
        self.assertRegex(
            result,
            r"<div.*>[ \n]+Ungrouped[ \n]+</div>[ \n]+"
            r"<div.*>\$10.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>\$0.00</div>",
        )

        form = {"amount": "100"}
        result, _ = self.web_put(url, data=form)
        with p.begin_session() as s:
            a = s.query(BudgetAssignment).first()
            if a is None:
                self.fail("BudgetAssignment is missing")
            self.assertEqual(a.month_ord, month_ord)
            self.assertEqual(a.category_id, t_cat_id)
            self.assertEqual(a.amount, Decimal(100))
        self.assertRegex(
            result,
            r"<div.*>[ \n]+Ungrouped[ \n]+</div>[ \n]+"
            r"<div.*>\$100.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>\$90.00</div>",
        )

        form = {"amount": "0"}
        result, _ = self.web_put(url, data=form)
        with p.begin_session() as s:
            n = s.query(BudgetAssignment).count()
            self.assertEqual(n, 0)
        self.assertRegex(
            result,
            r"<div.*>[ \n]+Ungrouped[ \n]+</div>[ \n]+"
            r"<div.*>\$0.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>[ \n]+"
            r"<div.*>-\$10.00</div>",
        )

    def test_overspending(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        month_str = month.isoformat()[:7]
        month_last = utils.date_add_months(month, -1)

        with p.begin_session() as s:
            t_cat_id_0 = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Uncategorized")
                .one()[0]
            )
            t_cat_id_1 = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "General Merchandise")
                .one()[0]
            )
            t_cat_uri_0 = TransactionCategory.id_to_uri(t_cat_id_0)
            t_cat_uri_1 = TransactionCategory.id_to_uri(t_cat_id_1)

        endpoint = "budgeting.overspending"
        url = endpoint, {"uri": t_cat_uri_0, "month": month_str}
        result, _ = self.web_get(url)
        self.assertIn("Uncategorized is overspent by $10.00", result)
        self.assertIn(
            '<option value="income">Assignable income $100.00</option>',
            result,
        )
        self.assertEqual(result.count("option"), 2)

        form = {"source": "income"}
        _, headers = self.web_put(url, data=form)
        self.assertIn("HX-Trigger", headers, msg=f"Response lack HX-Trigger {result}")
        self.assertEqual(headers["HX-Trigger"], "update-budget")
        with p.begin_session() as s:
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.category_id, t_cat_id_0)
            self.assertEqual(a.amount, Decimal(10))
            self.assertEqual(a.month_ord, month_ord)

            a.amount = Decimal(5)

            a = BudgetAssignment(month_ord=month_ord, amount=10, category_id=t_cat_id_1)
            s.add(a)

        result, _ = self.web_get(url)
        self.assertIn("Uncategorized is overspent by $5.00", result)
        self.assertIn(
            '<option value="income">Assignable income $85.00</option>',
            result,
        )
        self.assertIn(
            f'<option value="{t_cat_uri_1}">General Merchandise $10.00</option>',
            result,
        )
        self.assertEqual(result.count("option"), 4)

        form = {"source": t_cat_uri_1}
        self.web_put(url, data=form)
        with p.begin_session() as s:
            a = (
                s.query(BudgetAssignment)
                .where(BudgetAssignment.category_id == t_cat_id_0)
                .one()
            )
            self.assertEqual(a.amount, Decimal(10))
            self.assertEqual(a.month_ord, month_ord)
            a.amount = Decimal(100)

            a = (
                s.query(BudgetAssignment)
                .where(BudgetAssignment.category_id == t_cat_id_1)
                .one()
            )
            self.assertEqual(a.amount, Decimal(5))
            self.assertEqual(a.month_ord, month_ord)

        url = endpoint, {"uri": "income", "month": month_str}
        result, _ = self.web_get(url)
        self.assertIn("More money is assigned than held by $5.00", result)
        self.assertIn(
            f'<option value="{t_cat_uri_0}">Uncategorized $90.00</option>',
            result,
        )
        self.assertIn(
            f'<option value="{t_cat_uri_1}">General Merchandise $5.00</option>',
            result,
        )
        self.assertEqual(result.count("option"), 4)

        form = {"source": t_cat_uri_1}
        self.web_put(url, data=form)
        with p.begin_session() as s:
            # cat_1 would have been deleted
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.category_id, t_cat_id_0)
            self.assertEqual(a.amount, Decimal(100))
            self.assertEqual(a.month_ord, month_ord)

            a.amount = Decimal(200)
            a.month_ord = month_last.toordinal()

        url = endpoint, {"uri": "income", "month": month_str}
        result, _ = self.web_get(url)
        self.assertIn("More money is assigned than held by $100.00", result)
        self.assertIn(
            f'<option value="{t_cat_uri_0}">Uncategorized $190.00</option>',
            result,
        )
        self.assertEqual(result.count("option"), 2)

        form = {"source": t_cat_uri_0}
        self.web_put(url, data=form)
        with p.begin_session() as s:
            # cat_1 would have been deleted
            a = (
                s.query(BudgetAssignment)
                .where(BudgetAssignment.month_ord == month_last.toordinal())
                .one()
            )
            self.assertEqual(a.category_id, t_cat_id_0)
            self.assertEqual(a.amount, Decimal(200))

            a = (
                s.query(BudgetAssignment)
                .where(BudgetAssignment.month_ord == month_ord)
                .one()
            )
            self.assertEqual(a.category_id, t_cat_id_0)
            self.assertEqual(a.amount, Decimal(-100))

    def test_move(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        month_str = month.isoformat()[:7]
        month_last = utils.date_add_months(month, -1)

        with p.begin_session() as s:
            t_cat_id_0 = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Uncategorized")
                .one()[0]
            )
            t_cat_id_1 = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "General Merchandise")
                .one()[0]
            )
            t_cat_uri_0 = TransactionCategory.id_to_uri(t_cat_id_0)
            t_cat_uri_1 = TransactionCategory.id_to_uri(t_cat_id_1)

        endpoint = "budgeting.move"
        url = endpoint, {"uri": "income", "month": month_str}
        result, _ = self.web_get(url)
        self.assertIn("Assignable income has $100.00 available", result)
        self.assertIn(
            f'<option value="{t_cat_uri_0}">Uncategorized -$10.00</option>',
            result,
        )
        self.assertIn(
            f'<option value="{t_cat_uri_1}">General Merchandise $0.00</option>',
            result,
        )
        i_uncategorized = result.find("Uncategorized")
        i_general = result.find("General Merchandise")
        self.assertLess(i_uncategorized, i_general)

        form = {"destination": t_cat_uri_1}
        result, _ = self.web_put(url, data=form)
        self.assertIn("Amount to move must not be blank", result)

        form = {"destination": t_cat_uri_1, "amount": "100.00"}
        _, headers = self.web_put(url, data=form)
        self.assertIn("HX-Trigger", headers, msg=f"Response lack HX-Trigger {result}")
        self.assertEqual(headers["HX-Trigger"], "update-budget")
        with p.begin_session() as s:
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.category_id, t_cat_id_1)
            self.assertEqual(a.month_ord, month_ord)
            self.assertEqual(a.amount, Decimal(100))

        url = endpoint, {"uri": t_cat_uri_1, "month": month_str}
        result, _ = self.web_get(url)
        self.assertIn("General Merchandise has $100.00 available", result)
        self.assertIn(
            f'<option value="{t_cat_uri_0}">Uncategorized -$10.00</option>',
            result,
        )
        self.assertIn(
            '<option value="income">Assignable income $0.00</option>',
            result,
        )
        i_uncategorized = result.find("Uncategorized")
        i_income = result.find("Assignable income")
        self.assertLess(i_income, i_uncategorized)

        form = {"destination": t_cat_uri_0, "amount": "50.00"}
        self.web_put(url, data=form)
        with p.begin_session() as s:
            a = (
                s.query(BudgetAssignment)
                .where(BudgetAssignment.category_id == t_cat_id_0)
                .one()
            )
            self.assertEqual(a.amount, Decimal(50))
            self.assertEqual(a.month_ord, month_ord)

            a = (
                s.query(BudgetAssignment)
                .where(BudgetAssignment.category_id == t_cat_id_1)
                .one()
            )
            self.assertEqual(a.amount, Decimal(50))
            self.assertEqual(a.month_ord, month_ord)

        form = {"destination": "income", "amount": "50.00"}
        self.web_put(url, data=form)
        with p.begin_session() as s:
            # cat_1 would have been deleted
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.category_id, t_cat_id_0)
            self.assertEqual(a.amount, Decimal(50))
            self.assertEqual(a.month_ord, month_ord)

            a = BudgetAssignment(
                month_ord=month_last.toordinal(),
                amount=50,
                category_id=t_cat_id_1,
            )
            s.add(a)

        result, _ = self.web_get(url)
        self.assertIn("General Merchandise has $50.00 available", result)
        self.assertIn(
            f'<option value="{t_cat_uri_0}">Uncategorized $40.00</option>',
            result,
        )
        self.assertIn(
            '<option value="income">Assignable income $0.00</option>',
            result,
        )

        form = {"destination": t_cat_uri_0, "amount": "50.00"}
        self.web_put(url, data=form)
        with p.begin_session() as s:
            a = (
                s.query(BudgetAssignment)
                .where(
                    BudgetAssignment.category_id == t_cat_id_0,
                    BudgetAssignment.month_ord == month_ord,
                )
                .one()
            )
            self.assertEqual(a.amount, Decimal(100))

            a = (
                s.query(BudgetAssignment)
                .where(
                    BudgetAssignment.category_id == t_cat_id_1,
                    BudgetAssignment.month_ord == month_ord,
                )
                .one()
            )
            self.assertEqual(a.amount, Decimal(-50))

    def test_reorder(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio

        with p.begin_session() as s:
            g_0 = BudgetGroup(name=self.random_string(), position=0)
            g_1 = BudgetGroup(name=self.random_string(), position=1)
            s.add_all((g_0, g_1))
            s.flush()
            g_id_0 = g_0.id_
            g_uri_0 = g_0.uri
            g_id_1 = g_1.id_
            g_uri_1 = g_1.uri

            t_cat_0 = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "General Merchandise")
                .one()
            )
            t_cat_id_0 = t_cat_0.id_
            t_cat_uri_0 = t_cat_0.uri
            t_cat_0.budget_group_id = g_id_0
            t_cat_0.budget_position = 0

            t_cat_1 = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "Uncategorized")
                .one()
            )
            t_cat_id_1 = t_cat_1.id_
            t_cat_uri_1 = t_cat_1.uri
            t_cat_1.budget_group_id = g_id_0
            t_cat_1.budget_position = 1

            t_cat_2 = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "Groceries")
                .one()
            )
            t_cat_id_2 = t_cat_2.id_
            t_cat_uri_2 = t_cat_2.uri
            t_cat_2.budget_group_id = g_id_1
            t_cat_2.budget_position = 0

        endpoint = "budgeting.reorder"
        url = endpoint
        # Empty form doesn't make problems
        form = {}
        result, _ = self.web_put(url, data=form)
        self.assertIn('<div id="budget-table"', result)

        # Swap groups 0 and 1
        form = {
            "group_uri": [g_uri_1, g_uri_0],
            "row_uri": [t_cat_uri_2, t_cat_uri_0, t_cat_uri_1],
            "group": [g_uri_1, g_uri_0, g_uri_0],
        }
        result, _ = self.web_put(url, data=form)
        self.assertIn('<div id="budget-table"', result)

        with p.begin_session() as s:
            g = s.query(BudgetGroup).where(BudgetGroup.id_ == g_id_0).one()
            self.assertEqual(g.position, 1)
            g = s.query(BudgetGroup).where(BudgetGroup.id_ == g_id_1).one()
            self.assertEqual(g.position, 0)

            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_0)
                .one()
            )
            self.assertEqual(t_cat.budget_position, 0)
            self.assertEqual(t_cat.budget_group_id, g_id_0)
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_1)
                .one()
            )
            self.assertEqual(t_cat.budget_position, 1)
            self.assertEqual(t_cat.budget_group_id, g_id_0)
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_2)
                .one()
            )
            self.assertEqual(t_cat.budget_position, 0)
            self.assertEqual(t_cat.budget_group_id, g_id_1)

        form = {
            "group_uri": [g_uri_1, g_uri_0],
            "row_uri": [t_cat_uri_2, t_cat_uri_0, t_cat_uri_1],
            "group": [g_uri_1, g_uri_1, g_uri_0],
        }
        result, _ = self.web_put(url, data=form)
        self.assertIn('<div id="budget-table"', result)

        with p.begin_session() as s:
            g = s.query(BudgetGroup).where(BudgetGroup.id_ == g_id_0).one()
            self.assertEqual(g.position, 1)
            g = s.query(BudgetGroup).where(BudgetGroup.id_ == g_id_1).one()
            self.assertEqual(g.position, 0)

            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_0)
                .one()
            )
            self.assertEqual(t_cat.budget_position, 1)
            self.assertEqual(t_cat.budget_group_id, g_id_1)
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_1)
                .one()
            )
            self.assertEqual(t_cat.budget_position, 0)
            self.assertEqual(t_cat.budget_group_id, g_id_0)
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_2)
                .one()
            )
            self.assertEqual(t_cat.budget_position, 0)
            self.assertEqual(t_cat.budget_group_id, g_id_1)

        form = {
            "group_uri": [g_uri_1, g_uri_0],
            "row_uri": [t_cat_uri_0, t_cat_uri_1, t_cat_uri_2],
            "group": [g_uri_1, g_uri_0, ""],
        }
        result, _ = self.web_put(url, data=form)
        self.assertIn('<div id="budget-table"', result)

        with p.begin_session() as s:
            g = s.query(BudgetGroup).where(BudgetGroup.id_ == g_id_0).one()
            self.assertEqual(g.position, 1)
            g = s.query(BudgetGroup).where(BudgetGroup.id_ == g_id_1).one()
            self.assertEqual(g.position, 0)

            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_0)
                .one()
            )
            self.assertEqual(t_cat.budget_position, 0)
            self.assertEqual(t_cat.budget_group_id, g_id_1)
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_1)
                .one()
            )
            self.assertEqual(t_cat.budget_position, 0)
            self.assertEqual(t_cat.budget_group_id, g_id_0)
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_2)
                .one()
            )
            self.assertIsNone(t_cat.budget_position)
            self.assertIsNone(t_cat.budget_group_id)

    def test_group(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio

        with p.begin_session() as s:
            g_0 = BudgetGroup(name=self.random_string(), position=0)
            g_1 = BudgetGroup(name=self.random_string(), position=1)
            s.add_all((g_0, g_1))
            s.flush()
            g_id_0 = g_0.id_
            g_uri_0 = g_0.uri
            g_id_1 = g_1.id_
            g_uri_1 = g_1.uri

            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "General Merchandise")
                .one()
            )
            t_cat_id = t_cat.id_
            t_cat.budget_group_id = g_id_0
            t_cat.budget_position = 0

        endpoint = "budgeting.group"
        url = endpoint, {"uri": g_uri_0}
        form = {"name": ""}
        result, _ = self.web_put(url, data=form)
        self.assertIn("Budget group name must not be empty", result)

        form = {"name": "Bills", "closed": ""}
        result, _ = self.web_put(url, data=form)
        self.assertIn('<div id="budget-table"', result)
        self.assertIn("Bills", result)
        self.assertEqual(result.count("checked"), 1)

        form = {"name": "Bills"}
        result, _ = self.web_put(url, data=form)
        self.assertIn('<div id="budget-table"', result)
        self.assertIn("Bills", result)
        self.assertEqual(result.count("checked"), 0)

        with p.begin_session() as s:
            name = s.query(BudgetGroup.name).where(BudgetGroup.id_ == g_id_0).scalar()
            self.assertEqual(name, "Bills")

        result, _ = self.web_delete(url, data=form)
        self.assertIn('<div id="budget-table"', result)
        self.assertNotIn("Bills", result)

        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id)
                .one()
            )
            self.assertIsNone(t_cat.budget_group_id)
            self.assertIsNone(t_cat.budget_position)

            # Next category should move up
            position = (
                s.query(BudgetGroup.position).where(BudgetGroup.id_ == g_id_1).scalar()
            )
            self.assertEqual(position, 0)

        url = endpoint, {"uri": g_uri_1}
        form = {"name": "Bills", "closed": ""}
        result, _ = self.web_put(url, data=form)
        self.assertIn('<div id="budget-table"', result)
        self.assertEqual(result.count("checked"), 1)

        url = endpoint, {"uri": "ungrouped"}
        form = {"closed": ""}
        result, _ = self.web_put(url, data=form)
        self.assertIn('<div id="budget-table"', result)
        self.assertEqual(result.count("checked"), 2)

        url = endpoint, {"uri": "ungrouped"}
        form = {}
        result, _ = self.web_put(url, data=form)
        self.assertIn('<div id="budget-table"', result)
        self.assertEqual(result.count("checked"), 1)

    def test_new_group(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio

        with p.begin_session() as s:
            g_0 = BudgetGroup(name="Bills", position=0)
            s.add(g_0)

        endpoint = "budgeting.new_group"
        url = endpoint
        form = {"name": "Bills"}
        result, _ = self.web_post(url, data=form)
        self.assertIn("Budget group name must be unique", result)

        form = {"name": "Wants"}
        result, _ = self.web_post(url, data=form)
        self.assertIn('<div id="budget-table"', result)
        self.assertIn("Bills", result)
        self.assertIn("Wants", result)

    def test_ctx_target(self) -> None:
        # Test the context since testing the HTML would be very difficult
        _ = self._setup_portfolio()
        p = self._portfolio

        today = datetime.date.today()
        month = utils.start_of_month(today)
        next_year = utils.date_add_months(month, 12)

        with p.begin_session() as s:
            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "General Merchandise")
                .one()[0]
            )

            # BALANCE target, no due date
            tar = Target(
                category_id=t_cat_id,
                period=TargetPeriod.ONCE,
                type_=TargetType.BALANCE,
                amount=100,
                repeat_every=0,
            )
            s.add(tar)
            s.flush()

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(20),
                available=Decimal(30),
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(90),
                "total_assigned": Decimal(30),
                "to_go": Decimal(70),
                "on_track": False,
                "next_due_date": None,
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(70),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # Funded
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(100),
                available=Decimal(110),
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(90),
                "total_assigned": Decimal(110),
                "to_go": Decimal(-10),
                "on_track": True,
                "next_due_date": None,
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(0),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # Funded but spent a lot
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(100),
                available=Decimal(20),
                leftover=Decimal(10),
            )
            self.maxDiff = None
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(90),
                "total_assigned": Decimal(20),
                "to_go": Decimal(80),
                "on_track": False,
                "next_due_date": None,
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(80),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # BALANCE target, due in 12 months
            tar.due_date_ord = next_year.toordinal()
            s.flush()

            # Not on track
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(0),
                available=Decimal(9),
                leftover=Decimal(9),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(7),
                "total_assigned": Decimal(9),
                "to_go": Decimal(7),
                "on_track": False,
                "next_due_date": f"{next_year:%B %Y}",
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(91),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # On track
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(20),
                available=Decimal(29),
                leftover=Decimal(9),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(7),
                "total_assigned": Decimal(29),
                "to_go": Decimal(-13),
                "on_track": True,
                "next_due_date": f"{next_year:%B %Y}",
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(71),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # BALANCE target, due this month
            tar.due_date_ord = month.toordinal()
            s.flush()
            # Funded
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(120),
                available=Decimal(129),
                leftover=Decimal(9),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(91),
                "total_assigned": Decimal(129),
                "to_go": Decimal(-29),
                "on_track": True,
                "next_due_date": f"{month:%B %Y}",
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(0),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # WEEK target, REFILL
            tar.period = TargetPeriod.WEEK
            tar.type_ = TargetType.REFILL
            tar.due_date_ord = today.toordinal()
            tar.repeat_every = 1
            s.flush()
            n_weeks = utils.weekdays_in_month(today.weekday(), month)

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(20),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(100 * n_weeks - 10),
                "total_assigned": Decimal(30),
                "to_go": Decimal(100 * n_weeks - 30),
                "on_track": False,
                "next_due_date": utils.WEEKDAYS[today.weekday()],
                "progress_bars": [Decimal(100)] * n_weeks,
                "target": Decimal(100),
                "total_target": Decimal(100 * n_weeks),
                "total_to_go": Decimal(100 * n_weeks - 30),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # On track, be 2 weeks in
            now = datetime.datetime(month.year, month.month, 6)
            with time_machine.travel(now, tick=False):
                ctx = budgeting.ctx_target(
                    tar,
                    month,
                    assigned=Decimal(100 * 2),
                    available=Decimal(0),  # Spent it all
                    leftover=Decimal(10),
                )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(100 * n_weeks - 10),
                "total_assigned": Decimal(100 * 2 + 10),
                "to_go": Decimal(100 * (n_weeks - 2) - 10),
                "on_track": True,
                "next_due_date": utils.WEEKDAYS[today.weekday()],
                "progress_bars": [Decimal(100)] * n_weeks,
                "target": Decimal(100),
                "total_target": Decimal(100 * n_weeks),
                "total_to_go": Decimal(100 * (n_weeks - 2) - 10),
                "period": tar.period,
                "type": tar.type_,
            }
            self.maxDiff = None
            self.assertEqual(ctx, target)

            # Not on track, be 3 weeks in
            now = datetime.datetime(month.year, month.month, 17)
            with time_machine.travel(now, tick=False):
                ctx = budgeting.ctx_target(
                    tar,
                    month,
                    assigned=Decimal(100 * 2),
                    available=Decimal(0),  # Spent it all
                    leftover=Decimal(10),
                )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(100 * n_weeks - 10),
                "total_assigned": Decimal(100 * 2 + 10),
                "to_go": Decimal(100 * (n_weeks - 2) - 10),
                "on_track": False,
                "next_due_date": utils.WEEKDAYS[today.weekday()],
                "progress_bars": [Decimal(100)] * n_weeks,
                "target": Decimal(100),
                "total_target": Decimal(100 * n_weeks),
                "total_to_go": Decimal(100 * (n_weeks - 2) - 10),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # Funded
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(100 * n_weeks),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(100 * n_weeks - 10),
                "total_assigned": Decimal(100 * n_weeks + 10),
                "to_go": Decimal(-10),
                "on_track": True,
                "next_due_date": utils.WEEKDAYS[today.weekday()],
                "progress_bars": [Decimal(100)] * n_weeks,
                "target": Decimal(100),
                "total_target": Decimal(100 * n_weeks),
                "total_to_go": Decimal(0),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # WEEK target, ACCUMULATE
            tar.period = TargetPeriod.WEEK
            tar.type_ = TargetType.ACCUMULATE
            tar.due_date_ord = today.toordinal()
            tar.repeat_every = 1
            s.flush()
            n_weeks = utils.weekdays_in_month(today.weekday(), month)

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                utils.date_add_months(month, 1),
                assigned=Decimal(20),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            n_weeks = utils.weekdays_in_month(
                today.weekday(),
                utils.date_add_months(month, 1),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(100 * n_weeks),
                "total_assigned": Decimal(20),
                "to_go": Decimal(100 * n_weeks - 20),
                "on_track": False,
                "next_due_date": utils.WEEKDAYS[today.weekday()],
                "progress_bars": [Decimal(10)] + [Decimal(100)] * n_weeks,
                "target": Decimal(100),
                "total_target": Decimal(100 * n_weeks),
                "total_to_go": Decimal(100 * n_weeks - 20),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # MONTH target, ACCUMULATE
            tar.period = TargetPeriod.MONTH
            tar.type_ = TargetType.ACCUMULATE
            tar.due_date_ord = today.toordinal()
            tar.repeat_every = 2
            s.flush()

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(20),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(90),
                "total_assigned": Decimal(30),
                "to_go": Decimal(70),
                "on_track": False,
                "next_due_date": today,
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(70),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                utils.date_add_months(month, 1),
                assigned=Decimal(20),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(50),
                "total_assigned": Decimal(20),
                "to_go": Decimal(30),
                "on_track": False,
                "next_due_date": utils.date_add_months(today, 2),
                "progress_bars": [Decimal(10), Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(80),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # On track
            ctx = budgeting.ctx_target(
                tar,
                utils.date_add_months(month, 1),
                assigned=Decimal(60),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(50),
                "total_assigned": Decimal(60),
                "to_go": Decimal(-10),
                "on_track": True,
                "next_due_date": utils.date_add_months(today, 2),
                "progress_bars": [Decimal(10), Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(40),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # MONTH target, REFILL
            tar.period = TargetPeriod.MONTH
            tar.type_ = TargetType.REFILL
            tar.due_date_ord = today.toordinal()
            tar.repeat_every = 2
            s.flush()

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(20),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(90),
                "total_assigned": Decimal(30),
                "to_go": Decimal(70),
                "on_track": False,
                "next_due_date": today,
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(70),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                utils.date_add_months(month, 1),
                assigned=Decimal(20),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(45),
                "total_assigned": Decimal(30),
                "to_go": Decimal(25),
                "on_track": False,
                "next_due_date": utils.date_add_months(today, 2),
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(70),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # YEAR target, REFILL
            tar.period = TargetPeriod.YEAR
            tar.type_ = TargetType.REFILL
            tar.due_date_ord = today.toordinal()
            tar.repeat_every = 2
            s.flush()

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(20),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(90),
                "total_assigned": Decimal(30),
                "to_go": Decimal(70),
                "on_track": False,
                "next_due_date": today,
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(70),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                utils.date_add_months(month, 1),
                assigned=Decimal(20),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(4),
            )
            target: budgeting.TargetContext = {
                "target_assigned": Decimal(4),
                "total_assigned": Decimal(24),
                "to_go": Decimal(-16),
                "on_track": True,
                "next_due_date": utils.date_add_months(today, 24),
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(76),
                "period": tar.period,
                "type": tar.type_,
            }
            self.assertEqual(ctx, target)

    def test_target(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio

        today = datetime.date.today()

        with p.begin_session() as s:
            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "General Merchandise")
                .one()[0]
            )
            t_cat_uri = TransactionCategory.id_to_uri(t_cat_id)

        # Get new target editor
        endpoint = "budgeting.target"
        url = (endpoint, {"uri": t_cat_uri})
        result, _ = self.web_get(url)
        self.assertIn("New Target: General Merchandise", result)

        # Negative is bad
        form = {
            "period": "Once",
            "amount": "-100",
            "type": "BALANCE",
            "has-due": "off",
        }
        result, _ = self.web_post(url, data=form)
        self.assertIn("Target amount must be positive", result)

        # Create new target
        form = {
            "period": "Once",
            "amount": "100",
            "type": "BALANCE",
            "has-due": "off",
        }
        _, headers = self.web_post(url, data=form)
        self.assertIn("HX-Trigger", headers, msg=f"Response lack HX-Trigger {result}")
        self.assertEqual(headers["HX-Trigger"], "update-budget")

        with p.begin_session() as s:
            tar = s.query(Target).one()
            self.assertEqual(tar.category_id, t_cat_id)
            self.assertEqual(tar.period, TargetPeriod.ONCE)
            self.assertEqual(tar.type_, TargetType.BALANCE)
            self.assertEqual(tar.amount, 100)
            self.assertIsNone(tar.due_date_ord)
            self.assertEqual(tar.repeat_every, 0)

            tar_uri = tar.uri

        result, _ = self.web_post(url, data=form)
        self.assertIn("Cannot have multiple targets per category", result)

        result, _ = self.web_get((endpoint, {"uri": tar_uri, "has-due": "on"}))
        self.assertRegex(result, rf'value="{today.month}"[ \n]*selected>')

        # Edit target
        form = {
            "period": "Once",
            "amount": "100",
            "type": "BALANCE",
            "has-due": "on",
            "due-month": 12,
            "due-year": today.year + 1,
        }
        url = (endpoint, {"uri": tar_uri})
        self.web_put(url, data=form)
        with p.begin_session() as s:
            tar = s.query(Target).one()
            self.assertEqual(tar.category_id, t_cat_id)
            self.assertEqual(tar.period, TargetPeriod.ONCE)
            self.assertEqual(tar.type_, TargetType.BALANCE)
            self.assertEqual(tar.amount, 100)
            date = datetime.date(today.year + 1, 12, 1)
            self.assertEqual(tar.due_date_ord, date.toordinal())
            self.assertEqual(tar.repeat_every, 0)

        # No has-due means it shouldn't change due date
        result, _ = self.web_get(url)
        self.assertRegex(result, r'value="12"[ \n]*selected>[ \n]*December')
        self.assertRegex(result, rf'value="{today.year+1}"[ \n]*selected>')

        # Changing period to weekly should reset due date
        result, _ = self.web_get(
            (endpoint, {"uri": t_cat_uri, "period": "Weekly", "change": True}),
        )
        self.assertRegex(result, r'value="0"[ \n]*selected>[ \n]*Monday')

        form = {
            "period": "Weekly",
            "amount": "100",
            "type": "REFILL",
            "due": 1,
        }
        self.web_put(url, data=form)
        with p.begin_session() as s:
            tar = s.query(Target).one()
            self.assertEqual(tar.category_id, t_cat_id)
            self.assertEqual(tar.period, TargetPeriod.WEEK)
            self.assertEqual(tar.type_, TargetType.REFILL)
            if tar.due_date_ord is None:
                self.fail("due_date_ord is None")
            else:
                date = datetime.date.fromordinal(tar.due_date_ord)
                self.assertEqual(date.weekday(), 1)
            self.assertEqual(tar.repeat_every, 1)

        form = {
            "period": "Monthly",
            "amount": "100",
            "type": "ACCUMULATE",
            "due": today,
            "repeat": 2,
        }
        self.web_put(url, data=form)
        with p.begin_session() as s:
            tar = s.query(Target).one()
            self.assertEqual(tar.category_id, t_cat_id)
            self.assertEqual(tar.period, TargetPeriod.MONTH)
            self.assertEqual(tar.type_, TargetType.ACCUMULATE)
            if tar.due_date_ord is None:
                self.fail("due_date_ord is None")
            else:
                date = datetime.date.fromordinal(tar.due_date_ord)
                self.assertEqual(date, today)
            self.assertEqual(tar.repeat_every, 2)

        form = {
            "period": "Annually",
            "amount": "100",
            "type": "ACCUMULATE",
            "due": today,
        }
        self.web_put(url, data=form)
        with p.begin_session() as s:
            tar = s.query(Target).one()
            self.assertEqual(tar.category_id, t_cat_id)
            self.assertEqual(tar.period, TargetPeriod.YEAR)
            self.assertEqual(tar.type_, TargetType.ACCUMULATE)
            if tar.due_date_ord is None:
                self.fail("due_date_ord is None")
            else:
                date = datetime.date.fromordinal(tar.due_date_ord)
                self.assertEqual(date, today)
            self.assertEqual(tar.repeat_every, 2)

        _, headers = self.web_delete(url)
        self.assertIn("HX-Trigger", headers, msg=f"Response lack HX-Trigger {result}")
        self.assertEqual(headers["HX-Trigger"], "update-budget")
        with p.begin_session() as s:
            n = s.query(Target).count()
            self.assertEqual(n, 0)

    def test_sidebar(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio

        with p.begin_session() as s:
            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "General Merchandise")
                .one()[0]
            )
            t_cat_uri = TransactionCategory.id_to_uri(t_cat_id)

        # No category selected
        endpoint = "budgeting.sidebar"
        result, _ = self.web_get(endpoint)
        self.assertNotIn("General Merchandise", result)
        self.assertNotIn("Create Target", result)

        # Category selected without target
        url = (endpoint, {"uri": t_cat_uri})
        result, _ = self.web_get(url)
        self.assertIn("General Merchandise", result)
        self.assertIn("Create Target", result)

        with p.begin_session() as s:
            tar = Target(
                category_id=t_cat_id,
                period=TargetPeriod.ONCE,
                type_=TargetType.BALANCE,
                amount=100,
                repeat_every=0,
            )
            s.add(tar)

        # Category selected with target
        url = (endpoint, {"uri": t_cat_uri})
        result, _ = self.web_get(url)
        self.assertIn("General Merchandise", result)
        self.assertIn("Edit Target", result)
        self.assertIn("Have", result)
        self.assertIn("Assign $100.00 more to meet target", result)
