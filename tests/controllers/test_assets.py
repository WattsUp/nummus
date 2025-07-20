from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import utils
from nummus.controllers import assets, base
from nummus.models import Asset, AssetCategory, AssetValuation, query_count, Transaction

if TYPE_CHECKING:
    import datetime

    import flask
    from sqlalchemy import orm

    from tests.controllers.conftest import WebClient


# TODO (WattsUp): Remove flask references from ctx functions
def test_ctx_performance_empty(
    today: datetime.date,
    flask_app: flask.Flask,
    session: orm.Session,
    asset: Asset,
) -> None:
    start = utils.date_add_months(today, -12)
    with flask_app.app_context():
        ctx = assets.ctx_performance(session, asset, "1yr")
    labels, date_mode = base.date_labels(start.toordinal(), today.toordinal())
    target: assets.PerformanceContext = {
        "date_mode": date_mode,
        "labels": labels,
        "period": "1yr",
        "period_options": base.PERIOD_OPTIONS,
        "values": [Decimal()] * len(labels),
    }
    assert ctx == target


def test_ctx_performance(
    today: datetime.date,
    flask_app: flask.Flask,
    session: orm.Session,
    asset: Asset,
    asset_valuation: AssetValuation,
) -> None:
    with flask_app.app_context():
        ctx = assets.ctx_performance(session, asset, "max")
    labels, date_mode = base.date_labels(asset_valuation.date_ord, today.toordinal())
    target: assets.PerformanceContext = {
        "date_mode": date_mode,
        "labels": labels,
        "period": "max",
        "period_options": base.PERIOD_OPTIONS,
        "values": [Decimal(asset_valuation.value)] * len(labels),
    }
    assert ctx == target


def test_ctx_table_empty(
    month: datetime.date,
    flask_app: flask.Flask,
    session: orm.Session,
    asset: Asset,
) -> None:
    with flask_app.app_context():
        ctx = assets.ctx_table(session, asset, None, None, None, None)

    last_months = [utils.date_add_months(month, i) for i in range(0, -3, -1)]
    options_period = [
        ("All time", "all"),
        *((f"{m:%B}", m.isoformat()[:7]) for m in last_months),
        (str(month.year), str(month.year)),
        (str(month.year - 1), str(month.year - 1)),
        ("Custom date range", "custom"),
    ]
    target: assets.TableContext = {
        "uri": asset.uri,
        "first_page": True,
        "editable": asset.ticker is None,
        "valuations": [],
        "no_matches": True,
        "next_page": None,
        "any_filters": False,
        "period": None,
        "options_period": options_period,
        "start": None,
        "end": None,
    }
    assert ctx == target


@pytest.mark.parametrize(
    ("period", "start", "end", "page", "any_filters", "has_valuation"),
    [
        (None, None, None, None, False, True),
        ("all", None, None, None, False, True),
        (None, None, None, "2000-01-01", False, False),
        ("custom", "2000-01-01", None, None, True, True),
        ("custom", None, "2000-01-01", None, True, False),
        ("2000-01", None, None, None, True, False),
        ("2000", None, None, None, True, False),
    ],
)
def test_ctx_table(
    flask_app: flask.Flask,
    session: orm.Session,
    asset: Asset,
    asset_valuation: AssetValuation,
    period: str | None,
    start: str | None,
    end: str | None,
    page: str | None,
    any_filters: bool,
    has_valuation: bool,
) -> None:
    with flask_app.app_context():
        ctx = assets.ctx_table(session, asset, period, start, end, page)

    if page is None:
        assert ctx["first_page"]
    else:
        assert not ctx["first_page"]
    assert not ctx["editable"]
    if has_valuation:
        target: assets.ValuationContext = {
            "uri": asset_valuation.uri,
            "asset_uri": asset.uri,
            "date": asset_valuation.date,
            "date_max": None,
            "value": asset_valuation.value,
        }
        assert ctx["valuations"] == [target]
        if page is None:
            # Only first page is valid
            assert not ctx["no_matches"]
    else:
        assert ctx["valuations"] == []
        if page is None:
            # Only first page is valid
            assert ctx["no_matches"]
    assert ctx["next_page"] is None
    assert ctx["any_filters"] == any_filters


def test_ctx_asset_empty(
    flask_app: flask.Flask,
    session: orm.Session,
    asset: Asset,
) -> None:
    with flask_app.app_context():
        ctx = assets.ctx_asset(session, asset, None, None, None, None, None)
    assert ctx["uri"] == asset.uri
    assert ctx["name"] == asset.name
    assert ctx["category"] == asset.category
    assert ctx["description"] == asset.description
    assert ctx["value"] == Decimal()
    assert ctx["value_date"] is None


def test_ctx_asset(
    flask_app: flask.Flask,
    session: orm.Session,
    asset: Asset,
    asset_valuation: AssetValuation,
) -> None:
    with flask_app.app_context():
        ctx = assets.ctx_asset(session, asset, None, None, None, None, None)
    assert ctx["uri"] == asset.uri
    assert ctx["name"] == asset.name
    assert ctx["category"] == asset.category
    assert ctx["description"] == asset.description
    assert ctx["value"] == asset_valuation.value
    assert ctx["value_date"] == asset_valuation.date


def test_ctx_rows_empty(flask_app: flask.Flask, session: orm.Session) -> None:
    with flask_app.app_context():
        ctx = assets.ctx_rows(session, include_unheld=True)
    assert ctx == {}


def test_ctx_rows_unheld(
    flask_app: flask.Flask,
    session: orm.Session,
    asset: Asset,
) -> None:
    with flask_app.app_context():
        ctx = assets.ctx_rows(session, include_unheld=True)
    target: dict[AssetCategory, list[assets.RowContext]] = {
        asset.category: [
            {
                "uri": asset.uri,
                "name": asset.name,
                "ticker": asset.ticker,
                "qty": Decimal(),
                "price": Decimal(),
                "value": Decimal(),
            },
        ],
    }
    assert ctx == target


def test_ctx_rows(
    flask_app: flask.Flask,
    session: orm.Session,
    asset: Asset,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    with flask_app.app_context():
        ctx = assets.ctx_rows(session, include_unheld=False)
    target: dict[AssetCategory, list[assets.RowContext]] = {
        asset.category: [
            {
                "uri": asset.uri,
                "name": asset.name,
                "ticker": asset.ticker,
                "qty": Decimal(10),
                "price": asset_valuation.value,
                "value": Decimal(10) * asset_valuation.value,
            },
        ],
    }
    assert ctx == target


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


@pytest.mark.xfail
def test_new(web_client: WebClient) -> None:
    web_client.GET("assets.new")


def test_asset_get(web_client: WebClient, asset: Asset) -> None:
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
    ("prop", "value", "target"),
    [
        ("name", "New Name", ""),
        ("name", " ", "Required"),
        ("name", "a", "2 characters required"),
        ("name", "Banana ETF", "Must be unique"),
        ("description", "BANANA ETF", ""),
        ("ticker", "TICKER", ""),
        ("ticker", " ", ""),
        ("ticker", "A", ""),
        ("ticker", "BANANA_ETF", "Must be unique"),
        ("date", "2000-01-01", ""),
        ("date", " ", "Required"),
        ("value", "0", ""),
        ("value", " ", "Required"),
    ],
)
def test_validation(
    web_client: WebClient,
    asset: Asset,
    asset_etf: Asset,
    asset_valuation: AssetValuation,
    prop: str,
    value: str,
    target: str,
) -> None:
    _ = asset_etf
    result, _ = web_client.GET(
        (
            "assets.validation",
            {"uri": asset.uri, prop: value, "v": asset_valuation.uri},
        ),
    )
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
    _ = transactions
    session.query(Asset).where(Asset.category == AssetCategory.INDEX).delete()
    session.commit()

    result, headers = web_client.POST("assets.update")
    assert "The assets with the following tickers were updated" in result
    assert asset.ticker is not None
    assert asset.ticker in result
    assert headers["HX-Trigger"] == "valuation"


def test_update_error(
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.POST("assets.update")
    assert "No timezone found, symbol may be delisted" in result
