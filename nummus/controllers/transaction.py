"""Transaction controllers
"""

import datetime
from decimal import Decimal

import flask
import sqlalchemy
from sqlalchemy import orm

from nummus import portfolio, web_utils
from nummus import custom_types as t
from nummus.controllers import common
from nummus.models import (Account, TransactionCategory, TransactionSplit,
                           paginate, search)


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


def get_table() -> str:
  """GET /h/transactions/table

  Returns:
    string HTML response
  """
  return flask.render_template(
      "transactions/table.html",
      txn_table=ctx_table(),
      include_oob=True,
  )


def ctx_options_account(query: orm.Query,
                        accounts: t.DictIntStr) -> t.List[t.DictStr]:
  """Get the context to build the options for account

  Args:
    s: Session to use
    query: Query to use to get distinct values
    accounts: Account ID to name mapping

  Returns:
    List of HTML context
  """
  selected: t.Strings = flask.request.args.getlist("account")
  options: t.List[t.DictStr] = []
  for acct_id, in query.with_entities(TransactionSplit.account_id).distinct():
    name = accounts[acct_id]
    options.append({"name": name, "checked": name in selected})
  return sorted(options, key=lambda item: (not item["checked"], item["name"]))


def ctx_options_payee(query: orm.Query) -> t.List[t.DictStr]:
  """Get the context to build the options for payee

  Args:
    query: Query to use to get distinct values

  Returns:
    List of HTML context
  """
  selected: t.Strings = flask.request.args.getlist("payee")
  options: t.List[t.DictStr] = []
  for payee, in query.with_entities(TransactionSplit.payee).distinct():
    options.append({"name": payee, "checked": payee in selected})
  return sorted(options, key=lambda item: (not item["checked"], item["name"]))


def ctx_options_category(query: orm.Query,
                         categories: t.DictIntStr) -> t.List[t.DictStr]:
  """Get the context to build the options for category

  Args:
    query: Query to use to get distinct values
    categories: Category ID to name mapping

  Returns:
    List of HTML context
  """
  selected: t.Strings = flask.request.args.getlist("category")
  options: t.List[t.DictStr] = []
  for cat_id, in query.with_entities(TransactionSplit.category_id).distinct():
    name = categories[cat_id]
    options.append({"name": name, "checked": name in selected})
  return sorted(options, key=lambda item: (not item["checked"], item["name"]))


def ctx_options_tag(query: orm.Query) -> t.List[t.DictStr]:
  """Get the context to build the options for tag

  Args:
    query: Query to use to get distinct values

  Returns:
    List of HTML context
  """
  selected: t.Strings = flask.request.args.getlist("tag")
  options: t.List[t.DictStr] = []
  for tag, in query.with_entities(TransactionSplit.tag).distinct():
    if tag is None:
      continue
    options.append({"name": tag, "checked": tag in selected})
  return sorted(options, key=lambda item: (not item["checked"], item["name"]))


def ctx_table() -> t.DictStr:
  """Get the context to build the transaction table

  Returns:
    Dictionary HTML context
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    args = flask.request.args

    # Get account names
    query = s.query(Account)
    query = query.with_entities(Account.id, Account.name)
    accounts: t.DictIntStr = dict(query.all())

    # Get category names
    query = s.query(TransactionCategory)
    query = query.with_entities(TransactionCategory.id,
                                TransactionCategory.name)
    categories: t.DictIntStr = dict(query.all())

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
    options_account = ctx_options_account(query, accounts)
    options_payee = ctx_options_payee(query)
    options_category = ctx_options_category(query, categories)
    options_tag = ctx_options_tag(query)

    # TODO Add searching

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
      t_split_ctx = {
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


# TODO (WattsUp) Add inline edit for txn
# TODO (WattsUp) Add overlay edit for split transactions

ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/transactions": (page_all, ["GET"]),
    "/h/transactions/table": (get_table, ["GET"]),
}
