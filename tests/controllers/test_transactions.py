from __future__ import annotations

import datetime
import re
import urllib.parse
from decimal import Decimal

from nummus.models import (
    Account,
    Asset,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import HTTP_CODE_BAD_REQUEST, WebTestBase


class TestTransaction(WebTestBase):
    def test_page_all(self) -> None:
        p = self._portfolio
        self._setup_portfolio()
        with p.begin_session() as s:
            s.query(TransactionSplit).delete()
            s.query(Transaction).delete()
        endpoint = "transactions.page_all"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn('id="txn-config"', result)
        self.assertIn('id="txn-paging"', result)
        self.assertIn('id="txn-header"', result)
        self.assertIn('id="txn-table"', result)
        self.assertIn("No matching transactions for given query filters", result)

    def test_table(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.date.today()

        acct = d["acct"]
        acct_uri = d["acct_uri"]
        payee_0 = d["payee_0"]
        payee_1 = d["payee_1"]
        t_0 = d["t_0"]
        t_split_0 = d["t_split_0"]
        t_split_1 = d["t_split_1"]
        cat_0 = d["cat_0"]
        cat_1 = d["cat_1"]
        tag_1 = d["tag_1"]
        a_uri_0 = d["a_uri_0"]

        # Unlink transaction 0
        with p.begin_session() as s:
            query = s.query(Transaction).where(
                Transaction.id_ == Transaction.uri_to_id(t_0),
            )
            txn = query.one()
            txn.linked = False
            for t_split in txn.splits:
                t_split.parent = txn

        endpoint = "transactions.table"
        result, _ = self.web_get(endpoint)
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 2)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')
        self.assertRegex(result, r"<title>Transactions This Month \| nummus</title>")

        result, _ = self.web_get(
            (endpoint, {"period": "all", "account": "None selected"}),
        )
        self.assertNotIn("No matching transactions for given query filters", result)
        self.assertRegex(result, r"<title>Transactions All \| nummus</title>")

        result, _ = self.web_get(
            (endpoint, {"period": "all", "account": acct}),
        )
        self.assertNotIn("No matching transactions for given query filters", result)
        self.assertRegex(result, rf"<title>Transactions All, {acct} \| nummus</title>")

        # If a filter is not an option, ignore
        long_ago = today - datetime.timedelta(days=400)
        queries = {
            "account": "None selected",
            "period": "custom",
            "start": long_ago.isoformat(),
            "end": long_ago.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertNotRegex(result, r'<div id="txn-[a-f0-9]{8}"')
        self.assertIn("No matching transactions for given query filters", result)
        self.assertRegex(
            result,
            rf"<title>Transactions {long_ago} to {long_ago} \| nummus</title>",
        )

        result, _ = self.web_get(
            (endpoint, {"payee": payee_0}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')
        self.assertRegex(
            result,
            rf"<title>Transactions This Month, {payee_0} \| nummus</title>",
        )

        result, _ = self.web_get(
            (endpoint, {"payee": "[blank]"}),
        )
        self.assertNotRegex(result, r'<div id="txn-[a-f0-9]{8}"')
        self.assertIn("No matching transactions for given query filters", result)
        self.assertRegex(
            result,
            r"<title>Transactions This Month \| nummus</title>",
        )

        result, headers = self.web_get(
            (endpoint, {"payee": ["[blank]", payee_1]}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')
        self.assertRegex(
            result,
            rf"<title>Transactions This Month, {payee_1} \| nummus</title>",
        )
        self.assertEqual(
            headers["HX-Push-Url"].split("?")[1],
            f"payee={urllib.parse.quote('[blank]')}&payee={payee_1}",
        )

        result, _ = self.web_get(
            (endpoint, {"category": cat_0}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')
        self.assertRegex(
            result,
            rf"<title>Transactions This Month, {cat_0} \| nummus</title>",
        )

        result, _ = self.web_get(
            (endpoint, {"tag": tag_1}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')
        self.assertRegex(
            result,
            rf"<title>Transactions This Month, {tag_1} \| nummus</title>",
        )

        result, _ = self.web_get(
            (endpoint, {"tag": "[blank]"}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')
        self.assertRegex(
            result,
            r"<title>Transactions This Month \| nummus</title>",
        )

        result, _ = self.web_get(
            (endpoint, {"tag": ["[blank]", tag_1]}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 2)
        self.assertRegex(result, rf'<div id="txn-{t_split_0}"')
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')
        self.assertRegex(
            result,
            rf"<title>Transactions This Month, {tag_1} \| nummus</title>",
        )

        result, _ = self.web_get(
            (endpoint, {"locked": True}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')
        self.assertRegex(
            result,
            r"<title>Transactions This Month, Locked \| nummus</title>",
        )

        result, _ = self.web_get(
            (endpoint, {"linked": True}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')
        self.assertRegex(
            result,
            r"<title>Transactions This Month, Linked \| nummus</title>",
        )

        result, _ = self.web_get(
            (endpoint, {"search": payee_1}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')
        self.assertRegex(
            result,
            rf'<title>Transactions This Month, "{payee_1}" \| nummus</title>',
        )

        result, _ = self.web_get(
            (endpoint, {"search": payee_1, "period": "all"}),
        )
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"')
        self.assertRegex(
            result,
            rf'<title>Transactions All, "{payee_1}" \| nummus</title>',
        )

        queries = {
            "period": "all",
            "tag": tag_1,
            "category": cat_1,
            "locked": "true",
            "payee": payee_1,
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_1}"[^>]*hx-get[^>]*>')
        self.assertRegex(
            result,
            rf"<title>Transactions All, {payee_1}, {cat_1}, & 2 Filters "
            r"\| nummus</title>",
        )

        # Add dividend transaction
        with p.begin_session() as s:
            acct_id = Account.uri_to_id(acct_uri)
            a_id_0 = Asset.uri_to_id(a_uri_0)

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id_0,
                asset_quantity_unadjusted=1,
                category_id=categories["Dividends Received"],
            )
            s.add_all((txn, t_split))
            s.flush()

            t_split_2 = t_split.uri
        queries = {
            "period": "all",
            "category": "Dividends Received",
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertEqual(len(re.findall(r'<div id="txn-[a-f0-9]{8}"', result)), 1)
        self.assertRegex(result, rf'<div id="txn-{t_split_2}"')
        # Can't edit asset transactions
        self.assertNotRegex(result, rf'<div id="txn-{t_split_2}"[^>]*hx-get[^>]*>')

    def test_options(self) -> None:
        d = self._setup_portfolio()

        acct = d["acct"]
        payee_0 = d["payee_0"]
        payee_1 = d["payee_1"]
        cat_0 = d["cat_0"]
        cat_1 = d["cat_1"]
        tag_1 = d["tag_1"]

        endpoint = "transactions.table_options"
        result, _ = self.web_get(
            (endpoint, {"field": "account"}),
        )
        self.assertEqual(result.count("span"), 2)
        self.assertRegex(result, rf'value="{acct}"[ \n]+hx-get')
        self.assertNotIn("checked", result)

        result, _ = self.web_get(
            (endpoint, {"field": "category", "period": "all"}),
        )
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{cat_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        # Check sorting
        i_0 = result.find(cat_0)
        i_1 = result.find(cat_1)
        self.assertLess(i_0, i_1)

        result, _ = self.web_get(
            (endpoint, {"field": "category", "category": cat_1}),
        )
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{cat_1}"[ \n]+checked[ \n]+hx-get')
        # Check sorting
        i_0 = result.find(cat_0)
        i_1 = result.find(cat_1)
        self.assertLess(i_1, i_0)

        result, _ = self.web_get(
            (endpoint, {"field": "tag"}),
        )
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, r'value="\[blank\]"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{tag_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        # Check sorting
        i_blank = result.find("[blank]")
        i_0 = result.find(tag_1)
        self.assertLess(i_blank, i_1)

        result, _ = self.web_get(
            (endpoint, {"field": "payee"}),
        )
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

        result, _ = self.web_get(
            (endpoint, {"field": "payee", "payee": payee_1}),
        )
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
        result, _ = self.web_get(
            (endpoint, {"field": "payee", **queries}),
        )
        self.assertEqual(len(re.findall(r"<label.*>", result)), 3)
        self.assertEqual(len(re.findall(r"<label.*hidden.*>", result)), 2)
        self.assertRegex(result, rf'value="{payee_0}"[ \n]+checked[ \n]+hx-get')

        result, _ = self.web_get(
            (endpoint, {"field": "unknown"}),
            rc=HTTP_CODE_BAD_REQUEST,
        )

    def test_transaction(self) -> None:
        p = self._portfolio
        today = datetime.date.today()
        d = self._setup_portfolio()

        t_0 = d["t_0"]
        t_1 = d["t_1"]
        t_split_0 = d["t_split_0"]
        payee_0 = d["payee_0"]
        cat_0 = d["cat_0"]
        cat_1 = d["cat_1"]

        endpoint = "transactions.transaction"
        result, _ = self.web_get((endpoint, {"uri": t_split_0}))
        self.assertEqual(result.count('name="payee"'), 1)

        form = {}
        result, _ = self.web_put((endpoint, {"uri": t_0}), data=form)
        self.assertIn("Transaction date must not be empty", result)

        form = {"date": today, "amount": ""}
        result, _ = self.web_put((endpoint, {"uri": t_0}), data=form)
        self.assertIn("Non-zero remaining amount to be assigned", result)

        form = {"date": today, "amount": "100"}
        result, _ = self.web_put((endpoint, {"uri": t_0}), data=form)
        self.assertIn("Transaction must have at least one split", result)

        form = {"date": today, "payee": "", "amount": "100"}
        result, _ = self.web_put((endpoint, {"uri": t_0}), data=form)
        self.assertIn("Transaction split missing properties", result)

        form = {"date": today, "payee": "a", "amount": "100"}
        result, _ = self.web_put((endpoint, {"uri": t_0}), data=form)
        self.assertIn(
            "Transaction split payee must be at least 2 characters long",
            result,
        )

        form = {
            "date": today,
            "locked": "",
            "payee": [payee_0, ""],
            "description": ["", ""],
            "category": [cat_0, cat_1],
            "tag": ["", ""],
            "amount": ["100", ""],
        }
        result, _ = self.web_put((endpoint, {"uri": t_0}), data=form)
        self.assertIn("Transaction split amount must not be empty", result)

        # Add split
        new_date = today - datetime.timedelta(days=10)
        new_date_ord = new_date.toordinal()
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
        result, headers = self.web_put((endpoint, {"uri": t_0}), data=form)
        self.assertIn("HX-Trigger", headers, msg=f"Response lack HX-Trigger {result}")
        self.assertEqual(headers["HX-Trigger"], "update-transaction")

        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)

            query = s.query(Transaction)
            query = query.where(Transaction.id_ == Transaction.uri_to_id(t_0))
            txn: Transaction = query.one()
            splits = txn.splits

            self.assertEqual(txn.date_ord, new_date_ord)
            self.assertTrue(txn.locked)
            self.assertEqual(len(splits), 2)

            t_split = splits[0]
            self.assertEqual(t_split.date_ord, new_date_ord)
            self.assertTrue(t_split.locked)
            self.assertEqual(t_split.payee, payee_0)
            self.assertEqual(t_split.description, new_desc)
            self.assertEqual(categories[t_split.category_id], cat_0)
            self.assertIsNone(t_split.tag)
            self.assertEqual(t_split.amount, 20)

            t_split = splits[1]
            self.assertEqual(t_split.date_ord, new_date_ord)
            self.assertTrue(t_split.locked)
            self.assertIsNone(t_split.payee)
            self.assertIsNone(t_split.description)
            self.assertEqual(categories[t_split.category_id], cat_1)
            self.assertIsNone(t_split.tag)
            self.assertEqual(t_split.amount, 80)

        # Remove split
        new_date = today - datetime.timedelta(days=10)
        new_date_ord = new_date.toordinal()
        new_desc = self.random_string()
        form = {
            "date": new_date,
            "payee": payee_0,
            "description": new_desc,
            "category": cat_0,
            "tag": "",
            "amount": "100",
        }
        result, headers = self.web_put((endpoint, {"uri": t_0}), data=form)
        self.assertIn("HX-Trigger", headers, msg=f"Response lack HX-Trigger {result}")
        self.assertEqual(headers["HX-Trigger"], "update-transaction")

        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)

            query = s.query(Transaction)
            query = query.where(Transaction.id_ == Transaction.uri_to_id(t_0))
            txn: Transaction = query.scalar()
            splits = txn.splits

            self.assertEqual(txn.date_ord, new_date_ord)
            self.assertFalse(txn.locked)
            self.assertEqual(len(splits), 1)

            t_split = splits[0]
            self.assertEqual(t_split.date_ord, new_date_ord)
            self.assertFalse(t_split.locked)
            self.assertEqual(t_split.payee, payee_0)
            self.assertEqual(t_split.description, new_desc)
            self.assertEqual(categories[t_split.category_id], cat_0)
            self.assertIsNone(t_split.tag)
            self.assertEqual(t_split.amount, 100)

        result, _ = self.web_delete((endpoint, {"uri": t_1}), data=form)
        self.assertIn("Cannot delete linked transaction", result)

        # Unlink transaction 1
        with p.begin_session() as s:
            query = s.query(Transaction).where(
                Transaction.id_ == Transaction.uri_to_id(t_1),
            )
            txn = query.one()
            txn.locked = False
            txn.linked = False
            for t_split in txn.splits:
                t_split.parent = txn

        result, headers = self.web_delete((endpoint, {"uri": t_1}))
        self.assertIn("HX-Trigger", headers, msg=f"Response lack HX-Trigger {result}")
        self.assertEqual(headers["HX-Trigger"], "update-account")
        with p.begin_session() as s:
            n = (
                s.query(Transaction)
                .where(Transaction.id_ == Transaction.uri_to_id(t_1))
                .count()
            )
            self.assertEqual(n, 0)

            n = (
                s.query(TransactionSplit)
                .where(TransactionSplit.parent_id == Transaction.uri_to_id(t_1))
                .count()
            )
            self.assertEqual(n, 0)

    def test_split(self) -> None:
        d = self._setup_portfolio()

        t_0 = d["t_0"]
        t_1 = d["t_1"]
        payee_0 = d["payee_0"]
        payee_1 = d["payee_1"]
        cat_0 = d["cat_0"]
        cat_1 = d["cat_1"]
        tag_1 = d["tag_1"]

        desc = self.random_string()
        tag = self.random_string()

        # GET splits for t_0 by copying the similar transaction t_1
        endpoint = "transactions.split"
        result, _ = self.web_get((endpoint, {"uri": t_0, "similar": t_1}))
        self.assertEqual(result.count('name="payee"'), 1)
        self.assertRegex(result, rf'name="payee"[ \n]+value="{payee_1}"')
        self.assertRegex(result, r'name="description"[ \n]+value=""')
        self.assertEqual(result.count("selected"), 1)
        self.assertRegex(result, rf'value="{cat_1}"[ \n]+selected')
        self.assertRegex(result, rf'name="tag"[ \n]+value="{tag_1}"')
        # t_1 is -10 but it should adjust the amount to match t_0
        self.assertRegex(result, r'name="amount"[ \n]+value="100\.00"')
        self.assertRegex(result, r'id="txn-remaining"[^>]+>\$0\.00<')

        form = {
            "payee": payee_0,
            "description": desc,
            "category": cat_0,
            "tag": tag,
            "amount": "100",
        }
        result, _ = self.web_post((endpoint, {"uri": t_0}), data=form)
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
        result, _ = self.web_delete((endpoint, {"uri": t_0, "index": 2}), data=form)
        self.assertEqual(result.count('name="payee"'), 1)
        self.assertRegex(result, rf'name="payee"[ \n]+value="{payee_0}"')
        self.assertRegex(result, rf'name="description"[ \n]+value="{desc}"')
        self.assertEqual(result.count("selected"), 1)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+selected')
        self.assertRegex(result, rf'name="tag"[ \n]+value="{tag}"')
        self.assertRegex(result, r'name="amount"[ \n]+value="100\.00"')
        self.assertRegex(result, r'id="txn-remaining"[ \n]+hx-swap-oob="True"')

        # DELETE ?all should revert to empty and Uncategorized
        form = {
            "payee": [payee_0, ""],
            "description": [desc, ""],
            "category": [cat_0, ""],
            "tag": [tag, ""],
            "amount": ["100", ""],
        }
        result, _ = self.web_delete((endpoint, {"uri": t_0, "all": True}), data=form)
        self.assertEqual(result.count('name="payee"'), 1)
        self.assertRegex(result, r'name="payee"[ \n]+value=""')
        self.assertRegex(result, r'name="description"[ \n]+value=""')
        self.assertEqual(result.count("selected"), 1)
        self.assertRegex(result, r'value="Uncategorized"[ \n]+selected')
        self.assertRegex(result, r'name="tag"[ \n]+value=""')
        self.assertRegex(result, r'name="amount"[ \n]+value=""')
        self.assertRegex(result, r'id="txn-remaining"[ \n]+hx-swap-oob="True"')

    def test_remaining(self) -> None:
        d = self._setup_portfolio()

        t_0 = d["t_0"]

        endpoint = "transactions.remaining"
        form = {"amount": "100"}
        result, _ = self.web_post((endpoint, {"uri": t_0}), data=form)
        self.assertIn(">$0.00</div>", result)

        form = {"amount": ["20", "20.001"]}
        result, _ = self.web_post((endpoint, {"uri": t_0}), data=form)
        self.assertIn(">$60.00</div>", result)

    def test_new(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.date.today()

        acct = d["acct"]
        acct_uri = d["acct_uri"]

        endpoint = "transactions.new"
        result, _ = self.web_get(endpoint)
        self.assertIn("New transaction", result)
        self.assertNotIn(f"selected>{acct}", result)

        form = {}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Transaction date must not be empty", result)

        form = {"date": today + datetime.timedelta(days=1)}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Cannot create future transaction", result)

        form = {"date": today}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Transaction amount must not be empty", result)

        form = {"date": today, "amount": "1000"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Transaction account must not be empty", result)

        form = {"date": today, "amount": "1000", "account": acct, "statement": "n"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(
            "Transaction statement must be at least 2 characters long",
            result,
        )

        form = {"date": today, "amount": "1000", "account": acct}
        result, _ = self.web_post(endpoint, data=form)
        # Redirect to edit after creating
        self.assertIn("Edit transaction", result)
        with p.begin_session() as s:
            acct_id = Account.uri_to_id(acct_uri)
            txn = (
                s.query(Transaction)
                .where(
                    Transaction.account_id == acct_id,
                    Transaction.amount == Decimal("1000"),
                )
                .one()
            )
            self.assertEqual(txn.statement, "Manually added")
            self.assertFalse(txn.locked, "Transaction unexpectably locked")
            self.assertFalse(txn.linked, "Transaction unexpectably linked")

            category_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Uncategorized")
                .scalar()
            )
            t_split = (
                s.query(TransactionSplit)
                .where(
                    TransactionSplit.account_id == acct_id,
                    TransactionSplit.amount == Decimal("1000"),
                )
                .one()
            )
            self.assertEqual(t_split.category_id, category_id)
