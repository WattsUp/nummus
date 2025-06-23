from __future__ import annotations

import datetime

from nummus.models import (
    Asset,
    AssetCategory,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestAsset(WebTestBase):

    def test_page_all(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio

        today = datetime.date.today()

        acct_id = d["acct_id"]
        asset_0_name = d["asset_0_name"]
        asset_1_name = d["asset_1_name"]
        asset_0_id = d["asset_0_id"]
        asset_0_uri = d["asset_0_uri"]
        asset_1_uri = d["asset_1_uri"]

        with p.begin_session() as s:
            s.query(Asset).where(Asset.id_ == asset_0_id).update({"ticker": "BANANA"})

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}
            t_cat_id = categories["securities traded"]

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=1,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))

        endpoint = "assets.page_all"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("BANANA", result)
        self.assertIn("Item", result)
        self.assertIn(asset_0_name, result)
        self.assertIn(asset_0_uri, result)
        self.assertNotIn("Real Estate", result)
        self.assertNotIn(asset_1_name, result)
        self.assertNotIn(asset_1_uri, result)
        self.assertIn("Show unheld assets", result)

        result, _ = self.web_get(
            (endpoint, {"include-unheld": True}),
            headers=headers,
        )
        self.assertIn("Item", result)
        self.assertIn("BANANA", result)
        self.assertIn(asset_0_name, result)
        self.assertIn(asset_0_uri, result)
        self.assertIn("Real Estate", result)
        self.assertIn(asset_1_name, result)
        self.assertIn(asset_1_uri, result)
        self.assertIn("Hide unheld assets", result)

        with p.begin_session() as s:
            # Sell asset
            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=-1,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertNotIn("BANANA", result)
        self.assertNotIn("Item", result)
        self.assertNotIn(asset_0_name, result)
        self.assertNotIn(asset_0_uri, result)
        self.assertNotIn("Real Estate", result)
        self.assertNotIn(asset_1_name, result)
        self.assertNotIn(asset_1_uri, result)
        self.assertIn("Show unheld assets", result)

    def test_page(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()

        asset_0_name = d["asset_0_name"]
        asset_0_id = d["asset_0_id"]
        asset_0_uri = d["asset_0_uri"]

        endpoint = "assets.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(
            (endpoint, {"uri": asset_0_uri}),
            headers=headers,
        )
        self.assertIn(asset_0_name, result)
        self.assertIn("Asset has no valuations", result)

        # Add valuation
        with p.begin_session() as s:
            v = AssetValuation(
                asset_id=asset_0_id,
                value=100,
                date_ord=today_ord,
            )
            s.add(v)
            s.flush()
            v_uri = v.uri

        endpoint = "assets.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(
            (endpoint, {"uri": asset_0_uri}),
            headers=headers,
        )
        self.assertNotIn("Asset has no valuations", result)
        self.assertIn(f"$100.00 as of {today}", result)
        self.assertIn(v_uri, result)

    def test_asset(self) -> None:
        p = self._portfolio
        name = self.random_string()

        with p.begin_session() as s:
            # Delete index assets
            s.query(Asset).delete()
            s.flush()

            a = Asset(
                name=name,
                category=AssetCategory.STOCKS,
                interpolate=False,
            )
            s.add(a)
            s.flush()

            a_id = a.id_
            a_uri = a.uri

        endpoint = "assets.asset"
        url = endpoint, {"uri": a_uri}
        result, _ = self.web_get(url)
        self.assertNotIn("<html", result)
        self.assertIn("Edit asset", result)

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
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "asset")
        with p.begin_session() as s:
            a = s.query(Asset).where(Asset.id_ == a_id).one()
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

    def test_performance(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()

        asset_0_id = d["asset_0_id"]
        asset_0_uri = d["asset_0_uri"]

        with p.begin_session() as s:
            v = AssetValuation(
                asset_id=asset_0_id,
                value=10,
                date_ord=today.toordinal(),
            )
            s.add(v)

        endpoint = "assets.performance"
        result, _ = self.web_get((endpoint, {"uri": asset_0_uri}))
        self.assertIn("0.0,10.0]", result)

        result, _ = self.web_get(
            (endpoint, {"uri": asset_0_uri, "chart-period": "max"}),
        )
        self.assertIn("[10.0]", result)

    def test_table(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()

        asset_0_id = d["asset_0_id"]
        asset_0_uri = d["asset_0_uri"]

        with p.begin_session() as s:
            v = AssetValuation(
                asset_id=asset_0_id,
                value=10,
                date_ord=today.toordinal(),
            )
            s.add(v)
            s.flush()
            v_uri = v.uri

        endpoint = "assets.table"
        result, headers = self.web_get((endpoint, {"uri": asset_0_uri}))
        self.assertIn(v_uri, result)
        self.assertEqual(headers.get("HX-Push-Url"), f"/assets/{asset_0_uri}")

        result, headers = self.web_get(
            (endpoint, {"uri": asset_0_uri, "page": today.isoformat()}),
        )
        self.assertIn(v_uri, result)
        self.assertNotIn("HX-Push-Url", headers)
        self.assertIn(v_uri, result)

        result, headers = self.web_get(
            (endpoint, {"uri": asset_0_uri, "period": "2000"}),
        )
        self.assertIn("no valuations match query", result)
        self.assertNotIn(v_uri, result)
        self.assertEqual(
            headers.get("HX-Push-Url"),
            f"/assets/{asset_0_uri}?period=2000",
        )

        long_ago = today - datetime.timedelta(days=400)
        queries = {
            "uri": asset_0_uri,
            "period": "custom",
            "start": long_ago.isoformat(),
            "end": long_ago.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertIn("no valuations match query", result)
        self.assertNotIn(v_uri, result)

        queries = {
            "uri": asset_0_uri,
            "period": "custom",
            "end": long_ago.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertIn("no valuations match query", result)

        queries = {
            "uri": asset_0_uri,
            "period": "custom",
            "start": long_ago.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertNotIn("no valuations match query", result)

        result, _ = self.web_get(
            (endpoint, {"uri": asset_0_uri, "period": "2000-01"}),
        )
        self.assertIn("no valuations match query", result)
        self.assertNotIn(v_uri, result)

    def test_validation(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()

        asset_0_id = d["asset_0_id"]
        asset_0_uri = d["asset_0_uri"]
        asset_1_uri = d["asset_1_uri"]
        asset_0_name = d["asset_0_name"]

        with p.begin_session() as s:
            v = AssetValuation(
                asset_id=asset_0_id,
                value=10,
                date_ord=today.toordinal(),
            )
            s.add(v)
            s.flush()
            v_id = v.id_
            v_uri = v.uri

        endpoint = "assets.validation"

        result, _ = self.web_get((endpoint, {"uri": asset_0_uri, "name": " "}))
        self.assertEqual("Required", result)

        result, _ = self.web_get((endpoint, {"uri": asset_0_uri, "name": "a"}))
        self.assertEqual("2 characters required", result)

        result, _ = self.web_get((endpoint, {"uri": asset_0_uri, "name": "ab"}))
        self.assertEqual("", result)

        # Ticker not required
        result, _ = self.web_get((endpoint, {"uri": asset_0_uri, "ticker": " "}))
        self.assertEqual("", result)

        # Ticker can be short
        result, _ = self.web_get((endpoint, {"uri": asset_0_uri, "ticker": "a"}))
        self.assertEqual("", result)

        # Name cannot be duplicated
        result, _ = self.web_get((endpoint, {"uri": asset_1_uri, "name": asset_0_name}))
        self.assertEqual("Must be unique", result)

        with p.begin_session() as s:
            s.query(Asset).where(Asset.id_ == asset_0_id).update(
                {Asset.description: "stuff"},
            )

        # Description not checked for duplication
        result, _ = self.web_get(
            (endpoint, {"uri": asset_1_uri, "description": "stuff"}),
        )
        self.assertEqual("", result)

        args = {
            "uri": asset_0_uri,
            "date": " ",
            "v": v_uri,
        }
        result, _ = self.web_get((endpoint, args))
        self.assertEqual("Required", result)

        args = {
            "uri": asset_0_uri,
            "date": "a",
            "v": v_uri,
        }
        result, _ = self.web_get((endpoint, args))
        self.assertEqual("Unable to parse", result)

        args = {
            "uri": asset_0_uri,
            "date": (today + datetime.timedelta(days=10)).isoformat(),
            "v": v_uri,
        }
        result, _ = self.web_get((endpoint, args))
        self.assertEqual("Only up to a week in advance", result)

        args = {
            "uri": asset_0_uri,
            "date": today.isoformat(),
            "v": v_uri,
        }
        result, _ = self.web_get((endpoint, args))
        self.assertEqual("", result)

        v_uri = AssetValuation.id_to_uri(v_id + 1)
        args = {
            "uri": asset_0_uri,
            "date": today.isoformat(),
            "v": v_uri,
        }
        result, _ = self.web_get((endpoint, args))
        self.assertEqual("Must be unique", result)

        args = {
            "uri": asset_1_uri,
            "date": today.isoformat(),
            "v": v_uri,
        }
        result, _ = self.web_get((endpoint, args))
        self.assertEqual("", result)

        args = {
            "uri": asset_0_uri,
            "date": (today + datetime.timedelta(days=1)).isoformat(),
            "v": v_uri,
        }
        result, _ = self.web_get((endpoint, args))
        self.assertEqual("", result)

        result, _ = self.web_get((endpoint, {"uri": asset_0_uri, "value": "a"}))
        self.assertEqual("Unable to parse", result)

        result, _ = self.web_get((endpoint, {"uri": asset_0_uri, "value": " "}))
        self.assertEqual("Required", result)

        result, _ = self.web_get((endpoint, {"uri": asset_0_uri, "value": "10"}))
        self.assertEqual("", result)

    def test_new_valuation(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()

        asset_0_id = d["asset_0_id"]
        asset_0_uri = d["asset_0_uri"]

        endpoint = "assets.new_valuation"
        result, _ = self.web_get((endpoint, {"uri": asset_0_uri}))
        self.assertNotIn("Delete", result)

        form = {}
        result, _ = self.web_post((endpoint, {"uri": asset_0_uri}), data=form)
        e_str = "Date must not be empty"
        self.assertIn(e_str, result)

        form = {"date": today + datetime.timedelta(days=10)}
        result, _ = self.web_post((endpoint, {"uri": asset_0_uri}), data=form)
        e_str = "Date can only be up to a week in the future"
        self.assertIn(e_str, result)

        form = {"date": today}
        result, _ = self.web_post((endpoint, {"uri": asset_0_uri}), data=form)
        e_str = "Value must not be empty"
        self.assertIn(e_str, result)

        form = {"date": today, "value": "-100"}
        result, _ = self.web_post((endpoint, {"uri": asset_0_uri}), data=form)
        e_str = "Value must not be negative"
        self.assertIn(e_str, result)

        form = {"date": today, "value": "100"}
        result, headers = self.web_post((endpoint, {"uri": asset_0_uri}), data=form)
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "valuation")

        with p.begin_session() as s:
            v = (
                s.query(AssetValuation)
                .where(AssetValuation.asset_id == asset_0_id)
                .one()
            )
            self.assertEqual(v.asset_id, asset_0_id)
            self.assertEqual(v.date_ord, today_ord)
            self.assertEqual(v.value, 100)

        form = {"date": today, "value": "100"}
        result, _ = self.web_post((endpoint, {"uri": asset_0_uri}), data=form)
        e_str = "Date must be unique for each asset"
        self.assertIn(e_str, result)

    def test_valuation(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)
        yesterday_ord = yesterday.toordinal()

        asset_0_id = d["asset_0_id"]

        # Add valuations
        with p.begin_session() as s:
            v = AssetValuation(
                asset_id=asset_0_id,
                value=10,
                date_ord=yesterday_ord,
            )
            s.add(v)

            v = AssetValuation(
                asset_id=asset_0_id,
                value=100,
                date_ord=today_ord,
            )
            s.add(v)
            s.flush()
            v_id = v.id_
            v_uri = v.uri

        endpoint = "assets.valuation"
        result, _ = self.web_get((endpoint, {"uri": v_uri}))
        self.assertIn("Delete", result)

        form = {}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        e_str = "Date must not be empty"
        self.assertIn(e_str, result)

        form = {"date": today + datetime.timedelta(days=10)}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        e_str = "Date can only be up to a week in the future"
        self.assertIn(e_str, result)

        form = {"date": today}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        e_str = "Value must not be empty"
        self.assertIn(e_str, result)

        form = {"date": today, "value": "-100"}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        e_str = "Value must not be negative"
        self.assertIn(e_str, result)

        form = {"date": today, "value": "100*2"}
        result, headers = self.web_put((endpoint, {"uri": v_uri}), data=form)
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "valuation")

        with p.begin_session() as s:
            v = s.query(AssetValuation).where(AssetValuation.id_ == v_id).first()
            if v is None:
                self.fail("AssetValuation is missing")
            self.assertEqual(v.asset_id, asset_0_id)
            self.assertEqual(v.date_ord, today_ord)
            self.assertEqual(v.value, 200)

        form = {"date": yesterday, "value": "100"}
        result, _ = self.web_put((endpoint, {"uri": v_uri}), data=form)
        e_str = "Date must be unique for each asset"
        self.assertIn(e_str, result)

        result, headers = self.web_delete((endpoint, {"uri": v_uri}))
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "valuation")

        with p.begin_session() as s:
            n = s.query(AssetValuation).where(AssetValuation.id_ == v_id).count()
            self.assertEqual(n, 0)

    def test_update(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio

        acct_id = d["acct_id"]
        asset_0_id = d["asset_0_id"]
        asset_1_id = d["asset_1_id"]

        endpoint = "assets.update"
        result, _ = self.web_get(endpoint)
        self.assertIn("Update assets", result)
        self.assertIn("There are no assets to update", result)

        result, _ = self.web_post(endpoint)
        self.assertIn("No assets were updated", result)

        with p.begin_session() as s:
            s.query(Asset).where(Asset.id_ == asset_0_id).update({"ticker": "BANANA"})

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}
            t_cat_id = categories["securities traded"]

            date = datetime.date(2023, 5, 1)
            txn = Transaction(
                account_id=acct_id,
                date=date,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=-1,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))
            txn = Transaction(
                account_id=acct_id,
                date=date,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=asset_1_id,
                asset_quantity_unadjusted=-1,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))

        result, _ = self.web_get(endpoint)
        self.assertIn("There is one asset", result)

        result, _ = self.web_post(endpoint)
        self.assertIn("The assets with the following tickers were updated", result)
        self.assertIn("BANANA", result)

        with p.begin_session() as s:
            s.query(Asset).where(Asset.id_ == asset_1_id).update({"ticker": "ORANGE"})

        result, _ = self.web_get(endpoint)
        self.assertIn("There are 2 assets", result)

        result, _ = self.web_post(endpoint)
        self.assertIn(
            "ORANGE failed: ORANGE: No timezone found, symbol may be delisted",
            result,
        )
