from __future__ import annotations

import datetime

from nummus.models import (
    Account,
    Asset,
    AssetCategory,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import HTTP_CODE_BAD_REQUEST, WebTestBase


class TestAsset(WebTestBase):
    def test_edit(self) -> None:
        p = self._portfolio

        today = datetime.date.today()
        today_ord = today.toordinal()

        name = self.random_string()

        with p.get_session() as s:
            # Delete index assets
            s.query(Asset).delete()
            s.commit()

            a = Asset(
                name=name,
                category=AssetCategory.STOCKS,
                interpolate=False,
            )
            s.add(a)
            s.commit()

            a_id = a.id_
            a_uri = a.uri

        endpoint = "assets.edit"
        url = endpoint, {"uri": a_uri}
        result, _ = self.web_get(url)
        self.assertNotIn("<html", result)
        self.assertIn("Edit asset", result)
        self.assertIn("0.000000", result)
        self.assertIn("no valuations", result)

        name = self.random_string()
        description = self.random_string()
        ticker = self.random_string().upper()
        form = {
            "name": name,
            "description": description,
            "category": "real estate",
            "interpolate": "",
            "ticker": ticker,
        }
        result, headers = self.web_post(url, data=form)
        self.assertEqual(headers["HX-Trigger"], "update-asset")
        self.assertNotIn("<svg", result)  # No error SVG
        with p.get_session() as s:
            a = s.query(Asset).first()
            if a is None:
                self.fail("Asset is missing")
            self.assertEqual(a.name, name)
            self.assertEqual(a.description, description)
            self.assertEqual(a.category, AssetCategory.REAL_ESTATE)
            self.assertTrue(a.interpolate)

        form = {
            "name": "a",
            "description": description,
            "category": "real estate",
            "interpolate": "",
            "ticker": ticker,
        }
        result, _ = self.web_post(url, data=form)
        e_str = "Asset name must be at least 2 characters long"
        self.assertIn(e_str, result)

        form = {
            "name": name,
            "description": description,
            "category": "",
            "interpolate": "",
            "ticker": ticker,
        }
        result, _ = self.web_post(url, data=form)
        e_str = "Asset category must not be None"
        self.assertIn(e_str, result)

        # Add a valuations
        with p.get_session() as s:
            v = AssetValuation(
                asset_id=a_id,
                date_ord=today_ord,
                value=10,
            )
            s.add(v)
            s.commit()

        result, _ = self.web_get(url)
        self.assertIn("10.00", result)
        self.assertIn(f"as of {today}", result)

    def test_page_transactions(self) -> None:
        _ = self._setup_portfolio()

        endpoint = "assets.page_transactions"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("No matching transactions", result)

    def test_txns(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()

        acct_uri = d["acct_uri"]

        # Add dividend transaction
        with p.get_session() as s:
            acct_id = Account.uri_to_id(acct_uri)

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            # Create assets
            a_banana = Asset(name="Banana Inc.", category=AssetCategory.ITEM)
            a_house = Asset(name="Fruit Ct. House", category=AssetCategory.REAL_ESTATE)

            s.add_all((a_banana, a_house))
            s.commit()
            a_house_name = a_house.name
            a_house_id = a_house.id_

            # Buy the house but no ticker so excluded
            txn = Transaction(
                account_id=acct_id,
                date_ord=today_ord,
                amount=0,
                statement=self.random_string(),
            )
            t_split_2 = TransactionSplit(
                amount=10,
                parent=txn,
                asset_id=a_banana.id_,
                asset_quantity_unadjusted=0,
                category_id=categories["Dividends Received"],
            )
            t_split_3 = TransactionSplit(
                amount=-10,
                parent=txn,
                asset_id=a_banana.id_,
                asset_quantity_unadjusted=2,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split_2, t_split_3))
            s.commit()

            t_split_3 = t_split_3.uri

        endpoint = "assets.txns"
        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
        self.assertRegex(result, r"<div .*>\$5.00</div>")
        self.assertRegex(result, r"<div .*>2.000000</div>")
        self.assertRegex(result, r"<div .*>-\$10.00</div>")
        self.assertRegex(result, rf'<div id="txn-{t_split_3}"')
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_3}/edit"')

        with p.get_session() as s:
            txn = Transaction(
                account_id=acct_id,
                date_ord=today_ord - 2,
                amount=-100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_house_id,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))
            s.commit()

            t_split_4 = t_split.uri

        result, _ = self.web_get(
            (endpoint, {"period": "30-days", "asset": a_house_name}),
        )
        self.assertRegex(result, r"<div .*>\$100.00</div>")
        self.assertRegex(result, r"<div .*>1.000000</div>")
        self.assertRegex(result, r"<div .*>-\$100.00</div>")
        self.assertRegex(result, rf'<div id="txn-{t_split_4}"')

    def test_txns_options(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.date.today()
        today_ord = today.toordinal()

        acct = d["acct"]
        acct_uri = d["acct_uri"]
        d["payee_0"]
        d["payee_1"]
        d["t_split_0"]
        d["t_split_1"]

        # Add dividend transaction
        with p.get_session() as s:
            acct_id = Account.uri_to_id(acct_uri)

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            # Create assets
            a_banana = Asset(name="Banana Inc.", category=AssetCategory.ITEM)
            a_banana_name = a_banana.name

            s.add(a_banana)
            s.commit()

            # Buy the house but no ticker so excluded
            txn = Transaction(
                account_id=acct_id,
                date_ord=today_ord,
                amount=0,
                statement=self.random_string(),
            )
            t_split_2 = TransactionSplit(
                amount=10,
                parent=txn,
                asset_id=a_banana.id_,
                asset_quantity_unadjusted=0,
                category_id=categories["Dividends Received"],
            )
            t_split_3 = TransactionSplit(
                amount=-10,
                parent=txn,
                asset_id=a_banana.id_,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split_2, t_split_3))
            s.commit()

            t_split_2 = t_split_2.uri
            t_split_3 = t_split_3.uri

        endpoint = "assets.txns_options"
        result, _ = self.web_get(
            (endpoint, {"field": "account"}),
        )
        self.assertEqual(result.count("span"), 2)
        self.assertRegex(result, rf'value="{acct}"[ \n]+hx-get')
        self.assertNotIn("checked", result)

        result, _ = self.web_get(
            (endpoint, {"field": "asset"}),
        )
        self.assertEqual(result.count("span"), 2)
        self.assertRegex(result, rf'value="{a_banana_name}"[ \n]+hx-get')
        self.assertNotIn("checked", result)

        result, _ = self.web_get(
            (endpoint, {"field": "unknown"}),
            rc=HTTP_CODE_BAD_REQUEST,
        )
