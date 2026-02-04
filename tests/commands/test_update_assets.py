from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from nummus.commands.update_assets import UpdateAssets
from nummus.models.asset import (
    Asset,
    AssetCategory,
)

if TYPE_CHECKING:

    import pytest

    from nummus.models.transaction import Transaction
    from nummus.portfolio import Portfolio


def test_empty(
    capsys: pytest.CaptureFixture[str],
    empty_portfolio: Portfolio,
) -> None:
    c = UpdateAssets(empty_portfolio.path, None, no_bars=True)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = "Portfolio is unlocked\n"
    assert captured.out == target
    target = (
        "No assets were updated, add a ticker to an Asset to download market data\n"
    )
    assert captured.err == target


def test_one(
    capsys: pytest.CaptureFixture[str],
    today: datetime.date,
    empty_portfolio: Portfolio,
    transactions: list[Transaction],
    asset: Asset,
) -> None:
    with empty_portfolio.begin_session():
        Asset.query().where(Asset.category == AssetCategory.INDEX).delete()

    c = UpdateAssets(empty_portfolio.path, None, no_bars=True)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = (
        "Portfolio is unlocked\n"
        f"Asset {asset.name} ({asset.ticker}) updated "
        f"from {today - datetime.timedelta(days=9)} to {today}\n"
    )
    assert captured.out == target
    assert not captured.err


def test_failed(
    capsys: pytest.CaptureFixture[str],
    empty_portfolio: Portfolio,
    transactions: list[Transaction],
    asset: Asset,
) -> None:
    with empty_portfolio.begin_session():
        Asset.query().where(Asset.category == AssetCategory.INDEX).delete()
        Asset.query().update({"ticker": "FAKE"})
    asset.refresh()

    c = UpdateAssets(empty_portfolio.path, None, no_bars=True)
    assert c.run() != 0

    captured = capsys.readouterr()
    target = "Portfolio is unlocked\n"
    assert captured.out == target
    target = (
        f"Asset {asset.name} ({asset.ticker}) failed to update. "
        "Error: FAKE: No timezone found, symbol may be delisted\n"
    )
    assert captured.err == target
