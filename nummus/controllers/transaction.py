"""Transaction controllers
"""

import datetime
from decimal import Decimal

import flask
import sqlalchemy

from nummus import portfolio, web_utils
from nummus import custom_types as t
from nummus.controllers import common
from nummus.models import (Account, TransactionCategory, TransactionSplit,
                           paginate)


def page_all() -> str:
  """GET /transactions

  Returns:
    string HTML response
  """

  return flask.render_template("transactions/index.html",
                               sidebar=common.ctx_sidebar(),
                               table=ctx_table())


def get_body() -> str:
  """GET /h/transactions/body

  Returns:
    string HTML response
  """
  return flask.render_template("transactions/body.html", table=ctx_table())


def ctx_table() -> t.DictAny:
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

    page_len = 25
    offset = int(args.get("offset", 0))
    page_total = Decimal(0)

    query = s.query(TransactionSplit)
    query = query.where(TransactionSplit.asset_id.is_(None))
    if start is not None:
      query = query.where(TransactionSplit.date >= start)
    query = query.where(TransactionSplit.date <= end)
    query = query.order_by(TransactionSplit.date)

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
          "amount": t_split.amount
      }
      page_total += t_split.amount

      transactions.append(t_split_ctx)

    base_url = "/h/transactions/body?"

    offset_last = max(0, (count // page_len) * page_len)

    return {
        "transactions": transactions,
        "count": count,
        "offset": offset,
        "i_first": offset + 1,
        "i_last": min(offset + page_len, count),
        "page_len": page_len,
        "page_total": page_total,
        "query_total": query_total,
        "url_first": f"{base_url}&offset=0",
        "url_prev": f"{base_url}&offset={max(0, offset - page_len)}",
        "url_next": f"{base_url}&offset={offset_next or offset_last}",
        "url_last": f"{base_url}&offset={offset_last}",
        "start": start,
        "end": end,
        "period": period
    }


# TODO (WattsUp) Add inline edit for txn
# TODO (WattsUp) Add overlay edit for split transactions

ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/transactions": (page_all, ["GET"]),
    "/h/transactions/body": (get_body, ["GET"])
}
