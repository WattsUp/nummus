"""Base web controller functions."""

from __future__ import annotations

import re
import textwrap
from collections.abc import Callable

import flask

from nummus import exceptions as exc
from nummus import models, web
from nummus.web.utils import HTTP_CODE_OK, HTTP_CODE_REDIRECT

Routes = dict[str, tuple[Callable, list[str]]]


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
    p = web.portfolio

    # list[(group label, subpages {label: (icon name, endpoint, link type)})]
    nav_items: list[tuple[str, dict[str, tuple[str, str, LinkType] | None]]] = [
        (
            "",
            {
                "Home": ("home", "common.page_dashboard", LinkType.PAGE),
                "Budget": ("wallet", "budgeting.page", LinkType.PAGE),
                # TODO (WattsUp): Change to receipt_long and add_receipt_long if
                # request gets fulfilled
                "Transactions": ("note_stack", "transactions.page_all", LinkType.PAGE),
                "Accounts": ("account_balance", "accounts.page_all", LinkType.PAGE),
                "Insights": None,  # search_insights
            },
        ),
        # TODO (WattsUp): Banking section? Where to put spending by tag info?
        (
            "Investing",
            {
                "Assets": ("box", "assets.page_all", LinkType.PAGE),
                "Performance": None,  # ssid_chart
                "Allocation": (
                    "full_stacked_bar_chart",
                    "allocation.page",
                    LinkType.PAGE,
                ),
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
                "Import File": ("upload", "import_file.import_file", LinkType.DIALOG),
                "Update Assets": ("update", "assets.update", LinkType.DIALOG),
                "Health Checks": ("health_metrics", "health.page", LinkType.PAGE),
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
        else:  # pragma: no cover
            # There shouldn't be an empty group
            pass

    return {
        "nav_items": nav_items_filtered,
    }


def dialog_swap(
    content: str | None = None,
    event: str | None = None,
    snackbar: str | None = None,
) -> flask.Response:
    """Create a response to close the dialog and trigger listeners.

    Args:
        content: Content of dialog to swap to, None will close dialog
        event: Event to trigger
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
        response.headers["HX-Trigger"] = event
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

    Returns:
        Whole page or just main body
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


# Difficult to mock, just moves Location to HX-Redirect
def change_redirect_to_htmx(
    response: flask.Response,
) -> flask.Response:  # pragma: no cover
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
        response.headers["HX-Redirect"] = response.headers.pop("Location")
        response.status_code = HTTP_CODE_OK
        # werkzeug redirect doesn't have close tags
        # clear body
        response.data = ""

    return response
