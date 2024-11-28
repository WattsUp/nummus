"""Budgeting controllers."""

from __future__ import annotations

import datetime
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

    from nummus.controllers.base import Routes


def ctx_table(month: datetime.date | None = None) -> tuple[dict[str, object], str]:
    """Get the context to build the budgeting table.

    Args:
        month: Month of table, None will check request args

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    if month is None:
        month_str = args.get("month")
        month = (
            utils.start_of_month(datetime.date.today())
            if month_str is None
            else datetime.date.fromisoformat(month_str + "-01")
        )

    class CategoryContext(TypedDict):
        """Type definition for budget category context."""

        position: int | None
        name: str
        uri: str
        emoji_name: str
        assigned: Decimal
        activity: Decimal
        available: Decimal
        status_text: str
        # List of bars (width ratio, bg fill ratio, fg fill ratio, bg, fg)
        bars: list[tuple[Decimal, Decimal, Decimal, str, str]]

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

    with p.get_session() as s:
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
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

            status_text = ""
            target_assigned: Decimal | None = None
            bar_dollars: list[Decimal] = []
            if tar is None:
                if activity == 0 and available == 0:
                    bar_dollars.append(Decimal(0))
                elif available >= 0:
                    bar_dollars.append(available - activity)
                else:
                    bar_dollars.append(-activity)
                    status_text = '<span class="font-bold">Overspent</span>'
            else:
                balance = available - assigned
                target_assigned, next_due_date = tar.get_expected_assigned(
                    month,
                    balance,
                )
                target_assigned = round(target_assigned, 2)
                deficent = target_assigned - assigned

                if deficent <= 0:
                    if available < 0:
                        status_text = '<span class="font-bold">Overspent</span>'
                    else:
                        # Say funded unless next due date is out there, then On track
                        status_text = (
                            "Funded"
                            if next_due_date is None
                            or utils.date_months_between(month, next_due_date) == 0
                            else "On track"
                        )
                elif available < 0:
                    status_text = (
                        '<span class="font-bold">Overspent</span> '
                        f"{utils.format_financial(deficent)} more needed"
                    )
                else:
                    status_text = f"{utils.format_financial(deficent)} more needed"

                if tar.type_ != TargetType.REFILL and leftover != 0:
                    bar_dollars.append(leftover)

                if tar.period == TargetPeriod.WEEK and tar.due_date_ord is not None:
                    weekday = datetime.date.fromordinal(tar.due_date_ord).weekday()
                    n_bars = utils.weekdays_in_month(weekday, month)
                    bar_dollars.extend([tar.amount] * n_bars)
                else:
                    bar_dollars.append(tar.amount)

                # If assigned >= target_assigned: green else yellow
                # overspending always red

                # If any leftover and ACCUMULATE, have bar split starting with leftover
                # amount

                # If WEEK, have bar segment for each week
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
                "status_text": status_text,
                "bars": bars,
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
    table, title = ctx_table()
    return common.page(
        "budgeting/index-content.jinja",
        title=title,
        table=table,
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

    table, _ = ctx_table(month=month)
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
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

    table, _ = ctx_table()
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
    )


def group(uri: str) -> str:
    """PUT /h/budgeting/g/<path:uri>.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    if flask.request.method == "PUT":
        form = flask.request.form
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

    table, _ = ctx_table()
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
        oob=True,
    )


def new_group() -> str:
    """POST /h/budgeting/group.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    name = flask.request.form["name"]

    with p.get_session() as s:
        n = s.query(BudgetGroup).count()
        try:
            g = BudgetGroup(name=name, position=n)
            s.add(g)
            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

    table, _ = ctx_table()
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
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
        due = args.get("due")
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
        if due is not None:
            if tar.period == TargetPeriod.WEEK:
                # due is day of week, get a date that works
                due_date = today + datetime.timedelta(
                    days=int(due) - today.weekday(),
                )
            else:
                due_date = datetime.date.fromisoformat(due)
            tar.due_date_ord = due_date.toordinal()

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


# TODO (WattsUp): Add sidebar details of budget row, have edit/new target buttons there

ROUTES: Routes = {
    "/budgeting": (page, ["GET"]),
    "/h/budgeting/c/<path:uri>/assign": (assign, ["PUT"]),
    "/h/budgeting/c/<path:uri>/overspending": (overspending, ["GET", "PUT"]),
    "/h/budgeting/c/<path:uri>/move": (move, ["GET", "PUT"]),
    "/h/budgeting/reorder": (reorder, ["PUT"]),
    "/h/budgeting/g/<path:uri>": (group, ["PUT", "DELETE"]),
    "/h/budgeting/new-group": (new_group, ["POST"]),
    "/h/budgeting/t/<path:uri>": (target, ["GET", "POST", "PUT", "DELETE"]),
}
