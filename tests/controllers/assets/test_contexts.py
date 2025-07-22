from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import utils
from nummus.controllers import assets, base

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from nummus.models import Asset, AssetCategory, AssetValuation, Transaction


def test_ctx_performance_empty(
    today: datetime.date,
    session: orm.Session,
    asset: Asset,
) -> None:
    start = utils.date_add_months(today, -12)
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
    session: orm.Session,
    asset: Asset,
    asset_valuation: AssetValuation,
) -> None:
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
    session: orm.Session,
    asset: Asset,
) -> None:
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
    session: orm.Session,
    asset: Asset,
) -> None:
    ctx = assets.ctx_asset(session, asset, None, None, None, None, None)
    assert ctx["uri"] == asset.uri
    assert ctx["name"] == asset.name
    assert ctx["category"] == asset.category
    assert ctx["description"] == asset.description
    assert ctx["value"] == Decimal()
    assert ctx["value_date"] is None


def test_ctx_asset(
    session: orm.Session,
    asset: Asset,
    asset_valuation: AssetValuation,
) -> None:
    ctx = assets.ctx_asset(session, asset, None, None, None, None, None)
    assert ctx["uri"] == asset.uri
    assert ctx["name"] == asset.name
    assert ctx["category"] == asset.category
    assert ctx["description"] == asset.description
    assert ctx["value"] == asset_valuation.value
    assert ctx["value_date"] == asset_valuation.date


def test_ctx_rows_empty(session: orm.Session) -> None:
    ctx = assets.ctx_rows(session, include_unheld=True)
    assert ctx == {}


def test_ctx_rows_unheld(
    session: orm.Session,
    asset: Asset,
) -> None:
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
    session: orm.Session,
    asset: Asset,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    _ = transactions
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
