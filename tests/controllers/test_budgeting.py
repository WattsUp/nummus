from __future__ import annotations

import datetime
import re
from decimal import Decimal

import time_machine

from nummus import utils
from nummus.controllers import budgeting
from nummus.models import (
    BudgetAssignment,
    BudgetGroup,
    query_count,
    Target,
    TargetPeriod,
    TargetType,
    TransactionCategory,
    TransactionSplit,
)
from nummus.web.utils import HTTP_CODE_BAD_REQUEST
from tests.controllers.base import WebTestBase


class TestBudgeting(WebTestBase):
    def test_page(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.datetime.now().astimezone().date()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        month_str = month.isoformat()[:7]
        month_last = utils.date_add_months(month, -1)

        cat_1_id = d["cat_1_id"]
        cat_1_emoji_name = d["cat_1_emoji_name"]

        with p.begin_session() as s:
            cat_2_emoji_name = "General Merchandise"
            cat_2_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == cat_2_emoji_name.lower())
                .one()[0]
            )

        endpoint = "budgeting.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("Budgeting", result)
        self.assertIn(month_str, result)
        self.assertIn("Ungrouped", result)
        self.assertIn(r"1 category is overspent", result)

        # Assign to category and add a target
        with p.begin_session() as s:
            a = BudgetAssignment(month_ord=month_ord, amount=10, category_id=cat_1_id)
            s.add(a)

        result, _ = self.web_get((endpoint, {"month": month_str}), headers=headers)
        assigned = re.findall(r"Assigned</div><div>(-?\$\d+\.\d\d)</div>", result)
        activity = re.findall(r"Activity</div><div>(-?\$\d+\.\d\d)</div>", result)
        available = re.findall(r"Available</div><div>(-?\$\d+\.\d\d)</div>", result)
        self.assertEqual(assigned, ["$10.00"])
        self.assertEqual(activity, ["-$10.00"])
        self.assertEqual(available, ["$0.00"])
        self.assertNotIn("overspent", result)

        # Assign to other category
        with p.begin_session() as s:
            a = BudgetAssignment(
                month_ord=month_last.toordinal(),
                amount=50,
                category_id=cat_2_id,
            )
            s.add(a)

            tar = Target(
                category_id=cat_2_id,
                amount=Decimal(50),
                type_=TargetType.BALANCE,
                period=TargetPeriod.ONCE,
                repeat_every=0,
            )
            s.add(tar)

        result, _ = self.web_get(endpoint, headers=headers)
        assigned = re.findall(r"Assigned</div><div>(-?\$\d+\.\d\d)</div>", result)
        activity = re.findall(r"Activity</div><div>(-?\$\d+\.\d\d)</div>", result)
        available = re.findall(r"Available</div><div>(-?\$\d+\.\d\d)</div>", result)
        self.assertEqual(assigned, ["$10.00"])
        self.assertEqual(activity, ["-$10.00"])
        self.assertEqual(available, ["$50.00"])
        self.assertNotIn("overspent", result)
        i_cat_1 = result.find(cat_1_emoji_name)
        i_cat_2 = result.find(cat_2_emoji_name)
        self.assertLess(i_cat_2, i_cat_1)

        # Group cat 2
        with p.begin_session() as s:
            g = BudgetGroup(name="Bills", position=0)
            s.add(g)
            s.flush()
            g_bills_id = g.id_
            s.query(TransactionCategory).where(
                TransactionCategory.id_ == cat_2_id,
            ).update({"budget_group_id": g_bills_id, "budget_position": 0})

        result, _ = self.web_get(endpoint, headers=headers)
        assigned = re.findall(r"Assigned</div><div>(-?\$\d+\.\d\d)</div>", result)
        activity = re.findall(r"Activity</div><div>(-?\$\d+\.\d\d)</div>", result)
        available = re.findall(r"Available</div><div>(-?\$\d+\.\d\d)</div>", result)
        self.assertEqual(assigned, ["$0.00", "$10.00"])
        self.assertEqual(activity, ["$0.00", "-$10.00"])
        self.assertEqual(available, ["$50.00", "$0.00"])
        i_cat_1 = result.find(cat_1_emoji_name)
        i_cat_2 = result.find(cat_2_emoji_name)
        self.assertLess(i_cat_2, i_cat_1)

        # Group cat 1
        with p.begin_session() as s:
            s.query(BudgetGroup).where(BudgetGroup.id_ == g_bills_id).update(
                {"position": 1},
            )
            g = BudgetGroup(name="Wants", position=0)
            s.add(g)
            s.flush()
            g_wants_id = g.id_
            s.query(TransactionCategory).where(
                TransactionCategory.id_ == cat_1_id,
            ).update({"budget_group_id": g_wants_id, "budget_position": 0})

        result, _ = self.web_get(endpoint, headers=headers)
        assigned = re.findall(r"Assigned</div><div>(-?\$\d+\.\d\d)</div>", result)
        activity = re.findall(r"Activity</div><div>(-?\$\d+\.\d\d)</div>", result)
        available = re.findall(r"Available</div><div>(-?\$\d+\.\d\d)</div>", result)
        self.assertEqual(assigned, ["$10.00", "$0.00", "$0.00"])
        self.assertEqual(activity, ["-$10.00", "$0.00", "$0.00"])
        self.assertEqual(available, ["$0.00", "$50.00", "$0.00"])
        i_cat_1 = result.find(cat_1_emoji_name)
        i_cat_2 = result.find(cat_2_emoji_name)
        self.assertLess(i_cat_1, i_cat_2)
        i_bills = result.find("Bills")
        i_wants = result.find("Wants")
        self.assertLess(i_wants, i_bills)

        # Combine groups
        with p.begin_session() as s:
            s.query(TransactionCategory).where(
                TransactionCategory.id_ == cat_1_id,
            ).update({"budget_group_id": g_bills_id, "budget_position": 1})
            s.query(TransactionCategory).where(
                TransactionCategory.id_ == cat_2_id,
            ).update({"budget_group_id": g_bills_id, "budget_position": 0})

        result, _ = self.web_get(endpoint, headers=headers)
        assigned = re.findall(r"Assigned</div><div>(-?\$\d+\.\d\d)</div>", result)
        activity = re.findall(r"Activity</div><div>(-?\$\d+\.\d\d)</div>", result)
        available = re.findall(r"Available</div><div>(-?\$\d+\.\d\d)</div>", result)
        self.assertEqual(assigned, ["$0.00", "$10.00", "$0.00"])
        self.assertEqual(activity, ["$0.00", "-$10.00", "$0.00"])
        self.assertEqual(available, ["$0.00", "$50.00", "$0.00"])
        i_cat_1 = result.find(cat_1_emoji_name)
        i_cat_2 = result.find(cat_2_emoji_name)
        self.assertLess(i_cat_2, i_cat_1)

        # Unassign other category, assign remaining
        with p.begin_session() as s:
            s.query(BudgetAssignment).where(
                BudgetAssignment.month_ord == month_ord,
            ).update({"amount": Decimal(100)})
            a = BudgetAssignment(
                month_ord=month_ord,
                amount=-50,
                category_id=cat_2_id,
            )
            s.add(a)
        result, _ = self.web_get(endpoint, headers=headers)
        assigned = re.findall(r"Assigned</div><div>(-?\$\d+\.\d\d)</div>", result)
        activity = re.findall(r"Activity</div><div>(-?\$\d+\.\d\d)</div>", result)
        available = re.findall(r"Available</div><div>(-?\$\d+\.\d\d)</div>", result)
        self.assertEqual(assigned, ["$0.00", "$50.00", "$0.00"])
        self.assertEqual(activity, ["$0.00", "-$10.00", "$0.00"])
        self.assertEqual(available, ["$0.00", "$90.00", "$0.00"])
        self.assertIn("All money assigned", result)

        # Over assign
        with p.begin_session() as s:
            s.query(BudgetAssignment).where(
                BudgetAssignment.month_ord == month_ord,
            ).update({"amount": Decimal(100)})
        result, _ = self.web_get(endpoint, headers=headers)
        assigned = re.findall(r"Assigned</div><div>(-?\$\d+\.\d\d)</div>", result)
        activity = re.findall(r"Activity</div><div>(-?\$\d+\.\d\d)</div>", result)
        available = re.findall(r"Available</div><div>(-?\$\d+\.\d\d)</div>", result)
        self.assertEqual(assigned, ["$0.00", "$200.00", "$0.00"])
        self.assertEqual(activity, ["$0.00", "-$10.00", "$0.00"])
        self.assertEqual(available, ["$0.00", "$240.00", "$0.00"])
        self.assertIn("You assigned more than you have", result)

        # Add unbalanced transfer
        with p.begin_session() as s:
            cat_3_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "transfers")
                .one()[0]
            )
            s.query(TransactionSplit).where(TransactionSplit.amount > 0).update(
                {"category_id": cat_3_id},
            )
        result, _ = self.web_get(endpoint, headers=headers)
        assigned = re.findall(r"Assigned</div><div>(-?\$\d+\.\d\d)</div>", result)
        activity = re.findall(r"Activity</div><div>(-?\$\d+\.\d\d)</div>", result)
        available = re.findall(r"Available</div><div>(-?\$\d+\.\d\d)</div>", result)
        self.assertEqual(assigned, ["$0.00", "$200.00", "$0.00"])
        self.assertEqual(activity, ["$0.00", "-$10.00", "$100.00"])
        self.assertEqual(available, ["$0.00", "$240.00", "$100.00"])

    def test_validation(self) -> None:
        today = datetime.datetime.now().astimezone().date()

        endpoint = "budgeting.validation"

        result, headers = self.web_get((endpoint, {"date": " "}))
        self.assertEqual("Required", result)
        self.assertNotIn("HX-Trigger", headers)

        result, headers = self.web_get((endpoint, {"date": "a"}))
        self.assertEqual("Unable to parse", result)
        self.assertNotIn("HX-Trigger", headers)

        result, headers = self.web_get((endpoint, {"date": today.isoformat()}))
        self.assertEqual("", result)
        self.assertEqual(headers.get("HX-Trigger"), "target-desc")

        result, headers = self.web_get((endpoint, {"amount": " "}))
        self.assertEqual("Required", result)
        self.assertNotIn("HX-Trigger", headers)

        result, headers = self.web_get((endpoint, {"amount": "a"}))
        self.assertEqual("Unable to parse", result)
        self.assertNotIn("HX-Trigger", headers)

        result, headers = self.web_get((endpoint, {"amount": "10"}))
        self.assertEqual("", result)
        self.assertEqual(headers.get("HX-Trigger"), "target-desc")

        result, headers = self.web_get((endpoint, {"repeat": " "}))
        self.assertEqual("Required", result)
        self.assertNotIn("HX-Trigger", headers)

        result, headers = self.web_get((endpoint, {"repeat": "a"}))
        self.assertEqual("Unable to parse", result)
        self.assertNotIn("HX-Trigger", headers)

        result, headers = self.web_get((endpoint, {"repeat": "0"}))
        self.assertEqual("Must be positive", result)
        self.assertNotIn("HX-Trigger", headers)

        result, headers = self.web_get((endpoint, {"repeat": "10"}))
        self.assertEqual("", result)
        self.assertEqual(headers.get("HX-Trigger"), "target-desc")

    def test_assign(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.datetime.now().astimezone().date()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        month_str = month.isoformat()[:7]

        cat_1_id = d["cat_1_id"]
        cat_1_uri = d["cat_1_uri"]

        endpoint = "budgeting.assign"
        url = endpoint, {"uri": cat_1_uri, "month": month_str}
        form = {"amount": "5*2"}
        _, _ = self.web_put(url, data=form)
        with p.begin_session() as s:
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.month_ord, month_ord)
            self.assertEqual(a.category_id, cat_1_id)
            self.assertEqual(a.amount, Decimal(10))

        form = {"amount": "100"}
        _, _ = self.web_put(url, data=form)
        with p.begin_session() as s:
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.month_ord, month_ord)
            self.assertEqual(a.category_id, cat_1_id)
            self.assertEqual(a.amount, Decimal(100))

        form = {"amount": "0"}
        _, _ = self.web_put(url, data=form)
        with p.begin_session() as s:
            n = query_count(s.query(BudgetAssignment))
            self.assertEqual(n, 0)

    def test_move(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.datetime.now().astimezone().date()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        month_str = month.isoformat()[:7]
        month_last = utils.date_add_months(month, -1)

        cat_1_id = d["cat_1_id"]
        cat_1_uri = d["cat_1_uri"]
        cat_1_emoji_name = d["cat_1_emoji_name"]

        with p.begin_session() as s:
            cat_2_emoji_name = "General Merchandise"
            cat_2_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == cat_2_emoji_name.lower())
                .one()[0]
            )
            cat_2_uri = TransactionCategory.id_to_uri(cat_2_id)

        endpoint = "budgeting.move"
        # cat_1 is overspent
        url = endpoint, {"uri": cat_1_uri, "month": month_str}
        result, _ = self.web_get(url)
        self.assertIn(f"{cat_1_emoji_name} is overspent by $10.00", result)
        self.assertNotIn(
            f'<option value="{cat_1_uri}">{cat_1_emoji_name} -$10.00</option>',
            result,
        )
        self.assertNotIn(
            f'<option value="{cat_2_uri}">{cat_2_emoji_name} $0.00</option>',
            result,
        )
        self.assertIn(
            '<option value="income">Assignable income $100.00</option>',
            result,
        )

        url = endpoint, {"uri": "income", "month": month_str}
        result, _ = self.web_get(url)
        self.assertIn("Assignable income has $100.00 available", result)
        self.assertIn(
            f'<option value="{cat_1_uri}">{cat_1_emoji_name} -$10.00</option>',
            result,
        )
        self.assertIn(
            f'<option value="{cat_2_uri}">{cat_2_emoji_name} $0.00</option>',
            result,
        )
        self.assertNotIn(
            '<option value="income">Assignable income -$10.00</option>',
            result,
        )

        form = {"destination": cat_2_uri}
        result, _ = self.web_put(url, data=form)
        self.assertIn("Amount to move must not be blank", result)

        form = {"destination": cat_2_uri, "amount": "100.00"}
        _, headers = self.web_put(url, data=form)
        self.assertEqual(headers.get("HX-Trigger"), "budget")
        with p.begin_session() as s:
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.category_id, cat_2_id)
            self.assertEqual(a.month_ord, month_ord)
            self.assertEqual(a.amount, Decimal(100))

        url = endpoint, {"uri": cat_2_uri, "month": month_str}
        result, _ = self.web_get(url)
        self.assertIn(f"{cat_2_emoji_name} has $100.00 available", result)
        self.assertIn(
            f'<option value="{cat_1_uri}">{cat_1_emoji_name} -$10.00</option>',
            result,
        )
        self.assertIn(
            '<option value="income">Assignable income $0.00</option>',
            result,
        )

        form = {"destination": cat_1_uri, "amount": "50.00"}
        self.web_put(url, data=form)
        with p.begin_session() as s:
            a = (
                s.query(BudgetAssignment)
                .where(BudgetAssignment.category_id == cat_1_id)
                .one()
            )
            self.assertEqual(a.amount, Decimal(50))
            self.assertEqual(a.month_ord, month_ord)

            a = (
                s.query(BudgetAssignment)
                .where(BudgetAssignment.category_id == cat_2_id)
                .one()
            )
            self.assertEqual(a.amount, Decimal(50))
            self.assertEqual(a.month_ord, month_ord)

        form = {"destination": "income", "amount": "50.00"}
        self.web_put(url, data=form)
        with p.begin_session() as s:
            # cat_2 would have been deleted
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.category_id, cat_1_id)
            self.assertEqual(a.amount, Decimal(50))
            self.assertEqual(a.month_ord, month_ord)

            a = BudgetAssignment(
                month_ord=month_last.toordinal(),
                amount=50,
                category_id=cat_2_id,
            )
            s.add(a)

        result, _ = self.web_get(url)
        self.assertIn(f"{cat_2_emoji_name} has $50.00 available", result)
        self.assertIn(
            f'<option value="{cat_1_uri}">{cat_1_emoji_name} $40.00</option>',
            result,
        )
        self.assertIn(
            '<option value="income">Assignable income $0.00</option>',
            result,
        )

        form = {"destination": cat_1_uri, "amount": "50.00"}
        self.web_put(url, data=form)
        with p.begin_session() as s:
            a = (
                s.query(BudgetAssignment)
                .where(
                    BudgetAssignment.category_id == cat_1_id,
                    BudgetAssignment.month_ord == month_ord,
                )
                .one()
            )
            self.assertEqual(a.amount, Decimal(100))
            a.amount = Decimal(0)

            a = (
                s.query(BudgetAssignment)
                .where(
                    BudgetAssignment.category_id == cat_2_id,
                    BudgetAssignment.month_ord == month_ord,
                )
                .one()
            )
            self.assertEqual(a.amount, Decimal(-50))

        # Cover overspending with income
        url = endpoint, {"uri": cat_1_uri, "month": month_str}
        form = {"destination": "income"}
        self.web_put(url, data=form)

        with p.begin_session() as s:
            a = (
                s.query(BudgetAssignment)
                .where(
                    BudgetAssignment.category_id == cat_1_id,
                    BudgetAssignment.month_ord == month_ord,
                )
                .one()
            )
            self.assertEqual(a.amount, Decimal(10))

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
                .where(TransactionCategory.name == "general merchandise")
                .one()
            )
            t_cat_id_0 = t_cat_0.id_
            t_cat_uri_0 = t_cat_0.uri
            t_cat_0.budget_group_id = g_id_0
            t_cat_0.budget_position = 0

            t_cat_1 = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "uncategorized")
                .one()
            )
            t_cat_id_1 = t_cat_1.id_
            t_cat_uri_1 = t_cat_1.uri
            t_cat_1.budget_group_id = g_id_0
            t_cat_1.budget_position = 1

            t_cat_2 = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "groceries")
                .one()
            )
            t_cat_id_2 = t_cat_2.id_
            t_cat_uri_2 = t_cat_2.uri
            t_cat_2.budget_group_id = g_id_1
            t_cat_2.budget_position = 0

        endpoint = "budgeting.reorder"
        url = endpoint

        # Swap groups 0 and 1
        form = {
            "group-uri": [g_uri_1, g_uri_0],
            "category-uri": [t_cat_uri_2, t_cat_uri_0, t_cat_uri_1],
            "group": [g_uri_1, g_uri_0, g_uri_0],
        }
        result, _ = self.web_put(url, data=form)
        self.assertEqual(result, "")

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
            "group-uri": [g_uri_1, g_uri_0],
            "category-uri": [t_cat_uri_2, t_cat_uri_0, t_cat_uri_1],
            "group": [g_uri_1, g_uri_1, g_uri_0],
        }
        result, _ = self.web_put(url, data=form)
        self.assertEqual(result, "")

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
            "group-uri": [g_uri_1, g_uri_0],
            "category-uri": [t_cat_uri_0, t_cat_uri_1, t_cat_uri_2],
            "group": [g_uri_1, g_uri_0, "ungrouped"],
        }
        result, _ = self.web_put(url, data=form)
        self.assertEqual(result, "")

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

        # Missing group deletes it
        form = {
            "group-uri": [g_uri_0],
        }
        result, _ = self.web_put(url, data=form)
        self.assertEqual(result, "")

        with p.begin_session() as s:
            g = s.query(BudgetGroup).where(BudgetGroup.id_ == g_id_0).one()
            self.assertEqual(g.position, 0)

            n = query_count(s.query(BudgetGroup))
            self.assertEqual(n, 1)

            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_0)
                .one()
            )
            self.assertIsNone(t_cat.budget_position)
            self.assertIsNone(t_cat.budget_group_id)
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_1)
                .one()
            )
            self.assertIsNone(t_cat.budget_position)
            self.assertIsNone(t_cat.budget_group_id)
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id_2)
                .one()
            )
            self.assertIsNone(t_cat.budget_position)
            self.assertIsNone(t_cat.budget_group_id)

        form = {}
        result, _ = self.web_put(url, data=form)
        self.assertEqual(result, "")

        with p.begin_session() as s:
            n = query_count(s.query(BudgetGroup))
            self.assertEqual(n, 0)

    def test_group(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio

        with p.begin_session() as s:
            g_0 = BudgetGroup(name=self.random_string(), position=0)
            s.add(g_0)
            s.flush()
            g_uri_0 = g_0.uri

        group_name = "Shopping Group"

        endpoint = "budgeting.group"
        url = endpoint, {"uri": g_uri_0}
        form = {"name": " "}
        result, _ = self.web_put(url, data=form)
        self.assertIn("Budget group name must not be empty", result)

        form = {"name": group_name}
        result, _ = self.web_put(url, data=form)
        self.assertEqual(result, "")

        form = {"open": True}
        result, _ = self.web_put(url, data=form)
        self.assertEqual(result, "")
        with self._client.session_transaction() as session:
            self.assertEqual(session["groups_open"], [g_uri_0])

        form = {}
        result, _ = self.web_put(url, data=form)
        self.assertEqual(result, "")
        with self._client.session_transaction() as session:
            self.assertEqual(session["groups_open"], [])

        # Can't edit ungrouped
        form = {"name": group_name}
        url = endpoint, {"uri": "ungrouped"}
        self.web_put(url, data=form, rc=HTTP_CODE_BAD_REQUEST)

        form = {"open": group_name}
        result, _ = self.web_put(url, data=form)

    def test_new_group(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio

        with p.begin_session() as s:
            g_0 = BudgetGroup(name="Bills", position=0)
            s.add(g_0)
            s.flush()

            g_0_id = g_0.id_

        endpoint = "budgeting.new_group"
        result, _ = self.web_post(endpoint)
        target = '<div id="group-'
        self.assertEqual(result[: len(target)], target)
        self.assertIn("New Group", result)

        with p.begin_session() as s:
            result = (
                s.query(BudgetGroup.position).where(BudgetGroup.id_ == g_0_id).scalar()
            )
            self.assertEqual(result, 1)

        result, _ = self.web_post(endpoint)
        target = '<div id="group-'
        self.assertEqual(result[: len(target)], target)
        self.assertIn("New Group 2", result)

        with p.begin_session() as s:
            result = (
                s.query(BudgetGroup.position).where(BudgetGroup.id_ == g_0_id).scalar()
            )
            self.assertEqual(result, 2)

    def test_ctx_target(self) -> None:
        # Test the context since testing the HTML would be very difficult
        d = self._setup_portfolio()
        p = self._portfolio

        today = datetime.datetime.now().astimezone().date()
        month = utils.start_of_month(today)
        next_year = utils.date_add_months(month, 12)

        cat_1_id = d["cat_1_id"]

        with p.begin_session() as s:
            # BALANCE target, no due date
            tar = Target(
                category_id=cat_1_id,
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            now = datetime.datetime(month.year, month.month, 6).astimezone()
            with time_machine.travel(now, tick=False):
                ctx = budgeting.ctx_target(
                    tar,
                    month,
                    assigned=Decimal(100 * 2),
                    available=Decimal(0),  # Spent it all
                    leftover=Decimal(10),
                )
            target: budgeting._TargetContext = {
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
            now = datetime.datetime(month.year, month.month, 17).astimezone()
            with time_machine.travel(now, tick=False):
                ctx = budgeting.ctx_target(
                    tar,
                    month,
                    assigned=Decimal(100 * 2),
                    available=Decimal(0),  # Spent it all
                    leftover=Decimal(10),
                )
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
            tar.repeat_every = 6
            s.flush()

            # Underfunded
            ctx = budgeting.ctx_target(
                tar,
                month,
                assigned=Decimal(20),
                available=Decimal(0),  # Spent it all
                leftover=Decimal(10),
            )
            target: budgeting._TargetContext = {
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
                utils.date_add_months(month, 3),
                assigned=Decimal(0),
                available=Decimal(20),
                leftover=Decimal(20),
            )
            target: budgeting._TargetContext = {
                "target_assigned": Decimal(20),
                "total_assigned": Decimal(20),
                "to_go": Decimal(20),
                "on_track": False,
                "next_due_date": utils.date_add_months(today, 6),
                "progress_bars": [Decimal(100)],
                "target": Decimal(100),
                "total_target": Decimal(100),
                "total_to_go": Decimal(80),
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
            target: budgeting._TargetContext = {
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
            target: budgeting._TargetContext = {
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
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.datetime.now().astimezone().date()

        cat_1_id = d["cat_1_id"]
        cat_1_uri = d["cat_1_uri"]

        # Get new target editor
        endpoint = "budgeting.target"
        url = (endpoint, {"uri": cat_1_uri})
        result, _ = self.web_get(url)
        self.assertIn("New target", result)

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
        self.assertEqual(headers.get("HX-Trigger"), "budget")

        with p.begin_session() as s:
            tar = s.query(Target).one()
            self.assertEqual(tar.category_id, cat_1_id)
            self.assertEqual(tar.period, TargetPeriod.ONCE)
            self.assertEqual(tar.type_, TargetType.BALANCE)
            self.assertEqual(tar.amount, 100)
            self.assertIsNone(tar.due_date_ord)
            self.assertEqual(tar.repeat_every, 0)

            tar_uri = tar.uri

        result, _ = self.web_post(url, data=form)
        self.assertIn("Cannot have multiple targets per category", result)

        result, _ = self.web_get((endpoint, {"uri": tar_uri, "has-due": "on"}))
        self.assertIn(f'value="{today.month}" selected>', result)

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
            self.assertEqual(tar.category_id, cat_1_id)
            self.assertEqual(tar.period, TargetPeriod.ONCE)
            self.assertEqual(tar.type_, TargetType.BALANCE)
            self.assertEqual(tar.amount, 100)
            date = datetime.date(today.year + 1, 12, 1)
            self.assertEqual(tar.due_date_ord, date.toordinal())
            self.assertEqual(tar.repeat_every, 0)

        # No has-due means it shouldn't change due date
        result, _ = self.web_get(url)
        self.assertIn('value="12" selected>December', result)
        self.assertIn(f'value="{today.year + 1}" selected>', result)

        # Changing period to weekly should reset due date
        result, _ = self.web_get(
            (endpoint, {"uri": cat_1_uri, "period": "Weekly", "change": True}),
        )
        self.assertIn('value="0" selected>Monday', result)

        form = {
            "period": "Weekly",
            "amount": "100",
            "type": "REFILL",
            "due": 1,
        }
        self.web_put(url, data=form)
        with p.begin_session() as s:
            tar = s.query(Target).one()
            self.assertEqual(tar.category_id, cat_1_id)
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
            self.assertEqual(tar.category_id, cat_1_id)
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
            self.assertEqual(tar.category_id, cat_1_id)
            self.assertEqual(tar.period, TargetPeriod.YEAR)
            self.assertEqual(tar.type_, TargetType.ACCUMULATE)
            if tar.due_date_ord is None:
                self.fail("due_date_ord is None")
            else:
                date = datetime.date.fromordinal(tar.due_date_ord)
                self.assertEqual(date, today)
            self.assertEqual(tar.repeat_every, 2)

        _, headers = self.web_delete(url)
        self.assertEqual(headers.get("HX-Trigger"), "budget")
        with p.begin_session() as s:
            n = query_count(s.query(Target))
            self.assertEqual(n, 0)

    def test_sidebar(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio

        cat_1_id = d["cat_1_id"]
        cat_1_uri = d["cat_1_uri"]
        cat_1_emoji_name = d["cat_1_emoji_name"]

        # No category selected
        endpoint = "budgeting.sidebar"
        result, _ = self.web_get(endpoint)
        self.assertIn("Total to go", result)
        self.assertIn("<select", result)

        # Category selected without target
        url = (endpoint, {"uri": cat_1_uri})
        result, _ = self.web_get(url)
        self.assertNotIn("Total to go", result)
        self.assertNotIn("<select", result)
        self.assertIn(cat_1_emoji_name, result)
        self.assertIn("Create Target", result)

        with p.begin_session() as s:
            tar = Target(
                category_id=cat_1_id,
                period=TargetPeriod.ONCE,
                type_=TargetType.BALANCE,
                amount=100,
                repeat_every=0,
            )
            s.add(tar)

        # Category selected with target
        url = (endpoint, {"uri": cat_1_uri})
        result, _ = self.web_get(url)
        self.assertIn(cat_1_emoji_name, result)
        self.assertIn("Edit Target", result)
        self.assertIn("Have", result)
        # +10 from the spending
        self.assertIn("Assign $110.00 more to meet target", result)
