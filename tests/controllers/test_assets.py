from __future__ import annotations

import datetime
import re

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
    def test_asset(self) -> None:
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

        endpoint = "assets.asset"
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
            "ticker": ticker,
        }
        result, headers = self.web_put(url, data=form)
        self.assertIn("HX-Trigger", headers, msg=f"Response lack HX-Trigger {result}")
        self.assertEqual(headers["HX-Trigger"], "update-asset")
        self.assertNotIn("<svg", result)  # No error SVG
        with p.get_session() as s:
            a = s.query(Asset).first()
            if a is None:
                self.fail("Asset is missing")
            self.assertEqual(a.name, name)
            self.assertEqual(a.description, description)
            self.assertEqual(a.category, AssetCategory.REAL_ESTATE)

        form = {
            "name": "a",
            "description": description,
            "category": "real estate",
            "ticker": ticker,
        }
        result, _ = self.web_put(url, data=form)
        e_str = "Asset name must be at least 2 characters long"
        self.assertIn(e_str, result)

        form = {
            "name": name,
            "description": description,
            "category": "",
            "ticker": ticker,
        }
        result, _ = self.web_put(url, data=form)
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

    def test_page(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()

        a_0 = d["a_0"]
        a_uri_0 = d["a_uri_0"]
        a_id_0 = Asset.uri_to_id(a_uri_0)

        endpoint = "assets.page"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(
            (endpoint, {"uri": a_uri_0}),
            headers=headers,
        )
        self.assertIn(a_0, result)
        self.assertRegex(result, r"<h1 .*>\$0.00</h1>")
        self.assertRegex(result, r"<h2 .*>[ \n]*no valuations[ \n]*</h2>")
        self.assertRegex(result, r"<script>assetChart\.update\(.*\)</script>")
        self.assertIn("No matching valuations for given query filters", result)

        # Add valuation
        with p.get_session() as s:
            v = AssetValuation(
                asset_id=a_id_0,
                value=100,
                date_ord=today_ord,
            )
            s.add(v)
            s.commit()
            v_uri = v.uri

        endpoint = "assets.page"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(
            (endpoint, {"uri": a_uri_0}),
            headers=headers,
        )
        self.assertRegex(result, r"<h1 .*>\$100.00</h1>")
        self.assertRegex(result, rf"<h2 .*>[ \n]*as of {today}[ \n]*</h2>")
        self.assertRegex(result, r"<script>assetChart\.update\(.*\)</script>")
        self.assertRegex(result, rf'hx-get="/h/assets/v/{v_uri}"')

    def test_txns(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()

        acct_uri = d["acct_uri"]
        a_1 = d["a_1"]
        a_uri_0 = d["a_uri_0"]
        a_uri_1 = d["a_uri_1"]

        # Add dividend transaction
        with p.get_session() as s:
            acct_id = Account.uri_to_id(acct_uri)
            a_id_0 = Asset.uri_to_id(a_uri_0)
            a_id_1 = Asset.uri_to_id(a_uri_1)

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            txn = Transaction(
                account_id=acct_id,
                date_ord=today_ord,
                amount=0,
                statement=self.random_string(),
            )
            t_split_2 = TransactionSplit(
                amount=10,
                parent=txn,
                asset_id=a_id_0,
                asset_quantity_unadjusted=0,
                category_id=categories["Dividends Received"],
            )
            t_split_3 = TransactionSplit(
                amount=-10,
                parent=txn,
                asset_id=a_id_0,
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
                asset_id=a_id_1,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))
            s.commit()

            t_split_4 = t_split.uri

        result, _ = self.web_get(
            (endpoint, {"period": "30-days", "asset": a_1}),
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
        a_uri_0 = d["a_uri_0"]
        a_0 = d["a_0"]

        # Add dividend transaction
        with p.get_session() as s:
            acct_id = Account.uri_to_id(acct_uri)
            a_id_0 = Asset.uri_to_id(a_uri_0)

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

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
                asset_id=a_id_0,
                asset_quantity_unadjusted=0,
                category_id=categories["Dividends Received"],
            )
            t_split_3 = TransactionSplit(
                amount=-10,
                parent=txn,
                asset_id=a_id_0,
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
        self.assertRegex(result, rf'value="{a_0}"[ \n]+hx-get')
        self.assertNotIn("checked", result)

        result, _ = self.web_get(
            (endpoint, {"field": "unknown"}),
            rc=HTTP_CODE_BAD_REQUEST,
        )

    def test_valuations(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()

        a_uri_0 = d["a_uri_0"]
        a_id_0 = Asset.uri_to_id(a_uri_0)

        # Add valuation
        with p.get_session() as s:
            v = AssetValuation(
                asset_id=a_id_0,
                value=100,
                date_ord=today_ord,
            )
            s.add(v)
            s.commit()
            v_uri = v.uri

        endpoint = "assets.valuations"
        result, _ = self.web_get(
            (endpoint, {"uri": a_uri_0, "period": "all"}),
        )
        self.assertRegex(result, r"<div .*>\$100.00</div>")
        self.assertRegex(result, rf'<div id="val-{v_uri}"')
        self.assertRegex(result, rf'hx-get="/h/assets/v/{v_uri}"')

        result, _ = self.web_get(
            (endpoint, {"uri": a_uri_0, "period": "all"}),
        )
        # Second call for table should not update chart as well
        self.assertNotRegex(result, r"<script>assetChart\.update\(.*\)</script>")

        result, _ = self.web_get(
            (endpoint, {"uri": a_uri_0, "period": "30-days"}),
        )
        self.assertRegex(
            result,
            r'<script>assetChart\.update\(.*"min": null.*\)</script>',
        )
        self.assertIn('"date_mode": "weeks"', result)

        result, _ = self.web_get(
            (endpoint, {"uri": a_uri_0, "period": "last-year"}),
        )
        self.assertRegex(
            result,
            r'<script>assetChart\.update\(.*"min": null.*\)</script>',
        )
        self.assertIn('"date_mode": "months"', result)
        self.assertNotRegex(result, r"<div .*>\$100.00</div>")
        self.assertNotRegex(result, rf'<div id="val-{v_uri}"')
        self.assertNotRegex(result, rf'hx-get="/h/assets/v/{v_uri}/edit"')

        result, _ = self.web_get(
            (endpoint, {"uri": a_uri_0, "period": "5-years"}),
        )
        self.assertRegex(
            result,
            r'<script>assetChart\.update\(.*"min": \[.+\].*\)</script>',
        )
        m = re.search(
            r'<script>assetChart\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertNotIn(today.isoformat(), dates_s)
        self.assertIn(today.isoformat()[:7], dates_s)
        self.assertIn('"date_mode": "years"', result)

        # Make asset not editable
        with p.get_session() as s:
            a = s.query(Asset).where(Asset.id_ == a_id_0).first()
            if a is None:
                self.fail("Asset is missing")
            a.ticker = "BANANA"
            s.commit()

        headers = {"HX-Trigger": "val-table"}
        queries = {
            "period": "custom",
            "start": today.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get(
            (endpoint, {"uri": a_uri_0, **queries}),
            headers=headers,
        )
        self.assertRegex(result, rf'<div id="val-{v_uri}"')
        self.assertNotRegex(result, rf'hx-get="/h/assets/v/{v_uri}/edit"')

    def test_new_valuation(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()

        a_uri_0 = d["a_uri_0"]
        a_id_0 = Asset.uri_to_id(a_uri_0)

        endpoint = "assets.new_valuation"
        result, _ = self.web_get((endpoint, {"uri": a_uri_0}))
        self.assertNotIn("Delete", result)

        form = {}
        result, _ = self.web_post((endpoint, {"uri": a_uri_0}), data=form)
        e_str = "Asset valuation date must not be empty"
        self.assertIn(e_str, result)

        form = {"date": today}
        result, _ = self.web_post((endpoint, {"uri": a_uri_0}), data=form)
        e_str = "Asset valuation value must not be empty"
        self.assertIn(e_str, result)

        form = {"date": today, "value": "-100"}
        result, _ = self.web_post((endpoint, {"uri": a_uri_0}), data=form)
        e_str = "Asset valuation value must be zero or positive"
        self.assertIn(e_str, result)

        form = {"date": today, "value": "100"}
        result, _ = self.web_post((endpoint, {"uri": a_uri_0}), data=form)
        self.assertIn("empty:hidden", result)

        with p.get_session() as s:
            v = s.query(AssetValuation).first()
            if v is None:
                self.fail("AssetValuation is missing")
            self.assertEqual(v.asset_id, a_id_0)
            self.assertEqual(v.date_ord, today_ord)
            self.assertEqual(v.value, 100)

        form = {"date": today, "value": "100"}
        result, _ = self.web_post((endpoint, {"uri": a_uri_0}), data=form)
        e_str = "Asset valuation date must be unique for each asset"
        self.assertIn(e_str, result)

    def test_valuation(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)
        yesterday_ord = yesterday.toordinal()

        a_uri_0 = d["a_uri_0"]
        a_id_0 = Asset.uri_to_id(a_uri_0)

        # Add valuations
        with p.get_session() as s:
            v = AssetValuation(
                asset_id=a_id_0,
                value=10,
                date_ord=yesterday_ord,
            )
            s.add(v)
            s.commit()

            v = AssetValuation(
                asset_id=a_id_0,
                value=100,
                date_ord=today_ord,
            )
            s.add(v)
            s.commit()
            v_id = v.id_
            v_uri = v.uri

        endpoint = "assets.valuation"
        result, _ = self.web_get((endpoint, {"uri": v_uri}))
        self.assertIn("Delete", result)

        form = {}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        e_str = "Asset valuation date must not be empty"
        self.assertIn(e_str, result)

        form = {"date": today}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        e_str = "Asset valuation value must not be empty"
        self.assertIn(e_str, result)

        form = {"date": today, "value": "-100"}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        e_str = "Asset valuation value must be zero or positive"
        self.assertIn(e_str, result)

        form = {"date": today, "value": "200"}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        self.assertIn("empty:hidden", result)

        with p.get_session() as s:
            v = s.query(AssetValuation).where(AssetValuation.id_ == v_id).first()
            if v is None:
                self.fail("AssetValuation is missing")
            self.assertEqual(v.asset_id, a_id_0)
            self.assertEqual(v.date_ord, today_ord)
            self.assertEqual(v.value, 200)

        form = {"date": yesterday, "value": "100"}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        e_str = "Asset valuation date must be unique for each asset"
        self.assertIn(e_str, result)

        result, _ = self.web_delete((endpoint, {"uri": v_uri}))
        self.assertIn("empty:hidden", result)

        with p.get_session() as s:
            n = s.query(AssetValuation).where(AssetValuation.id_ == v_id).count()
            self.assertEqual(n, 0)
