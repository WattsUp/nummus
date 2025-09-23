from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import utils
from nummus.controllers import base
from nummus.controllers import transactions as txn_controller
from nummus.models import (
    Account,
    Asset,
    Label,
    LabelLink,
    query_count,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Transaction,
    )


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
    tbl_query = txn_controller.table_query(
        session,
        None,
        account.uri if include_account else None,
        period,
        start,
        end,
        TransactionCategory.id_to_uri(categories[category]) if category else None,
        uncleared=uncleared,
    )
    assert tbl_query.any_filters == target[1]
    assert query_count(tbl_query.final_query) == target[0]


def test_ctx_txn(
    today: datetime.date,
    account: Account,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    ctx = txn_controller.ctx_txn(txn, today)

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
    labels: dict[str, int],
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
        {labels["engineer"]: "engineer"},
    )

    assert ctx["parent_uri"] == txn.uri
    assert ctx["amount"] == t_split.amount
    assert ctx["category_uri"] == TransactionCategory.id_to_uri(t_split.category_id)
    assert ctx["memo"] == t_split.memo
    assert ctx["labels"] == [
        base.NamePair(Label.id_to_uri(labels["engineer"]), "engineer"),
    ]
    assert ctx.get("asset_name") is None
    assert ctx.get("asset_ticker") is None
    assert ctx.get("asset_price") is None
    assert ctx.get("asset_quantity") == Decimal()


def test_ctx_split_asset(
    session: orm.Session,
    asset: Asset,
    transactions: list[Transaction],
    labels: dict[str, int],
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
        {labels["engineer"]: "engineer"},
    )

    assert ctx["parent_uri"] == txn.uri
    assert ctx["amount"] == t_split.amount
    assert ctx["category_uri"] == TransactionCategory.id_to_uri(t_split.category_id)
    assert ctx["memo"] == t_split.memo
    assert ctx["labels"] == [
        base.NamePair(Label.id_to_uri(labels["engineer"]), "engineer"),
    ]
    assert ctx.get("asset_name") == asset.name
    assert ctx.get("asset_ticker") == asset.ticker
    assert ctx.get("asset_price") == Decimal(1)
    assert ctx.get("asset_quantity") == Decimal(10)


def test_ctx_row(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
    labels: dict[str, int],
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
        {labels["engineer"]: "engineer"},
        set(),
    )

    assert ctx["parent_uri"] == txn.uri
    assert ctx["amount"] == t_split.amount
    assert ctx["category_uri"] == TransactionCategory.id_to_uri(t_split.category_id)
    assert ctx["memo"] == t_split.memo
    assert ctx["labels"] == [
        base.NamePair(Label.id_to_uri(labels["engineer"]), "engineer"),
    ]
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
    today: datetime.date,
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
    categories: dict[str, int],
) -> None:
    _ = transactions
    tbl_query = txn_controller.TableQuery(
        session.query(TransactionSplit),
        {},
        any_filters=False,
    )

    ctx = txn_controller.ctx_options(
        tbl_query,
        today,
        Account.map_name(session),
        base.tranaction_category_groups(session),
        None,
        None,
    )

    assert ctx["options_account"] == [base.NamePair(account.uri, account.name)]
    target = {
        TransactionCategoryGroup.INCOME: [
            base.CategoryContext(
                TransactionCategory.id_to_uri(categories["other income"]),
                "other income",
                "Other Income",
                TransactionCategoryGroup.INCOME,
                asset_linked=False,
            ),
        ],
        TransactionCategoryGroup.OTHER: [
            base.CategoryContext(
                TransactionCategory.id_to_uri(categories["securities traded"]),
                "securities traded",
                "Securities Traded",
                TransactionCategoryGroup.OTHER,
                asset_linked=True,
            ),
        ],
    }
    assert ctx["options_category"] == target


def test_ctx_options_selected(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    categories: dict[str, int],
) -> None:
    tbl_query = txn_controller.TableQuery(
        session.query(TransactionSplit),
        {},
        any_filters=False,
    )

    ctx = txn_controller.ctx_options(
        tbl_query,
        today,
        Account.map_name(session),
        base.tranaction_category_groups(session),
        account.uri,
        TransactionCategory.id_to_uri(categories["other income"]),
    )

    assert ctx["options_account"] == [base.NamePair(account.uri, account.name)]
    target = {
        TransactionCategoryGroup.INCOME: [
            base.CategoryContext(
                TransactionCategory.id_to_uri(categories["other income"]),
                "other income",
                "Other Income",
                TransactionCategoryGroup.INCOME,
                asset_linked=False,
            ),
        ],
    }
    assert ctx["options_category"] == target


@pytest.mark.parametrize(
    ("account", "period", "start", "end", "category", "uncleared", "target"),
    [
        (None, None, None, None, None, False, "Transactions"),
        ("Monkey Bank", None, None, None, None, False, "Transactions, Monkey Bank"),
        (None, "all", None, None, None, False, "All Transactions"),
        (None, "2000-01", None, None, None, False, "2000-01 Transactions"),
        (None, "2000", None, None, None, False, "2000 Transactions"),
        (None, "custom", None, None, None, False, "Transactions"),
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
    title = txn_controller._table_title(
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

    result = txn_controller._table_results(
        session.query(TransactionSplit),
        assets,
        Account.map_name(session),
        TransactionCategory.map_name_emoji(session),
        Label.map_name(session),
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
    labels = Label.map_name(session)
    categories = TransactionCategory.map_name_emoji(session)

    result = txn_controller._table_results(
        session.query(TransactionSplit).order_by(TransactionSplit.date_ord),
        assets,
        accounts,
        categories,
        labels,
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
                    {
                        label_id: labels[label_id]
                        for label_id, in session.query(LabelLink.label_id).where(
                            LabelLink.t_split_id == txn.splits[0].id_,
                        )
                    },
                    set(),
                ),
            ],
        )
        for txn in transactions[::-1]
    ]
    assert result == target


def test_ctx_table_empty(today: datetime.date, session: orm.Session) -> None:
    ctx, title = txn_controller.ctx_table(
        session,
        today,
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
    today: datetime.date,
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    ctx, title = txn_controller.ctx_table(
        session,
        today,
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
    today: datetime.date,
    monkeypatch: pytest.MonkeyPatch,
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    monkeypatch.setattr(txn_controller, "PAGE_LEN", 2)
    ctx, _ = txn_controller.ctx_table(
        session,
        today,
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
    today: datetime.date,
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    ctx, _ = txn_controller.ctx_table(
        session,
        today,
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
    today: datetime.date,
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    ctx, _ = txn_controller.ctx_table(
        session,
        today,
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
