from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.controllers import settings
from nummus.models.currency import Currency, DEFAULT_CURRENCY

if TYPE_CHECKING:
    from sqlalchemy import orm


def test_ctx(session: orm.Session) -> None:
    ctx = settings.ctx_settings(session)

    target: settings.SettingsContext = {
        "currency": DEFAULT_CURRENCY,
        "currency_type": Currency,
    }
    assert ctx == target
