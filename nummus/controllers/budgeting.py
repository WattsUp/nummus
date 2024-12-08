"""Budgeting controllers."""

from __future__ import annotations

import datetime
import math
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import sql

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import (
    BudgetAssignment,
    BudgetGroup,
    Target,
    TargetPeriod,
    TargetType,
    TransactionCategory,
    TransactionCategoryGroup,
    YIELD_PER,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.controllers.base import Routes


class TargetContext(TypedDict):
    """Target Monthly Context."""

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


def ctx_target(
    tar: Target,
    month: datetime.date,
    assigned: Decimal,
    available: Decimal,
    leftover: Decimal,
) -> TargetContext:
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
            "on_track": to_go > 0,
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
        next_due_date = datetime.date.today()
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
            "total_to_go": total_to_go,
            "period": tar.period,
            "type": tar.type_,
        }

    if tar.period == TargetPeriod.ONCE:
        # This is a BALANCE target
        n_months = max(0, utils.date_months_between(month, due_date))
        target_assigned = (tar.amount - leftover) / (n_months + 1)
        total_to_go = tar.amount - available
        return {
            "target_assigned": target_assigned,
            "total_assigned": available,
            "to_go": target_assigned - assigned,
            "on_track": assigned >= target_assigned,
            "next_due_date": due_date,
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
    total_assigned = assigned
    progress_bars = [leftover, tar.amount]
    if tar.type_ == TargetType.REFILL or not last_repeat_last_month:
        # Adjust leftover to/from everything
        total_assigned += leftover
        progress_bars.pop(0)
    total_to_go = tar.amount - total_assigned

    n_months = utils.date_months_between(month, due_date)
    target_assigned = tar.amount / (n_months + 1)

    return {
        "target_assigned": target_assigned,
        "total_assigned": total_assigned,
        "to_go": target_assigned - total_assigned,
        "on_track": total_assigned >= target_assigned,
        "next_due_date": due_date,
        "progress_bars": progress_bars,
        "target": tar.amount,
        "total_target": tar.amount,
        "total_to_go": max(Decimal(0), total_to_go),
        "period": tar.period,
        "type": tar.type_,
    }


def ctx_table(
    s: orm.Session,
    month: datetime.date,
    categories: dict[int, tuple[Decimal, Decimal, Decimal, Decimal]],
    assignable: Decimal,
    future_assigned: Decimal,
) -> tuple[dict[str, object], str]:
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

    class CategoryContext(TypedDict):
        """Type definition for budget category context."""

        position: int | None
        name: str
        uri: str
        emoji_name: str
        assigned: Decimal
        activity: Decimal
        available: Decimal
        # List of bars (width ratio, bg fill ratio, fg fill ratio, bg, fg)
        bars: list[tuple[Decimal, Decimal, Decimal, str, str]]

        target: TargetContext | None

    class GroupContext(TypedDict):
        """Type definition for budget group context."""

        position: int
        name: str | None
        uri: str | None
        is_closed: bool
        categories: list[CategoryContext]
        assigned: Decimal
        activity: Decimal
        available: Decimal

    n_overspent = 0

    targets: dict[int, Target] = {
        t.category_id: t for t in s.query(Target).yield_per(YIELD_PER)
    }

    groups_closed: list[str] = flask.session.get("groups_closed", [])

    groups: dict[int | None, GroupContext] = {}
    query = s.query(BudgetGroup)
    for g in query.all():
        groups[g.id_] = {
            "position": g.position,
            "name": g.name,
            "uri": g.uri,
            "is_closed": g.uri in groups_closed,
            "assigned": Decimal(0),
            "activity": Decimal(0),
            "available": Decimal(0),
            "categories": [],
        }
    ungrouped: GroupContext = {
        "position": -1,
        "name": None,
        "uri": None,
        "is_closed": "ungrouped" in groups_closed,
        "assigned": Decimal(0),
        "activity": Decimal(0),
        "available": Decimal(0),
        "categories": [],
    }

    query = s.query(TransactionCategory)
    for t_cat in query.yield_per(YIELD_PER):
        assigned, activity, available, leftover = categories[t_cat.id_]
        tar = targets.get(t_cat.id_)
        # Skip category if all numbers are 0 and not grouped
        if (
            t_cat.budget_group_id is None
            and activity == 0
            and assigned == 0
            and available == 0
            and tar is None
        ):
            continue
        if t_cat.group == TransactionCategoryGroup.INCOME:
            continue

        if available < 0:
            n_overspent += 1

        bar_dollars: list[Decimal] = []
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

        bar_dollars_sum = sum(bar_dollars)
        bars: list[tuple[Decimal, Decimal, Decimal, str, str]] = []
        bar_start = Decimal(0)
        total_assigned = available - activity
        if total_assigned > bar_dollars_sum:
            bar_dollars[-1] += total_assigned - bar_dollars_sum
            bar_dollars_sum = total_assigned
        for v in bar_dollars:
            bar_w = Decimal(1) if bar_dollars_sum == 0 else v / bar_dollars_sum

            fg = "green"
            if v == 0:
                bg = "grey-400"
                bg_fill_w = Decimal(1)
                fg_fill_w = Decimal(0)
            elif available < 0:
                bg = "red"
                fg = "yellow"
                bg_fill_w = utils.clamp((-activity - bar_start) / v)
                fg_fill_w = utils.clamp((total_assigned - bar_start) / v)
            else:
                bg = "green" if total_assigned == bar_dollars_sum else "yellow"
                bg_fill_w = utils.clamp((total_assigned - bar_start) / v)
                fg_fill_w = utils.clamp((-activity - bar_start) / v)

            bars.append((bar_w, bg_fill_w, fg_fill_w, bg, fg))
            bar_start += v

        cat_ctx: CategoryContext = {
            "position": t_cat.budget_position,
            "uri": t_cat.uri,
            "name": t_cat.name,
            "emoji_name": t_cat.emoji_name,
            "assigned": assigned,
            "activity": activity,
            "available": available,
            "bars": bars,
            "target": target_ctx,
        }
        g = groups.get(t_cat.budget_group_id, ungrouped)
        g["assigned"] += assigned
        g["activity"] += activity
        g["available"] += available
        g["categories"].append(cat_ctx)

    groups_list = sorted(groups.values(), key=lambda item: item["position"])
    groups_list.append(ungrouped)

    for g in groups_list:
        g["categories"] = sorted(
            g["categories"],
            key=lambda item: (item["position"] or 0, item["name"]),
        )

    month_str = month.isoformat()[:7]
    title = f"Budgeting { month_str} | nummus"
    return {
        "month": month_str,
        "month_next": utils.date_add_months(month, 1).isoformat()[:7],
        "month_prev": utils.date_add_months(month, -1).isoformat()[:7],
        "assignable": assignable,
        "future_assigned": future_assigned,
        "groups": groups_list,
        "n_overspent": n_overspent,
    }, title


def page() -> str:
    """GET /budgeting.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args
    month_str = args.get("month")
    month = (
        utils.start_of_month(datetime.date.today())
        if month_str is None
        else datetime.date.fromisoformat(month_str + "-01")
    )
    sidebar_uri = args.get("sidebar") or None

    with p.get_session() as s:
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        table, title = ctx_table(s, month, categories, assignable, future_assigned)
        sidebar = ctx_sidebar(s, month, categories, future_assigned, sidebar_uri)
    return common.page(
        "budgeting/index-content.jinja",
        title=title,
        table=table,
        budget_sidebar=sidebar,
    )


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
    amount = utils.parse_real(form.get("amount")) or Decimal(0)

    with p.get_session() as s:
        cat = web_utils.find(s, TransactionCategory, uri)
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
        s.commit()

        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        table, _ = ctx_table(s, month, categories, assignable, future_assigned)
        sidebar_uri = form.get("sidebar") or None
        sidebar = ctx_sidebar(s, month, categories, future_assigned, sidebar_uri)
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
        budget_sidebar=sidebar,
    )


def overspending(uri: str) -> str | flask.Response:
    """GET & PUT /h/budgeting/c/<uri>/overspending.

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

    with p.get_session() as s:
        t_cat: TransactionCategory | None
        t_cat = None if uri == "income" else web_utils.find(s, TransactionCategory, uri)
        categories, assignable, _ = BudgetAssignment.get_monthly_available(s, month)

        if flask.request.method == "PUT":
            if t_cat is None:
                available = assignable
            else:
                _, _, available, _ = categories[t_cat.id_]
            source = flask.request.form["source"]
            if source == "income":
                source_id = None
                source_available = assignable
            else:
                source_id = TransactionCategory.uri_to_id(source)
                _, _, source_available, _ = categories[source_id]
            to_move = min(source_available, -available)

            # Add assignment
            if t_cat is not None:
                a = (
                    s.query(BudgetAssignment)
                    .where(
                        BudgetAssignment.category_id == t_cat.id_,
                        BudgetAssignment.month_ord == month_ord,
                    )
                    .one_or_none()
                )
                if a is None:
                    a = BudgetAssignment(
                        month_ord=month_ord,
                        amount=to_move,
                        category_id=t_cat.id_,
                    )
                    s.add(a)
                else:
                    a.amount += to_move

            if source_id is not None:
                a = (
                    s.query(BudgetAssignment)
                    .where(
                        BudgetAssignment.category_id == source_id,
                        BudgetAssignment.month_ord == month_ord,
                    )
                    .one_or_none()
                )
                if a is None:
                    a = BudgetAssignment(
                        month_ord=month_ord,
                        amount=-to_move,
                        category_id=source_id,
                    )
                    s.add(a)
                elif a.amount == to_move:
                    s.delete(a)
                else:
                    a.amount -= to_move

            s.commit()
            return common.overlay_swap(event="update-budget")

        category_names = TransactionCategory.map_name(s)

        options: list[tuple[str, str, Decimal]] = [
            (
                TransactionCategory.id_to_uri(t_cat_id),
                category_names[t_cat_id],
                available,
            )
            for t_cat_id, (_, _, available, _) in categories.items()
            if available > 0
        ]
        if t_cat is None:
            available = assignable
        else:
            _, _, available, _ = categories[t_cat.id_]
        options = sorted(options, key=lambda x: x[1])
        if assignable > 0:
            options.insert(0, ("income", "Assignable income", assignable))

        month_str = month.isoformat()[:7]
        category = {
            "uri": uri,
            "name": None if t_cat is None else t_cat.emoji_name,
            "available": available,
            "month": month_str,
            "options": options,
        }
    return flask.render_template(
        "budgeting/edit-overspending.jinja",
        category=category,
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

    with p.get_session() as s:
        t_cat: TransactionCategory | None
        t_cat = None if uri == "income" else web_utils.find(s, TransactionCategory, uri)
        categories, assignable, _ = BudgetAssignment.get_monthly_available(s, month)

        if flask.request.method == "PUT":
            if t_cat is None:
                available = assignable
            else:
                _, _, available, _ = categories[t_cat.id_]
            dest = flask.request.form["destination"]
            to_move = utils.parse_real(flask.request.form.get("amount"))
            if to_move is None:
                return common.error("Amount to move must not be blank")

            dest_id = None if dest == "income" else TransactionCategory.uri_to_id(dest)

            # Add assignment
            if t_cat is not None:
                a = (
                    s.query(BudgetAssignment)
                    .where(
                        BudgetAssignment.category_id == t_cat.id_,
                        BudgetAssignment.month_ord == month_ord,
                    )
                    .one_or_none()
                )
                if a is None:
                    a = BudgetAssignment(
                        month_ord=month_ord,
                        amount=-to_move,
                        category_id=t_cat.id_,
                    )
                    s.add(a)
                elif a.amount == to_move:
                    s.delete(a)
                else:
                    a.amount -= to_move

            if dest_id is not None:
                a = (
                    s.query(BudgetAssignment)
                    .where(
                        BudgetAssignment.category_id == dest_id,
                        BudgetAssignment.month_ord == month_ord,
                    )
                    .one_or_none()
                )
                if a is None:
                    a = BudgetAssignment(
                        month_ord=month_ord,
                        amount=to_move,
                        category_id=dest_id,
                    )
                    s.add(a)
                else:
                    a.amount += to_move

            s.commit()
            return common.overlay_swap(event="update-budget")

        category_names = TransactionCategory.map_name(s)

        options: list[tuple[str, str, Decimal]] = [
            (
                TransactionCategory.id_to_uri(t_cat_id),
                category_names[t_cat_id],
                available,
            )
            for t_cat_id, (_, _, available, _) in categories.items()
            if (t_cat is None or t_cat_id != t_cat.id_) and t_cat_id in category_names
        ]
        if t_cat is None:
            available = assignable
        else:
            _, _, available, _ = categories[t_cat.id_]
        options = sorted(options, key=lambda x: (x[2] >= 0, x[1]))
        if t_cat is not None:
            options.insert(0, ("income", "Assignable income", assignable))

        month_str = month.isoformat()[:7]
        category = {
            "uri": uri,
            "name": None if t_cat is None else t_cat.emoji_name,
            "available": available,
            "month": month_str,
            "options": options,
        }
    return flask.render_template(
        "budgeting/edit-move.jinja",
        category=category,
    )


def reorder() -> str:
    """GET & PUT /h/budgeting/reorder.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    form = flask.request.form
    group_uris = form.getlist("group_uri")
    row_uris = form.getlist("row_uri")
    groups = form.getlist("group")

    with p.get_session() as s:
        g_positions = {
            BudgetGroup.uri_to_id(g_uri): i for i, g_uri in enumerate(group_uris)
        }

        t_cat_groups: dict[int, int | None] = {}
        t_cat_positions: dict[int, int | None] = {}

        i = 0
        last_group = None
        for t_cat_uri, g_uri in zip(row_uris, groups, strict=True):
            g_id = None if g_uri == "" else BudgetGroup.uri_to_id(g_uri)
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

        # Set all to -index first so swapping can occur without unique violations
        if len(g_positions) > 0 and len(t_cat_positions) > 0:
            s.query(BudgetGroup).update(
                {
                    BudgetGroup.position: sql.case(
                        {g_id: -i - 1 for i, g_id in enumerate(g_positions)},
                        value=BudgetGroup.id_,
                    ),
                },
            )
            # Set all to None first so swapping can occur without unique violations
            s.query(TransactionCategory).update(
                {
                    TransactionCategory.budget_group_id: None,
                    TransactionCategory.budget_position: None,
                },
            )

            s.query(BudgetGroup).update(
                {
                    BudgetGroup.position: sql.case(
                        g_positions,
                        value=BudgetGroup.id_,
                    ),
                },
            )
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
            s.commit()

        month_str = form.get("month")
        month = (
            utils.start_of_month(datetime.date.today())
            if month_str is None
            else datetime.date.fromisoformat(month_str + "-01")
        )
        sidebar_uri = form.get("sidebar") or None

        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        table, _ = ctx_table(s, month, categories, assignable, future_assigned)
        sidebar = ctx_sidebar(s, month, categories, future_assigned, sidebar_uri)
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
        budget_sidebar=sidebar,
    )


def group(uri: str) -> str:
    """PUT /h/budgeting/g/<path:uri>.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    form = flask.request.form
    if flask.request.method == "PUT":
        closed = "closed" in form
        if uri != "ungrouped":
            name = form["name"]

            with p.get_session() as s:
                g = web_utils.find(s, BudgetGroup, uri)
                try:
                    g.name = name
                    s.commit()
                except (exc.IntegrityError, exc.InvalidORMValueError) as e:
                    return common.error(e)

        groups_closed: list[str] = flask.session.get("groups_closed", [])
        groups_closed = [x for x in groups_closed if x != uri]
        if closed:
            groups_closed.append(uri)
        flask.session["groups_closed"] = groups_closed
    elif flask.request.method == "DELETE":
        with p.get_session() as s:
            g = web_utils.find(s, BudgetGroup, uri)
            s.query(TransactionCategory).where(
                TransactionCategory.budget_group_id == g.id_,
            ).update(
                {
                    TransactionCategory.budget_group_id: None,
                    TransactionCategory.budget_position: None,
                },
            )
            s.delete(g)
            # Subtract 1 from the following positions to close the gap
            query = (
                s.query(BudgetGroup)
                .where(BudgetGroup.position >= g.position)
                .order_by(BudgetGroup.position)
            )
            for g in query.yield_per(YIELD_PER):
                g.position -= 1
            s.commit()
    else:
        raise NotImplementedError

    month_str = form.get("month")
    month = (
        utils.start_of_month(datetime.date.today())
        if month_str is None
        else datetime.date.fromisoformat(month_str + "-01")
    )
    sidebar_uri = form.get("sidebar") or None

    with p.get_session() as s:
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        table, _ = ctx_table(s, month, categories, assignable, future_assigned)
        sidebar = ctx_sidebar(s, month, categories, future_assigned, sidebar_uri)
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
        budget_sidebar=sidebar,
        oob=True,
    )


def new_group() -> str:
    """POST /h/budgeting/group.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    form = flask.request.form
    name = form["name"]

    with p.get_session() as s:
        n = s.query(BudgetGroup).count()
        try:
            g = BudgetGroup(name=name, position=n)
            s.add(g)
            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

    month_str = form.get("month")
    month = (
        utils.start_of_month(datetime.date.today())
        if month_str is None
        else datetime.date.fromisoformat(month_str + "-01")
    )
    sidebar_uri = form.get("sidebar") or None

    with p.get_session() as s:
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        table, _ = ctx_table(s, month, categories, assignable, future_assigned)
        sidebar = ctx_sidebar(s, month, categories, future_assigned, sidebar_uri)
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
        budget_sidebar=sidebar,
        oob=True,
    )


def target(uri: str) -> str | flask.Response:
    """GET /h/budgeting/t/<path:uri>.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args if flask.request.method == "GET" else flask.request.form
    today = datetime.date.today()

    with p.get_session() as s:
        try:
            tar = web_utils.find(s, Target, uri)
            t_cat_id = tar.category_id
        except exc.http.BadRequest:
            t_cat_id = TransactionCategory.uri_to_id(uri)
            tar = s.query(Target).where(Target.category_id == t_cat_id).one_or_none()

        emoji, name = (
            s.query(TransactionCategory)
            .with_entities(TransactionCategory.emoji, TransactionCategory.name)
            .where(TransactionCategory.id_ == t_cat_id)
            .one()
        )
        emoji_name = f"{emoji} {name}" if emoji else name

        period_options = {
            TargetPeriod.ONCE: "Once",
            TargetPeriod.WEEK: "Weekly",
            TargetPeriod.MONTH: "Monthly",
            TargetPeriod.YEAR: "Annually",
        }
        period_options_rev = {v: k for k, v in period_options.items()}

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
            s.commit()
            return common.overlay_swap(event="update-budget")

        # Parse form
        period = args.get("period")
        if period is not None:
            tar.period = period_options_rev[period]
        due = args.get("due") or None
        if "change" in args:
            due = "0" if tar.period == TargetPeriod.WEEK else today.isoformat()
        amount = utils.parse_real(args.get("amount"))
        if amount is not None:
            tar.amount = amount
        tar_type = args.get("type", type=TargetType)
        if tar_type is not None:
            tar.type_ = tar_type
        repeat_every = args.get("repeat", type=int)
        if repeat_every is not None:
            tar.repeat_every = repeat_every
        if tar.period != TargetPeriod.ONCE:
            tar.repeat_every = max(1, tar.repeat_every)
        if due is not None:
            if tar.period == TargetPeriod.WEEK:
                # due is day of week, get a date that works
                due_date = today + datetime.timedelta(
                    days=int(due) - today.weekday(),
                )
            else:
                due_date = datetime.date.fromisoformat(due)
            tar.due_date_ord = due_date.toordinal()
        elif tar.type_ == TargetType.BALANCE:
            tar.due_date_ord = None

        if tar.period == TargetPeriod.ONCE:
            tar.repeat_every = 0
            tar.type_ = TargetType.BALANCE
        elif tar.period == TargetPeriod.WEEK:
            tar.repeat_every = 1

        try:
            if flask.request.method == "PUT":
                s.commit()
                return common.overlay_swap(event="update-budget")
            if flask.request.method == "POST":
                s.add(tar)
                s.commit()
                return common.overlay_swap(event="update-budget")
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
            "period_options": period_options,
            "repeat_every": tar.repeat_every,
            "due_date": due_date,
            "due_date_weekday": None if due_date is None else due_date.weekday(),
            "amount": tar.amount,
            "weekdays": utils.WEEKDAYS,
        }

        return flask.render_template(
            "budgeting/target.jinja",
            target=ctx,
        )


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
        total_leftover = Decimal(0)
        total_assigned = Decimal(0)
        total_activity = Decimal(0)

        query = s.query(TransactionCategory.id_).where(
            TransactionCategory.group == TransactionCategoryGroup.INCOME,
        )
        income_ids = {row[0] for row in query.all()}

        for t_cat_id, item in categories.items():
            if t_cat_id in income_ids:
                continue
            assigned, activity, available, leftover = item
            total_assigned += assigned
            total_activity += activity
            total_available += available
            total_leftover += leftover
        return {
            "uri": None,
            "name": None,
            "month": month_str,
            "available": total_available,
            "leftover": total_leftover,
            "assigned": total_assigned,
            "future_assigned": future_assigned,
            "activity": total_activity,
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
        utils.start_of_month(datetime.date.today())
        if month_str is None
        else datetime.date.fromisoformat(month_str + "-01")
    )
    uri = args.get("uri")

    with p.get_session() as s:
        categories, _, future_assigned = BudgetAssignment.get_monthly_available(
            s,
            month,
        )
        sidebar = ctx_sidebar(s, month, categories, future_assigned, uri)
        html = flask.render_template(
            "budgeting/sidebar.jinja",
            oob=True,
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


ROUTES: Routes = {
    "/budgeting": (page, ["GET"]),
    "/h/budgeting/c/<path:uri>/assign": (assign, ["PUT"]),
    "/h/budgeting/c/<path:uri>/overspending": (overspending, ["GET", "PUT"]),
    "/h/budgeting/c/<path:uri>/move": (move, ["GET", "PUT"]),
    "/h/budgeting/reorder": (reorder, ["PUT"]),
    "/h/budgeting/g/<path:uri>": (group, ["PUT", "DELETE"]),
    "/h/budgeting/new-group": (new_group, ["POST"]),
    "/h/budgeting/t/<path:uri>": (target, ["GET", "POST", "PUT", "DELETE"]),
    "/h/budgeting/sidebar": (sidebar, ["GET"]),
}
