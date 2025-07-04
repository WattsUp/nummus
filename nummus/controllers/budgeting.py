"""Budgeting controllers."""

from __future__ import annotations

import datetime
import math
import operator
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import sql

from nummus import exceptions as exc
from nummus import portfolio, utils
from nummus.controllers import common
from nummus.models import (
    BudgetAssignment,
    BudgetGroup,
    query_count,
    Target,
    TargetPeriod,
    TargetType,
    TransactionCategory,
    TransactionCategoryGroup,
    YIELD_PER,
)
from nummus.web import utils as web_utils

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.controllers.base import Routes

PERIOD_OPTIONS = {
    TargetPeriod.ONCE: "Once",
    TargetPeriod.WEEK: "Weekly",
    TargetPeriod.MONTH: "Monthly",
    TargetPeriod.YEAR: "Annually",
}
PERIOD_OPTIONS_REV = {v: k for k, v in PERIOD_OPTIONS.items()}


class _TargetContext(TypedDict):
    """Type definition for target context."""

    target_assigned: Decimal
    total_assigned: Decimal
    to_go: Decimal
    on_track: bool
    next_due_date: datetime.date | str | None

    progress_bars: list[Decimal]
    target: Decimal
    total_target: Decimal
    total_to_go: Decimal

    period: TargetPeriod
    type: TargetType


class _CategoryContext(TypedDict):
    """Type definition for budget category context."""

    position: int | None
    name: str
    emoji_name: str
    uri: str
    assigned: Decimal
    activity: Decimal
    available: Decimal
    # List of bars (width ratio, bg fill ratio, fg fill ratio)
    bars: list[tuple[Decimal, Decimal, Decimal]]
    hidden: bool

    target: _TargetContext | None


class _GroupContext(TypedDict):
    """Type definition for budget group context."""

    position: int
    name: str | None
    uri: str | None
    is_open: bool
    categories: list[_CategoryContext]
    assigned: Decimal
    activity: Decimal
    available: Decimal
    has_error: bool


class _BudgetContext(TypedDict):
    """Type definition for budget context."""

    month: str
    month_next: str | None
    month_prev: str
    assignable: Decimal
    future_assigned: Decimal
    groups: list[_GroupContext]
    n_overspent: int


def page() -> flask.Response:
    """GET /budgeting.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args
    month_str = args.get("month")
    month = (
        utils.start_of_month(datetime.datetime.now().astimezone().date())
        if month_str is None
        else datetime.date.fromisoformat(month_str + "-01")
    )
    sidebar_uri = args.get("sidebar") or None

    with p.begin_session() as s:
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        budget, title = ctx_budget(s, month, categories, assignable, future_assigned)
        sidebar = ctx_sidebar(s, month, categories, future_assigned, sidebar_uri)
    return common.page(
        "budgeting/page.jinja",
        title=title,
        ctx=budget,
        budget_sidebar=sidebar,
    )


def validation() -> flask.Response | str:
    """GET /h/budgeting/validation.

    Returns:
        string HTML response
    """
    args = flask.request.args

    def update_target_desc() -> flask.Response:
        response = flask.make_response()
        response.headers["HX-Trigger"] = "target-desc"
        return response

    if "date" in args:
        return (
            web_utils.validate_date(args["date"], is_required=True, max_future=None)
            or update_target_desc()
        )

    if "amount" in args:
        return (
            web_utils.validate_real(
                args["amount"],
                is_required=True,
                is_positive=True,
            )
            or update_target_desc()
        )

    if "repeat" in args:
        return (
            web_utils.validate_int(
                args["repeat"],
                is_required=True,
                is_positive=True,
            )
            or update_target_desc()
        )

    raise NotImplementedError


def assign(uri: str) -> str:
    """PUT /h/budgeting/c/<path:uri>/assign.

    Args:
        uri: Category URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    month_str = args["month"]
    month = datetime.date.fromisoformat(month_str + "-01")
    month_ord = month.toordinal()

    form = flask.request.form
    amount = utils.evaluate_real_statement(form.get("amount")) or Decimal(0)

    with p.begin_session() as s:
        cat = web_utils.find(s, TransactionCategory, uri)
        group_uri = (
            None
            if cat.budget_group_id is None
            else BudgetGroup.id_to_uri(cat.budget_group_id)
        )
        if amount == 0:
            s.query(BudgetAssignment).where(
                BudgetAssignment.month_ord == month_ord,
                BudgetAssignment.category_id == cat.id_,
            ).delete()
        else:
            a = (
                s.query(BudgetAssignment)
                .where(
                    BudgetAssignment.month_ord == month_ord,
                    BudgetAssignment.category_id == cat.id_,
                )
                .one_or_none()
            )
            if a is None:
                a = BudgetAssignment(
                    month_ord=month_ord,
                    category_id=cat.id_,
                    amount=amount,
                )
                s.add(a)
            else:
                a.amount = amount

        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        budget, _ = ctx_budget(s, month, categories, assignable, future_assigned)
        sidebar_uri = form.get("sidebar") or None
        sidebar = ctx_sidebar(s, month, categories, future_assigned, sidebar_uri)
    return flask.render_template(
        "budgeting/group.jinja",
        ctx=budget,
        group=next(group for group in budget["groups"] if group["uri"] == group_uri),
        budget_sidebar=sidebar,
        include_oob=True,
    )


def move(uri: str) -> str | flask.Response:
    """GET & PUT /h/budgeting/c/<uri>/move.

    Args:
        uri: Category URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    month_str = args["month"]
    month = datetime.date.fromisoformat(month_str + "-01")
    month_ord = month.toordinal()

    with p.begin_session() as s:
        categories, assignable, _ = BudgetAssignment.get_monthly_available(s, month)
        if uri == "income":
            src_cat = None
            src_cat_id = None
            src_available = assignable
        else:
            src_cat = web_utils.find(s, TransactionCategory, uri)
            src_cat_id = src_cat.id_
            _, _, src_available, _ = categories[src_cat_id]

        if flask.request.method == "PUT":
            dest = flask.request.form["destination"]
            if dest == "income":
                dest_cat_id = None
                dest_available = assignable
            else:
                dest_cat_id = TransactionCategory.uri_to_id(dest)
                _, _, dest_available, _ = categories[dest_cat_id]
            if src_available > 0:
                to_move = utils.evaluate_real_statement(
                    flask.request.form.get("amount"),
                )
                if to_move is None:
                    return common.error("Amount to move must not be blank")
            else:
                # Min of the positive number is max of negative
                to_move = max(src_available, -dest_available)

            BudgetAssignment.move(s, month_ord, src_cat_id, dest_cat_id, to_move)

            return common.dialog_swap(
                event="budget",
                snackbar=f"{utils.format_financial(abs(to_move))} reallocated",
            )

        query = (
            s.query(TransactionCategory)
            .with_entities(
                TransactionCategory.id_,
                TransactionCategory.emoji_name,
                TransactionCategory.group,
            )
            .where(
                TransactionCategory.group.not_in(
                    (TransactionCategoryGroup.INCOME, TransactionCategoryGroup.OTHER),
                ),
            )
            .order_by(TransactionCategory.group, TransactionCategory.name)
        )
        options: list[tuple[str, str, Decimal, TransactionCategoryGroup]] = []
        for t_cat_id, name, group in query.yield_per(YIELD_PER):
            t_cat_id: int
            name: str
            group: TransactionCategoryGroup

            t_cat_uri = TransactionCategory.id_to_uri(t_cat_id)
            available = categories[t_cat_id][2]
            if src_available > 0 or available > 0:
                options.append((t_cat_uri, name, available, group))

        if src_cat_id is not None and (src_available > 0 or assignable > 0):
            options.insert(
                0,
                (
                    "income",
                    "Assignable income",
                    assignable,
                    TransactionCategoryGroup.INCOME,
                ),
            )

        month_str = month.isoformat()[:7]
        category = {
            "uri": uri,
            "name": None if src_cat is None else src_cat.emoji_name,
            "available": src_available,
            "month": month_str,
            "options": options,
        }
    return flask.render_template(
        "budgeting/edit-move.jinja",
        category=category,
    )


def reorder() -> str:
    """PUT /h/budgeting/reorder.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    form = flask.request.form
    group_uris = form.getlist("group-uri")
    t_cat_uris = form.getlist("category-uri")
    groups = form.getlist("group")

    with p.begin_session() as s:
        g_positions = {
            BudgetGroup.uri_to_id(g_uri): i for i, g_uri in enumerate(group_uris)
        }

        t_cat_groups: dict[int, int | None] = {}
        t_cat_positions: dict[int, int | None] = {}

        i = 0
        last_group = None
        for t_cat_uri, g_uri in zip(t_cat_uris, groups, strict=True):
            g_id = None if g_uri == "ungrouped" else BudgetGroup.uri_to_id(g_uri)
            if g_uri != last_group:
                i = 0

            t_cat_id = TransactionCategory.uri_to_id(t_cat_uri)
            if g_id is None:
                t_cat_groups[t_cat_id] = None
                t_cat_positions[t_cat_id] = None
            else:
                t_cat_groups[t_cat_id] = g_id
                t_cat_positions[t_cat_id] = i

            i += 1
            last_group = g_uri

        # Set all to None first so swapping can occur without unique violations
        s.query(TransactionCategory).update(
            {
                TransactionCategory.budget_group_id: None,
                TransactionCategory.budget_position: None,
            },
        )

        # Delete any groups
        s.query(BudgetGroup).where(BudgetGroup.id_.not_in(g_positions)).delete()

        if g_positions:
            # Set all to -index first so swapping can occur without unique violations
            s.query(BudgetGroup).update(
                {
                    BudgetGroup.position: sql.case(
                        {g_id: -i - 1 for i, g_id in enumerate(g_positions)},
                        value=BudgetGroup.id_,
                    ),
                },
            )

            # Set new group positions
            s.query(BudgetGroup).update(
                {
                    BudgetGroup.position: sql.case(
                        g_positions,
                        value=BudgetGroup.id_,
                    ),
                },
            )

        if t_cat_positions:
            # Set new category positions
            s.query(TransactionCategory).update(
                {
                    TransactionCategory.budget_group_id: sql.case(
                        t_cat_groups,
                        value=TransactionCategory.id_,
                    ),
                    TransactionCategory.budget_position: sql.case(
                        t_cat_positions,
                        value=TransactionCategory.id_,
                    ),
                },
            )

    # No response expected, actual moving done in JS
    return ""


def group(uri: str) -> str:
    """PUT /h/budgeting/g/<path:uri>.

    Returns:
        string HTML response

    Raises:
        BadRequest: If ungrouped is renamed
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    form = flask.request.form
    name = form.get("name")
    if name is None:
        # sending open state
        is_open = "open" in form
        groups_open: list[str] = flask.session.get("groups_open", [])
        groups_open = [x for x in groups_open if x != uri]
        if is_open:
            groups_open.append(uri)
        flask.session["groups_open"] = groups_open
    elif uri != "ungrouped":
        try:
            with p.begin_session() as s:
                g = web_utils.find(s, BudgetGroup, uri)
                g.name = name
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)
    else:
        msg = "Cannot rename ungrouped"
        raise exc.http.BadRequest(msg)

    # No response expected, actual opening done in JS
    return ""


def new_group() -> str:
    """POST /h/budgeting/group.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    name = "New Group"
    with p.begin_session() as s:
        # Ensure the name isn't a duplicate
        i = 1
        n = query_count(s.query(BudgetGroup).where(BudgetGroup.name == name))
        while n != 0:
            i += 1
            name = f"New Group {i}"
            n = query_count(s.query(BudgetGroup).where(BudgetGroup.name == name))

        # Move existing groups down one
        n = query_count(s.query(BudgetGroup))
        for i in range(n, -1, -1):
            # Do one at a time in reverse order to prevent duplicate value
            s.query(BudgetGroup).where(BudgetGroup.position == i).update(
                {BudgetGroup.position: i + 1},
            )

        g = BudgetGroup(name=name, position=0)
        s.add(g)
        s.flush()
        g_uri = g.uri
    ctx: _GroupContext = {
        "position": 0,
        "name": name,
        "uri": g_uri,
        "is_open": False,
        "assigned": Decimal(0),
        "activity": Decimal(0),
        "available": Decimal(0),
        "categories": [],
        "has_error": False,
    }
    return flask.render_template_string(
        """\
        <div
            id="group-{{ group.uri or "ungrouped" }}"
            class="budget-group"
        >
            {% include "budgeting/group.jinja" %}
        </div>
        """,
        group=ctx,
    )


def target(uri: str) -> str | flask.Response:
    """GET, POST, PUT, DELETE /h/budgeting/t/<path:uri>.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args if flask.request.method == "GET" else flask.request.form
    today = datetime.datetime.now().astimezone().date()

    with p.begin_session() as s:
        try:
            tar = web_utils.find(s, Target, uri)
            t_cat_id = tar.category_id
        except exc.http.BadRequest:
            t_cat_id = TransactionCategory.uri_to_id(uri)
            tar = s.query(Target).where(Target.category_id == t_cat_id).one_or_none()

        emoji_name = (
            s.query(TransactionCategory.emoji_name)
            .where(TransactionCategory.id_ == t_cat_id)
            .one()[0]
        )

        new_target = tar is None
        if tar is None:
            # New target
            tar = Target(
                category_id=t_cat_id,
                amount=0,
                type_=TargetType.ACCUMULATE,
                period=TargetPeriod.MONTH,
                due_date_ord=today.toordinal(),
                repeat_every=1,
            )
        elif flask.request.method == "DELETE":
            s.delete(tar)
            return common.dialog_swap(event="budget")
        elif flask.request.method == "POST":
            error = "Cannot have multiple targets per category"
            return common.error(error)

        # TODO (WattsUp): Move edit logic out

        # Parse form
        parse_target_form(tar)

        if flask.request.method == "PUT":
            return common.dialog_swap(event="budget")
        try:
            if flask.request.method == "POST":
                with s.begin_nested():
                    s.add(tar)
                return common.dialog_swap(event="budget")
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        # Create context
        due_date = (
            None
            if tar.due_date_ord is None
            else datetime.date.fromordinal(tar.due_date_ord)
        )
        ctx = {
            "uri": uri,
            "new": new_target,
            "category": emoji_name,
            "type": tar.type_,
            "period": tar.period,
            "period_options": PERIOD_OPTIONS,
            "repeat_every": tar.repeat_every,
            "due_date": due_date,
            "due_date_weekday": None if due_date is None else due_date.weekday(),
            "due_date_month": None if due_date is None else due_date.month,
            "due_date_year": None if due_date is None else due_date.year,
            "amount": tar.amount,
            "weekdays": utils.WEEKDAYS,
            "months": utils.MONTHS,
            "from_amount": (
                flask.request.headers.get("HX-Trigger") == "budgeting-amount"
            ),
        }
        # Don't make the changes
        s.rollback()

        return flask.render_template(
            (
                "budgeting/target-desc.jinja"
                if "desc" in args
                else "budgeting/target.jinja"
            ),
            target=ctx,
        )


def parse_target_form(target: Target) -> None:
    """Parse edit target form and modify target.

    Args:
        target: Target to modify
    """
    args = flask.request.args if flask.request.method == "GET" else flask.request.form
    today = datetime.datetime.now().astimezone().date()

    period = args.get("period")
    if period is not None:
        target.period = PERIOD_OPTIONS_REV[period]

    due = args.get("due") or None
    if "change" in args:
        due = "0" if target.period == TargetPeriod.WEEK else today.isoformat()

    amount = utils.evaluate_real_statement(args.get("amount"))
    target.amount = amount or target.amount

    tar_type = args.get("type", type=TargetType)
    target.type_ = tar_type or target.type_

    repeat_every = args.get("repeat", type=int)
    target.repeat_every = repeat_every or max(1, target.repeat_every)

    if due is not None:
        # due is day of week, get a date that works
        due_date = (
            today
            + datetime.timedelta(
                days=int(due) - today.weekday(),
            )
            if target.period == TargetPeriod.WEEK
            else datetime.date.fromisoformat(due)
        )
        target.due_date_ord = due_date.toordinal()
    elif target.period == TargetPeriod.ONCE:
        has_due_date = args.get("has-due")
        if has_due_date == "on":
            due_month = args.get("due-month", type=int)
            due_year = args.get("due-year", type=int)
            due_date = (
                datetime.date(due_year, due_month, 1)
                if due_month is not None and due_year is not None
                else today
            )
            target.due_date_ord = due_date.toordinal()
        elif has_due_date == "off":
            target.due_date_ord = None

    if target.period == TargetPeriod.ONCE:
        target.repeat_every = 0
        target.type_ = TargetType.BALANCE
    elif target.period == TargetPeriod.WEEK:
        target.repeat_every = 1


def ctx_sidebar(
    s: orm.Session,
    month: datetime.date,
    categories: dict[int, tuple[Decimal, Decimal, Decimal, Decimal]],
    future_assigned: Decimal,
    uri: str | None,
) -> dict[str, object]:
    """Get the context to build the budgeting sidebar.

    Args:
        s: SQL session to use
        month: Month of table
        categories: Dict of categories from Budget.get_monthly_available
        future_assigned: Assigned amount in the future from Budget.get_monthly_available
        uri: Category URI to build context for, None for totals

    Returns:
        Dictionary HTML context
    """
    month_str = month.isoformat()[:7]
    if uri is None:
        total_available = Decimal(0)
        total_to_go = Decimal(0)
        total_leftover = Decimal(0)
        total_assigned = Decimal(0)
        total_activity = Decimal(0)

        query = s.query(TransactionCategory.id_).where(
            TransactionCategory.group == TransactionCategoryGroup.INCOME,
        )
        income_ids = {row[0] for row in query.all()}

        targets: dict[int, Target] = {
            t.category_id: t for t in s.query(Target).yield_per(YIELD_PER)
        }
        no_target: set[int] = set()

        for t_cat_id, item in categories.items():
            if t_cat_id in income_ids:
                continue
            assigned, activity, available, leftover = item
            total_assigned += assigned
            total_activity += activity
            total_available += available
            total_leftover += leftover

            tar = targets.get(t_cat_id)
            if tar is None:
                no_target.add(t_cat_id)
            else:
                target_ctx = ctx_target(
                    tar,
                    month,
                    assigned,
                    available,
                    leftover,
                )
                total_to_go += target_ctx["to_go"]

        query = (
            s.query(TransactionCategory)
            .with_entities(
                TransactionCategory.id_,
                TransactionCategory.emoji_name,
            )
            .where(TransactionCategory.id_.in_(no_target))
            .order_by(TransactionCategory.name)
        )
        no_target_names = {
            TransactionCategory.id_to_uri(t_cat_id): name
            for t_cat_id, name in query.all()
        }

        return {
            "uri": None,
            "name": None,
            "month": month_str,
            "available": total_available,
            "leftover": total_leftover,
            "assigned": total_assigned,
            "future_assigned": future_assigned,
            "activity": total_activity,
            "to_go": total_to_go,
            "no_target": no_target_names,
            "target": None,
        }
    t_cat = web_utils.find(s, TransactionCategory, uri)
    t_cat_id = t_cat.id_
    assigned, activity, available, leftover = categories[t_cat_id]

    tar = s.query(Target).where(Target.category_id == t_cat_id).one_or_none()
    if tar is None:
        return {
            "uri": uri,
            "name": t_cat.emoji_name,
            "month": month_str,
            "available": available,
            "leftover": leftover,
            "assigned": assigned,
            "future_assigned": Decimal(0),
            "activity": activity,
            "target": None,
        }
    target_ctx = ctx_target(
        tar,
        month,
        assigned,
        available,
        leftover,
    )

    return {
        "uri": uri,
        "name": t_cat.emoji_name,
        "month": month_str,
        "available": available,
        "leftover": leftover,
        "assigned": assigned,
        "future_assigned": Decimal(0),
        "activity": activity,
        "target": target_ctx,
    }


def sidebar() -> flask.Response:
    """GET /h/budgeting/sidebar.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args
    month_str = args.get("month")
    month = (
        utils.start_of_month(datetime.datetime.now().astimezone().date())
        if month_str is None
        else datetime.date.fromisoformat(month_str + "-01")
    )
    uri = args.get("uri")

    with p.begin_session() as s:
        categories, _, future_assigned = BudgetAssignment.get_monthly_available(
            s,
            month,
        )
        sidebar = ctx_sidebar(s, month, categories, future_assigned, uri)
        html = flask.render_template(
            "budgeting/sidebar.jinja",
            ctx={"month": month_str},
            budget_sidebar=sidebar,
        )
    response = flask.make_response(html)
    response.headers["HX-Push-Url"] = flask.url_for(
        "budgeting.page",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        month=month.isoformat()[:7],
        sidebar=uri,
    )
    return response


def ctx_target(
    tar: Target,
    month: datetime.date,
    assigned: Decimal,
    available: Decimal,
    leftover: Decimal,
) -> _TargetContext:
    """Get monthly context for target.

    Args:
        tar: Target to get context for
        month: Month to check progress during
        assigned: Amount assigned this month
        available: Available balance this month
        leftover: Category leftover balance from previous month

    Returns:
        TargetContext
    """
    if tar.due_date_ord is None:
        # No due date, easy to figure out progress
        # This is a BALANCE target
        target_assigned = tar.amount - leftover
        to_go = tar.amount - available
        return {
            "target_assigned": target_assigned,
            "total_assigned": available,
            "to_go": to_go,
            "on_track": to_go <= 0,
            "next_due_date": None,
            "progress_bars": [tar.amount],
            "target": tar.amount,
            "total_target": tar.amount,
            "total_to_go": max(Decimal(0), to_go),
            "period": tar.period,
            "type": tar.type_,
        }

    due_date = datetime.date.fromordinal(tar.due_date_ord)
    if tar.period == TargetPeriod.WEEK:
        # Need the number of weekdays that fall in this month
        weekday = due_date.weekday()
        n_weekdays = utils.weekdays_in_month(weekday, month)
        total_target = n_weekdays * tar.amount
        target_assigned = total_target
        total_assigned = assigned
        progress_bars = [leftover] + [tar.amount] * n_weekdays
        if tar.type_ == TargetType.REFILL or leftover == 0:
            # Adjust leftover to/from everything
            target_assigned -= leftover
            total_assigned += leftover
            progress_bars.pop(0)
        total_to_go = total_target - total_assigned

        on_track = assigned >= target_assigned
        next_due_date = datetime.datetime.now().astimezone().date()
        if month.year == next_due_date.year and month.month == next_due_date.month:
            # Move next_due_date to next weekday
            n_days = weekday - next_due_date.weekday()
            # Keep positive
            next_due_date += datetime.timedelta(
                days=n_days + (utils.DAYS_IN_WEEK if n_days < 0 else 0),
            )
            n_weeks_elapsed = math.ceil(next_due_date.day / utils.DAYS_IN_WEEK)
            on_track = assigned >= (tar.amount * n_weeks_elapsed)

        return {
            "target_assigned": target_assigned,
            "total_assigned": total_assigned,
            "to_go": target_assigned - assigned,
            "on_track": on_track,
            "next_due_date": utils.WEEKDAYS[weekday],
            "progress_bars": progress_bars,
            "target": tar.amount,
            "total_target": total_target,
            "total_to_go": max(Decimal(0), total_to_go),
            "period": tar.period,
            "type": tar.type_,
        }

    if tar.period == TargetPeriod.ONCE:
        # This is a BALANCE target
        n_months = max(0, utils.date_months_between(month, due_date))
        target_assigned = (tar.amount - leftover) / (n_months + 1)
        target_available = leftover + target_assigned
        total_to_go = tar.amount - available
        return {
            "target_assigned": target_assigned,
            "total_assigned": available,
            "to_go": target_available - available,
            "on_track": available >= target_available,
            "next_due_date": f"{due_date:%B %Y}",
            "progress_bars": [tar.amount],
            "target": tar.amount,
            "total_target": tar.amount,
            "total_to_go": max(Decimal(0), total_to_go),
            "period": tar.period,
            "type": tar.type_,
        }

    # Move due_date into month
    n = utils.date_months_between(due_date, month)
    n_months_every = (
        tar.repeat_every if tar.period == TargetPeriod.MONTH else tar.repeat_every * 12
    )
    n = math.ceil(n / n_months_every) * n_months_every
    due_date = utils.date_add_months(due_date, n)
    last_due_date = utils.date_add_months(due_date, -n_months_every)
    last_repeat_last_month = utils.date_months_between(last_due_date, month) == 1

    # If ACCUMULATE and last repeat ended last month, ignore balance
    target_assigned = tar.amount
    total_assigned = assigned
    progress_bars = [leftover, tar.amount]
    if tar.type_ == TargetType.REFILL or not last_repeat_last_month or leftover == 0:
        # Adjust leftover to/from everything
        target_assigned -= leftover
        total_assigned += leftover
        progress_bars.pop(0)
    total_to_go = tar.amount - total_assigned

    n_months = utils.date_months_between(month, due_date)
    target_assigned /= n_months + 1

    return {
        "target_assigned": target_assigned,
        "total_assigned": total_assigned,
        "to_go": target_assigned - assigned,
        "on_track": assigned >= target_assigned,
        "next_due_date": due_date,
        "progress_bars": progress_bars,
        "target": tar.amount,
        "total_target": tar.amount,
        "total_to_go": max(Decimal(0), total_to_go),
        "period": tar.period,
        "type": tar.type_,
    }


def ctx_budget(
    s: orm.Session,
    month: datetime.date,
    categories: dict[int, tuple[Decimal, Decimal, Decimal, Decimal]],
    assignable: Decimal,
    future_assigned: Decimal,
) -> tuple[_BudgetContext, str]:
    """Get the context to build the budgeting table.

    Args:
        s: SQL session to use
        month: Month of table
        categories: Dict of categories from Budget.get_monthly_available
        assignable: Assignable amount from Budget.get_monthly_available
        future_assigned: Assigned amount in the future from Budget.get_monthly_available

    Returns:
        Dictionary HTML context
    """
    n_overspent = 0

    targets: dict[int, Target] = {
        t.category_id: t for t in s.query(Target).yield_per(YIELD_PER)
    }

    groups_open: list[str] = flask.session.get("groups_open", [])

    groups: dict[int | None, _GroupContext] = {}
    query = s.query(BudgetGroup)
    for g in query.all():
        groups[g.id_] = {
            "position": g.position,
            "name": g.name,
            "uri": g.uri,
            "is_open": g.uri in groups_open,
            "assigned": Decimal(0),
            "activity": Decimal(0),
            "available": Decimal(0),
            "categories": [],
            "has_error": False,
        }
    ungrouped: _GroupContext = {
        "position": -1,
        "name": None,
        "uri": None,
        "is_open": "ungrouped" in groups_open,
        "assigned": Decimal(0),
        "activity": Decimal(0),
        "available": Decimal(0),
        "categories": [],
        "has_error": False,
    }

    query = s.query(TransactionCategory)
    for t_cat in query.yield_per(YIELD_PER):
        assigned, activity, available, leftover = categories[t_cat.id_]
        tar = targets.get(t_cat.id_)
        # Skip category if all numbers are 0 and not grouped
        hidden = (
            t_cat.budget_group_id is None
            and activity == 0
            and assigned == 0
            and available == 0
            and tar is None
        )
        if t_cat.group == TransactionCategoryGroup.INCOME:
            continue

        if available < 0:
            n_overspent += 1

        if tar is None:
            bar_dollars = [max(available, Decimal(0)) - activity]
            target_ctx = None
        else:
            target_ctx = ctx_target(
                tar,
                month,
                assigned,
                available,
                leftover,
            )
            bar_dollars = target_ctx["progress_bars"]

        cat_ctx: _CategoryContext = {
            "position": t_cat.budget_position,
            "uri": t_cat.uri,
            "name": t_cat.name,
            "emoji_name": t_cat.emoji_name,
            "assigned": assigned,
            "activity": activity,
            "available": available,
            "hidden": hidden,
            "bars": ctx_progress_bars(available, activity, bar_dollars),
            "target": target_ctx,
        }
        g = groups.get(t_cat.budget_group_id, ungrouped)
        g["assigned"] += assigned
        g["activity"] += activity
        g["available"] += available
        g["categories"].append(cat_ctx)
        if available < 0:
            g["has_error"] = True

    groups_list = sorted(groups.values(), key=operator.itemgetter("position"))
    groups_list.append(ungrouped)

    for g in groups_list:
        g["categories"] = sorted(
            g["categories"],
            key=lambda item: (item["position"] or 0, item["name"]),
        )

    month_str = month.isoformat()[:7]
    title = f"Budgeting { month_str}"
    today = datetime.datetime.now().astimezone().date()
    month_next = (
        None if month > today else utils.date_add_months(month, 1).isoformat()[:7]
    )
    return {
        "month": month_str,
        "month_next": month_next,
        "month_prev": utils.date_add_months(month, -1).isoformat()[:7],
        "assignable": assignable,
        "future_assigned": future_assigned,
        "groups": groups_list,
        "n_overspent": n_overspent,
    }, title


def ctx_progress_bars(
    available: Decimal,
    activity: Decimal,
    bar_dollars: list[Decimal],
) -> list[tuple[Decimal, Decimal, Decimal]]:
    """Create the budget progress bars.

    Args:
        available: Money available to spend
        activity: Money spent this month
        bar_dollars: List of targets for this month

    Returns:
        list[(
            bar width, [0, 1]
            background fill width, [0, 1]
            foreground fill width, [0, 1]
        )
    """
    bar_dollars_sum = sum(bar_dollars)
    bars: list[tuple[Decimal, Decimal, Decimal]] = []
    bar_start = Decimal(0)
    total_assigned = available - activity
    max_bar_dollars = max(total_assigned, -activity)
    if max_bar_dollars > bar_dollars_sum:
        bar_dollars[-1] += max_bar_dollars - bar_dollars_sum
        bar_dollars_sum = max_bar_dollars
    for v in bar_dollars:
        bar_w = Decimal(1) if bar_dollars_sum == 0 else v / bar_dollars_sum

        if v == 0:
            bg_fill_w = Decimal(0)
            fg_fill_w = Decimal(0)
        elif available < 0:
            bg_fill_w = utils.clamp((-activity - bar_start) / v)
            fg_fill_w = utils.clamp((total_assigned - bar_start) / v)
        else:
            bg_fill_w = utils.clamp((total_assigned - bar_start) / v)
            fg_fill_w = utils.clamp((-activity - bar_start) / v)

        bars.append((bar_w, bg_fill_w, fg_fill_w))
        bar_start += v
    return bars


ROUTES: Routes = {
    "/budgeting": (page, ["GET"]),
    "/h/budgeting/validation": (validation, ["GET"]),
    "/h/budgeting/c/<path:uri>/assign": (assign, ["PUT"]),
    "/h/budgeting/c/<path:uri>/move": (move, ["GET", "PUT"]),
    "/h/budgeting/reorder": (reorder, ["PUT"]),
    "/h/budgeting/g/<path:uri>": (group, ["PUT"]),
    "/h/budgeting/new-group": (new_group, ["POST"]),
    "/h/budgeting/t/<path:uri>": (target, ["GET", "POST", "PUT", "DELETE"]),
    "/h/budgeting/sidebar": (sidebar, ["GET"]),
}
