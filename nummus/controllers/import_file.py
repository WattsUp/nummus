"""Import file controller."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import flask
import werkzeug.utils

from nummus import exceptions as exc
from nummus import portfolio
from nummus.controllers import common

if TYPE_CHECKING:
    from nummus.controllers.base import Routes


def import_file() -> str | flask.Response:
    """GET & POST /h/import.

    Returns:
        HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    if flask.request.method == "GET":
        return flask.render_template("import/overlay.jinja")

    file = flask.request.files.get("file")
    if file is None or file.filename == "":
        return common.error("No file selected")

    filename = Path(werkzeug.utils.secure_filename(file.filename or ""))
    with tempfile.NamedTemporaryFile(
        "wb",
        delete=False,
        delete_on_close=False,
        suffix=filename.suffix,
    ) as file_local:
        path_file_local = Path(file_local.name)
        file_local.write(file.stream.read())

    force = "force" in flask.request.form

    error: str | None = None
    path_debug = p.path.with_suffix(".importer_debug")
    try:
        p.import_file(path_file_local, path_debug, force=force)
    except exc.FileAlreadyImportedError as e:
        html_button = flask.render_template(
            "import/button.jinja",
            oob=True,
            force=True,
        )
        html_error = common.error(f"File already imported on {e.date}")
        return html_button + "\n" + html_error
    except exc.UnknownImporterError:
        error = "Could not find an importer for file"
    except exc.FailedImportError as e:
        error = f"{e.importer} failed to import file"
    except exc.EmptyImportError as e:
        error = f"{e.importer} did not import any transactions for file"
    except Exception as e:  # noqa: BLE001
        return common.error(e)
    path_file_local.unlink()

    if error:
        return common.error(error)

    html = flask.render_template(
        "import/overlay.jinja",
        success=True,
    )
    return common.overlay_swap(
        html,
        event=[
            "update-account",
            "update-asset",
            "update-transaction",
        ],
    )


ROUTES: Routes = {
    "/h/import": (import_file, ["GET", "POST"]),
}
