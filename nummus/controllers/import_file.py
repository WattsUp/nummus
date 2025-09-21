"""Import file controller."""

from __future__ import annotations

import tempfile
import traceback
from pathlib import Path

import flask
import werkzeug.utils

from nummus import exceptions as exc
from nummus import web
from nummus.controllers import base


def import_file() -> str | flask.Response:
    """GET & POST /h/import.

    Returns:
        HTML response

    """
    p = web.portfolio
    if flask.request.method == "GET":
        return flask.render_template("import/dialog.jinja")

    file = flask.request.files.get("file")
    if file is None or not file.filename:
        return base.error("No file selected")

    force = "force" in flask.request.form

    filename = Path(werkzeug.utils.secure_filename(file.filename or ""))
    path_file_local = Path(tempfile.mkstemp(suffix=filename.suffix)[1])

    with path_file_local.open("wb") as file_local:
        file_local.write(file.stream.read())

    path_debug = p.path.with_suffix(".importer_debug")
    try:
        p.import_file(path_file_local, path_debug, force=force)
    except exc.FileAlreadyImportedError as e:
        html_button = flask.render_template(
            "import/button.jinja",
            oob=True,
            force=True,
        )
        html_error = base.error(f"File already imported on {e.date}")
        return html_button + "\n" + html_error
    except exc.UnknownImporterError:
        return base.error("Could not find an importer for file")
    except exc.FailedImportError as e:
        traceback.print_exception(e)  # For logs
        return base.error(f"{e.importer} failed to import file")
    except exc.EmptyImportError as e:
        traceback.print_exception(e)  # For logs
        return base.error(f"{e.importer} did not import any transactions for file")
    except exc.FutureTransactionError:
        return base.error("Cannot create transaction in the future")
    except exc.NoResultFound as e:
        return base.error(f"{e}, please create first")
    finally:
        path_file_local.unlink()

    html = flask.render_template(
        "import/dialog.jinja",
        success=True,
    )
    return base.dialog_swap(html, event="account")


ROUTES: base.Routes = {
    "/h/import": (import_file, ["GET", "POST"]),
}
