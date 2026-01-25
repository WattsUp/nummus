"""Settings controllers."""

from __future__ import annotations

from typing import TypedDict

import flask

from nummus import web
from nummus.controllers import base
from nummus.models.config import Config, ConfigKey
from nummus.models.currency import Currency


class SettingsContext(TypedDict):
    """Type definition for settings context."""

    currency: Currency
    currency_type: type[Currency]


def page() -> flask.Response:
    """GET /settings.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session():
        return base.page(
            "settings/page.jinja",
            "Settings",
            ctx=ctx_settings(),
        )


def edit() -> flask.Response:
    """PATCH /h/settings/edit.

    Returns:
        string HTML response

    """
    p = web.portfolio
    currency = flask.request.form.get("currency", type=Currency)
    if currency:
        with p.begin_session():
            Config.set_(ConfigKey.BASE_CURRENCY, str(currency.value))
    else:
        raise NotImplementedError

    return base.dialog_swap(event="config", snackbar="All changes saved")


def ctx_settings() -> SettingsContext:
    """Get the context to build the settings page.

    Returns:
        SettingsContext

    """
    return {
        "currency": Config.base_currency(),
        "currency_type": Currency,
    }


ROUTES: base.Routes = {
    "/settings": (page, ["GET"]),
    "/h/settings/edit": (edit, ["PATCH"]),
}
