from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import utils
from nummus.controllers import base
from nummus.models import Asset, AssetCategory, AssetValuation, query_count

if TYPE_CHECKING:
    import datetime
    from decimal import Decimal

    from sqlalchemy import orm

    from nummus.models import Transaction
    from tests.controllers.conftest import WebClient


def test_page_all(web_client: WebClient, asset: Asset) -> None:
    result, _ = web_client.GET(("assets.page_all", {"include-unheld": True}))
    assert "Assets" in result
    assert "Stocks" in result
    assert asset.name in result
    assert "Asset is not currently held" in result


def test_page(
    web_client: WebClient,
    asset: Asset,
    asset_valuation: AssetValuation,
) -> None:
    result, _ = web_client.GET(("assets.page", {"uri": asset.uri}))
    assert asset.name in result
    target = (
        f"{utils.format_financial(asset_valuation.value)} as of {asset_valuation.date}"
    )
    assert target in result
    assert "no more valuations match query" in result
    assert "new" not in result


def test_new_get(web_client: WebClient) -> None:
    result, _ = web_client.GET("assets.new")
    assert "New asset" in result
    assert "Save" in result
    assert "Delete" not in result


def test_new(
    web_client: WebClient,
    session: orm.Session,
) -> None:
    session.query(Asset).delete()
    session.commit()

    result, headers = web_client.POST(
        "assets.new",
        data={
            "name": "New name",
            "category": "STOCKS",
            "description": "Nothing to see",
            "ticker": "1234",
        },
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "asset"

    a = session.query(Asset).one()
    assert a.name == "New name"
    assert a.category == AssetCategory.STOCKS
    assert a.description == "Nothing to see"
    assert a.ticker == "1234"


def test_new_error(web_client: WebClient) -> None:
    result, _ = web_client.POST(
        "assets.new",
        data={
            "name": "a",
            "category": "STOCKS",
            "description": "Nothing to see",
            "ticker": "1234",
        },
    )
    assert result == base.error("Asset name must be at least 2 characters long")


def test_asset_get_empty(web_client: WebClient, asset: Asset) -> None:
    result, _ = web_client.GET(("assets.asset", {"uri": asset.uri}))
    assert asset.name in result
    assert asset.ticker is not None
    assert asset.ticker in result
    assert asset.description is not None
    assert asset.description in result
    assert "Edit asset" in result
    assert "Save" in result
    assert "Delete" in result


def test_asset_get(
    web_client: WebClient,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.GET(("assets.asset", {"uri": asset.uri}))
    assert asset.name in result
    assert asset.ticker is not None
    assert asset.ticker in result
    assert asset.description is not None
    assert asset.description in result
    assert "Edit asset" in result
    assert "Save" in result
    assert "Delete" not in result


def test_asset_edit(web_client: WebClient, session: orm.Session, asset: Asset) -> None:
    result, headers = web_client.PUT(
        ("assets.asset", {"uri": asset.uri}),
        data={
            "name": "New name",
            "category": "BONDS",
            "ticker": "",
            "description": "Nothing to see",
        },
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "asset"

    session.refresh(asset)
    assert asset.name == "New name"
    assert asset.category == AssetCategory.BONDS
    assert asset.ticker is None
    assert asset.description == "Nothing to see"


def test_asset_edit_error(web_client: WebClient, asset: Asset) -> None:
    result, _ = web_client.PUT(
        ("assets.asset", {"uri": asset.uri}),
        data={
            "name": "a",
            "category": "BONDS",
            "ticker": "",
            "description": "Nothing to see",
        },
    )
    assert result == base.error("Asset name must be at least 2 characters long")


def test_account_delete(
    web_client: WebClient,
    asset: Asset,
    asset_valuation: AssetValuation,
) -> None:
    _ = asset_valuation
    result, headers = web_client.DELETE(("assets.asset", {"uri": asset.uri}))
    assert not result
    assert headers["HX-Redirect"] == web_client.url_for("assets.page_all")


def test_performance(web_client: WebClient, asset: Asset) -> None:
    result, headers = web_client.GET(("assets.performance", {"uri": asset.uri}))
    assert "<script>" in result
    assert headers["HX-Push-URL"] == web_client.url_for("assets.page", uri=asset.uri)


def test_table(web_client: WebClient, asset: Asset) -> None:
    result, headers = web_client.GET(("assets.table", {"uri": asset.uri}))
    assert "no valuations match query" in result
    assert headers["HX-Push-URL"] == web_client.url_for("assets.page", uri=asset.uri)


def test_table_second_page(web_client: WebClient, asset: Asset) -> None:
    result, headers = web_client.GET(
        ("assets.table", {"uri": asset.uri, "page": "2000-01-01"}),
    )
    assert "no more valuations match query" in result
    assert "HX-Push-URL" not in headers


@pytest.mark.parametrize(
    ("include_asset", "include_valuation", "prop", "value", "target"),
    [
        (True, False, "name", "New Name", ""),
        (True, False, "name", " ", "Required"),
        (True, False, "name", "a", "2 characters required"),
        (True, False, "name", "Banana ETF", "Must be unique"),
        (False, False, "name", "Banana incorporated", "Must be unique"),
        (True, False, "description", "BANANA ETF", ""),
        (True, False, "ticker", "TICKER", ""),
        (True, False, "ticker", " ", ""),
        (True, False, "ticker", "A", ""),
        (True, False, "ticker", "BANANA_ETF", "Must be unique"),
        (True, False, "date", "2000-01-01", ""),
        (True, False, "date", " ", "Required"),
        (True, True, "date", "2000-01-01", ""),
        (True, True, "date", " ", "Required"),
        (False, True, "date", "2000-01-01", ""),
        (True, False, "value", "0", ""),
        (True, False, "value", " ", "Required"),
    ],
)
def test_validation(
    web_client: WebClient,
    asset: Asset,
    asset_etf: Asset,
    asset_valuation: AssetValuation,
    include_asset: bool,
    include_valuation: bool,
    prop: str,
    value: str,
    target: str,
) -> None:
    _ = asset_etf
    args = {prop: value}
    if include_asset:
        args["uri"] = asset.uri
    if include_valuation:
        args["v"] = asset_valuation.uri
    result, _ = web_client.GET(("assets.validation", args))
    assert result == target


def test_new_valuation_get(
    today: datetime.date,
    web_client: WebClient,
    asset: Asset,
) -> None:
    result, _ = web_client.GET(("assets.new_valuation", {"uri": asset.uri}))
    assert "New valuation" in result
    assert today.isoformat() in result


def test_new_valuation(
    today: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    asset: Asset,
    rand_real: Decimal,
) -> None:
    result, headers = web_client.POST(
        ("assets.new_valuation", {"uri": asset.uri}),
        data={
            "date": today,
            "value": rand_real,
        },
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "valuation"

    v = session.query(AssetValuation).one()
    assert v.asset_id == asset.id_
    assert v.date == today
    assert v.value == rand_real


@pytest.mark.parametrize(
    ("date", "value", "target"),
    [
        ("", "", "Date must not be empty"),
        ("a", "", "Unable to parse date"),
        ("2100-01-01", "", "Only up to 7 days in advance"),
        ("2000-01-01", "", "Value must not be empty"),
        ("2000-01-01", "a", "Value must not be empty"),
        ("2000-01-01", "-1", "Value must not be negative"),
    ],
)
def test_new_valuation_error(
    web_client: WebClient,
    asset: Asset,
    date: str,
    value: str,
    target: str,
) -> None:
    result, _ = web_client.POST(
        ("assets.new_valuation", {"uri": asset.uri}),
        data={
            "date": date,
            "value": value,
        },
    )
    assert result == base.error(target)


def test_new_valuation_duplicate(
    web_client: WebClient,
    asset: Asset,
    asset_valuation: AssetValuation,
) -> None:
    result, _ = web_client.POST(
        ("assets.new_valuation", {"uri": asset.uri}),
        data={
            "date": asset_valuation.date,
            "value": asset_valuation.value,
        },
    )
    assert result == base.error("Date must be unique for each asset")


def test_valuation_get(
    web_client: WebClient,
    asset_valuation: AssetValuation,
) -> None:
    result, _ = web_client.GET(("assets.valuation", {"uri": asset_valuation.uri}))
    assert "Edit valuation" in result
    assert asset_valuation.date.isoformat() in result
    assert str(asset_valuation.value).strip("0").strip(".") in result


def test_valuation_delete(
    session: orm.Session,
    web_client: WebClient,
    asset_valuation: AssetValuation,
) -> None:
    result, headers = web_client.DELETE(
        ("assets.valuation", {"uri": asset_valuation.uri}),
    )
    assert "snackbar.show" in result
    assert f"{asset_valuation.date} valuation deleted" in result
    assert headers["HX-Trigger"] == "valuation"

    v = session.query(AssetValuation).one_or_none()
    assert v is None


def test_valuation_edit(
    tomorrow: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    asset_valuation: AssetValuation,
    rand_real: Decimal,
) -> None:
    result, headers = web_client.PUT(
        ("assets.valuation", {"uri": asset_valuation.uri}),
        data={
            "date": tomorrow,
            "value": rand_real,
        },
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "valuation"

    session.refresh(asset_valuation)
    assert asset_valuation.date == tomorrow
    assert asset_valuation.value == rand_real


@pytest.mark.parametrize(
    ("date", "value", "target"),
    [
        ("", "", "Date must not be empty"),
        ("a", "", "Unable to parse date"),
        ("2100-01-01", "", "Only up to 7 days in advance"),
        ("2000-01-01", "", "Value must not be empty"),
        ("2000-01-01", "a", "Value must not be empty"),
        ("2000-01-01", "-1", "Value must not be negative"),
    ],
)
def test_valuation_error(
    web_client: WebClient,
    asset_valuation: AssetValuation,
    date: str,
    value: str,
    target: str,
) -> None:
    result, _ = web_client.PUT(
        ("assets.valuation", {"uri": asset_valuation.uri}),
        data={
            "date": date,
            "value": value,
        },
    )
    assert result == base.error(target)


def test_valuation_duplicate(
    tomorrow: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    asset: Asset,
    asset_valuation: AssetValuation,
) -> None:
    v = AssetValuation(
        asset_id=asset.id_,
        date_ord=tomorrow.toordinal(),
        value=asset_valuation.value,
    )
    session.add(v)
    session.commit()

    result, _ = web_client.PUT(
        ("assets.valuation", {"uri": asset_valuation.uri}),
        data={
            "date": tomorrow,
            "value": asset_valuation.value,
        },
    )
    assert result == base.error("Date must be unique for each asset")


def test_update_get_empty(session: orm.Session, web_client: WebClient) -> None:
    session.query(Asset).delete()
    session.commit()

    result, _ = web_client.GET("assets.update")
    assert "Update assets" in result
    assert "There are no assets to update, set ticker on edit asset page" in result


def test_update_get_one(
    session: orm.Session,
    web_client: WebClient,
    asset: Asset,
) -> None:
    _ = asset
    session.query(Asset).where(Asset.category == AssetCategory.INDEX).delete()
    session.commit()

    result, _ = web_client.GET("assets.update")
    assert "Update assets" in result
    assert "There is one asset with ticker to update" in result


def test_update_get(session: orm.Session, web_client: WebClient) -> None:
    n = query_count(session.query(Asset))

    result, _ = web_client.GET("assets.update")
    assert "Update assets" in result
    assert f"There are {n} assets with tickers to update" in result


def test_update_empty(web_client: WebClient) -> None:
    result, _ = web_client.POST("assets.update")
    assert "No assets were updated" in result


def test_update(
    session: orm.Session,
    web_client: WebClient,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    _ = asset
    _ = transactions
    session.query(Asset).where(Asset.category == AssetCategory.INDEX).delete()
    session.commit()

    result, headers = web_client.POST("assets.update")
    assert "snackbar.show" in result
    assert "1 asset updated" in result
    assert headers["HX-Trigger"] == "valuation"


def test_update_error(
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.POST("assets.update")
    assert "No timezone found, symbol may be delisted" in result
