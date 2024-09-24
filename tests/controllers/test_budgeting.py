from __future__ import annotations

import datetime
from decimal import Decimal

from nummus import utils
from nummus.models import BudgetAssignment, TransactionCategory
from nummus.models.transaction import TransactionSplit
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

        with p.get_session() as s:
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
            r"<div .*>Ungrouped</div>[ \n]+"
            r"<div .*>\$0.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>",
        )
        self.assertRegex(result, r"hx-get=.*>-\$10.00</span>")
        self.assertNotIn("General Merchandise", result)
        self.assertRegex(
            result,
            r"<div>\$100.00</div>[ \n]+<div .*>Ready to assign</div>[ \n]+",
        )
        self.assertRegex(result, r"1[ \n]+category is[ \n]+overspent")

        # Assign to category
        with p.get_session() as s:
            a = BudgetAssignment(month_ord=month_ord, amount=10, category_id=t_cat_id_0)
            s.add(a)
            s.commit()

        result, _ = self.web_get((endpoint, {"month": month_str}), headers=headers)
        self.assertRegex(
            result,
            r"<div .*>Ungrouped</div>[ \n]+"
            r"<div .*>\$10.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>\$0.00</div>",
        )
        self.assertRegex(result, r"<span .*>\$0.00</span>")
        self.assertRegex(
            result,
            r"<div>\$90.00</div>[ \n]+<div .*>Ready to assign</div>",
        )
        self.assertNotIn("overspent", result)

        # Assign to other category
        with p.get_session() as s:
            a = BudgetAssignment(
                month_ord=month_last.toordinal(),
                amount=50,
                category_id=t_cat_id_1,
            )
            s.add(a)
            s.commit()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<div .*>Ungrouped</div>[ \n]+"
            r"<div .*>\$10.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>\$50.00</div>",
        )
        self.assertRegex(result, r"<span .*>\$0.00</span>")
        self.assertRegex(result, r"hx-get=.*>\$50.00</span>")
        self.assertRegex(
            result,
            r"<div>\$40.00</div>[ \n]+<div .*>Ready to assign</div>[ \n]+",
        )
        self.assertNotIn("overspent", result)
        i_uncategorized = result.find("Uncategorized")
        i_general = result.find("General Merchandise")
        self.assertLess(i_general, i_uncategorized)

        # Group General Merchandise
        with p.get_session() as s:
            s.query(TransactionCategory).where(
                TransactionCategory.name == "General Merchandise",
            ).update({"budget_group": "Bills", "budget_position": 1})
            s.commit()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<div .*>Bills</div>[ \n]+"
            r"<div .*>\$0.00</div>[ \n]+"
            r"<div .*>\$0.00</div>[ \n]+"
            r"<div .*>\$50.00</div>",
        )
        self.assertRegex(
            result,
            r"<div .*>Ungrouped</div>[ \n]+"
            r"<div .*>\$10.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>\$0.00</div>",
        )
        i_uncategorized = result.find("Uncategorized")
        i_general = result.find("General Merchandise")
        self.assertLess(i_general, i_uncategorized)

        # Group Uncategorized
        with p.get_session() as s:
            s.query(TransactionCategory).where(
                TransactionCategory.name == "General Merchandise",
            ).update({"budget_group": "Bills", "budget_position": 2})
            s.query(TransactionCategory).where(
                TransactionCategory.name == "Uncategorized",
            ).update({"budget_group": "Wants", "budget_position": 1})
            s.commit()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<div .*>Bills</div>[ \n]+"
            r"<div .*>\$0.00</div>[ \n]+"
            r"<div .*>\$0.00</div>[ \n]+"
            r"<div .*>\$50.00</div>",
        )
        self.assertRegex(
            result,
            r"<div .*>Wants</div>[ \n]+"
            r"<div .*>\$10.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>\$0.00</div>",
        )
        self.assertNotIn("Ungrouped", result)
        i_uncategorized = result.find("Uncategorized")
        i_general = result.find("General Merchandise")
        self.assertLess(i_uncategorized, i_general)
        i_bills = result.find("Bills")
        i_wants = result.find("Wants")
        self.assertLess(i_wants, i_bills)

        # Combine groups
        with p.get_session() as s:
            s.query(TransactionCategory).where(
                TransactionCategory.name == "General Merchandise",
            ).update({"budget_group": "Bills", "budget_position": 2})
            s.query(TransactionCategory).where(
                TransactionCategory.name == "Uncategorized",
            ).update({"budget_group": "Bills", "budget_position": 1})
            s.commit()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<div .*>Bills</div>[ \n]+"
            r"<div .*>\$10.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>\$50.00</div>",
        )
        self.assertNotIn("Ungrouped", result)
        i_uncategorized = result.find("Uncategorized")
        i_general = result.find("General Merchandise")
        self.assertLess(i_uncategorized, i_general)

        # Unassign other category, assign remaining
        with p.get_session() as s:
            s.query(BudgetAssignment).where(
                BudgetAssignment.month_ord == month_ord,
            ).update({"amount": Decimal(100)})
            a = BudgetAssignment(
                month_ord=month_ord,
                amount=-50,
                category_id=t_cat_id_1,
            )
            s.add(a)
            s.commit()
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<div .*>Bills</div>[ \n]+"
            r"<div .*>\$50.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>\$90.00</div>",
        )
        self.assertRegex(
            result,
            r"<div>\$0.00</div>[ \n]+<div .*>All money assigned</div>",
        )

        # Over assign
        with p.get_session() as s:
            s.query(BudgetAssignment).where(
                BudgetAssignment.month_ord == month_ord,
            ).update({"amount": Decimal(100)})
            s.commit()
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<div .*>Bills</div>[ \n]+"
            r"<div .*>\$200.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>\$240.00</div>",
        )
        self.assertRegex(
            result,
            r"<div>-\$150.00</div>[ \n]+<div .*>More money assigned than held</div>",
        )

        # Add unbalanced transfer
        with p.get_session() as s:
            t_cat_id_2 = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Transfers")
                .one()[0]
            )
            s.query(TransactionSplit).where(TransactionSplit.amount > 0).update(
                {"category_id": t_cat_id_2},
            )
            s.commit()
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(
            result,
            r"<div .*>Ungrouped</div>[ \n]+"
            r"<div .*>\$0.00</div>[ \n]+"
            r"<div .*>\$100.00</div>[ \n]+"
            r"<div .*>\$100.00</div>",
        )

    def test_assign(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        month_str = month.isoformat()[:7]

        with p.get_session() as s:
            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Uncategorized")
                .one()[0]
            )
            t_cat_uri = TransactionCategory.id_to_uri(t_cat_id)

        endpoint = "budgeting.assign"
        url = endpoint, {"uri": t_cat_uri, "month": month_str}
        form = {"amount": "10"}
        result, _ = self.web_put(url, data=form)
        with p.get_session() as s:
            a = s.query(BudgetAssignment).first()
            if a is None:
                self.fail("BudgetAssignment is missing")
            self.assertEqual(a.month_ord, month_ord)
            self.assertEqual(a.category_id, t_cat_id)
            self.assertEqual(a.amount, Decimal(10))
        self.assertRegex(
            result,
            r"<div .*>Ungrouped</div>[ \n]+"
            r"<div .*>\$10.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>\$0.00</div>",
        )

        form = {"amount": "100"}
        result, _ = self.web_put(url, data=form)
        with p.get_session() as s:
            a = s.query(BudgetAssignment).first()
            if a is None:
                self.fail("BudgetAssignment is missing")
            self.assertEqual(a.month_ord, month_ord)
            self.assertEqual(a.category_id, t_cat_id)
            self.assertEqual(a.amount, Decimal(100))
        self.assertRegex(
            result,
            r"<div .*>Ungrouped</div>[ \n]+"
            r"<div .*>\$100.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>\$90.00</div>",
        )

        form = {"amount": "0"}
        result, _ = self.web_put(url, data=form)
        with p.get_session() as s:
            n = s.query(BudgetAssignment).count()
            self.assertEqual(n, 0)
        self.assertRegex(
            result,
            r"<div .*>Ungrouped</div>[ \n]+"
            r"<div .*>\$0.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>[ \n]+"
            r"<div .*>-\$10.00</div>",
        )

    def test_overspending(self) -> None:
        _ = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        month = utils.start_of_month(today)
        month_ord = month.toordinal()
        month_str = month.isoformat()[:7]
        month_last = utils.date_add_months(month, -1)

        with p.get_session() as s:
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
        with p.get_session() as s:
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.category_id, t_cat_id_0)
            self.assertEqual(a.amount, Decimal(10))
            self.assertEqual(a.month_ord, month_ord)

            a.amount = Decimal(5)
            s.commit()

            a = BudgetAssignment(month_ord=month_ord, amount=10, category_id=t_cat_id_1)
            s.add(a)
            s.commit()

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
        with p.get_session() as s:
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

            s.commit()

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
        with p.get_session() as s:
            # cat_1 would have been deleted
            a = s.query(BudgetAssignment).one()
            self.assertEqual(a.category_id, t_cat_id_0)
            self.assertEqual(a.amount, Decimal(100))
            self.assertEqual(a.month_ord, month_ord)

            a.amount = Decimal(200)
            a.month_ord = month_last.toordinal()
            s.commit()

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
        with p.get_session() as s:
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

        with p.get_session() as s:
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
        with p.get_session() as s:
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
        with p.get_session() as s:
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
        with p.get_session() as s:
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
            s.commit()

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
        with p.get_session() as s:
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
