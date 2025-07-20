from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import flask
import pytest

from nummus import utils
from nummus.controllers import base
from nummus.controllers import transactions as txn_controller
from nummus.models import (
    Account,
    Asset,
    query_count,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:

    from sqlalchemy import orm

    from tests.controllers.conftest import WebClient


@pytest.mark.parametrize(
    ("include_account", "period", "start", "end", "category", "uncleared", "target"),
    [
        (False, None, None, None, None, False, (4, False)),
        (True, None, None, None, None, False, (4, True)),
        (False, "2000-01", None, None, None, False, (0, True)),
        (False, "2000", None, None, None, False, (0, True)),
        (False, "custom", None, None, None, False, (4, True)),
        (False, "custom", "2000-01-01", None, None, False, (4, True)),
        (False, "custom", None, "2000-01-01", None, False, (0, True)),
        (False, None, None, None, "other income", False, (1, True)),
        (False, None, None, None, "securities traded", False, (3, True)),
        (False, None, None, None, None, True, (0, True)),
    ],
)
def test_table_query(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
    categories: dict[str, int],
    include_account: bool,
    period: str | None,
    start: str | None,
    end: str | None,
    category: str | None,
    uncleared: bool,
    target: tuple[int, bool],
) -> None:
    _ = transactions
    query, any_filters = txn_controller.table_query(
        session,
        None,
        account.uri if include_account else None,
        period,
        start,
        end,
        TransactionCategory.id_to_uri(categories[category]) if category else None,
        uncleared=uncleared,
    )
    assert any_filters == target[1]
    assert query_count(query) == target[0]


def test_ctx_txn(
    today: datetime.date,
    account: Account,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    ctx = txn_controller.ctx_txn(txn)

    assert ctx["uri"] == txn.uri
    assert ctx["account"] == account.name
    assert ctx["account_uri"] == account.uri
    assert ctx["accounts"] == [(account.uri, account.name, account.closed)]
    assert ctx["cleared"] == txn.cleared
    assert ctx["date"] == txn.date
    assert ctx["date_max"] == today + datetime.timedelta(days=utils.DAYS_IN_WEEK)
    assert ctx["amount"] == txn.amount
    assert ctx["statement"] == txn.statement
    assert ctx["payee"] == txn.payee


def test_ctx_split(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    query = session.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
    assets: dict[int, tuple[str, str | None]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }
    txn = transactions[0]
    t_split = txn.splits[0]

    ctx = txn_controller.ctx_split(
        t_split,
        assets,
    )

    assert ctx["parent_uri"] == txn.uri
    assert ctx["amount"] == t_split.amount
    assert ctx["category_uri"] == TransactionCategory.id_to_uri(t_split.category_id)
    assert ctx["memo"] == t_split.memo
    assert ctx["tag"] == t_split.tag
    assert ctx.get("asset_name") is None
    assert ctx.get("asset_ticker") is None
    assert ctx.get("asset_price") is None
    assert ctx.get("asset_quantity") == Decimal()


def test_ctx_split_asset(
    session: orm.Session,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    query = session.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
    assets: dict[int, tuple[str, str | None]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }
    txn = transactions[1]
    t_split = txn.splits[0]

    ctx = txn_controller.ctx_split(
        t_split,
        assets,
    )

    assert ctx["parent_uri"] == txn.uri
    assert ctx["amount"] == t_split.amount
    assert ctx["category_uri"] == TransactionCategory.id_to_uri(t_split.category_id)
    assert ctx["memo"] == t_split.memo
    assert ctx["tag"] == t_split.tag
    assert ctx.get("asset_name") == asset.name
    assert ctx.get("asset_ticker") == asset.ticker
    assert ctx.get("asset_price") == Decimal(1)
    assert ctx.get("asset_quantity") == Decimal(10)


def test_ctx_row(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    query = session.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
    assets: dict[int, tuple[str, str | None]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }
    txn = transactions[0]
    t_split = txn.splits[0]

    ctx = txn_controller.ctx_row(
        t_split,
        assets,
        Account.map_name(session),
        TransactionCategory.map_name_emoji(session),
        set(),
    )

    assert ctx["parent_uri"] == txn.uri
    assert ctx["amount"] == t_split.amount
    assert ctx["category_uri"] == TransactionCategory.id_to_uri(t_split.category_id)
    assert ctx["memo"] == t_split.memo
    assert ctx["tag"] == t_split.tag
    assert ctx.get("asset_name") is None
    assert ctx.get("asset_ticker") is None
    assert ctx.get("asset_price") is None
    assert ctx.get("asset_quantity") == Decimal()
    assert ctx["date"] == t_split.date
    assert ctx["account"] == account.name
    assert ctx["category"] == "Other Income"
    assert ctx["payee"] == t_split.payee
    assert ctx["cleared"] == t_split.cleared
    assert not ctx["is_split"]


def test_ctx_options(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
    categories: dict[str, int],
) -> None:
    _ = transactions
    query = session.query(TransactionSplit)

    ctx = txn_controller.ctx_options(
        query,
        Account.map_name(session),
        TransactionCategory.map_name_emoji(session),
        None,
        None,
    )

    assert ctx["options_account"] == [(account.name, account.uri)]
    target = [
        ("Other Income", TransactionCategory.id_to_uri(categories["other income"])),
        (
            "Securities Traded",
            TransactionCategory.id_to_uri(categories["securities traded"]),
        ),
    ]
    assert ctx["options_category"] == target


def test_ctx_options_selected(
    session: orm.Session,
    account: Account,
    categories: dict[str, int],
) -> None:
    query = session.query(TransactionSplit)

    ctx = txn_controller.ctx_options(
        query,
        Account.map_name(session),
        TransactionCategory.map_name_emoji(session),
        account.uri,
        TransactionCategory.id_to_uri(categories["other income"]),
    )

    assert ctx["options_account"] == [(account.name, account.uri)]
    target = [
        ("Other Income", TransactionCategory.id_to_uri(categories["other income"])),
    ]
    assert ctx["options_category"] == target


@pytest.mark.parametrize(
    ("account", "period", "start", "end", "category", "uncleared", "target"),
    [
        (None, None, None, None, None, False, "Transactions"),
        ("Monkey Bank", None, None, None, None, False, "Transactions, Monkey Bank"),
        (None, "all", None, None, None, False, "All Transactions"),
        (None, "2000-01", None, None, None, False, "2000-01 Transactions"),
        (None, "2000", None, None, None, False, "2000 Transactions"),
        (
            None,
            "custom",
            "2000-01-01",
            None,
            None,
            False,
            "from 2000-01-01 Transactions",
        ),
        (None, "custom", None, "2000-01-01", None, False, "to 2000-01-01 Transactions"),
        (
            None,
            "custom",
            "2000-01-01",
            "2001-01-01",
            None,
            False,
            "2000-01-01 to 2001-01-01 Transactions",
        ),
        (None, None, None, None, "Other Income", False, "Transactions, Other Income"),
        (None, None, None, None, None, True, "Transactions, Uncleared"),
    ],
)
def test_table_title(
    account: str | None,
    period: str | None,
    start: str | None,
    end: str | None,
    category: str | None,
    uncleared: bool,
    target: str,
) -> None:
    title = txn_controller._table_title(  # noqa: SLF001
        account,
        period,
        start,
        end,
        category,
        uncleared=uncleared,
    )
    assert title == target


def test_table_results_empty(
    session: orm.Session,
) -> None:
    query = session.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
    assets: dict[int, tuple[str, str | None]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }

    result = txn_controller._table_results(  # noqa: SLF001
        session.query(TransactionSplit),
        assets,
        Account.map_name(session),
        TransactionCategory.map_name_emoji(session),
        {},
    )
    assert result == []


def test_table_results(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    query = session.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
    assets: dict[int, tuple[str, str | None]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }
    accounts = Account.map_name(session)
    categories = TransactionCategory.map_name_emoji(session)

    result = txn_controller._table_results(  # noqa: SLF001
        session.query(TransactionSplit).order_by(TransactionSplit.date_ord),
        assets,
        accounts,
        categories,
        {},
    )
    target = [
        (
            txn.date,
            [
                txn_controller.ctx_row(
                    txn.splits[0],
                    assets,
                    accounts,
                    categories,
                    set(),
                ),
            ],
        )
        for txn in transactions[::-1]
    ]
    assert result == target


def test_ctx_table_empty(flask_app: flask.Flask) -> None:
    with flask_app.app_context():
        ctx, title = txn_controller.ctx_table(
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            uncleared=False,
        )

    assert title == "Transactions"
    assert ctx["uri"] is None
    assert ctx["transactions"] == []
    assert ctx["query_total"] == Decimal()
    assert ctx["no_matches"]
    assert ctx["next_page"] is None
    assert not ctx["any_filters"]
    assert ctx["search"] is None
    assert ctx["selected_period"] is None
    assert ctx["selected_account"] is None
    assert ctx["selected_category"] is None
    assert not ctx["uncleared"]
    assert ctx["start"] is None
    assert ctx["end"] is None


def test_ctx_table(
    flask_app: flask.Flask,
    transactions: list[Transaction],
) -> None:
    with flask_app.app_context():
        ctx, title = txn_controller.ctx_table(
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            uncleared=False,
        )

    assert title == "Transactions"
    assert ctx["uri"] is None
    assert len(ctx["transactions"]) == len(transactions)
    assert ctx["query_total"] == sum(txn.amount for txn in transactions)
    assert not ctx["no_matches"]
    assert ctx["next_page"] is None
    assert not ctx["any_filters"]
    assert ctx["search"] is None
    assert ctx["selected_period"] is None
    assert ctx["selected_account"] is None
    assert ctx["selected_category"] is None
    assert not ctx["uncleared"]
    assert ctx["start"] is None
    assert ctx["end"] is None


def test_ctx_table_paging(
    monkeypatch: pytest.MonkeyPatch,
    flask_app: flask.Flask,
    transactions: list[Transaction],
) -> None:
    monkeypatch.setattr(txn_controller, "PAGE_LEN", 2)
    with flask_app.app_context():
        ctx, _ = txn_controller.ctx_table(
            None,
            None,
            None,
            None,
            None,
            None,
            transactions[2].date.isoformat(),
            uncleared=False,
        )

    assert len(ctx["transactions"]) == 2
    assert ctx["next_page"] == transactions[0].date.isoformat()


def test_ctx_table_search(
    flask_app: flask.Flask,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    with flask_app.app_context():
        ctx, _ = txn_controller.ctx_table(
            "rent",
            None,
            None,
            None,
            None,
            None,
            None,
            uncleared=False,
        )

    assert len(ctx["transactions"]) == 2
    assert ctx["search"] == "rent"


def test_ctx_table_search_paging(
    flask_app: flask.Flask,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    with flask_app.app_context():
        ctx, _ = txn_controller.ctx_table(
            "rent",
            None,
            None,
            None,
            None,
            None,
            "1",
            uncleared=False,
        )

    assert len(ctx["transactions"]) == 1
    assert ctx["search"] == "rent"


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
    categories: dict[str, int],
) -> None:
    result, _ = web_client.PUT(
        "transactions.new",
        data={
            "date": "",
            "account": "",
            "amount": "",
            "payee": "",
            "category": [TransactionCategory.id_to_uri(categories["other income"])],
            "memo": [""],
            "tag": [""],
        },
    )
    assert "New transaction" in result
    assert today.isoformat() in result
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
            "tag": ["", ""],
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
            "tag": [""],
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
            "tag": [""],
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
    assert t_split.tag is None


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
            "tag": ["Engineer", "", "", ""],
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

    t_split = splits[0]
    assert t_split.amount == Decimal(10)
    assert t_split.category_id == categories["other income"]
    assert t_split.memo is None
    assert t_split.tag == "Engineer"

    t_split = splits[1]
    assert t_split.amount == round(rand_real - 10, 2)
    assert t_split.category_id == categories["groceries"]
    assert t_split.memo == "bananas"
    assert t_split.tag is None


@pytest.mark.parametrize(
    ("date", "include_account", "amount", "include_split", "tag", "target"),
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
            "Transaction split tag must be at least 2 characters long",
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
    tag: str,
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
            "tag": tag,
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
            "tag": ["Engineer", "", "", ""],
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
            "tag": t_split.tag,
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
            "date": txn.date,
            "account": Account.id_to_uri(txn.account_id),
            "amount": txn.amount,
            "payee": "a",
            "category": [
                TransactionCategory.id_to_uri(t_split.category_id),
            ],
            "memo": "",
            "tag": t_split.tag,
        },
    )
    assert result == base.error("Transaction payee must be at least 2 characters long")


def test_transaction_edit_split_error(
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
            "payee": txn.payee,
            "memo": "",
            "tag": t_split.tag,
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
            "tag": [""],
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
            "tag": ["", ""],
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
        ("tag", "Groceries", ""),
        ("tag", " ", ""),
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
    ("amount", "split_amount", "split", "target"),
    [
        ("10", ["10"], False, ""),
        ("10", ["11"], False, "Remove $1.00 from splits"),
        ("10", ["9"], False, "Assign $1.00 to splits"),
        ("10", ["9"], True, "Assign $1.00 to splits"),
    ],
)
def test_validation_amounts(
    flask_app: flask.Flask,
    web_client: WebClient,
    amount: str,
    split_amount: list[str],
    split: bool,
    target: str,
) -> None:
    result, _ = web_client.GET(
        (
            "transactions.validation",
            {"amount": amount, "split-amount": split_amount, "split": split},
        ),
    )

    with flask_app.app_context():
        target = flask.render_template(
            "shared/dialog-headline-error.jinja",
            oob=True,
            headline_error=target,
        )
    assert result == target
