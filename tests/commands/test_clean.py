from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.commands.clean import Clean

if TYPE_CHECKING:
    import pytest

    from nummus.portfolio import Portfolio


def test_clean(capsys: pytest.CaptureFixture[str], empty_portfolio: Portfolio) -> None:
    c = Clean(empty_portfolio.path, None)
    assert c.run() == 0

    path_backup = empty_portfolio.path.with_suffix(".backup1.tar")
    assert path_backup.exists()

    captured = capsys.readouterr()
    target = (
        "Portfolio is unlocked\n"
        "Portfolio cleaned\n"
        "Portfolio was optimized by 0.0KB/0.0KiB\n"
    )
    assert captured.out == target
    assert not captured.err
