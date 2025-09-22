from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus.controllers import base, spending
from nummus.models import (
    Account,
    Label,
    query_count,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from nummus.models import (
        Transaction,
    )


@pytest.mark.parametrize(
    (
        "include_account",
        "period",
        "start",
        "end",
        "category",
        "label",
        "is_income",
        "target",
    ),
    [
        (False, None, None, None, None, None, False, (3, False)),
        (False, None, None, None, None, None, True, (5, False)),
        (True, None, None, None, None, None, False, (3, True)),
        (False, "2000-01", None, None, None, None, False, (0, True)),
        (False, "2000", None, None, None, None, False, (0, True)),
        (False, "custom", None, None, None, None, False, (3, True)),
        (False, "custom", "2000-01-01", None, None, None, False, (3, True)),
        (False, "custom", None, "2000-01-01", None, None, False, (0, True)),
        (False, None, None, None, "groceries", None, False, (2, True)),
        (False, None, None, None, None, "apartments 4 U", False, (1, True)),
    ],
)
def test_data_query(
    session: orm.Session,
    account: Account,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
    labels: dict[str, int],
    include_account: bool,
    period: str | None,
    start: str | None,
    end: str | None,
    category: str | None,
    label: str | None,
    is_income: bool,
    target: tuple[int, bool],
) -> None:
    _ = transactions_spending
    dat_query = spending.data_query(
        session,
        account.uri if include_account else None,
        period,
        start,
        end,
        TransactionCategory.id_to_uri(categories[category]) if category else None,
        Label.id_to_uri(labels[label]) if label else None,
        is_income=is_income,
    )
    assert dat_query.any_filters == target[1]
    assert query_count(dat_query.final_query) == target[0]


def test_ctx_options(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
    categories: dict[str, int],
    labels: dict[str, int],
) -> None:
    _ = transactions
    dat_query = spending.DataQuery(
        session.query(TransactionSplit),
        {},
        any_filters=False,
    )

    ctx = spending.ctx_options(
        dat_query,
        today,
        Account.map_name(session),
        base.tranaction_category_groups(session),
        Label.map_name(session),
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
    assert ctx["options_label"] == [
        base.NamePair(Label.id_to_uri(labels["engineer"]), "engineer"),
    ]


def test_ctx_options_selected(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    categories: dict[str, int],
    labels: dict[str, int],
) -> None:
    dat_query = spending.DataQuery(
        session.query(TransactionSplit),
        {},
        any_filters=False,
    )

    ctx = spending.ctx_options(
        dat_query,
        today,
        Account.map_name(session),
        base.tranaction_category_groups(session),
        Label.map_name(session),
        account.uri,
        TransactionCategory.id_to_uri(categories["other income"]),
        Label.id_to_uri(labels["engineer"]),
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
    assert ctx["options_label"] == [
        base.NamePair(Label.id_to_uri(labels["engineer"]), "engineer"),
    ]


def test_ctx_chart_empty(
    today: datetime.date,
    account: Account,
    session: orm.Session,
) -> None:
    _ = account
    ctx, title = spending.ctx_chart(
        session,
        today,
        None,
        None,
        None,
        None,
        None,
        None,
        is_income=False,
    )

    assert title == "Spending"
    assert ctx["no_matches"]
    assert ctx["selected_period"] is None
    assert ctx["selected_account"] is None
    assert ctx["selected_category"] is None
    assert ctx["selected_label"] is None
    assert ctx["start"] is None
    assert ctx["end"] is None
    assert len(ctx["by_account"]) == 0
    assert len(ctx["by_payee"]) == 0
    assert len(ctx["by_category"]) == 0
    assert len(ctx["by_label"]) == 0


def test_ctx_chart(
    today: datetime.date,
    session: orm.Session,
    transactions_spending: list[Transaction],
) -> None:
    _ = transactions_spending
    ctx, title = spending.ctx_chart(
        session,
        today,
        None,
        None,
        None,
        None,
        None,
        None,
        is_income=False,
    )

    assert title == "Spending"
    assert not ctx["no_matches"]
    assert ctx["selected_period"] is None
    assert ctx["selected_account"] is None
    assert ctx["selected_category"] is None
    assert ctx["start"] is None
    assert ctx["end"] is None
    assert len(ctx["by_account"]) == 1
    assert len(ctx["by_payee"]) == 1
    assert len(ctx["by_category"]) == 2
    assert len(ctx["by_label"]) == 2
