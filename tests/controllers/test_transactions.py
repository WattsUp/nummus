from __future__ import annotations

import datetime
import re

from nummus.models import Transaction, TransactionCategory
from tests.controllers.base import WebTestBase


class TestTransaction(WebTestBase):
    def test_page_all(self) -> None:
        endpoint = "/transactions"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn('id="txn-config"', result)
        self.assertIn('id="txn-paging"', result)
        self.assertIn('id="txn-header"', result)
        self.assertIn('id="txn-table"', result)
        self.assertIn("No matching transactions for given query filters", result)

    def test_table(self) -> None:
        d = self._setup_portfolio()

        payee_0 = d["payee_0"]
        payee_1 = d["payee_1"]
        t_split_0 = d["t_split_0"]
        t_split_1 = d["t_split_1"]
        cat_0 = d["cat_0"]
        tag_1 = d["tag_1"]

        endpoint = "/h/transactions/table"
        result, _ = self.web_get(endpoint)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 2)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')

        queries = {"account": "Non selected", "period": "all"}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertNotRegex(result, r'<div id="txn-[a-f0-9]{8}"')
        self.assertIn("No matching transactions for given query filters", result)

        queries = {"payee": payee_0}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')

        queries = {"payee": "[blank]"}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertNotRegex(result, r'<div id="txn-[a-f0-9]{8}"')
        self.assertIn("No matching transactions for given query filters", result)

        queries = {"payee": ["[blank]", payee_1]}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')

        queries = {"category": cat_0}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')

        queries = {"tag": tag_1}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')

        queries = {"tag": "[blank]"}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')

        queries = {"tag": ["[blank]", tag_1]}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 2)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')

        queries = {"locked": "true"}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')

        queries = {"search": payee_1}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')

    def test_options(self) -> None:
        d = self._setup_portfolio()

        acct = d["acct"]
        payee_0 = d["payee_0"]
        payee_1 = d["payee_1"]
        cat_0 = d["cat_0"]
        cat_1 = d["cat_1"]
        tag_1 = d["tag_1"]

        endpoint = "/h/transactions/options/account"
        result, _ = self.web_get(endpoint)
        self.assertEqual(result.count("span"), 2)
        self.assertRegex(result, rf'value="{acct}"[ \n]+hx-get')
        self.assertNotIn("checked", result)

        endpoint = "/h/transactions/options/category"
        queries = {"period": "all"}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{cat_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        # Check sorting
        i_0 = result.find(cat_0)
        i_1 = result.find(cat_1)
        self.assertLess(i_0, i_1)

        queries = {"category": cat_1}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{cat_1}"[ \n]+checked[ \n]+hx-get')
        # Check sorting
        i_0 = result.find(cat_0)
        i_1 = result.find(cat_1)
        self.assertLess(i_1, i_0)

        endpoint = "/h/transactions/options/tag"
        result, _ = self.web_get(endpoint)
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, r'value="\[blank\]"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{tag_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        # Check sorting
        i_blank = result.find("[blank]")
        i_0 = result.find(tag_1)
        self.assertLess(i_blank, i_1)

        endpoint = "/h/transactions/options/payee"
        result, _ = self.web_get(endpoint)
        self.assertEqual(result.count("span"), 6)
        self.assertRegex(result, r'value="\[blank\]"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{payee_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{payee_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        # Check sorting
        i_blank = result.find("[blank]")
        i_0 = result.find(payee_0)
        i_1 = result.find(payee_1)
        self.assertLess(i_blank, i_0)
        self.assertLess(i_0, i_1)

        queries = {"payee": payee_1}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(result.count("span"), 6)
        self.assertRegex(result, r'value="\[blank\]"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{payee_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{payee_1}"[ \n]+checked[ \n]+hx-get')
        # Check sorting
        i_blank = result.find("[blank]")
        i_0 = result.find(payee_0)
        i_1 = result.find(payee_1)
        self.assertLess(i_blank, i_1)
        self.assertLess(i_1, i_0)

        queries = {"payee": [payee_0, payee_1], "search-payee": payee_0}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(result.count("span"), 2)
        self.assertRegex(result, rf'value="{payee_0}"[ \n]+checked[ \n]+hx-get')

    def test_edit(self) -> None:
        p = self._portfolio
        today = datetime.date.today()
        d = self._setup_portfolio()

        t_0 = d["t_0"]
        t_split_0 = d["t_split_0"]
        payee_0 = d["payee_0"]
        cat_0 = d["cat_0"]
        cat_1 = d["cat_1"]

        endpoint = f"/h/transactions/t/{t_split_0}/edit"
        result, _ = self.web_get(endpoint)
        self.assertEqual(result.count('name="payee"'), 1)

        endpoint = f"/h/transactions/t/{t_0}/edit"
        form = {"amount": ""}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Non-zero remaining amount to be assigned", result)

        form = {"amount": "100"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Transaction must have at least one split", result)

        form = {"payee": "", "amount": "100"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Transaction date must not be empty", result)

        form = {"date": today, "payee": "ab", "amount": "100"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(
            "Transaction split payee must be at least 3 characters long",
            result,
        )

        # Add split
        new_date = today - datetime.timedelta(days=10)
        new_desc = self.random_string()
        form = {
            "date": new_date,
            "locked": "",
            "payee": [payee_0, ""],
            "description": [new_desc, ""],
            "category": [cat_0, cat_1],
            "tag": ["", ""],
            "amount": ["20", "80"],
        }
        result, headers = self.web_post(endpoint, data=form)
        self.assertEqual(headers["HX-Trigger"], "update-transaction")

        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)

            query = s.query(Transaction)
            query = query.where(Transaction.id_ == Transaction.uri_to_id(t_0))
            txn: Transaction = query.scalar()
            splits = txn.splits

            self.assertEqual(txn.date, new_date)
            self.assertTrue(txn.locked)
            self.assertEqual(len(splits), 2)

            t_split = splits[0]
            self.assertEqual(t_split.date, new_date)
            self.assertTrue(t_split.locked)
            self.assertEqual(t_split.payee, payee_0)
            self.assertEqual(t_split.description, new_desc)
            self.assertEqual(categories[t_split.category_id], cat_0)
            self.assertIsNone(t_split.tag)
            self.assertEqual(t_split.amount, 20)

            t_split = splits[1]
            self.assertEqual(t_split.date, new_date)
            self.assertTrue(t_split.locked)
            self.assertIsNone(t_split.payee)
            self.assertIsNone(t_split.description)
            self.assertEqual(categories[t_split.category_id], cat_1)
            self.assertIsNone(t_split.tag)
            self.assertEqual(t_split.amount, 80)

        # Remove split
        new_date = today - datetime.timedelta(days=10)
        new_desc = self.random_string()
        form = {
            "date": new_date,
            "payee": payee_0,
            "description": new_desc,
            "category": cat_0,
            "tag": "",
            "amount": "100",
        }
        result, headers = self.web_post(endpoint, data=form)
        self.assertEqual(headers["HX-Trigger"], "update-transaction")

        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)

            query = s.query(Transaction)
            query = query.where(Transaction.id_ == Transaction.uri_to_id(t_0))
            txn: Transaction = query.scalar()
            splits = txn.splits

            self.assertEqual(txn.date, new_date)
            self.assertFalse(txn.locked)
            self.assertEqual(len(splits), 1)

            t_split = splits[0]
            self.assertEqual(t_split.date, new_date)
            self.assertFalse(t_split.locked)
            self.assertEqual(t_split.payee, payee_0)
            self.assertEqual(t_split.description, new_desc)
            self.assertEqual(categories[t_split.category_id], cat_0)
            self.assertIsNone(t_split.tag)
            self.assertEqual(t_split.amount, 100)

    def test_split(self) -> None:
        d = self._setup_portfolio()

        t_0 = d["t_0"]
        payee_0 = d["payee_0"]
        cat_0 = d["cat_0"]

        desc = self.random_string()
        tag = self.random_string()

        endpoint = f"/h/transactions/t/{t_0}/split"
        form = {
            "payee": payee_0,
            "description": desc,
            "category": cat_0,
            "tag": tag,
            "amount": "100",
        }
        result, _ = self.web_put(endpoint, data=form)
        self.assertEqual(result.count('name="payee"'), 2)
        self.assertRegex(result, rf'name="payee"[ \n]+value="{payee_0}"')
        self.assertRegex(result, r'name="payee"[ \n]+value=""')
        self.assertRegex(result, rf'name="description"[ \n]+value="{desc}"')
        self.assertRegex(result, r'name="description"[ \n]+value=""')
        self.assertEqual(result.count("selected"), 2)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+selected')
        self.assertRegex(result, r'value="Uncategorized"[ \n]+selected')
        self.assertRegex(result, rf'name="tag"[ \n]+value="{tag}"')
        self.assertRegex(result, r'name="tag"[ \n]+value=""')
        self.assertRegex(result, r'name="amount"[ \n]+value="100\.00"')
        self.assertRegex(result, r'name="amount"[ \n]+value=""')

        form = {
            "payee": [payee_0, ""],
            "description": [desc, ""],
            "category": [cat_0, ""],
            "tag": [tag, ""],
            "amount": ["100", ""],
        }
        result, _ = self.web_delete(endpoint + "?index=2", data=form)
        self.assertEqual(result.count('name="payee"'), 1)
        self.assertRegex(result, rf'name="payee"[ \n]+value="{payee_0}"')
        self.assertRegex(result, rf'name="description"[ \n]+value="{desc}"')
        self.assertEqual(result.count("selected"), 1)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+selected')
        self.assertRegex(result, rf'name="tag"[ \n]+value="{tag}"')
        self.assertRegex(result, r'name="amount"[ \n]+value="100\.00"')
        self.assertRegex(result, r'id="txn-remaining"[ \n]+hx-swap-oob="True"')

    def test_remaining(self) -> None:
        d = self._setup_portfolio()

        t_0 = d["t_0"]

        endpoint = f"/h/transactions/t/{t_0}/remaining"
        form = {"amount": "100"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(">$0.00</div>", result)

        form = {"amount": ["20", "20.001"]}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(">$60.00</div>", result)
