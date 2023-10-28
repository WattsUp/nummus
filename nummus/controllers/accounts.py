"""Account controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import flask
import sqlalchemy.exc

from nummus import portfolio, web_utils
from nummus.controllers import common
from nummus.models import Account, AccountCategory

if TYPE_CHECKING:
    from nummus import custom_types as t


def edit(uri: str) -> str:
    """GET & POST /h/accounts/a/<uri>/edit.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio
    today = datetime.date.today()

    with p.get_session() as s:
        acct: Account = web_utils.find(s, Account, uri)

        _, values, _ = acct.get_value(today, today)
        v = values[0]

        if flask.request.method == "GET":
            return flask.render_template(
                "accounts/edit.jinja",
                account=ctx_account(acct, v),
            )

        form = flask.request.form
        institution = form["institution"].strip()
        name = form["name"].strip()
        category = form.get("category", type=AccountCategory.parse)
        closed = "closed" in form

        try:
            if closed and v != 0:
                msg = "Cannot close Account with non-zero balance"
                return common.error(msg)

            # Make the changes
            acct.institution = institution
            acct.name = name
            acct.category = category
            acct.closed = closed
            s.commit()
        except (sqlalchemy.exc.IntegrityError, ValueError) as e:
            return common.error(e)

        return common.overlay_swap(event="update-account")


def ctx_account(acct: Account, current_value: t.Real | None = None) -> t.DictAny:
    """Get the context to build the account details.

    Args:
        acct: Account to generate context for
        current_value: Current value to include, None will fetch

    Returns:
        Dictionary HTML context
    """
    today = datetime.date.today()
    if current_value is None:
        _, values, _ = acct.get_value(today, today)
        current_value = values[0]

    return {
        "uri": acct.uri,
        "name": acct.name,
        "institution": acct.institution,
        "category": acct.category,
        "category_type": AccountCategory,
        "value": current_value,
        "closed": acct.closed,
        "updated_days_ago": (today - acct.updated_on).days,
        "opened_days_ago": (today - acct.opened_on).days,
    }


def page(uri: str) -> str:
    """GET /accounts/<uri>.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio

    with p.get_session() as s:
        acct: Account = web_utils.find(s, Account, uri)
        return common.page(
            "accounts/index-content.jinja",
            account=ctx_account(acct),
        )


ROUTES: t.Routes = {
    "/accounts/<path:uri>": (page, ["GET"]),
    "/h/accounts/a/<path:uri>/edit": (edit, ["GET", "POST"]),
}
