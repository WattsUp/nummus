from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import flask
import pytest

from nummus.controllers import base
from nummus.models import (
    Account,
    Label,
    LabelLink,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from nummus.models.base import YIELD_PER

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from tests.controllers.conftest import WebClient


def test_page_all(web_client: WebClient, transactions: list[Transaction]) -> None:
    result, _ = web_client.GET("transactions.page_all")
    assert "Transactions" in result
    assert transactions[0].date.isoformat() in result
    assert transactions[-1].date.isoformat() in result


def test_table(web_client: WebClient) -> None:
    result, headers = web_client.GET("transactions.table")
    assert "no transactions match query" in result
    assert headers["HX-Push-URL"] == web_client.url_for("transactions.page_all")


def test_table_second_page(
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    result, headers = web_client.GET(
        ("transactions.table", {"page": transactions[0].date.isoformat()}),
    )
    assert "no more transactions match query" in result
    assert "HX-Push-URL" not in headers


def test_table_options(
    web_client: WebClient,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result, _ = web_client.GET("transactions.table_options")
    assert 'name="period"' in result
    assert 'name="category"' in result
    assert 'name="start"' in result
    assert 'name="end"' in result
    assert 'name="account"' in result
    assert "Other Income" in result
    assert "Securities Traded" in result
    assert account.name in result


def test_new_get(
    today: datetime.date,
    web_client: WebClient,
) -> None:
    result, _ = web_client.GET("transactions.new")
    assert "New transaction" in result
    assert today.isoformat() in result
    assert result.count('name="memo"') == 1
    assert "Delete" not in result


def test_new_put(
    today: datetime.date,
    web_client: WebClient,
    account: Account,
    categories: dict[str, int],
) -> None:
    result, _ = web_client.PUT(
        "transactions.new",
        data={
            "date": "2000-01-01",
            "account": account.uri,
            "amount": "1234",
            "payee": "Banana Farm",
            "category": [TransactionCategory.id_to_uri(categories["other income"])],
            "memo": ["Apples"],
            "label-0": ["Fruit"],
        },
    )
    assert "New transaction" in result
    assert today.isoformat() not in result
    assert "2000-01-01" in result
    assert f'value="{account.uri}" selected' in result
    assert "1234" in result
    assert "Banana Farm" in result
    assert "Apples" in result
    assert "Fruit" in result
    assert result.count('name="memo"') == 4


def test_new_put_more(
    today: datetime.date,
    web_client: WebClient,
    categories: dict[str, int],
) -> None:
    result, _ = web_client.PUT(
        "transactions.new",
        data={
            "date": "",
            "account": "",
            "amount": "",
            "payee": "",
            "split-amount": ["", ""],
            "category": [
                TransactionCategory.id_to_uri(categories["other income"]),
                TransactionCategory.id_to_uri(categories["uncategorized"]),
            ],
            "memo": ["", ""],
        },
    )
    assert "New transaction" in result
    assert today.isoformat() in result
    assert result.count('name="memo"') == 5


def test_new_put_bad_date(
    today: datetime.date,
    web_client: WebClient,
    categories: dict[str, int],
) -> None:
    result, _ = web_client.PUT(
        "transactions.new",
        data={
            "date": "a",
            "account": "",
            "amount": "",
            "payee": "",
            "category": [TransactionCategory.id_to_uri(categories["other income"])],
            "memo": [""],
        },
    )
    assert "New transaction" in result
    assert today.isoformat() in result
    assert result.count('name="memo"') == 4


def test_new(
    today: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    account: Account,
    categories: dict[str, int],
    rand_str: str,
    rand_real: Decimal,
) -> None:
    result, headers = web_client.POST(
        "transactions.new",
        data={
            "date": today,
            "account": account.uri,
            "amount": rand_real,
            "payee": rand_str,
            "category": [TransactionCategory.id_to_uri(categories["other income"])],
            "memo": [""],
        },
    )
    assert "snackbar.show" in result
    assert "Transaction created" in result
    assert headers["HX-Trigger"] == "account"

    txn = session.query(Transaction).one()
    assert txn.account_id == account.id_
    assert txn.date == today
    assert txn.amount == round(rand_real, 2)
    assert txn.payee == rand_str

    splits = txn.splits
    assert len(splits) == 1
    t_split = splits[0]
    assert t_split.amount == round(rand_real, 2)
    assert t_split.category_id == categories["other income"]
    assert t_split.memo is None

    labels = Label.map_name(session)
    assert not labels


def test_new_split(
    today: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    account: Account,
    categories: dict[str, int],
    rand_str: str,
    rand_real: Decimal,
) -> None:
    result, headers = web_client.POST(
        "transactions.new",
        data={
            "date": today,
            "account": account.uri,
            "amount": rand_real,
            "split-amount": ["10", rand_real - 10, "", ""],
            "payee": rand_str,
            "category": [
                TransactionCategory.id_to_uri(categories["other income"]),
                TransactionCategory.id_to_uri(categories["groceries"]),
                TransactionCategory.id_to_uri(categories["uncategorized"]),
                TransactionCategory.id_to_uri(categories["uncategorized"]),
            ],
            "memo": ["", "bananas", "", ""],
            "label-0": ["Engineer", "Salary", "Engineer", ""],
        },
    )
    assert "snackbar.show" in result
    assert "Transaction created" in result
    assert headers["HX-Trigger"] == "account"

    txn = session.query(Transaction).one()
    assert txn.account_id == account.id_
    assert txn.date == today
    assert txn.amount == round(rand_real, 2)
    assert txn.payee == rand_str

    splits = txn.splits
    assert len(splits) == 2

    labels = Label.map_name(session)
    assert len(labels) == 2

    t_split = splits[0]
    assert t_split.amount == Decimal(10)
    assert t_split.category_id == categories["other income"]
    assert t_split.memo is None
    query = session.query(LabelLink.label_id).where(LabelLink.t_split_id == t_split.id_)
    split_labels = {labels[label_id] for label_id, in query.yield_per(YIELD_PER)}
    assert split_labels == {"Engineer", "Salary"}

    t_split = splits[1]
    assert t_split.amount == round(rand_real - 10, 2)
    assert t_split.category_id == categories["groceries"]
    assert t_split.memo == "bananas"
    query = session.query(LabelLink.label_id).where(LabelLink.t_split_id == t_split.id_)
    split_labels = {labels[label_id] for label_id, in query.yield_per(YIELD_PER)}
    assert not split_labels


@pytest.mark.parametrize(
    ("date", "include_account", "amount", "include_split", "label", "target"),
    [
        ("", False, "", False, "", "Date must not be empty"),
        ("a", False, "", False, "", "Unable to parse date"),
        ("2100-01-01", False, "", False, "", "Only up to 7 days in advance"),
        ("2000-01-01", False, "", False, "", "Amount must not be empty"),
        ("2000-01-01", False, "a", False, "", "Amount must not be empty"),
        ("2000-01-01", False, "1", False, "", "Account must not be empty"),
        ("2000-01-01", True, "1", False, "", "Must have at least one split"),
        (
            "2000-01-01",
            True,
            "1",
            True,
            "a",
            "Label name must be at least 2 characters long",
        ),
    ],
)
def test_new_error(
    web_client: WebClient,
    categories: dict[str, int],
    account: Account,
    date: str,
    include_account: bool,
    amount: str,
    include_split: bool,
    label: str,
    target: str,
) -> None:
    result, _ = web_client.POST(
        "transactions.new",
        data={
            "date": date,
            "account": account.uri if include_account else "",
            "amount": amount,
            "payee": "",
            "category": (
                [
                    TransactionCategory.id_to_uri(categories["other income"]),
                ]
                if include_split
                else []
            ),
            "memo": "",
            "label-0": [label],
        },
    )
    assert result == base.error(target)


@pytest.mark.parametrize(
    ("amount", "target"),
    [
        ("11", "Remove $1.00 from splits"),
        ("9", "Assign $1.00 to splits"),
    ],
)
def test_new_unbalanced_split(
    today: datetime.date,
    web_client: WebClient,
    account: Account,
    categories: dict[str, int],
    rand_str: str,
    rand_real: Decimal,
    amount: str,
    target: str,
) -> None:
    result, _ = web_client.POST(
        "transactions.new",
        data={
            "date": today,
            "account": account.uri,
            "amount": rand_real,
            "split-amount": [amount, rand_real - 10, "", ""],
            "payee": rand_str,
            "category": [
                TransactionCategory.id_to_uri(categories["other income"]),
                TransactionCategory.id_to_uri(categories["groceries"]),
                TransactionCategory.id_to_uri(categories["uncategorized"]),
                TransactionCategory.id_to_uri(categories["uncategorized"]),
            ],
            "memo": ["", "bananas", "", ""],
        },
    )
    assert result == base.error(target)


def test_transaction_get_uncleared(
    session: orm.Session,
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    txn.cleared = False
    session.commit()

    result, _ = web_client.GET(("transactions.transaction", {"uri": txn.uri}))
    assert "Edit transaction" in result
    assert txn.date.isoformat() in result
    assert result.count('name="memo"') == 1
    assert "Delete" in result


def test_transaction_get(
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    result, _ = web_client.GET(("transactions.transaction", {"uri": txn.uri}))
    assert "Edit transaction" in result
    assert txn.date.isoformat() in result
    assert result.count('name="memo"') == 1
    assert "Delete" not in result


def test_transaction_delete_uncleared(
    session: orm.Session,
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    txn.cleared = False
    session.commit()

    result, headers = web_client.DELETE(("transactions.transaction", {"uri": txn.uri}))
    assert "snackbar.show" in result
    assert f"Transaction on {txn.date} deleted" in result
    assert headers["HX-Trigger"] == "account"

    t = session.query(Transaction).where(Transaction.id_ == txn.id_).one_or_none()
    assert t is None

    t = (
        session.query(TransactionSplit)
        .where(TransactionSplit.parent_id == txn.id_)
        .one_or_none()
    )
    assert t is None


def test_transaction_delete(
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    result, _ = web_client.DELETE(("transactions.transaction", {"uri": txn.uri}))
    assert result == base.error("Cannot delete cleared transaction")


def test_transaction_edit(
    today: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    t_split = txn.splits[0]

    result, headers = web_client.PUT(
        ("transactions.transaction", {"uri": txn.uri}),
        data={
            "date": today,
            "account": Account.id_to_uri(txn.account_id),
            "amount": txn.amount,
            "payee": txn.payee,
            "category": [
                TransactionCategory.id_to_uri(t_split.category_id),
            ],
            "memo": "",
        },
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "transaction"

    session.refresh(txn)
    assert txn.date == today


def test_transaction_edit_error(
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    t_split = txn.splits[0]

    result, _ = web_client.PUT(
        ("transactions.transaction", {"uri": txn.uri}),
        data={
            "date": "",
            "account": Account.id_to_uri(txn.account_id),
            "amount": txn.amount,
            "payee": txn.payee,
            "category": [
                TransactionCategory.id_to_uri(t_split.category_id),
            ],
            "memo": "",
        },
    )
    assert result == base.error("Date must not be empty")


def test_transaction_edit_payee_error(
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    t_split = txn.splits[0]

    result, _ = web_client.PUT(
        ("transactions.transaction", {"uri": txn.uri}),
        data={
            "date": txn.date,
            "account": Account.id_to_uri(txn.account_id),
            "amount": txn.amount,
            "payee": "a",
            "category": [
                TransactionCategory.id_to_uri(t_split.category_id),
            ],
            "memo": "",
        },
    )
    assert result == base.error("Transaction payee must be at least 2 characters long")


def test_transaction_edit_split_error(
    web_client: WebClient,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]

    result, _ = web_client.PUT(
        ("transactions.transaction", {"uri": txn.uri}),
        data={
            "date": txn.date,
            "account": Account.id_to_uri(txn.account_id),
            "amount": txn.amount,
            "payee": txn.payee,
            "memo": "",
        },
    )
    assert result == base.error("Must have at least one split")


def test_split(
    web_client: WebClient,
    categories: dict[str, int],
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    result, _ = web_client.PUT(
        ("transactions.split", {"uri": txn.uri}),
        data={
            "date": txn.date,
            "account": Account.id_to_uri(txn.account_id),
            "amount": txn.amount,
            "payee": txn.payee,
            "category": [TransactionCategory.id_to_uri(categories["other income"])],
            "memo": [""],
        },
    )
    assert "Edit transaction" in result
    assert result.count('name="memo"') == 4


def test_split_more(
    web_client: WebClient,
    categories: dict[str, int],
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    result, _ = web_client.PUT(
        ("transactions.split", {"uri": txn.uri}),
        data={
            "date": txn.date,
            "account": Account.id_to_uri(txn.account_id),
            "amount": txn.amount,
            "payee": txn.payee,
            "category": [
                TransactionCategory.id_to_uri(categories["other income"]),
                TransactionCategory.id_to_uri(categories["other income"]),
            ],
            "split-amount": ["", ""],
            "memo": ["", ""],
        },
    )
    assert "Edit transaction" in result
    assert result.count('name="memo"') == 5


@pytest.mark.parametrize(
    ("prop", "value", "target"),
    [
        ("payee", "New Name", ""),
        ("payee", " ", "Required"),
        ("payee", "a", "2 characters required"),
        ("memo", "Groceries", ""),
        ("memo", " ", ""),
        ("label", "Groceries", ""),
        ("label", " ", ""),
        ("date", "2000-01-01", ""),
        ("date", " ", "Required"),
        ("amount", " ", "Required"),
        ("split-amount", "a", "Unable to parse"),
    ],
)
def test_validation(
    web_client: WebClient,
    prop: str,
    value: str,
    target: str,
) -> None:
    result, _ = web_client.GET(
        (
            "transactions.validation",
            {prop: value, "split": "split" in prop},
        ),
    )
    assert result == target


@pytest.mark.parametrize(
    ("split_amount", "split", "target"),
    [
        # Just amount with a single split is okay
        ([], False, ""),
        (["10"], False, ""),
        (["11"], False, "Remove $1.00 from splits"),
        (["9"], False, "Assign $1.00 to splits"),
        (["9"], True, "Assign $1.00 to splits"),
    ],
)
def test_validation_amounts(
    flask_app: flask.Flask,
    web_client: WebClient,
    split_amount: list[str],
    split: bool,
    target: str,
) -> None:
    result, _ = web_client.GET(
        (
            "transactions.validation",
            {"amount": "10", "split-amount": split_amount, "split": split},
        ),
    )

    with flask_app.app_context():
        target = flask.render_template(
            "shared/dialog-headline-error.jinja",
            oob=True,
            headline_error=target,
        )
    assert result == target
