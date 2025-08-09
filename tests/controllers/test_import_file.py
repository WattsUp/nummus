from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus.controllers import base

if TYPE_CHECKING:
    import datetime
    from pathlib import Path

    from nummus.models import Account
    from tests.controllers.conftest import WebClient


def test_dialog(web_client: WebClient) -> None:
    result, _ = web_client.GET("import_file.import_file")
    assert "Import file" in result
    assert "Upload" in result


def test_no_file(web_client: WebClient) -> None:
    result, _ = web_client.POST("import_file.import_file")
    assert result == base.error("No file selected")


@pytest.mark.parametrize(
    ("file", "target", "traceback"),
    [
        ("transactions_lacking.csv", "Could not find an importer for file", False),
        (
            "transactions_corrupt.csv",
            "CSVTransactionImporter failed to import file",
            True,
        ),
        ("transactions_future.csv", "Cannot create transaction in the future", False),
        (
            "transactions_empty.csv",
            "CSVTransactionImporter did not import any transactions for file",
            True,
        ),
        (
            "transactions_bad_account.csv",
            "Account matching 'Unknown' could not be found, please create first",
            False,
        ),
    ],
)
def test_error(
    capsys: pytest.CaptureFixture,
    web_client: WebClient,
    data_path: Path,
    file: str,
    target: str,
    traceback: bool,
    account: Account,
) -> None:
    _ = account
    path = data_path / file
    result, _ = web_client.POST(
        "import_file.import_file",
        data={"file": (path, path.name)},
    )

    assert result == base.error(target)
    captured = capsys.readouterr()
    assert not captured.out
    if traceback:
        assert captured.err
    else:
        assert not captured.err


def test_import_file(
    web_client: WebClient,
    data_path: Path,
    account: Account,
    account_investments: Account,
) -> None:
    _ = account
    _ = account_investments
    path = data_path / "transactions_required.csv"
    result, headers = web_client.POST(
        "import_file.import_file",
        data={"file": (path, path.name)},
    )
    assert "File successfully imported" in result
    assert headers["HX-Trigger"] == "account"


def test_duplicate(
    today: datetime.date,
    web_client: WebClient,
    data_path: Path,
    account: Account,
    account_investments: Account,
) -> None:
    _ = account
    _ = account_investments
    path = data_path / "transactions_required.csv"
    web_client.POST(
        "import_file.import_file",
        data={"file": (path, path.name)},
    )

    result, _ = web_client.POST(
        "import_file.import_file",
        data={"file": (path, path.name)},
    )

    target = f"File already imported on {today}"
    assert base.error(target) in result
    assert "Force importing" in result


def test_duplicate_force(
    web_client: WebClient,
    data_path: Path,
    account: Account,
    account_investments: Account,
) -> None:
    _ = account
    _ = account_investments
    path = data_path / "transactions_required.csv"
    web_client.POST(
        "import_file.import_file",
        data={"file": (path, path.name)},
    )

    result, headers = web_client.POST(
        "import_file.import_file",
        data={"file": (path, path.name), "force": True},
    )

    assert "File successfully imported" in result
    assert headers["HX-Trigger"] == "account"
