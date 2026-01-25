from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from nummus.models.asset import (
    Asset,
    AssetCategory,
)
from nummus.portfolio import AssetUpdate, Portfolio

if TYPE_CHECKING:
    import pytest
    from sqlalchemy import orm

    from nummus.models.transaction import Transaction
    from nummus.portfolio import Portfolio


def test_empty(capsys: pytest.CaptureFixture[str], empty_portfolio: Portfolio) -> None:
    assert empty_portfolio.update_assets(no_bars=True) == []

    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_no_txns(empty_portfolio: Portfolio, asset: Asset) -> None:
    assert empty_portfolio.update_assets(no_bars=True) == []


def test_update_assets(
    today: datetime.date,
    empty_portfolio: Portfolio,
    session: orm.Session,
    asset: Asset,
    asset_etf: Asset,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        asset.interpolate = True
        Asset.query().where(Asset.category == AssetCategory.INDEX).delete()
    target: list[AssetUpdate] = [
        AssetUpdate(
            asset.name,
            asset.ticker or "",
            today - datetime.timedelta(days=9),
            today,
            None,
        ),
    ]

    assert empty_portfolio.update_assets(no_bars=True) == target

    session.refresh(asset)
    assert not asset.interpolate


def test_error(
    empty_portfolio: Portfolio,
    session: orm.Session,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        asset.ticker = "FAKE"
        Asset.query().where(Asset.category == AssetCategory.INDEX).delete()
    target: list[AssetUpdate] = [
        AssetUpdate(
            asset.name,
            asset.ticker or "",
            None,
            None,
            "FAKE: No timezone found, symbol may be delisted",
        ),
    ]

    assert empty_portfolio.update_assets(no_bars=True) == target
