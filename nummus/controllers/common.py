"""Common component controllers."""

import datetime
import re
from decimal import Decimal

import flask
import sqlalchemy
import sqlalchemy.exc

from nummus import custom_types as t
from nummus import portfolio
from nummus.models import Account, AccountCategory, Transaction


def sidebar() -> str:
    """GET /h/sidebar.

    Returns:
        HTML string response
    """
    include_closed = flask.request.args.get("closed") == "included"
    return flask.render_template(
        "shared/sidebar.html",
        sidebar=ctx_sidebar(include_closed),
    )


def ctx_sidebar(include_closed: bool = False) -> t.DictAny:
    """Get the context to build the sidebar.

    Args:
        include_closed: True will include Accounts marked closed, False will exclude

    Returns:
        Dictionary HTML context
    """
    # Create sidebar context
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio
    today = datetime.date.today()

    assets = Decimal(0)
    liabilities = Decimal(0)

    sorted_categories: t.List[AccountCategory] = [
        AccountCategory.CASH,
        AccountCategory.CREDIT,
        AccountCategory.INVESTMENT,
        AccountCategory.MORTGAGE,
        AccountCategory.LOAN,
        AccountCategory.FIXED,
        AccountCategory.OTHER,
    ]

    categories_total: t.Dict[AccountCategory, t.Real] = {
        cat: Decimal(0) for cat in sorted_categories
    }
    categories: t.Dict[AccountCategory, t.List[t.DictAny]] = {
        cat: [] for cat in sorted_categories
    }

    n_closed = 0
    with p.get_session() as s:
        # Get basic info
        accounts: t.Dict[int, t.DictAny] = {}
        query = s.query(Account)
        query = query.with_entities(
            Account.id,
            Account.uuid,
            Account.name,
            Account.institution,
            Account.category,
            Account.closed,
        )
        for acct_id, acct_uuid, name, institution, category, closed in query.all():
            acct_id: int
            acct_uuid: str
            name: str
            institution: str
            category: AccountCategory
            closed: bool
            accounts[acct_id] = {
                "uuid": acct_uuid,
                "name": name,
                "institution": institution,
                "category": category,
                "closed": closed,
            }
            if closed:
                n_closed += 1

        # Get updated_on
        query = s.query(Transaction)
        query = query.with_entities(
            Transaction.account_id,
            sqlalchemy.func.max(Transaction.date),  # pylint: disable=not-callable
        )
        query = query.group_by(Transaction.account_id)
        for acct_id, updated_on in query.all():
            acct_id: int
            updated_on: datetime.date
            accounts[acct_id]["updated_days_ago"] = (today - updated_on).days

        # Get all Account values
        _, acct_values = Account.get_value_all(s, today, today)
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

    # TODO (WattsUp) Add account UUIDs for links
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


def empty() -> str:
    """GET /h/empty.

    Returns:
        HTML string response
    """
    return ""


def overlay_swap(
    content: t.Optional[str] = None,
    event: t.Optional[t.Union[str, t.Strings]] = None,
) -> flask.Response:
    """Create a response to close the overlay and trigger listeners.

    Args:
        content: Content of overlay to swap to, None will close overlay
        event: Event or list of events to trigger

    Returns:
        Response that updates overlay OOB and triggers events
    """
    html = flask.render_template("shared/overlay.html", oob=True, content=content or "")
    response = flask.make_response(html)
    if event:
        if isinstance(event, str):
            response.headers["HX-Trigger"] = event
        else:
            response.headers["HX-Trigger"] = ",".join(event)
    return response


def error(e: t.Union[str, Exception]) -> str:
    """Convert exception into an readable error string.

    Args:
        e: Exception to parse

    Returns:
        HTML string response
    """
    if isinstance(e, sqlalchemy.exc.IntegrityError):
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
                msg = (
                    f"{table} {field} must "
                    f"{constraints.get(constraint, 'be ' + constraint)}"
                )
        else:  # pragma: no cover
            # Don't need to test fallback
            msg = orig
        return flask.render_template("shared/error.html", error=msg)

    # Default return exception's string
    return flask.render_template("shared/error.html", error=str(e))


ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/h/sidebar": (sidebar, ["GET"]),
    "/h/empty": (empty, ["GET"]),
}
