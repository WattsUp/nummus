"""Tags controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flask

from nummus import exceptions as exc
from nummus import web
from nummus.controllers import base
from nummus.models import Tag, TagLink
from nummus.models.base import YIELD_PER

if TYPE_CHECKING:
    from sqlalchemy import orm


def page() -> flask.Response:
    """GET /tags.

    Returns:
        string HTML response

    """
    p = web.portfolio

    with p.begin_session() as s:
        return base.page(
            "tags/page.jinja",
            "Tags",
            tags=ctx_tags(s),
        )


def tag(uri: str) -> str | flask.Response:
    """GET, PUT, & DELETE /h/tags/t/<uri>.

    Args:
        uri: Tag URI

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        tag = base.find(s, Tag, uri)

        if flask.request.method == "GET":
            ctx: dict[str, object] = {
                "uri": uri,
                "name": tag.name,
            }

            return flask.render_template(
                "tags/edit.jinja",
                tag=ctx,
            )

        if flask.request.method == "DELETE":

            s.query(TagLink).where(
                TagLink.tag_id == tag.id_,
            ).delete()
            s.delete(tag)

            return base.dialog_swap(
                event="tag",
                snackbar=f"Deleted tag {tag.name}",
            )

        form = flask.request.form
        name = form["name"]

        try:
            with s.begin_nested():
                tag.name = name
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return base.error(e)

        return base.dialog_swap(
            event="tag",
            snackbar="All changes saved",
        )


def validation() -> str:
    """GET /h/tags/validation.

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
                no_duplicates=Tag.name,
                no_duplicate_wheres=([Tag.id_ != Tag.uri_to_id(uri)]),
            )

    raise NotImplementedError


def ctx_tags(s: orm.Session) -> list[base.NamePair]:
    """Get the context required to build the tags table.

    Args:
        s: SQL session to use

    Returns:
        List of HTML context

    """
    query = s.query(Tag).order_by(Tag.name)
    return [base.NamePair(tag.uri, tag.name) for tag in query.yield_per(YIELD_PER)]


ROUTES: base.Routes = {
    "/tags": (page, ["GET"]),
    "/h/tags/t/<path:uri>": (tag, ["GET", "PUT", "DELETE"]),
    "/h/tags/validation": (validation, ["GET"]),
}
