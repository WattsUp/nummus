from __future__ import annotations

import datetime

from nummus.models import Asset, AssetCategory, AssetValuation
from tests.controllers.base import WebTestBase


class TestAsset(WebTestBase):
    def test_edit(self) -> None:
        p = self._portfolio

        today = datetime.date.today()
        today_ord = today.toordinal()

        name = self.random_string()

        with p.get_session() as s:
            a = Asset(
                name=name,
                category=AssetCategory.STOCKS,
                interpolate=False,
            )
            s.add(a)
            s.commit()

            a_id = a.id_
            a_uri = a.uri

        endpoint = f"/h/assets/a/{a_uri}/edit"
        result, _ = self.web_get(endpoint)
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
        result, headers = self.web_post(endpoint, data=form)
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
            "name": "ab",
            "description": description,
            "category": "real estate",
            "interpolate": "",
            "ticker": ticker,
        }
        result, _ = self.web_post(endpoint, data=form)
        e_str = "Asset name must be at least 3 characters long"
        self.assertIn(e_str, result)

        form = {
            "name": name,
            "description": description,
            "category": "",
            "interpolate": "",
            "ticker": ticker,
        }
        result, _ = self.web_post(endpoint, data=form)
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

        endpoint = f"/h/assets/a/{a_uri}/edit"
        result, _ = self.web_get(endpoint)
        self.assertIn("10.00", result)
        self.assertIn(f"as of {today}", result)
