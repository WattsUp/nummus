from __future__ import annotations

from nummus.controllers import settings
from nummus.models.currency import Currency, DEFAULT_CURRENCY


def test_ctx() -> None:
    ctx = settings.ctx_settings()

    target: settings.SettingsContext = {
        "currency": DEFAULT_CURRENCY,
        "currency_type": Currency,
    }
    assert ctx == target
