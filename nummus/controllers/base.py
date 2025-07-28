"""Base web controller functions."""

from __future__ import annotations

import datetime
import json
import re
import textwrap
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import flask
from typing_extensions import NamedTuple, TypedDict, TypeVar

from nummus import exceptions as exc
from nummus import utils, web
from nummus.models import (
    Base,
    BaseEnum,
    query_count,
    TransactionCategory,
    TransactionCategoryGroup,
    YIELD_PER,
)

if TYPE_CHECKING:
    import sqlalchemy
    from sqlalchemy import orm

Routes = dict[str, tuple[Callable, list[str]]]


class LinkType(BaseEnum):
    """Header link type."""

    PAGE = 1
    DIALOG = 2
    HX_POST = 3


class Page(NamedTuple):
    """Page specification."""

    icon: str
    endpoint: str
    type_: LinkType


class PageGroup(NamedTuple):
    """Group of pages specification."""

    name: str
    pages: dict[str, Page]


class BaseContext(TypedDict):
    """Base context type."""

    nav_items: list[PageGroup]
    icons: str


class DateLabels(NamedTuple):
    """Date labels tuple."""

    labels: list[str]
    mode: str


class CategoryContext(NamedTuple):
    """Context for a category option."""

    uri: str
    name: str
    emoji_name: str
    group: TransactionCategoryGroup
    asset_linked: bool


CategoryGroups = dict[TransactionCategoryGroup, list[CategoryContext]]

LIMIT_DOWNSAMPLE = 400  # if n_days > LIMIT_DOWNSAMPLE then plot min/avg/max by month
# else plot normally by days

LIMIT_PLOT_YEARS = 400  # if n_days > LIMIT_PLOT_YEARS then plot by years
LIMIT_PLOT_MONTHS = 100  # if n_days > LIMIT_PLOT_MONTHS then plot by months
# else plot normally by days

LIMIT_TICKS_YEARS = 400  # if n_days > LIMIT_TICKS_YEARS then have ticks on the new year
LIMIT_TICKS_MONTHS = 50  # if n_days > LIMIT_TICKS_MONTHS then have ticks on the 1st
LIMIT_TICKS_WEEKS = 20  # if n_days > LIMIT_TICKS_WEEKS then have ticks on Sunday
# else tick each day

HTTP_CODE_OK = 200
HTTP_CODE_REDIRECT = 302
HTTP_CODE_BAD_REQUEST = 400
HTTP_CODE_FORBIDDEN = 403

PERIOD_OPTIONS = {
    "1m": "1M",
    "6m": "6M",
    "ytd": "YTD",
    "1yr": "1Y",
    "max": "MAX",
}

RE_ICONS = re.compile(r"<icon[^>]*>([\w\-]+)</icon>")
TEMPLATES: dict[Path, tuple[int, set[str]]] = {}
PAGES: list[PageGroup] = []


def ctx_base(templates: Path, *, is_encrypted: bool, debug: bool) -> BaseContext:
    """Get the context to build the base page.

    Args:
        templates: Path to templates
        is_encrypted: Portfolio encrypted status
        debug: Flask app debug status

    Returns:
        BaseContext
    """
    if not PAGES:
        nav_items: list[tuple[str, dict[str, Page | None]]] = [
            (
                "",
                {
                    "Home": Page("home", "common.page_dashboard", LinkType.PAGE),
                    "Budget": Page("wallet", "budgeting.page", LinkType.PAGE),
                    # TODO (WattsUp): Change to receipt_long and add_receipt_long if
                    # request gets fulfilled
                    "Transactions": Page(
                        "note_stack",
                        "transactions.page_all",
                        LinkType.PAGE,
                    ),
                    "Accounts": Page(
                        "account_balance",
                        "accounts.page_all",
                        LinkType.PAGE,
                    ),
                    "Insights": None,  # search_insights
                },
            ),
            # TODO (WattsUp): Banking section? Where to put spending by tag info?
            (
                "Investing",
                {
                    "Assets": Page("box", "assets.page_all", LinkType.PAGE),
                    "Performance": None,  # ssid_chart
                    "Allocation": Page(
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
                    "Emergency fund": Page(
                        "emergency",
                        "emergency_fund.page",
                        LinkType.PAGE,
                    ),
                },
            ),
            (
                "Utilities",
                {
                    "Logout": (
                        Page("logout", "auth.logout", LinkType.HX_POST)
                        if is_encrypted
                        else None
                    ),
                    "Categories": Page(
                        "category",
                        "transaction_categories.page",
                        LinkType.PAGE,
                    ),
                    "Import file": Page(
                        "upload",
                        "import_file.import_file",
                        LinkType.DIALOG,
                    ),
                    "Update assets": Page("update", "assets.update", LinkType.DIALOG),
                    "Health checks": Page(
                        "health_metrics",
                        "health.page",
                        LinkType.PAGE,
                    ),
                    "Style test": (
                        Page("style", "common.page_style_test", LinkType.PAGE)
                        if debug
                        else None
                    ),
                },
            ),
        ]

        # Filter out empty subpages
        no_blanks = [
            PageGroup(
                name,
                {page_name: page for page_name, page in pages.items() if page},
            )
            for name, pages in nav_items
        ]
        # Filter out empty groups
        no_blanks = [group for group in no_blanks if group.pages]
        PAGES.extend(no_blanks)

    icons: set[str] = set()

    for group in PAGES:
        icons.update(page.icon for page in group.pages.values())

    if not TEMPLATES:
        TEMPLATES.update(dict.fromkeys(templates.glob("**/*.jinja"), (0, set())))
    for path, (last_modified_ns, path_icons) in TEMPLATES.items():
        mtime_ns = path.stat().st_mtime_ns
        if mtime_ns == last_modified_ns:
            icons.update(path_icons)
            continue
        with path.open("r", encoding="utf-8") as file:
            buf = file.read()
        path_icons_new = set(RE_ICONS.findall(buf))
        icons.update(path_icons_new)
        TEMPLATES[path] = (mtime_ns, path_icons_new)

    return {
        "nav_items": PAGES,
        "icons": ",".join(sorted(icons)),
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
        # Triggering events should reset dialog
        reset_dialog=event is not None,
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
        nav_trigger = "<script>onLoad(nav.update)</script>\n"
        content = flask.render_template(content_template, **context)
        html = html_title + nav_trigger + content
    else:
        p = web.portfolio
        templates = Path(flask.current_app.root_path) / (
            flask.current_app.template_folder or "templates"
        )
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
            **ctx_base(
                templates,
                is_encrypted=p.is_encrypted,
                debug=flask.current_app.debug,
            ),
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
        response.headers["HX-Redirect"] = response.headers.pop("Location")
        response.status_code = HTTP_CODE_OK
        # werkzeug redirect doesn't have close tags
        # clear body
        response.data = ""

    return response


T = TypeVar("T", bound=Base)


def find(s: orm.Session, cls: type[T], uri: str) -> T:
    """Find the matching object by URI.

    Args:
        s: SQL session to search
        cls: Type of object to find
        uri: URI to find

    Returns:
        Object

    Raises:
        BadRequest: If URI is malformed
        NotFound: If object is not found
    """
    try:
        id_ = cls.uri_to_id(uri)
    except (exc.InvalidURIError, exc.WrongURITypeError) as e:
        raise exc.http.BadRequest(str(e)) from e
    try:
        obj = s.query(cls).where(cls.id_ == id_).one()
    except exc.NoResultFound as e:
        msg = f"{cls.__name__} {uri} not found in Portfolio"
        raise exc.http.NotFound(msg) from e
    return obj


def parse_period(period: str) -> tuple[datetime.date | None, datetime.date]:
    """Parse time period from arguments.

    Args:
        period: Name of period

    Returns:
        start, end dates
        start is None for "all"

    Raises:
        BadRequest: If period is unknown
    """
    today = datetime.datetime.now().astimezone().date()
    if period == "1yr":
        start = datetime.date(today.year - 1, today.month, today.day)
    elif period == "ytd":
        start = datetime.date(today.year, 1, 1)
    elif period == "max":
        start = None
    elif m := re.match(r"(\d)m", period):
        n = min(0, -int(m.group(1)))
        start = utils.date_add_months(today, n)
    else:
        msg = f"Unknown period '{period}'"
        raise exc.http.BadRequest(msg)

    return start, today


def date_labels(start_ord: int, end_ord: int) -> DateLabels:
    """Generate date labels and proper date mode.

    Args:
        start_ord: Start date ordinal
        end_ord: End date ordinal

    Returns:
        DateLabels
    """
    dates = utils.range_date(start_ord, end_ord)
    n = len(dates)
    if n > LIMIT_TICKS_YEARS:
        date_mode = "years"
    elif n > LIMIT_TICKS_MONTHS:
        date_mode = "months"
    elif n > LIMIT_TICKS_WEEKS:
        date_mode = "weeks"
    else:
        date_mode = "days"
    return DateLabels([d.isoformat() for d in dates], date_mode)


def ctx_to_json(d: dict[str, object]) -> str:
    """Convert web context to JSON.

    Args:
        d: Object to serialize

    Returns:
        JSON object
    """

    def default(obj: object) -> str | float:
        if isinstance(obj, Decimal):
            return float(round(obj, 2))
        msg = f"Unknown type {type(obj)}"
        raise TypeError(msg)

    return json.dumps(d, default=default, separators=(",", ":"))


def validate_string(
    value: str,
    *,
    is_required: bool = False,
    check_length: bool = True,
    session: orm.Session | None = None,
    no_duplicates: orm.QueryableAttribute | None = None,
    no_duplicate_wheres: list[sqlalchemy.ColumnExpressionArgument] | None = None,
) -> str:
    """Validate a string matches requirements.

    Args:
        value: String to test
        is_required: True will require the value be non-empty
        check_length: True will require value to be MIN_STR_LEN long
        session: SQL session to use for no_duplicates
        no_duplicates: Property to test for duplicate values
        no_duplicate_wheres: Additional where clauses to add to no_duplicates

    Returns:
        Error message or ""
    """
    value = value.strip()
    if not value:
        return "Required" if is_required else ""
    if check_length and len(value) < utils.MIN_STR_LEN:
        # Ticker can be short
        return f"{utils.MIN_STR_LEN} characters required"
    if no_duplicates is None:
        return ""
    return _test_duplicates(
        value,
        session,
        no_duplicates,
        no_duplicate_wheres,
    )


def _test_duplicates(
    value: object,
    session: orm.Session | None,
    no_duplicates: orm.QueryableAttribute,
    no_duplicate_wheres: list[sqlalchemy.ColumnExpressionArgument] | None,
) -> str:
    if session is None:
        msg = "Cannot test no_duplicates without a session"
        raise TypeError(msg)
    query = session.query(no_duplicates.parent).where(
        no_duplicates == value,
        *(no_duplicate_wheres or []),
    )
    n = query_count(query)
    if n != 0:
        return "Must be unique"
    return ""


def validate_date(
    value: str,
    *,
    is_required: bool = False,
    max_future: int | None = utils.DAYS_IN_WEEK,
    session: orm.Session | None = None,
    no_duplicates: orm.QueryableAttribute | None = None,
    no_duplicate_wheres: list[sqlalchemy.ColumnExpressionArgument] | None = None,
) -> str:
    """Validate a date string matches requirements.

    Args:
        value: Date string to test
        is_required: True will require the value be non-empty
        max_future: Maximum number of days date is allowed in the future
        session: SQL session to use for no_duplicates
        no_duplicates: Property to test for duplicate values
        no_duplicate_wheres: Additional where clauses to add to no_duplicates

    Returns:
        Error message or ""
    """
    value = value.strip()
    try:
        date = utils.parse_date(value)
    except ValueError:
        return "Unable to parse"
    if date is None:
        return "Required" if is_required else ""

    if max_future == 0:
        today = datetime.datetime.now().astimezone().date()
        if date > today:
            return "Cannot be in advance"
    elif max_future is not None:
        today = datetime.datetime.now().astimezone().date()
        if date > (today + datetime.timedelta(days=max_future)):
            return f"Only up to {utils.format_days(max_future)} in advance"

    if no_duplicates is None:
        return ""
    return _test_duplicates(
        date.toordinal(),
        session,
        no_duplicates,
        no_duplicate_wheres,
    )


def validate_real(
    value: str,
    *,
    is_required: bool = False,
    is_positive: bool = False,
) -> str:
    """Validate a number string matches requirements.

    Args:
        value: Number string to test
        is_required: True will require the value be non-empty
        is_positive: True will require the value be > 0

    Returns:
        Error message or ""
    """
    value = value.strip()
    if not value:
        return "Required" if is_required else ""
    n = utils.evaluate_real_statement(value)
    if n is None:
        return "Unable to parse"
    if is_positive and n <= 0:
        return "Must be positive"
    return ""


def validate_int(
    value: str,
    *,
    is_required: bool = False,
    is_positive: bool = False,
) -> str:
    """Validate an integer string matches requirements.

    Args:
        value: Number string to test
        is_required: True will require the value be non-empty
        is_positive: True will require the value be > 0

    Returns:
        Error message or ""
    """
    value = value.strip()
    if not value:
        return "Required" if is_required else ""
    try:
        n = int(value)
    except ValueError:
        return "Unable to parse"
    if is_positive and n <= 0:
        return "Must be positive"
    return ""


def parse_date(
    value: str,
    *,
    max_future: int | None = utils.DAYS_IN_WEEK,
) -> datetime.date:
    """Parse a date string.

    Args:
        value: Raw string to parse
        max_future: Maximum number of days date is allowed in the future

    Returns:
        date object

    Raises:
        ValueError: if failed to parse, empty, or in advance
    """
    try:
        date = utils.parse_date(value)
    except ValueError as e:
        msg = "Unable to parse date"
        raise ValueError(msg) from e
    if date is None:
        msg = "Date must not be empty"
        raise ValueError(msg)
    if max_future == 0:
        today = datetime.datetime.now().astimezone().date()
        if date > today:
            msg = "Cannot be in advance"
            raise ValueError(msg)
    elif max_future is not None:
        today = datetime.datetime.now().astimezone().date()
        if date > (today + datetime.timedelta(days=max_future)):
            msg = f"Only up to {utils.format_days(max_future)} in advance"
            raise ValueError(msg)

    return date


def tranaction_category_groups(s: orm.Session) -> CategoryGroups:
    """Get TransactionCategory by groups.

    Args:
        s: SQL session to use

    Returns:
        dict{group: list[CategoryContext]}
    """
    query = (
        s.query(TransactionCategory)
        .with_entities(
            TransactionCategory.id_,
            TransactionCategory.name,
            TransactionCategory.emoji_name,
            TransactionCategory.asset_linked,
            TransactionCategory.group,
        )
        .order_by(TransactionCategory.name)
    )
    category_groups: CategoryGroups = {
        TransactionCategoryGroup.INCOME: [],
        TransactionCategoryGroup.EXPENSE: [],
        TransactionCategoryGroup.TRANSFER: [],
        TransactionCategoryGroup.OTHER: [],
    }
    for t_cat_id, name, emoji_name, asset_linked, group in query.yield_per(YIELD_PER):
        category_groups[group].append(
            CategoryContext(
                TransactionCategory.id_to_uri(t_cat_id),
                name,
                emoji_name,
                group,
                asset_linked,
            ),
        )
    return category_groups
