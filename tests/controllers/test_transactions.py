from __future__ import annotations

import datetime
from decimal import Decimal

from nummus.models import (
    query_count,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestTransactions(WebTestBase):
    def test_page_all(self) -> None:
        p = self._portfolio
        self._setup_portfolio()
        with p.begin_session() as s:
            s.query(TransactionSplit).delete()
            s.query(Transaction).delete()
        endpoint = "transactions.page_all"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn('id="txn-header"', result)
        self.assertIn('id="txn-filters"', result)
        self.assertIn('id="txn-table"', result)
        self.assertIn("no transactions match query", result)

    def test_table(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.datetime.now().astimezone().date()

        acct_id = d["acct_id"]
        acct_uri = d["acct_uri"]
        acct_name = d["acct_name"]
        payee_1 = d["payee_1"]
        txn_0_id = d["txn_0_id"]
        txn_0_uri = d["txn_0_uri"]
        txn_1_uri = d["txn_1_uri"]
        cat_0_uri = d["cat_0_uri"]
        cat_0_emoji_name = d["cat_0_emoji_name"]
        asset_0_id = d["asset_0_id"]

        # Unclear transaction 0
        with p.begin_session() as s:
            query = s.query(Transaction).where(Transaction.id_ == txn_0_id)
            txn = query.one()
            txn.cleared = False
            for t_split in txn.splits:
                t_split.parent = txn

        endpoint = "transactions.table"
        result, headers = self.web_get(endpoint)
        self.assertEqual(headers.get("HX-Push-Url"), "/transactions")
        self.assertEqual(result.count('<div class="txn"'), 2)
        self.assertIn(txn_0_uri, result)
        self.assertIn(txn_1_uri, result)
        self.assertIn("<title>Transactions - nummus</title>", result)

        result, headers = self.web_get((endpoint, {"page": today.isoformat()}))
        self.assertNotIn("HX-Push-Url", headers)
        self.assertEqual(result.count('<div class="txn"'), 2)
        self.assertIn(txn_0_uri, result)
        self.assertIn(txn_1_uri, result)
        self.assertIn("<title>Transactions - nummus</title>", result)

        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
        self.assertNotIn("no transaction match query", result)
        self.assertIn(r"<title>All Transactions - nummus</title>", result)

        result, _ = self.web_get(
            (endpoint, {"period": "all", "account": acct_uri}),
        )
        self.assertNotIn("no transactions match query", result)
        self.assertIn(f"<title>All Transactions, {acct_name} - nummus</title>", result)

        result, _ = self.web_get(
            (endpoint, {"period": "2000", "account": acct_uri}),
        )
        self.assertIn("no transactions match query", result)
        self.assertIn(f"<title>2000 Transactions, {acct_name} - nummus</title>", result)

        long_ago = today - datetime.timedelta(days=400)
        queries = {
            "period": "custom",
            "start": long_ago.isoformat(),
            "end": long_ago.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertIn("no transactions match query", result)
        self.assertIn(
            f"<title>{long_ago} to {long_ago} Transactions - nummus</title>",
            result,
        )

        queries = {
            "period": "custom",
            "end": long_ago.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertIn("no transactions match query", result)
        self.assertIn(
            f"<title>to {long_ago} Transactions - nummus</title>",
            result,
        )

        queries = {
            "period": "custom",
            "start": long_ago.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertNotIn("no transactions match query", result)
        self.assertIn(
            f"<title>from {long_ago} Transactions - nummus</title>",
            result,
        )

        long_ago_month = long_ago.isoformat()[:7]
        queries = {
            "period": long_ago_month,
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertIn("no transactions match query", result)
        self.assertIn(
            f"<title>{long_ago_month} Transactions - nummus</title>",
            result,
        )

        long_ago_year = f"{long_ago.year:04}"
        queries = {
            "period": long_ago_year,
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertIn("no transactions match query", result)
        self.assertIn(
            f"<title>{long_ago_year} Transactions - nummus</title>",
            result,
        )

        result, _ = self.web_get(
            (endpoint, {"category": cat_0_uri}),
        )
        self.assertEqual(result.count('<div class="txn"'), 1)
        self.assertIn(txn_0_uri, result)
        self.assertNotIn(txn_1_uri, result)
        self.assertIn(
            f"<title>Transactions, {cat_0_emoji_name} - nummus</title>",
            result,
        )

        result, _ = self.web_get(
            (endpoint, {"period": "2000", "category": cat_0_uri}),
        )
        self.assertIn("no transactions match query", result)
        self.assertIn(
            f"<title>2000 Transactions, {cat_0_emoji_name} - nummus</title>",
            result,
        )

        result, _ = self.web_get(
            (endpoint, {"uncleared": True}),
        )
        self.assertEqual(result.count('<div class="txn"'), 1)
        self.assertIn(txn_0_uri, result)
        self.assertNotIn(txn_1_uri, result)
        self.assertIn(
            "<title>Transactions, Uncleared - nummus</title>",
            result,
        )

        result, _ = self.web_get(
            (endpoint, {"search": payee_1}),
        )
        self.assertEqual(result.count('<div class="txn"'), 1)
        self.assertNotIn(txn_0_uri, result)
        self.assertIn(txn_1_uri, result)
        self.assertIn(
            "<title>Transactions - nummus</title>",
            result,
        )

        # Add dividend transaction
        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}
            cat_2_id = categories["dividends received"]
            cat_2_uri = TransactionCategory.id_to_uri(cat_2_id)

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=1,
                category_id=cat_2_id,
            )
            s.add_all((txn, t_split))
            s.flush()

            txn_2_uri = txn.uri
        queries = {
            "category": cat_2_uri,
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertEqual(result.count('<div class="txn"'), 1)
        self.assertNotIn(txn_0_uri, result)
        self.assertNotIn(txn_1_uri, result)
        self.assertIn(txn_2_uri, result)

        # Create many transactions
        with p.begin_session() as s:
            for i in range(50):
                txn = Transaction(
                    account_id=acct_id,
                    date=today - datetime.timedelta(days=i),
                    amount=-10,
                    statement=self.random_string(),
                    payee=payee_1,
                    cleared=True,
                )
                t_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    category_id=cat_2_id,
                )
                s.add_all((txn, t_split))
        result, _ = self.web_get(endpoint)
        # <=25 days included
        self.assertLessEqual(result.count('class="txn-header"'), 25)
        # 25 days included
        self.assertEqual(result.count('class="txn"'), 25)

    def test_table_options(self) -> None:
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        acct_name = d["acct_name"]
        cat_0_uri = d["cat_0_uri"]
        cat_0_emoji_name = d["cat_0_emoji_name"]
        cat_1_uri = d["cat_1_uri"]
        cat_1_emoji_name = d["cat_1_emoji_name"]

        endpoint = "transactions.table_options"
        result, _ = self.web_get(endpoint)
        self.assertIn(acct_uri, result)
        self.assertIn(acct_name, result)
        self.assertIn(cat_0_uri, result)
        self.assertIn(cat_0_emoji_name, result)
        self.assertIn(cat_1_uri, result)
        self.assertIn(cat_1_emoji_name, result)
        self.assertNotIn("checked", result)

    def test_new(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.datetime.now().astimezone().date()

        acct_id = d["acct_id"]
        acct_uri = d["acct_uri"]
        acct_name = d["acct_name"]
        cat_0_id = d["cat_0_id"]
        cat_0_uri = d["cat_0_uri"]
        payee_0 = d["payee_0"]

        endpoint = "transactions.new"
        result, _ = self.web_get(endpoint)
        self.assertIn("New transaction", result)
        self.assertNotIn(f"selected>{acct_name}", result)
        self.assertIn(acct_name, result)

        form = {}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Transaction date must not be empty", result)

        form = {"date": today + datetime.timedelta(days=10)}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Date can only be up to 7 days in advance", result)

        form = {"date": today}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Transaction amount must not be empty", result)

        form = {"date": today, "amount": "1000"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Transaction account must not be empty", result)

        form = {
            "date": today,
            "amount": "1000",
            "account": acct_uri,
            "split-amount": "1000",
            "category": cat_0_uri,
            "memo": "n",
            "tag": "",
        }
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(
            "Transaction split memo must be at least 2 characters long",
            result,
        )

        form = {
            "date": today,
            "amount": "1000",
            "account": acct_uri,
            "payee": payee_0,
            "split-amount": "1000",
            "category": cat_0_uri,
            "memo": "n",
            "tag": "abc",
        }
        result, _ = self.web_put(endpoint, data=form)
        self.assertIn(f'name="payee" value="{payee_0}"', result)
        self.assertIn('name="memo" value="n"', result)
        self.assertIn('name="memo" value=""', result)
        self.assertEqual(result.count("selected"), 1 + 4)  # 1 for acct, 4 for splits
        self.assertIn(f'value="{cat_0_uri}" selected', result)
        self.assertIn('name="tag" value="abc"', result)
        self.assertIn('name="tag" value=""', result)
        self.assertIn('name="split-amount" value="1000"', result)
        self.assertIn('name="split-amount" value=""', result)

        memo = self.random_string()
        tag = self.random_string()
        form = {
            "date": today,
            "amount": "1000",
            "account": acct_uri,
            "split-amount": "1000",
            "category": cat_0_uri,
            "memo": memo,
            "tag": tag,
        }
        result, headers = self.web_post(endpoint, data=form)
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "account")
        with p.begin_session() as s:
            txn = (
                s.query(Transaction)
                .where(
                    Transaction.account_id == acct_id,
                    Transaction.amount == Decimal(1000),
                )
                .one()
            )
            self.assertEqual(txn.statement, "Manually added")
            self.assertFalse(txn.cleared, "Transaction unexpectably cleared")

            t_split = (
                s.query(TransactionSplit)
                .where(
                    TransactionSplit.account_id == acct_id,
                    TransactionSplit.amount == Decimal(1000),
                )
                .one()
            )
            self.assertEqual(t_split.category_id, cat_0_id)
            self.assertEqual(t_split.memo, memo)
            self.assertEqual(t_split.tag, tag)

    def test_transaction(self) -> None:
        p = self._portfolio
        today = datetime.datetime.now().astimezone().date()
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        payee_0 = d["payee_0"]
        txn_0_id = d["txn_0_id"]
        txn_0_uri = d["txn_0_uri"]
        txn_1_id = d["txn_1_id"]
        txn_1_uri = d["txn_1_uri"]
        cat_0_id = d["cat_0_id"]
        cat_0_uri = d["cat_0_uri"]
        cat_1_id = d["cat_1_id"]
        cat_1_uri = d["cat_1_uri"]

        endpoint = "transactions.transaction"
        result, _ = self.web_get((endpoint, {"uri": txn_0_uri}))
        self.assertEqual(result.count('name="payee"'), 1)

        form = {}
        result, _ = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn("Transaction date must not be empty", result)

        form = {"date": today + datetime.timedelta(days=10)}
        result, _ = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn("Date can only be up to a week in the future", result)

        form = {"date": today, "account": acct_uri, "amount": ""}
        result, _ = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn("Transaction amount must not be empty", result)

        form = {"date": today, "account": acct_uri, "amount": "100"}
        result, _ = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn("Transaction must have at least one split", result)

        form = {"date": today, "account": acct_uri, "payee": "", "amount": "100"}
        result, _ = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn("Transaction must have at least one split", result)

        form = {"date": today, "account": acct_uri, "payee": "a", "amount": "100"}
        result, _ = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn(
            "Transaction payee must be at least 2 characters long",
            result,
        )

        form = {
            "date": today,
            "account": acct_uri,
            "cleared": "",
            "payee": payee_0,
            "memo": ["", ""],
            "category": [cat_0_uri, cat_1_uri],
            "tag": ["", ""],
            "amount": "100",
            "split-amount": ["90", ""],
        }
        result, _ = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn("Non-zero remaining amount to be assigned", result)

        # Add split
        new_date = today - datetime.timedelta(days=10)
        new_date_ord = new_date.toordinal()
        new_memo = self.random_string()
        form = {
            "date": new_date,
            "account": acct_uri,
            "payee": payee_0,
            "memo": [new_memo, ""],
            "category": [cat_0_uri, cat_1_uri],
            "tag": ["", ""],
            "amount": "100",
            "split-amount": ["40/2", "(100-3*10)+10"],
        }
        result, headers = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "transaction")

        with p.begin_session() as s:
            query = s.query(Transaction).where(Transaction.id_ == txn_0_id)
            txn = query.one()
            splits = txn.splits

            self.assertEqual(txn.date_ord, new_date_ord)
            self.assertEqual(len(splits), 2)

            t_split = splits[0]
            self.assertEqual(t_split.date_ord, new_date_ord)
            self.assertEqual(t_split.payee, payee_0)
            self.assertEqual(t_split.memo, new_memo)
            self.assertEqual(t_split.category_id, cat_0_id)
            self.assertIsNone(t_split.tag)
            self.assertEqual(t_split.amount, 20)

            t_split = splits[1]
            self.assertEqual(t_split.date_ord, new_date_ord)
            self.assertEqual(t_split.payee, payee_0)
            self.assertIsNone(t_split.memo)
            self.assertEqual(t_split.category_id, cat_1_id)
            self.assertIsNone(t_split.tag)
            self.assertEqual(t_split.amount, 80)

        # Remove split
        new_date = today - datetime.timedelta(days=10)
        new_date_ord = new_date.toordinal()
        new_memo = self.random_string()
        form = {
            "date": new_date,
            "account": acct_uri,
            "payee": payee_0,
            "memo": new_memo,
            "category": cat_0_uri,
            "tag": "",
            "amount": "100",
        }
        result, headers = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "transaction")

        with p.begin_session() as s:
            query = s.query(Transaction).where(Transaction.id_ == txn_0_id)
            txn = query.one()
            splits = txn.splits

            self.assertEqual(txn.date_ord, new_date_ord)
            self.assertFalse(txn.cleared)
            self.assertEqual(len(splits), 1)

            t_split = splits[0]
            self.assertEqual(t_split.date_ord, new_date_ord)
            self.assertFalse(t_split.cleared)
            self.assertEqual(t_split.payee, payee_0)
            self.assertEqual(t_split.memo, new_memo)
            self.assertEqual(t_split.category_id, cat_0_id)
            self.assertIsNone(t_split.tag)
            self.assertEqual(t_split.amount, 100)

        result, _ = self.web_delete((endpoint, {"uri": txn_1_uri}), data=form)
        self.assertIn("Cannot delete cleared transaction", result)

        # Cannot edit account or total of cleared transaction
        form = {
            "date": new_date,
            "account": acct_uri,
            "payee": payee_0,
            "memo": [new_memo, ""],
            "category": [cat_0_uri, cat_1_uri],
            "tag": ["", ""],
            "amount": "100",
            "split-amount": ["40/2", "(100-3*10)+10"],
        }
        result, headers = self.web_put((endpoint, {"uri": txn_1_uri}), data=form)
        self.assertIn("Non-zero remaining amount to be assigned", result)

        # Unclear transaction 1
        with p.begin_session() as s:
            query = s.query(Transaction).where(Transaction.id_ == txn_1_id)
            txn = query.one()
            txn.cleared = False
            for t_split in txn.splits:
                t_split.parent = txn

        result, headers = self.web_delete((endpoint, {"uri": txn_1_uri}))
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "account")
        with p.begin_session() as s:
            n = query_count(s.query(Transaction).where(Transaction.id_ == txn_1_id))
            self.assertEqual(n, 0)

            n = query_count(
                s.query(TransactionSplit).where(TransactionSplit.parent_id == txn_1_id),
            )
            self.assertEqual(n, 0)

    def test_split(self) -> None:
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        payee_0 = d["payee_0"]
        payee_1 = d["payee_1"]
        txn_0_uri = d["txn_0_uri"]
        txn_1_uri = d["txn_1_uri"]
        cat_0_uri = d["cat_0_uri"]
        cat_1_uri = d["cat_1_uri"]
        tag_1 = d["tag_1"]

        memo = self.random_string()
        tag = self.random_string()

        # GET splits for t_0 by copying the similar transaction t_1
        endpoint = "transactions.split"
        if False:
            result, _ = self.web_get(
                (endpoint, {"uri": txn_0_uri, "similar": txn_1_uri}),
            )
            self.assertIn(f'name="payee" value="{payee_1}"', result)
            self.assertIn('name="memo" value=""', result)
            self.assertEqual(result.count("selected"), 1)
            self.assertIn(f'value="{cat_1_uri}" selected', result)
            self.assertIn(f'name="tag" value="{tag_1}"', result)
            # t_1 is -10 but it should adjust the amount to match t_0
            self.assertIn('name="amount" value="100.00"', result)
            self.assertRegex(result, r'id="txn-remaining"[^>]+>\$0\.00<')

        form = {
            "account": acct_uri,
            "payee": payee_0,
            "memo": memo,
            "category": cat_0_uri,
            "tag": tag,
            "amount": "100",
        }
        result, _ = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn(f'name="payee" value="{payee_0}"', result)
        self.assertIn(f'name="memo" value="{memo}"', result)
        self.assertIn('name="memo" value=""', result)
        self.assertEqual(result.count("selected"), 1 + 4)  # 1 for acct, 4 for splits
        self.assertIn(f'value="{cat_0_uri}" selected', result)
        self.assertIn(f'name="tag" value="{tag}"', result)
        self.assertIn('name="tag" value=""', result)
        self.assertIn('name="split-amount" value="100"', result)
        self.assertIn('name="split-amount" value=""', result)

        form = {
            "account": acct_uri,
            "payee": payee_0,
            "memo": [memo, ""],
            "category": [cat_0_uri, ""],
            "tag": [tag, ""],
            "amount": "100",
            "split-amount": ["80", "20"],
        }
        result, _ = self.web_put((endpoint, {"uri": txn_0_uri}), data=form)
        self.assertIn(f'name="payee" value="{payee_0}"', result)
        self.assertIn(f'name="memo" value="{memo}"', result)
        self.assertIn('name="memo" value=""', result)
        self.assertEqual(result.count("selected"), 1 + 5)  # 1 for acct, 5 for splits
        self.assertIn(f'value="{cat_0_uri}" selected', result)
        self.assertIn(f'name="tag" value="{tag}"', result)
        self.assertIn('name="tag" value=""', result)
        self.assertIn('name="split-amount" value="80"', result)
        self.assertIn('name="split-amount" value="20"', result)
        self.assertIn('name="split-amount" value=""', result)

    def test_validation(self) -> None:
        today = datetime.datetime.now().astimezone().date()

        endpoint = "transactions.validation"

        result, _ = self.web_get((endpoint, {"payee": " "}))
        self.assertEqual("Required", result)

        result, _ = self.web_get((endpoint, {"payee": "a"}))
        self.assertEqual("2 characters required", result)

        result, _ = self.web_get((endpoint, {"payee": "ab"}))
        self.assertEqual("", result)

        # Memo not required
        result, _ = self.web_get((endpoint, {"memo": " "}))
        self.assertEqual("", result)

        result, _ = self.web_get((endpoint, {"date": " "}))
        self.assertEqual("Required", result)

        result, _ = self.web_get((endpoint, {"date": "a"}))
        self.assertEqual("Unable to parse", result)

        result, _ = self.web_get(
            (endpoint, {"date": (today + datetime.timedelta(days=10)).isoformat()}),
        )
        self.assertEqual("Only up to 7 days in advance", result)

        result, _ = self.web_get(
            (endpoint, {"date": (today + datetime.timedelta(days=1)).isoformat()}),
        )
        self.assertEqual("", result)

        result, _ = self.web_get(
            (endpoint, {"split-amount": "a", "split": True}),
        )
        self.assertEqual("Unable to parse", result)

        result, _ = self.web_get((endpoint, {"amount": "a"}))
        self.assertEqual("Unable to parse", result)

        result, _ = self.web_get((endpoint, {"amount": " "}))
        self.assertEqual("Required", result)

        result, _ = self.web_get(
            (endpoint, {"split-amount": ["1", "2"], "amount": "10"}),
        )
        self.assertIn("dialog-headline-error", result)
        self.assertIn("Sum of splits $3.00 not equal to total $10.00", result)

        result, _ = self.web_get(
            (endpoint, {"split-amount": ["1", "2"], "amount": "3", "split": True}),
        )
        self.assertIn("dialog-headline-error", result)
        self.assertIn("></error>", result)
