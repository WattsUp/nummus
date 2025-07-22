from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.controllers.conftest import WebClient


def test_page(web_client: WebClient) -> None:
    result, _ = web_client.GET("emergency_fund.page")
    assert "Emergency fund" in result
    assert "Current balance" in result
    assert "Recommended balance" in result
    assert "Essential spending" in result


def test_dashboard(web_client: WebClient) -> None:
    result, _ = web_client.GET("emergency_fund.dashboard")
    assert "Emergency fund" in result
    assert "Current balance" not in result
    assert "Recommended balance" not in result
    assert "Essential spending" not in result
