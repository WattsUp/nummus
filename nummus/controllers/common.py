"""Common component controllers."""

from __future__ import annotations

import re
import textwrap
from typing import TYPE_CHECKING

import flask

from nummus import exceptions as exc
from nummus import models
from nummus.web_utils import HTTP_CODE_OK, HTTP_CODE_REDIRECT

if TYPE_CHECKING:
    from nummus import portfolio
    from nummus.controllers.base import Routes


class LinkType(models.BaseEnum):
    """Header link type."""

    PAGE = 1
    DIALOG = 2
    HX_POST = 3


def ctx_base() -> dict[str, object]:
    """Get the context to build the base page.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    # list[(group label, subpages {label: (icon name, endpoint, link type)})]
    nav_items: list[tuple[str, dict[str, None | tuple[str, str, LinkType]]]] = [
        (
            "",
            {
                "Home": ("home", "dashboard.page", LinkType.PAGE),
                "Budget": None,  # wallet
                # TODO (WattsUp): Change to receipt_long and add_receipt_long if
                # request gets fulfilled
                "Transactions": ("note_stack", "transactions.page_all", LinkType.PAGE),
                "Accounts": ("account_balance", "accounts.page_all", LinkType.PAGE),
                "Insights": None,  # search_insights
            },
        ),
        (
            "Investing",
            {
                "Assets": ("box", "assets.page_all", LinkType.PAGE),
                "Performance": None,  # ssid_chart
                "Allocation": None,  # full_stacked_bar_chart
            },
        ),
        (
            "Planning",
            {
                "Retirement": None,  # person_play
                "Emergency Fund": ("emergency", "emergency_fund.page", LinkType.PAGE),
            },
        ),
        (
            "Utilities",
            {
                "Logout": (
                    ("logout", "auth.logout", LinkType.HX_POST)
                    if p.is_encrypted
                    else None
                ),
                "Categories": (
                    "category",
                    "transaction_categories.page",
                    LinkType.PAGE,
                ),
                "Import File": None,  # upload
                "Update Assets": None,  # update
                "Health Checks": None,  # health_metrics
                "Style Test": (
                    ("style", "common.page_style_test", LinkType.PAGE)
                    if flask.current_app.debug
                    else None
                ),
            },
        ),
    ]

    nav_items_filtered: list[tuple[str, dict[str, tuple[str, str, LinkType]]]] = []
    for label, subpages in nav_items:
        subpages_filtered = {}
        for sub_label, item in subpages.items():
            if item is None:
                continue
            subpages_filtered[sub_label] = item
        if subpages_filtered:
            nav_items_filtered.append((label, subpages_filtered))

    return {
        "nav_items": nav_items_filtered,
    }


def dialog_swap(
    content: str | None = None,
    event: str | list[str] | None = None,
    snackbar: str | None = None,
) -> flask.Response:
    """Create a response to close the dialog and trigger listeners.

    Args:
        content: Content of dialog to swap to, None will close dialog
        event: Event or list of events to trigger
        snackbar: Snackbar message to display

    Returns:
        Response that updates dialog OOB and triggers events
    """
    html = flask.render_template(
        "shared/dialog.jinja",
        oob=True,
        content=content or "",
        snackbar=snackbar,
        # Triggering events should clear history
        clear_history=event is not None,
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
    icon = "<icon>error</icon>"
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
        return icon + msg

    # Default return exception's string
    return icon + str(e)


def page(content_template: str, title: str, **context: object) -> flask.Response:
    """Render a page with a given content template.

    Args:
        content_template: Path to content template
        title: Title of the page
        context: context passed to render_template
    """
    if flask.request.headers.get("HX-Request", "false") == "true":
        # Send just the content
        html_title = f"<title>{title} - nummus</title>\n"
        nav_trigger = "<script>nav.update()</script>\n"
        content = flask.render_template(content_template, **context)
        html = html_title + nav_trigger + content
    else:
        html = flask.render_template_string(
            textwrap.dedent(
                f"""\
                {{% extends "shared/base.jinja" %}}
                {{% block content %}}
                {{% include "{content_template}" %}}
                {{% endblock content %}}
                """,
            ),
            title=f"{title} - nummus",
            **ctx_base(),
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


def page_style_test() -> flask.Response:
    """GET /style-test.

    Returns:
        string HTML response
    """
    return page(
        "shared/style-test.jinja",
        "Style Test",
    )


ROUTES: Routes = {
    "/d/style-test": (page_style_test, ["GET"]),
}
