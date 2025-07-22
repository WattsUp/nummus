from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.controllers.conftest import WebClient


def test_page(web_client: WebClient) -> None:
    result, _ = web_client.GET("allocation.page")
    assert "Asset allocation" in result
    assert "By category" in result
    assert "By U.S. sector" in result
