"""Transaction controllers
"""

import datetime
from decimal import Decimal

import flask
from rapidfuzz import process
import sqlalchemy
from sqlalchemy import orm

from nummus import portfolio, web_utils
from nummus import custom_types as t
from nummus.controllers import common
from nummus.models import (Account, Transaction, TransactionCategory,
                           TransactionSplit, paginate, search)


def page_all() -> str:
  """GET /transactions

  Returns:
    string HTML response
  """
  return flask.render_template(
      "transactions/index.html",
      sidebar=common.ctx_sidebar(),
      txn_table=ctx_table(),
  )


def table() -> str:
  """GET /h/transactions/table

  Returns:
    string HTML response
  """
  return flask.render_template(
      "transactions/table.html",
      txn_table=ctx_table(),
      include_oob=True,
  )


def options(field: str) -> str:
  """GET /h/transactions/options/<field>

  Args:
    field: Name of field to get options for

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    args = flask.request.args

    id_mapping = None
    if field == "account":
      id_mapping = Account.map_name(s)
    elif field == "category":
      id_mapping = TransactionCategory.map_name(s)

    period = args.get("period", "this-month")
    start, end = web_utils.parse_period(period, args.get("start"),
                                        args.get("end"))

    query = s.query(TransactionSplit)
    query = query.where(TransactionSplit.asset_id.is_(None))
    if start is not None:
      query = query.where(TransactionSplit.date >= start)
    query = query.where(TransactionSplit.date <= end)

    search_str = args.get(f"search-{field}")

    return flask.render_template(
        "transactions/table-options.html",
        options=ctx_options(query, field, id_mapping, search_str=search_str),
        name=field,
        search_str=search_str,
    )


def ctx_options(query: orm.Query,
                field: str,
                id_mapping: t.DictIntStr = None,
                search_str: str = None) -> t.List[t.DictStr]:
  """Get the context to build the options for table

  Args:
    s: Session to use
    query: Query to use to get distinct values
    id_mapping: Item ID to name mapping
    search_str: Search options and hide non-matches

  Returns:
    List of HTML context
  """
  query = query.order_by(None)
  args = flask.request.args
  selected: t.Strings = args.getlist(field)
  options_: t.List[t.DictStr] = []
  entities = {
      "account": TransactionSplit.account_id,
      "payee": TransactionSplit.payee,
      "category": TransactionSplit.category_id,
      "tag": TransactionSplit.tag,
  }
  for name, in query.with_entities(entities[field]).distinct():
    if name is None:
      continue
    if id_mapping is not None:
      name = id_mapping[name]
    options_.append({
        "name": name,
        "checked": name in selected,
        "hidden": False,
        "score": 0,
    })
  if search_str not in [None, ""]:
    names = {i: item["name"] for i, item in enumerate(options_)}
    extracted = process.extract(search_str,
                                names,
                                limit=None,
                                processor=lambda s: s.lower())
    for _, score, i in extracted:
      options_[i]["score"] = score
      options_[i]["hidden"] = score < 60

  return sorted(options_,
                key=lambda item:
                (-item["score"], not item["checked"], item["name"]))


def ctx_table() -> t.DictStr:
  """Get the context to build the transaction table

  Returns:
    Dictionary HTML context
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    args = flask.request.args

    accounts = Account.map_name(s)
    categories = TransactionCategory.map_name(s)

    period = args.get("period", "this-month")
    start, end = web_utils.parse_period(period, args.get("start"),
                                        args.get("end"))
    search_str = args.get("search", "").strip()
    locked = web_utils.parse_bool(args.get("locked"))

    page_len = 25
    offset = int(args.get("offset", 0))
    page_total = Decimal(0)

    query = s.query(TransactionSplit)
    query = query.where(TransactionSplit.asset_id.is_(None))
    if start is not None:
      query = query.where(TransactionSplit.date >= start)
    query = query.where(TransactionSplit.date <= end)
    query = query.order_by(TransactionSplit.date)

    # Get options with these filters
    options_account = ctx_options(query, "account", accounts)
    options_payee = ctx_options(query, "payee")
    options_category = ctx_options(query, "category", categories)
    options_tag = ctx_options(query, "tag")

    selected_accounts = args.getlist("account")
    selected_payees = args.getlist("payee")
    selected_categories = args.getlist("category")
    selected_tags = args.getlist("tag")

    if len(selected_accounts) != 0:
      ids = [
          acct_id for acct_id, name in accounts.items()
          if name in selected_accounts
      ]
      query = query.where(TransactionSplit.account_id.in_(ids))

    if len(selected_payees) != 0:
      query = query.where(TransactionSplit.payee.in_(selected_payees))

    if len(selected_categories) != 0:
      ids = [
          cat_id for cat_id, name in categories.items()
          if name in selected_categories
      ]
      query = query.where(TransactionSplit.category_id.in_(ids))

    if len(selected_tags) != 0:
      query = query.where(TransactionSplit.tag.in_(selected_tags))

    if locked is not None:
      query = query.where(TransactionSplit.locked == locked)

    if search_str != "":
      query = search(query, TransactionSplit, search_str)

    page, count, offset_next = paginate(query, page_len, offset)

    query = query.with_entities(sqlalchemy.func.sum(TransactionSplit.amount))  # pylint: disable=not-callable
    query_total = query.scalar() or Decimal(0)

    if start is None:
      query = s.query(TransactionSplit)
      query = query.where(TransactionSplit.asset_id.is_(None))
      query = query.with_entities(sqlalchemy.func.min(TransactionSplit.date))  # pylint: disable=not-callable
      start = query.scalar() or datetime.date(1970, 1, 1)

    transactions: t.List[t.DictAny] = []
    for t_split in page:
      t_split: TransactionSplit
      t_split_ctx = ctx_split(t_split, accounts, categories)
      page_total += t_split.amount

      transactions.append(t_split_ctx)

    offset_last = max(0, (count // page_len) * page_len)

    return {
        "transactions": transactions,
        "count": count,
        "offset": offset,
        "i_first": 0 if count == 0 else offset + 1,
        "i_last": min(offset + page_len, count),
        "page_len": page_len,
        "page_total": page_total,
        "query_total": query_total,
        "offset_first": "offset=0",
        "offset_prev": f"offset={max(0, offset - page_len)}",
        "offset_next": f"offset={offset_next or offset_last}",
        "offset_last": f"offset={offset_last}",
        "start": start,
        "end": end,
        "period": period,
        "search": search_str,
        "locked": locked,
        "options-account": options_account,
        "options-payee": options_payee,
        "options-category": options_category,
        "options-tag": options_tag,
    }


def ctx_split(t_split: TransactionSplit, accounts: t.DictIntStr,
              categories: t.DictIntStr) -> t.DictStr:
  """Get the context to build the transaction edit dialog

  Returns:
    Dictionary HTML context
  """
  return {
      "uuid": t_split.uuid,
      "date": t_split.date,
      "account": accounts[t_split.account_id],
      "payee": t_split.payee,
      "description": t_split.description,
      "category": categories[t_split.category_id],
      "tag": t_split.tag,
      "amount": t_split.amount,
      "locked": t_split.locked
  }


def edit(path_uuid: str) -> str:
  """GET & POST /h/transactions/t/<path_uuid>/edit

  Args:
    path_uuid: UUID of TransactionSplit

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  if flask.request.method == "POST":
    form = flask.request.form
    print(form)

  with p.get_session() as s:
    accounts = Account.map_name(s)
    categories = TransactionCategory.map_name(s)

    parent: Transaction = web_utils.find(s,
                                         Transaction,
                                         path_uuid,
                                         do_raise=False)
    if parent is None:
      child: TransactionSplit = web_utils.find(s, TransactionSplit, path_uuid)
      parent = child.parent

    parent_ctx = {
        "uuid": parent.uuid,
        "account": accounts[parent.account_id],
        "locked": parent.locked,
        "date": parent.date,
        "amount": parent.amount,
    }

    splits = parent.splits

    splits_ctx: t.List[t.DictStr] = [
        ctx_split(t_split, accounts, categories) for t_split in splits
    ]

    query = s.query(TransactionSplit.payee)
    query = query.where(TransactionSplit.asset_id.is_(None))
    payees = sorted(item for item, in query.distinct())

    query = s.query(TransactionSplit.tag)
    query = query.where(TransactionSplit.asset_id.is_(None))
    tags = sorted(item for item, in query.distinct() if item is not None)

    return flask.render_template(
        "transactions/edit.html",
        splits=splits_ctx,
        parent=parent_ctx,
        payees=payees,
        categories=categories.values(),
        tags=tags,
    )


def view(path_uuid: str) -> str:
  """GET /h/transactions/t/<path_uuid>

  Args:
    path_uuid: UUID of TransactionSplit

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    accounts = Account.map_name(s)
    categories = TransactionCategory.map_name(s)

    t_split: TransactionSplit = web_utils.find(s, TransactionSplit, path_uuid)

    return flask.render_template(
        "transactions/table-view.html",
        txn=ctx_split(t_split, accounts, categories),
    )


def split(path_uuid: str) -> str:
  """PUT & DELETE /h/transactions/t/<path_uuid>/split

  Args:
    path_uuid: UUID of TransactionSplit

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    accounts = Account.map_name(s)
    categories = TransactionCategory.map_name(s)

    t_split: TransactionSplit = web_utils.find(s, TransactionSplit, path_uuid)

    return flask.render_template(
        "transactions/table-view.html",
        txn=ctx_split(t_split, accounts, categories),
    )


# TODO (WattsUp) Add POST endpoint for transaction edits
# TODO (WattsUp) Add GET endpoint for transaction add split
# TODO (WattsUp) CSS edit overlay, table header too

ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/transactions": (page_all, ["GET"]),
    "/h/transactions/table": (table, ["GET"]),
    "/h/transactions/options/<path:field>": (options, ["GET"]),
    "/h/transactions/t/<path:path_uuid>": (view, ["GET"]),
    "/h/transactions/t/<path:path_uuid>/edit": (edit, ["GET", "POST"]),
    "/h/transactions/t/<path:path_uuid>/split": (split, ["PUT", "DELETE"]),
}
