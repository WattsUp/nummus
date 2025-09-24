"""Transaction controllers."""

from __future__ import annotations

import datetime
import operator
from collections import defaultdict
from decimal import Decimal
from typing import NamedTuple, NotRequired, TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func

from nummus import exceptions as exc
from nummus import utils, web
from nummus.controllers import base
from nummus.models import (
    Account,
    Asset,
    Label,
    LabelLink,
    obj_session,
    query_count,
    query_to_dict,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    update_rows_list,
    YIELD_PER,
)

if TYPE_CHECKING:
    import sqlalchemy
    from sqlalchemy import orm

PAGE_LEN = 25


class TxnContext(TypedDict):
    """Type definition for transaction context."""

    uri: str
    account: str
    account_uri: str
    accounts: list[base.NamePairState]
    cleared: bool
    date: datetime.date
    date_max: datetime.date
    amount: Decimal
    statement: str
    payee: str | None
    splits: list[SplitContext]
    category_groups: base.CategoryGroups
    payees: list[str]
    labels: list[str]
    similar_uri: str | None
    any_asset_splits: bool


class SplitContext(TypedDict):
    """Type definition for transaction split context."""

    parent_uri: str
    category_id: int
    category_uri: str
    memo: str | None
    labels: list[base.NamePair]
    amount: Decimal | None

    asset_name: NotRequired[str | None]
    asset_ticker: NotRequired[str | None]
    asset_price: NotRequired[Decimal | None]
    asset_quantity: NotRequired[Decimal | None]


class RowContext(SplitContext):
    """Type definition for transaction row context."""

    date: datetime.date
    account: str
    payee: str | None
    category: str
    cleared: bool
    is_split: bool


class OptionsContext(TypedDict):
    """Type definition for table options context."""

    options_period: list[base.NamePair]
    options_account: list[base.NamePair]
    options_category: base.CategoryGroups


class TableContext(OptionsContext):
    """Type definition for table context."""

    uri: str | None
    transactions: list[tuple[datetime.date, list[SplitContext]]]
    query_total: Decimal
    no_matches: bool
    next_page: str | None
    any_filters: bool
    search: str | None
    selected_period: str | None
    selected_account: str | None
    selected_category: str | None
    uncleared: bool
    start: str | None
    end: str | None


class TableQuery(NamedTuple):
    """Type definition for result of table_query()."""

    query: orm.Query[TransactionSplit]
    clauses: dict[str, sqlalchemy.ColumnElement]
    any_filters: bool

    @property
    def final_query(self) -> orm.Query[TransactionSplit]:
        """Build the final query with clauses."""
        return self.query.where(*self.clauses.values())

    def where(self, **clauses: sqlalchemy.ColumnElement) -> TableQuery:
        """Add clauses to query.

        Args:
            clauses: New clauses to add

        Returns:
            New TableQuery

        """
        new_clauses = self.clauses.copy()
        new_clauses.update(clauses)
        return TableQuery(self.query, new_clauses, any_filters=True)


def page_all() -> flask.Response:
    """GET /transactions.

    Returns:
        string HTML response

    """
    args = flask.request.args

    p = web.portfolio
    with p.begin_session() as s:
        txn_table, title = ctx_table(
            s,
            base.today_client(),
            args.get("search"),
            args.get("account"),
            args.get("category"),
            args.get("period"),
            args.get("start"),
            args.get("end"),
            args.get("page"),
            uncleared="uncleared" in args,
        )
    return base.page(
        "transactions/page-all.jinja",
        title=title,
        ctx=txn_table,
        endpoint="transactions.table",
    )


def table() -> str | flask.Response:
    """GET /h/transactions/table.

    Returns:
        HTML response with url set

    """
    args = flask.request.args
    first_page = "page" not in args
    p = web.portfolio
    with p.begin_session() as s:
        txn_table, title = ctx_table(
            s,
            base.today_client(),
            args.get("search"),
            args.get("account"),
            args.get("category"),
            args.get("period"),
            args.get("start"),
            args.get("end"),
            args.get("page"),
            uncleared="uncleared" in args,
        )
    html_title = f"<title>{title} - nummus</title>\n"
    html = html_title + flask.render_template(
        "transactions/table-rows.jinja",
        ctx=txn_table,
        endpoint="transactions.table",
        include_oob=first_page,
    )
    if not first_page:
        # Don't push URL for following pages
        return html
    response = flask.make_response(html)
    response.headers["HX-Push-URL"] = flask.url_for(
        "transactions.page_all",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **flask.request.args,
    )
    return response


def table_options() -> str:
    """GET /h/transactions/table-options.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        accounts = Account.map_name(s)

        args = flask.request.args
        uncleared = "uncleared" in args
        selected_account = args.get("account")
        selected_category = args.get("category")
        selected_period = args.get("period")
        selected_start = args.get("start")
        selected_end = args.get("end")

        tbl_query = table_query(
            s,
            None,
            selected_account,
            selected_period,
            selected_start,
            selected_end,
            selected_category,
            uncleared=uncleared,
        )
        options = ctx_options(
            tbl_query,
            base.today_client(),
            accounts,
            base.tranaction_category_groups(s),
            selected_account,
            selected_category,
        )

        return flask.render_template(
            "transactions/table-filters.jinja",
            only_inner=True,
            endpoint="transactions.table",
            ctx={
                **options,
                "selected_period": selected_period,
                "selected_account": selected_account,
                "selected_category": selected_category,
                "uncleared": uncleared,
                "start": selected_start,
                "end": selected_end,
            },
        )


def new() -> str | flask.Response:
    """GET, PUT, & POST /h/transactions/new.

    Returns:
        string HTML response

    """
    p = web.portfolio
    today = base.today_client()

    with p.begin_session() as s:
        query = (
            s.query(Account)
            .with_entities(Account.id_, Account.name)
            .where(Account.closed.is_(False))
            .order_by(Account.name)
        )
        accounts: dict[int, str] = query_to_dict(query)

        uncategorized_id, uncategorized_uri = TransactionCategory.uncategorized(s)

        query = s.query(Transaction.payee)
        payees = sorted(
            filter(None, (item for item, in query.distinct())),
            key=lambda item: item.lower(),
        )

        query = s.query(Label.name)
        labels = sorted(item for item, in query.distinct())

        empty_split: SplitContext = {
            "parent_uri": "",
            "category_id": uncategorized_id,
            "category_uri": uncategorized_uri,
            "memo": None,
            "labels": [],
            "amount": None,
        }
        ctx: TxnContext = {
            "uri": "",
            "account": "",
            "account_uri": flask.request.args.get("account") or "",
            "accounts": [
                base.NamePairState(Account.id_to_uri(acct_id), name, state=False)
                for acct_id, name in accounts.items()
            ],
            "cleared": False,
            "date": today,
            "date_max": today + datetime.timedelta(days=utils.DAYS_IN_WEEK),
            "amount": Decimal(),
            "statement": "Manually created",
            "payee": None,
            "splits": [empty_split],
            "category_groups": base.tranaction_category_groups(s),
            "payees": payees,
            "labels": labels,
            "similar_uri": None,
            "any_asset_splits": False,
        }

        if flask.request.method == "GET":
            return flask.render_template(
                "transactions/edit.jinja",
                txn=ctx,
            )

        if flask.request.method == "PUT":
            form = flask.request.form
            amount = utils.evaluate_real_statement(form["amount"]) or Decimal()
            ctx["account_uri"] = form.get("account") or ""
            ctx["amount"] = amount
            ctx["payee"] = form["payee"]
            try:
                ctx["date"] = utils.parse_date(form["date"]) or today
            except ValueError:
                ctx["date"] = today

            split_memos = form.getlist("memo")
            split_categories = [
                TransactionCategory.uri_to_id(x) for x in form.getlist("category")
            ]
            split_labels: list[set[str]] = [
                set(form.getlist(f"label-{i}")) for i in range(len(split_categories))
            ]
            split_amounts = [
                utils.evaluate_real_statement(x) for x in form.getlist("split-amount")
            ]
            if len(split_categories) == 1:
                split_amounts = [amount]

            split_sum = sum(filter(None, split_amounts)) or Decimal()
            remaining = amount - split_sum
            splits: list[SplitContext] = [
                {
                    "parent_uri": "",
                    "category_id": cat_id,
                    "category_uri": TransactionCategory.id_to_uri(cat_id),
                    "memo": memo,
                    "labels": sorted(
                        [base.NamePair("", label) for label in labels],
                        key=operator.itemgetter(1),
                    ),
                    "amount": amount,
                }
                for cat_id, memo, labels, amount in zip(
                    split_categories,
                    split_memos,
                    split_labels,
                    split_amounts,
                    strict=True,
                )
            ]
            headline_error = (
                (
                    f"Assign {utils.format_financial(remaining)} to splits"
                    if remaining > 0
                    else f"Remove {utils.format_financial(-remaining)} from splits"
                )
                if remaining != 0
                else ""
            )
            splits.extend(
                [empty_split] * 3,
            )
            ctx["splits"] = splits
            return flask.render_template(
                "transactions/edit.jinja",
                txn=ctx,
                headline_error=headline_error,
            )

        try:
            with s.begin_nested():
                txn = Transaction(
                    statement="Manually added",
                )
                if err := _transaction_edit(txn, today):
                    return base.error(err)
                s.add(txn)
                s.flush()
                if err := _transaction_split_edit(s, txn):
                    return base.error(err)
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return base.error(e)

        return base.dialog_swap(
            # account since transaction was created
            event="account",
            snackbar="Transaction created",
        )


def transaction(uri: str) -> str | flask.Response:
    """GET, PUT, & DELETE /h/transactions/t/<uri>.

    Args:
        uri: URI of Transaction

    Returns:
        string HTML response

    """
    p = web.portfolio
    today = base.today_client()
    with p.begin_session() as s:
        txn = base.find(s, Transaction, uri)

        if flask.request.method == "GET":
            return flask.render_template(
                "transactions/edit.jinja",
                txn=ctx_txn(txn, today),
            )
        if flask.request.method == "DELETE":
            if txn.cleared:
                return base.error("Cannot delete cleared transaction")
            date = txn.date
            query = s.query(TransactionSplit.id_).where(
                TransactionSplit.parent_id == txn.id_,
            )
            t_split_ids = {r[0] for r in query.yield_per(YIELD_PER)}
            s.query(LabelLink).where(LabelLink.t_split_id.in_(t_split_ids)).delete()
            s.query(TransactionSplit).where(
                TransactionSplit.id_.in_(t_split_ids),
            ).delete()
            s.delete(txn)
            return base.dialog_swap(
                # update-account since transaction was deleted
                event="account",
                snackbar=f"Transaction on {date} deleted",
            )

        try:
            amount_before = txn.amount
            with s.begin_nested():
                if err := _transaction_edit(txn, today):
                    return base.error(err)
                s.flush()
                if err := _transaction_split_edit(s, txn):
                    return base.error(err)
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return base.error(e)

        return base.dialog_swap(
            event="account" if txn.amount != amount_before else "transaction",
            snackbar="All changes saved",
        )


def _transaction_edit(txn: Transaction, today: datetime.date) -> str:
    """Edit transaction from form.

    Args:
        txn: Transaction to edit
        today: Today's date

    Returns:
        Error string or ""

    """
    form = flask.request.form

    try:
        txn.date = base.parse_date(form["date"], today)
    except ValueError as e:
        return str(e)
    txn.payee = form["payee"]

    if not txn.cleared:
        amount = utils.evaluate_real_statement(form["amount"])
        if amount is None:
            return "Amount must not be empty"
        txn.amount = amount
        account = form["account"]
        if not account:
            return "Account must not be empty"
        acct_id = Account.uri_to_id(account)
        txn.account_id = acct_id
    return ""


def _transaction_split_edit(s: orm.Session, txn: Transaction) -> str:
    """Edit transaction from form.

    Args:
        s: SQL session to use
        txn: Transaction to edit

    Returns:
        Error string or ""

    """
    form = flask.request.form

    split_memos = form.getlist("memo")
    split_categories = [
        TransactionCategory.uri_to_id(x) for x in form.getlist("category")
    ]
    split_amounts = [
        utils.evaluate_real_statement(x) for x in form.getlist("split-amount")
    ]

    if len(split_categories) < 1:
        return "Must have at least one split"
    if len(split_categories) == 1:
        split_amounts = [txn.amount]

    remaining = txn.amount - sum(filter(None, split_amounts))
    if remaining > 0:
        return f"Assign {utils.format_financial(remaining)} to splits"
    if remaining < 0:
        return f"Remove {utils.format_financial(-remaining)} from splits"

    splits = [
        {
            "parent": txn,
            "category_id": cat_id,
            "memo": memo,
            "amount": amount,
        }
        for cat_id, memo, amount in zip(
            split_categories,
            split_memos,
            split_amounts,
            strict=True,
        )
        if amount
    ]
    query = (
        s.query(TransactionSplit)
        .where(TransactionSplit.parent_id == txn.id_)
        .order_by(TransactionSplit.id_)
    )
    t_split_ids = update_rows_list(
        s,
        TransactionSplit,
        query,
        splits,
    )
    s.flush()
    LabelLink.add_links(
        s,
        {
            t_split_id: set(form.getlist(f"label-{i}"))
            for i, t_split_id in enumerate(t_split_ids)
        },
    )

    return ""


def split(uri: str) -> str:
    """PUT /h/transactions/<uri>/split.

    Args:
        uri: Transaction URI

    Returns:
        string HTML response

    """
    p = web.portfolio
    form = flask.request.form

    with p.begin_session() as s:
        txn = base.find(s, Transaction, uri)

        parent_amount = utils.parse_real(form["amount"]) or Decimal()
        account_id = Account.uri_to_id(form["account"])
        payee = form["payee"]
        date = utils.parse_date(form["date"])

        split_memos: list[str | None] = list(form.getlist("memo"))
        split_categories: list[str | None] = list(form.getlist("category"))
        split_amounts: list[Decimal | None] = [
            utils.evaluate_real_statement(x) for x in form.getlist("split-amount")
        ]
        split_labels: list[set[str]] = [
            set(form.getlist(f"label-{i}")) for i in range(len(split_categories))
        ]
        if len(split_categories) == 1:
            split_amounts = [parent_amount]

        for _ in range(3):
            split_memos.append(None)
            split_categories.append(None)
            split_labels.append(set())
            split_amounts.append(None)

        _, uncategorized_uri = TransactionCategory.uncategorized(s)

        ctx_splits: list[SplitContext] = []
        for memo, cat_uri, labels, amount in zip(
            split_memos,
            split_categories,
            split_labels,
            split_amounts,
            strict=True,
        ):
            item: SplitContext = {
                "parent_uri": uri,
                "category_id": 0,
                "category_uri": cat_uri or uncategorized_uri,
                "memo": memo,
                "labels": sorted(
                    [base.NamePair("", label) for label in labels],
                    key=operator.itemgetter(1),
                ),
                "amount": amount,
                "asset_name": None,
                "asset_ticker": None,
                "asset_price": None,
                "asset_quantity": None,
            }
            ctx_splits.append(item)

        split_sum = sum(filter(None, split_amounts)) or Decimal()

        remaining = parent_amount - split_sum
        headline_error = (
            (
                f"Sum of splits {utils.format_financial(split_sum)} "
                f"not equal to total {utils.format_financial(parent_amount)}. "
                f"{utils.format_financial(remaining)} to assign"
            )
            if remaining != 0
            else ""
        )

        ctx = ctx_txn(
            txn,
            base.today_client(),
            amount=parent_amount,
            account_id=account_id,
            payee=payee,
            date=date,
            splits=ctx_splits,
        )

        return flask.render_template(
            "transactions/edit.jinja",
            txn=ctx,
            headline_error=headline_error,
        )


def validation() -> str:
    """GET /h/transactions/validation.

    Returns:
        string HTML response

    """
    # dict{key: required}
    properties: dict[str, bool] = {
        "payee": True,
        "memo": False,
        "label": False,
    }

    args = flask.request.args
    for key, required in properties.items():
        if key not in args:
            continue
        return base.validate_string(
            args[key],
            is_required=required,
        )

    if "date" in args:
        return base.validate_date(
            args["date"],
            base.today_client(),
            is_required=True,
        )

    validate_splits = False
    if "split" in args:
        # Editing a split
        if err := base.validate_real(args["split-amount"]):
            return err
        validate_splits = True
    elif "amount" in args:
        # Editing a split
        if err := base.validate_real(
            args["amount"],
            is_required=True,
        ):
            return err
        validate_splits = True
    else:
        raise NotImplementedError

    if validate_splits:
        parent_amount = utils.evaluate_real_statement(args["amount"]) or Decimal()
        split_amounts = [
            utils.evaluate_real_statement(x) for x in args.getlist("split-amount")
        ]
        if len(split_amounts) == 0:
            # No splits is okay for single split
            msg = ""
        else:
            split_sum = sum(filter(None, split_amounts)) or Decimal()

            remaining = parent_amount - split_sum
            msg = (
                (
                    f"Assign {utils.format_financial(remaining)} to splits"
                    if remaining > 0
                    else f"Remove {utils.format_financial(-remaining)} from splits"
                )
                if remaining != 0
                else ""
            )

        # Render sum of splits to headline since its a global error
        return flask.render_template(
            "shared/dialog-headline-error.jinja",
            oob=True,
            headline_error=msg,
        )

    raise NotImplementedError


def table_query(
    s: orm.Session,
    acct_uri: str | None = None,
    selected_account: str | None = None,
    selected_period: str | None = None,
    selected_start: str | None = None,
    selected_end: str | None = None,
    selected_category: str | None = None,
    *,
    uncleared: bool | None = False,
) -> TableQuery:
    """Create transactions table query.

    Args:
        s: SQL session to use
        acct_uri: Account URI to filter to
        selected_account: URI of account from args
        selected_period: Name of period from args
        selected_start: ISO date string of start from args
        selected_end: ISO date string of end from args
        selected_category: URI of category from args
        uncleared: True will only query uncleared transactions

    Returns:
        TableQuery

    """
    selected_account = acct_uri or selected_account
    query = s.query(TransactionSplit).order_by(
        TransactionSplit.date_ord.desc(),
        TransactionSplit.account_id,
        TransactionSplit.payee,
        TransactionSplit.category_id,
        TransactionSplit.memo,
    )
    clauses: dict[str, sqlalchemy.ColumnElement] = {}

    any_filters = False

    start = None
    end = None
    if selected_period and selected_period != "all":
        any_filters = True
        if selected_period == "custom":
            start = utils.parse_date(selected_start)
            end = utils.parse_date(selected_end)
        elif "-" in selected_period:
            start = datetime.date.fromisoformat(selected_period + "-01")
            end = utils.end_of_month(start)
        else:
            year = int(selected_period)
            start = datetime.date(year, 1, 1)
            end = datetime.date(year, 12, 31)

        if start:
            clauses["start"] = TransactionSplit.date_ord >= start.toordinal()
        if end:
            clauses["end"] = TransactionSplit.date_ord <= end.toordinal()

    if selected_account:
        any_filters |= acct_uri is None
        clauses["account"] = TransactionSplit.account_id == Account.uri_to_id(
            selected_account,
        )

    if selected_category:
        any_filters = True
        cat_id = TransactionCategory.uri_to_id(selected_category)
        clauses["category"] = TransactionSplit.category_id == cat_id

    if uncleared:
        any_filters = True
        clauses["cleared"] = TransactionSplit.cleared.is_(False)

    return TableQuery(query, clauses, any_filters)


def ctx_txn(
    txn: Transaction,
    today: datetime.date,
    *,
    amount: Decimal | None = None,
    account_id: int | None = None,
    payee: str | None = None,
    date: datetime.date | None = None,
    splits: list[SplitContext] | None = None,
) -> TxnContext:
    """Get the context to build the transaction edit dialog.

    Args:
        txn: Transaction to build context for
        today: Today's date
        amount: Override context amount
        account_id: Override context account
        payee: Override context payee
        date: Override context date
        splits: Override context splits

    Returns:
        Dictionary HTML context

    """
    s = obj_session(txn)

    account_id = txn.account_id if account_id is None else account_id

    query = (
        s.query(Account)
        .with_entities(
            Account.id_,
            Account.name,
            Account.closed,
        )
        .order_by(Account.name)
    )
    accounts: dict[int, tuple[str, bool]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }
    query = s.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
    assets: dict[int, tuple[str, str | None]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }
    query = s.query(Label.id_, Label.name)
    labels: dict[int, str] = query_to_dict(query)

    query = (
        s.query(LabelLink)
        .with_entities(LabelLink.t_split_id, LabelLink.label_id)
        .where(LabelLink.t_split_id.in_(t_split.id_ for t_split in txn.splits))
    )
    label_links: dict[int, set[int]] = defaultdict(set)
    for t_split_id, label_id in query.yield_per(YIELD_PER):
        label_links[t_split_id].add(label_id)

    ctx_splits: list[SplitContext] = (
        [
            ctx_split(
                t_split,
                assets,
                {label_id: labels[label_id] for label_id in label_links[t_split.id_]},
            )
            for t_split in txn.splits
        ]
        if splits is None
        else splits
    )
    any_asset_splits = any(split.get("asset_name") for split in ctx_splits)

    query = s.query(Transaction.payee)
    payees = sorted(
        filter(None, (item for item, in query.distinct())),
        key=lambda item: item.lower(),
    )

    # Run similar transaction
    similar_id = txn.find_similar(set_property=False)
    similar_uri = None if similar_id is None else Transaction.id_to_uri(similar_id)
    return {
        "uri": txn.uri,
        "account": accounts[account_id][0],
        "account_uri": Account.id_to_uri(account_id),
        "accounts": [
            base.NamePairState(Account.id_to_uri(acct_id), name, closed)
            for acct_id, (name, closed) in accounts.items()
        ],
        "cleared": txn.cleared,
        "date": date or txn.date,
        "date_max": today + datetime.timedelta(days=utils.DAYS_IN_WEEK),
        "amount": txn.amount if amount is None else amount,
        "statement": txn.statement,
        "payee": txn.payee if payee is None else payee,
        "splits": ctx_splits,
        "category_groups": base.tranaction_category_groups(s),
        "payees": payees,
        "labels": sorted(labels.values()),
        "similar_uri": similar_uri,
        "any_asset_splits": any_asset_splits,
    }


def ctx_split(
    t_split: TransactionSplit,
    assets: dict[int, tuple[str, str | None]],
    labels: dict[int, str],
) -> SplitContext:
    """Get the context to build the transaction edit dialog.

    Args:
        t_split: TransactionSplit to build context for
        assets: Dict {id: (asset name, ticker)}
        labels: Labels for TransactionSplit

    Returns:
        Dictionary HTML context

    """
    qty = t_split.asset_quantity or Decimal()
    if t_split.asset_id:
        asset_name, asset_ticker = assets[t_split.asset_id]
    else:
        asset_name = None
        asset_ticker = None
    return {
        "parent_uri": Transaction.id_to_uri(t_split.parent_id),
        "amount": t_split.amount,
        "category_id": t_split.category_id,
        "category_uri": TransactionCategory.id_to_uri(t_split.category_id),
        "memo": t_split.memo,
        "labels": sorted(
            [
                base.NamePair(Label.id_to_uri(label_id), name)
                for label_id, name in labels.items()
            ],
            key=operator.itemgetter(1),
        ),
        "asset_name": asset_name,
        "asset_ticker": asset_ticker,
        "asset_price": abs(t_split.amount / qty) if qty else None,
        "asset_quantity": qty,
    }


def ctx_row(
    t_split: TransactionSplit,
    assets: dict[int, tuple[str, str | None]],
    accounts: dict[int, str],
    categories: dict[int, str],
    labels: dict[int, str],
    split_parents: set[int],
) -> RowContext:
    """Get the context to build the transaction edit dialog.

    Args:
        t_split: TransactionSplit to build context for
        assets: Dict {id: (asset name, ticker)}
        accounts: Account name mapping
        categories: Category name mapping
        labels: Labels for TransactionSplit
        split_parents: Set {Transaction.id_ that have more than 1 TransactionSplit}

    Returns:
        Dictionary HTML context

    """
    return {
        **ctx_split(t_split, assets, labels),
        "date": t_split.date,
        "account": accounts[t_split.account_id],
        "category": categories[t_split.category_id],
        "payee": t_split.payee,
        "cleared": t_split.cleared,
        "is_split": t_split.parent_id in split_parents,
    }


def ctx_options(
    tbl_query: TableQuery,
    today: datetime.date,
    accounts: dict[int, str],
    categories: base.CategoryGroups,
    selected_account: str | None = None,
    selected_category: str | None = None,
) -> OptionsContext:
    """Get the context to build the options for table.

    Args:
        tbl_query: Query to use to get distinct values
        today: Today's date
        accounts: Account name mapping
        categories: TransactionCategory name mapping
        selected_account: URI of account from args
        selected_category: URI of category from args

    Returns:
        OptionsContext

    """
    query = tbl_query.query.order_by(None)

    month = utils.start_of_month(today)
    last_months = [utils.date_add_months(month, i) for i in range(0, -3, -1)]
    options_period = [
        base.NamePair("all", "All time"),
        *(base.NamePair(m.isoformat()[:7], f"{m:%B}") for m in last_months),
        base.NamePair(str(month.year), str(month.year)),
        base.NamePair(str(month.year - 1), str(month.year - 1)),
        base.NamePair("custom", "Custom date range"),
    ]

    clauses = tbl_query.clauses.copy()
    clauses.pop("account", None)
    query_options = (
        query.with_entities(TransactionSplit.account_id)
        .where(*clauses.values())
        .distinct()
    )
    options_account = sorted(
        [
            base.NamePair(Account.id_to_uri(acct_id), accounts[acct_id])
            for acct_id, in query_options.yield_per(YIELD_PER)
        ],
        key=operator.itemgetter(0),
    )
    if len(options_account) == 0 and selected_account:
        acct_id = Account.uri_to_id(selected_account)
        options_account = [base.NamePair(selected_account, accounts[acct_id])]

    clauses = tbl_query.clauses.copy()
    clauses.pop("category", None)
    query_options = (
        query.with_entities(TransactionSplit.category_id)
        .where(*clauses.values())
        .distinct()
    )
    options_uris = {
        TransactionCategory.id_to_uri(r[0]) for r in query_options.yield_per(YIELD_PER)
    }
    if selected_category:
        options_uris.add(selected_category)
    options_category = {
        group: [cat for cat in items if cat.uri in options_uris]
        for group, items in categories.items()
    }
    options_category = {
        group: sorted(items, key=operator.attrgetter("name"))
        for group, items in options_category.items()
        if items
    }

    return {
        "options_period": options_period,
        "options_account": options_account,
        "options_category": options_category,
    }


def ctx_table(
    s: orm.Session,
    today: datetime.date,
    search_str: str | None,
    selected_account: str | None,
    selected_category: str | None,
    selected_period: str | None,
    selected_start: str | None,
    selected_end: str | None,
    page_start: str | None,
    *,
    uncleared: bool,
    acct_uri: str | None = None,
) -> tuple[TableContext, str]:
    """Get the context to build the transaction table.

    Args:
        s: SQL session to use
        today: Today's date
        search_str: String to search for
        selected_account: Selected account for filtering
        selected_category: Selected category for filtering
        selected_period: Selected period for filtering
        selected_start: Selected start date for custom period
        selected_end: Selected end date for custom period
        page_start: Offset or date_ord of page
        uncleared: True will filter to only uncleared
        acct_uri: Account uri to get transactions for, None will use filter queries

    Returns:
        tuple(TableContext, title)

    """
    accounts = Account.map_name(s)
    categories_emoji = TransactionCategory.map_name_emoji(s)
    categories = {
        cat_id: TransactionCategory.clean_emoji_name(name)
        for cat_id, name in categories_emoji.items()
    }
    query = s.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
    assets: dict[int, tuple[str, str | None]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }
    labels = Label.map_name(s)

    if page_start is None:
        page_start_int = None
    else:
        try:
            page_start_int = int(page_start)
        except ValueError:
            page_start_int = datetime.date.fromisoformat(page_start).toordinal()

    tbl_query = table_query(
        s,
        acct_uri,
        selected_account,
        selected_period,
        selected_start,
        selected_end,
        selected_category,
        uncleared=uncleared,
    )
    options = ctx_options(
        tbl_query,
        today,
        accounts,
        base.tranaction_category_groups(s),
        selected_account,
        selected_category,
    )

    # Do search
    try:
        matches = TransactionSplit.search(
            tbl_query.final_query,
            search_str or "",
            categories,
        )
    except exc.EmptySearchError:
        matches = None

    if matches is not None:
        tbl_query = tbl_query.where(search=TransactionSplit.id_.in_(matches))
        t_split_order = {t_split_id: i for i, t_split_id in enumerate(matches)}
    else:
        t_split_order = {}

    final_query = tbl_query.final_query
    query_total = final_query.with_entities(func.sum(TransactionSplit.amount))

    if matches is not None:
        i_start = page_start_int or 0
        page = matches[i_start : i_start + PAGE_LEN]
        final_query = final_query.where(TransactionSplit.id_.in_(page))
        next_page = i_start + PAGE_LEN
    else:
        # Find the fewest dates to include that will make page at least
        # PAGE_LEN long
        included_date_ords: set[int] = set()
        query_page_count = final_query.with_entities(
            TransactionSplit.date_ord,
            func.count(),
        ).group_by(TransactionSplit.date_ord)
        if page_start_int:
            query_page_count = query_page_count.where(
                TransactionSplit.date_ord <= page_start_int,
            )
        page_count = 0
        # Limit to PAGE_LEN since at most there is one txn per day
        for date_ord, count in query_page_count.limit(PAGE_LEN).yield_per(
            YIELD_PER,
        ):
            included_date_ords.add(date_ord)
            page_count += count
            if page_count >= PAGE_LEN:
                break

        final_query = final_query.where(
            TransactionSplit.date_ord.in_(included_date_ords),
        )

        next_page = (
            None
            if len(included_date_ords) == 0
            else datetime.date.fromordinal(min(included_date_ords) - 1)
        )

    n_matches = query_count(final_query)
    groups = _table_results(
        final_query,
        assets,
        accounts,
        categories_emoji,
        labels,
        t_split_order,
    )
    title = _table_title(
        selected_account and accounts[Account.uri_to_id(selected_account)],
        selected_period,
        selected_start,
        selected_end,
        selected_category
        and categories_emoji[TransactionCategory.uri_to_id(selected_category)],
        uncleared=uncleared,
    )
    return {
        "uri": acct_uri,
        "transactions": groups,
        "query_total": query_total.scalar() or Decimal(),
        "no_matches": n_matches == 0 and page_start_int is None,
        "next_page": None if n_matches < PAGE_LEN else str(next_page),
        "any_filters": tbl_query.any_filters,
        "search": search_str,
        **options,
        "selected_period": selected_period,
        "selected_account": selected_account,
        "selected_category": selected_category,
        "uncleared": uncleared,
        "start": selected_start,
        "end": selected_end,
    }, title


def _table_results(
    query: orm.Query[TransactionSplit],
    assets: dict[int, tuple[str, str | None]],
    accounts: dict[int, str],
    categories: dict[int, str],
    labels: dict[int, str],
    t_split_order: dict[int, int],
) -> list[tuple[datetime.date, list[SplitContext]]]:
    """Get the table results from query.

    Args:
        query: TransactionSplit query for table
        assets: Dict {id: (asset name, ticker)}
        accounts: Account name mapping
        categories: Account name mapping
        labels: Label name mapping
        t_split_order: Mapping of id_ to order if it matters

    Returns:
        TransactionSplits grouped by date
        list[(
            date,
            list[SplitContext],
        )]

    """
    s = query.session

    # Iterate first to get required second query
    t_splits: list[TransactionSplit] = []
    parent_ids: set[int] = set()
    for t_split in query.yield_per(YIELD_PER):
        t_splits.append(t_split)
        parent_ids.add(t_split.parent_id)

    # There are no more if there wasn't enough for a full page

    query_has_splits = (
        s.query(Transaction.id_)
        .join(TransactionSplit)
        .where(
            Transaction.id_.in_(parent_ids),
        )
        .group_by(Transaction.id_)
        .having(func.count() > 1)
    )
    has_splits = {r[0] for r in query_has_splits.yield_per(YIELD_PER)}

    query_labels = (
        s.query(LabelLink)
        .with_entities(LabelLink.t_split_id, LabelLink.label_id)
        .where(LabelLink.t_split_id.in_(t_split.id_ for t_split in t_splits))
    )
    label_links: dict[int, set[int]] = defaultdict(set)
    for t_split_id, label_id in query_labels.yield_per(YIELD_PER):
        label_links[t_split_id].add(label_id)

    t_splits_flat: list[tuple[RowContext, int]] = []
    for t_split in t_splits:
        t_split_ctx = ctx_row(
            t_split,
            assets,
            accounts,
            categories,
            {label_id: labels[label_id] for label_id in label_links[t_split.id_]},
            has_splits,
        )
        t_splits_flat.append(
            (t_split_ctx, t_split_order.get(t_split.id_, -t_split.date_ord)),
        )

    # sort by reverse date or search ranking
    t_splits_flat = sorted(t_splits_flat, key=operator.itemgetter(1))

    # Split by date boundaries but don't put dates together
    # since that messes up search ranking
    last_date: datetime.date | None = None
    groups: list[tuple[datetime.date, list[SplitContext]]] = []
    current_group: list[SplitContext] = []
    for t_split_ctx, _ in t_splits_flat:
        date = t_split_ctx["date"]
        if last_date and date != last_date:
            groups.append((last_date, current_group))
            current_group = []
        current_group.append(t_split_ctx)
        last_date = date
    if last_date and current_group:
        groups.append((last_date, current_group))

    return groups


def _table_title(
    account: str | None,
    period: str | None,
    start: str | None,
    end: str | None,
    category: str | None,
    *,
    uncleared: bool,
) -> str:
    """Create the table title.

    Args:
        account: Selected account name
        period: Selected period
        start: Selected start date
        end: Selected stop date
        category: Selected category name
        uncleared: Uncleared only or not

    Returns:
        Title string

    """
    if not period:
        title = ""
    elif period != "custom":
        title = period.title()
    elif start and end:
        title = f"{start} to {end}"
    elif start:
        title = f"from {start}"
    elif end:
        title = f"to {end}"
    else:
        title = ""
    title += " Transactions"

    if account:
        title += f", {account}"
    if category:
        title += f", {category}"
    if uncleared:
        title += ", Uncleared"
    return title.strip()


ROUTES: base.Routes = {
    "/transactions": (page_all, ["GET"]),
    "/h/transactions/table": (table, ["GET"]),
    "/h/transactions/table-options": (table_options, ["GET"]),
    "/h/transactions/new": (new, ["GET", "PUT", "POST"]),
    "/h/transactions/validation": (validation, ["GET"]),
    "/h/transactions/t/<path:uri>": (transaction, ["GET", "PUT", "DELETE"]),
    "/h/transactions/t/<path:uri>/split": (split, ["PUT"]),
}
