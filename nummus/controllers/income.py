"""Income controllers."""

from __future__ import annotations

import flask

from nummus import web
from nummus.controllers import base, spending


def page() -> flask.Response:
    """GET /income.

    Returns:
        string HTML response

    """
    args = flask.request.args
    p = web.portfolio
    with p.begin_session() as s:
        today = base.today_client()
        ctx, title = spending.ctx_chart(
            s,
            today,
            args.get("account"),
            args.get("category"),
            args.get("label"),
            args.get("period", str(today.year)),
            args.get("start"),
            args.get("end"),
            is_income=True,
        )
    return base.page(
        "spending/page.jinja",
        title=title,
        ctx=ctx,
        is_income=True,
        controller="income",
    )


def chart() -> flask.Response:
    """GET /h/income/chart.

    Returns:
        string HTML response

    """
    args = flask.request.args
    p = web.portfolio
    with p.begin_session() as s:
        today = base.today_client()
        ctx, title = spending.ctx_chart(
            s,
            today,
            args.get("account"),
            args.get("category"),
            args.get("label"),
            args.get("period", str(today.year)),
            args.get("start"),
            args.get("end"),
            is_income=True,
        )
    html_title = f"<title>{title} - nummus</title>\n"
    html = html_title + flask.render_template(
        "spending/chart-data.jinja",
        ctx=ctx,
        is_income=True,
        controller="income",
        include_oob=True,
    )
    response = flask.make_response(html)
    response.headers["HX-Push-Url"] = flask.url_for(
        "income.page",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **args,
    )
    return response


def dashboard() -> str:
    """GET /h/dashboard/income.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        today = base.today_client()
        ctx, _ = spending.ctx_chart(
            s,
            today,
            None,
            None,
            None,
            str(today.year),
            None,
            None,
            is_income=True,
        )
    return flask.render_template(
        "spending/dashboard.jinja",
        ctx=ctx,
        is_income=True,
        controller="income",
    )


ROUTES: base.Routes = {
    "/income": (page, ["GET"]),
    "/h/income/chart": (chart, ["GET"]),
    "/h/dashboard/income": (dashboard, ["GET"]),
}
