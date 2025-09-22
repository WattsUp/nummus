"""Labels controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flask

from nummus import exceptions as exc
from nummus import web
from nummus.controllers import base
from nummus.models import Label, LabelLink
from nummus.models.base import YIELD_PER

if TYPE_CHECKING:
    from sqlalchemy import orm


def page() -> flask.Response:
    """GET /labels.

    Returns:
        string HTML response

    """
    p = web.portfolio

    with p.begin_session() as s:
        return base.page(
            "labels/page.jinja",
            "Labels",
            labels=ctx_labels(s),
        )


def label(uri: str) -> str | flask.Response:
    """GET, PUT, & DELETE /h/labels/t/<uri>.

    Args:
        uri: Label URI

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        label = base.find(s, Label, uri)

        if flask.request.method == "GET":
            ctx: dict[str, object] = {
                "uri": uri,
                "name": label.name,
            }

            return flask.render_template(
                "labels/edit.jinja",
                label=ctx,
            )

        if flask.request.method == "DELETE":

            s.query(LabelLink).where(
                LabelLink.label_id == label.id_,
            ).delete()
            s.delete(label)

            return base.dialog_swap(
                event="label",
                snackbar=f"Deleted label {label.name}",
            )

        form = flask.request.form
        name = form["name"]

        try:
            with s.begin_nested():
                label.name = name
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return base.error(e)

        return base.dialog_swap(
            event="label",
            snackbar="All changes saved",
        )


def validation() -> str:
    """GET /h/labels/validation.

    Returns:
        string HTML response

    """
    p = web.portfolio
    args = flask.request.args
    uri = args["uri"]
    if "name" in args:
        with p.begin_session() as s:
            return base.validate_string(
                args["name"],
                is_required=True,
                session=s,
                no_duplicates=Label.name,
                no_duplicate_wheres=([Label.id_ != Label.uri_to_id(uri)]),
            )

    raise NotImplementedError


def ctx_labels(s: orm.Session) -> list[base.NamePair]:
    """Get the context required to build the labels table.

    Args:
        s: SQL session to use

    Returns:
        List of HTML context

    """
    query = s.query(Label).order_by(Label.name)
    return [
        base.NamePair(label.uri, label.name) for label in query.yield_per(YIELD_PER)
    ]


ROUTES: base.Routes = {
    "/labels": (page, ["GET"]),
    "/h/labels/t/<path:uri>": (label, ["GET", "PUT", "DELETE"]),
    "/h/labels/validation": (validation, ["GET"]),
}
