from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.models.config import Config
from nummus.models.currency import Currency

if TYPE_CHECKING:
    from sqlalchemy import orm

    from tests.controllers.conftest import WebClient


def test_page(web_client: WebClient) -> None:
    result, _ = web_client.GET("settings.page")
    assert "Base currency" in result


def test_edit_currency(web_client: WebClient, session: orm.Session) -> None:
    result, headers = web_client.PATCH("settings.edit", data={"currency": "CHF"})
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert "config" in headers["HX-Trigger"]

    assert Config.base_currency(session) == Currency.CHF
