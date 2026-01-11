"""Settings controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

import flask

from nummus import web
from nummus.controllers import base
from nummus.models.config import Config, ConfigKey
from nummus.models.currency import Currency

if TYPE_CHECKING:
    from sqlalchemy import orm


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
    with p.begin_session() as s:
        return base.page(
            "settings/page.jinja",
            "Settings",
            ctx=ctx_settings(s),
        )


def edit() -> flask.Response:
    """PATCH /h/settings/edit.

    Returns:
        string HTML response

    """
    p = web.portfolio
    currency = flask.request.form.get("currency", type=Currency)
    if currency:
        with p.begin_session() as s:
            Config.set_(s, ConfigKey.BASE_CURRENCY, str(currency.value))
    else:
        raise NotImplementedError

    return base.dialog_swap(event="config", snackbar="All changes saved")


def ctx_settings(s: orm.Session) -> SettingsContext:
    """Get the context to build the settings page.

    Args:
        s: SQL session to use

    Returns:
        SettingsContext

    """
    return {
        "currency": Config.base_currency(s),
        "currency_type": Currency,
    }


ROUTES: base.Routes = {
    "/settings": (page, ["GET"]),
    "/h/settings/edit": (edit, ["PATCH"]),
}
