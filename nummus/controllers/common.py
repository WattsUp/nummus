"""Common component controllers."""

from __future__ import annotations

import datetime
import re
import textwrap
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func

from nummus import exceptions as exc
from nummus import models
from nummus.models import Account, AccountCategory, Transaction
from nummus.web_utils import HTTP_CODE_OK, HTTP_CODE_REDIRECT

if TYPE_CHECKING:
    from nummus import portfolio
    from nummus.controllers.base import Routes


def sidebar() -> str:
    """GET /h/sidebar.

    Returns:
        HTML string response
    """
    args = flask.request.args
    include_closed = args.get("closed") == "included"
    is_open = "open" in args
    return flask.render_template(
        "shared/sidebar.jinja",
        sidebar=ctx_sidebar(include_closed=include_closed),
        is_open=is_open,
    )


def ctx_sidebar(*, include_closed: bool = False) -> dict[str, object]:
    """Get the context to build the sidebar.

    Args:
        include_closed: True will include Accounts marked closed, False will exclude

    Returns:
        Dictionary HTML context
    """
    # Create sidebar context
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
    today = datetime.date.today()
    today_ord = today.toordinal()

    assets = Decimal(0)
    liabilities = Decimal(0)

    sorted_categories: list[AccountCategory] = [
        AccountCategory.CASH,
        AccountCategory.CREDIT,
        AccountCategory.INVESTMENT,
        AccountCategory.MORTGAGE,
        AccountCategory.LOAN,
        AccountCategory.FIXED,
        AccountCategory.OTHER,
    ]

    class AccountContext(TypedDict):
        """Type definition for Account context."""

        uri: str | None
        name: str
        institution: str
        category: AccountCategory
        closed: bool
        updated_days_ago: int
        value: Decimal

    categories_total: dict[AccountCategory, Decimal] = {
        cat: Decimal(0) for cat in sorted_categories
    }
    categories: dict[AccountCategory, list[AccountContext]] = {
        cat: [] for cat in sorted_categories
    }

    n_closed = 0
    with p.begin_session() as s:
        # Get basic info
        accounts: dict[int, AccountContext] = {}
        query = s.query(Account).with_entities(
            Account.id_,
            Account.name,
            Account.institution,
            Account.category,
            Account.closed,
        )
        for acct_id, name, institution, category, closed in query.all():
            acct_id: int
            name: str
            institution: str
            category: AccountCategory
            closed: bool
            accounts[acct_id] = {
                "uri": Account.id_to_uri(acct_id),
                "name": name,
                "institution": institution,
                "category": category,
                "closed": closed,
                "updated_days_ago": 0,
                "value": Decimal(0),
            }
            if closed:
                n_closed += 1

        # Get updated_on
        query = (
            s.query(Transaction)
            .with_entities(
                Transaction.account_id,
                func.max(Transaction.date_ord),
            )
            .group_by(Transaction.account_id)
        )
        for acct_id, updated_on_ord in query.all():
            acct_id: int
            updated_on_ord: int
            accounts[acct_id]["updated_days_ago"] = today_ord - updated_on_ord

        # Get all Account values
        acct_values, _, _ = Account.get_value_all(s, today_ord, today_ord)
        for acct_id, values in acct_values.items():
            acct_dict = accounts[acct_id]
            v = values[0]
            if v > 0:
                assets += v
            else:
                liabilities += v
            acct_dict["value"] = v
            category = acct_dict["category"]

            categories_total[category] += v
            categories[category].append(acct_dict)

    bar_total = assets - liabilities
    if bar_total == 0:
        asset_width = 0
        liabilities_width = 0
    else:
        asset_width = round(assets / (assets - liabilities) * 100, 2)
        liabilities_width = 100 - asset_width

    if not include_closed:
        categories = {
            cat: [acct for acct in accounts if not acct["closed"]]
            for cat, accounts in categories.items()
        }

    # Removed empty categories and sort
    categories = {
        cat: sorted(accounts, key=lambda acct: acct["name"])
        for cat, accounts in categories.items()
        if len(accounts) > 0
    }

    return {
        "net-worth": assets + liabilities,
        "assets": assets,
        "liabilities": liabilities,
        "assets-w": asset_width,
        "liabilities-w": liabilities_width,
        "categories": {
            cat: (categories_total[cat], accounts)
            for cat, accounts in categories.items()
        },
        "include_closed": include_closed,
        "n_closed": n_closed,
    }


class LinkType(models.BaseEnum):
    """Header link type."""

    PAGE = 1
    OVERLAY = 2
    HX_POST = 3


def ctx_base() -> dict[str, object]:
    """Get the context to build the base page.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    pages: dict[str, dict[str, None | tuple[str, LinkType]]] = {
        "Overview": {
            "Dashboard": ("dashboard.page", LinkType.PAGE),
            "Net Worth": ("net_worth.page", LinkType.PAGE),
            "Transactions": ("transactions.page_all", LinkType.PAGE),
            "Asset Transactions": ("assets.page_transactions", LinkType.PAGE),
        },
        "Banking": {
            "Cash Flow": ("cash_flow.page", LinkType.PAGE),
            "Budgeting": ("budgeting.page", LinkType.PAGE),
        },
        "Investing": {
            "Assets": ("assets.page_all", LinkType.PAGE),
            "Asset Transactions": ("assets.page_transactions", LinkType.PAGE),
            "Performance": ("performance.page", LinkType.PAGE),
            "Allocation": ("allocation.page", LinkType.PAGE),
        },
        "Planning": {
            "Future Net Worth": None,
            "Retirement": None,
            "Emergency Fund": ("emergency_fund.page", LinkType.PAGE),
            "Investment": None,
        },
    }
    for section, subpages in pages.items():
        pages[section] = {k: v for k, v in subpages.items() if v}

    menu: dict[str, None | tuple[str, LinkType]] = {
        "Logout": ("auth.logout", LinkType.HX_POST) if p.is_encrypted else None,
        "Edit Transaction Categories": (
            "transaction_categories.overlay",
            LinkType.OVERLAY,
        ),
        "Import File": ("import_file.import_file", LinkType.OVERLAY),
        "Update Asset Valuations": (
            "assets.update",
            LinkType.OVERLAY,
        ),
        "Heath Checks": ("health.page", LinkType.PAGE),
    }
    return {
        "pages": {k: v for k, v in pages.items() if v},
        "menu": {k: v for k, v in menu.items() if v},
    }


def overlay_swap(
    content: str | None = None,
    event: str | list[str] | None = None,
) -> flask.Response:
    """Create a response to close the overlay and trigger listeners.

    Args:
        content: Content of overlay to swap to, None will close overlay
        event: Event or list of events to trigger

    Returns:
        Response that updates overlay OOB and triggers events
    """
    html = flask.render_template(
        "shared/overlay.jinja",
        oob=True,
        content=content or "",
    )
    response = flask.make_response(html)
    if event:
        if isinstance(event, str):
            response.headers["HX-Trigger"] = event
        else:
            response.headers["HX-Trigger"] = ",".join(event)
    return response


def error(e: str | Exception) -> str:
    """Convert exception into an readable error string.

    Args:
        e: Exception to parse

    Returns:
        HTML string response
    """
    if isinstance(e, exc.IntegrityError):
        # Get the line that starts with (...IntegrityError)
        orig = str(e.orig)
        m = re.match(r"([\w ]+) constraint failed: (\w+).(\w+)(.*)", orig)
        if m is not None:
            constraint = m.group(1)
            table = m.group(2).replace("_", " ").capitalize()
            field = m.group(3)
            additional = m.group(4)
            constraints = {
                "UNIQUE": "be unique",
                "NOT NULL": "not be empty",
            }
            if constraint == "CHECK":
                msg = f"{table} {field}{additional}"
            else:
                s = constraints.get(constraint, "be " + constraint)
                msg = f"{table} {field} must {s}"
        else:  # pragma: no cover
            # Don't need to test fallback
            msg = orig
        return flask.render_template("shared/error.jinja", error=msg)

    # Default return exception's string
    return flask.render_template("shared/error.jinja", error=str(e))


def page(content_template: str, title: str, **context: object) -> flask.Response:
    """Render a page with a given content template.

    Args:
        content_template: Path to content template
        title: Title of the page
        context: context passed to render_template
    """
    if flask.request.headers.get("HX-Request", "false") == "true":
        # Send just the content
        html_title = f"<title>{title}</title>\n"
        html = html_title + flask.render_template(content_template, **context)
    else:
        html = flask.render_template_string(
            textwrap.dedent(
                f"""\
                {{% extends "shared/base.jinja" %}}
                {{% block title %}}
                {title}
                {{% endblock title %}}
                {{% block content %}}
                {{% include "{content_template}" %}}
                {{% endblock content %}}
                """,
            ),
            sidebar=ctx_sidebar(),
            base=ctx_base(),
            **context,
        )

    # Create response and add Vary: HX-Request
    # Since the cache needs to cache both
    response = flask.make_response(html)
    response.headers["Vary"] = "HX-Request"
    return response


def change_redirect_to_htmx(response: flask.Response) -> flask.Response:
    """Change redirect responses to HX-Redirect.

    Args:
        response: HTTP response

    Returns:
        Modified HTTP response
    """
    if (
        response.status_code == HTTP_CODE_REDIRECT
        and flask.request.headers.get("HX-Request", "false") == "true"
    ):
        # If a redirect is issued to a HX-Request, send OK and HX-Redirect
        location = response.headers["Location"]
        response.headers["HX-Redirect"] = location
        response.status_code = HTTP_CODE_OK
        # werkzeug redirect doesn't have close tags
        # clear body
        response.data = ""

    return response


ROUTES: Routes = {
    "/h/sidebar": (sidebar, ["GET"]),
}
