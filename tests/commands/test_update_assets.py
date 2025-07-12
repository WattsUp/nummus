from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from colorama import Fore

from nummus.commands.update_assets import UpdateAssets
from nummus.models import Asset, AssetCategory

if TYPE_CHECKING:

    import pytest

    from nummus.models import Transaction
    from nummus.portfolio import Portfolio


def test_empty(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
) -> None:

    c = UpdateAssets(empty_portfolio.path, None, no_bars=True)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.out == target
    target = (
        f"{Fore.YELLOW}No assets were updated, "
        "add a ticker to an Asset to download market data\n"
    )
    assert captured.err == target


def test_one(
    capsys: pytest.CaptureFixture,
    today: datetime.date,
    empty_portfolio: Portfolio,
    transactions: list[Transaction],
    asset: Asset,
) -> None:
    _ = transactions
    with empty_portfolio.begin_session() as s:
        s.query(Asset).where(Asset.category == AssetCategory.INDEX).delete()

    c = UpdateAssets(empty_portfolio.path, None, no_bars=True)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = (
        f"{Fore.GREEN}Portfolio is unlocked\n"
        f"{Fore.GREEN}Asset {asset.name} ({asset.ticker}) updated "
        f"from {today - datetime.timedelta(days=9)} to {today}\n"
    )
    assert captured.out == target
    assert not captured.err


def test_failed(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    transactions: list[Transaction],
    asset: Asset,
) -> None:
    _ = transactions
    with empty_portfolio.begin_session() as s:
        s.query(Asset).where(Asset.category == AssetCategory.INDEX).delete()
        s.query(Asset).update({"ticker": "FAKE"})

    c = UpdateAssets(empty_portfolio.path, None, no_bars=True)
    assert c.run() != 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.out == target
    target = (
        f"{Fore.RED}Asset {asset.name} ({asset.ticker}) failed to update. "
        "Error: FAKE: No timezone found, symbol may be delisted\n"
    )
    assert captured.err == target
