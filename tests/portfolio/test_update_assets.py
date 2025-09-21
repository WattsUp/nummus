from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from nummus.models import Asset, AssetCategory
from nummus.portfolio import AssetUpdate

if TYPE_CHECKING:
    import pytest
    from sqlalchemy import orm

    from nummus.models import Transaction
    from nummus.portfolio import Portfolio


def test_empty(capsys: pytest.CaptureFixture, empty_portfolio: Portfolio) -> None:
    assert empty_portfolio.update_assets(no_bars=True) == []

    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_no_txns(empty_portfolio: Portfolio, asset: Asset) -> None:
    _ = asset
    assert empty_portfolio.update_assets(no_bars=True) == []


def test_update_assets(
    today: datetime.date,
    empty_portfolio: Portfolio,
    session: orm.Session,
    asset: Asset,
    asset_etf: Asset,
    transactions: list[Transaction],
) -> None:
    _ = asset_etf
    asset.interpolate = True
    session.query(Asset).where(Asset.category == AssetCategory.INDEX).delete()
    session.commit()
    _ = transactions
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
    asset.ticker = "FAKE"
    session.query(Asset).where(Asset.category == AssetCategory.INDEX).delete()
    session.commit()
    _ = transactions
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
