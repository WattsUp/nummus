from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.controllers.conftest import WebClient


def test_page_dashboard(web_client: WebClient) -> None:
    result, _ = web_client.GET("common.page_dashboard")
    assert "Dashboard" in result


def test_page_style_test(web_client: WebClient) -> None:
    result, _ = web_client.GET("common.page_style_test")
    assert "Style Test" in result
