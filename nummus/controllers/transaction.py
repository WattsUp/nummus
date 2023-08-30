"""Transaction controllers
"""

from decimal import Decimal

import flask
import sqlalchemy

from nummus import portfolio
from nummus import custom_types as t
from nummus.controllers import common
from nummus.models import (Account, TransactionCategory, TransactionSplit,
                           paginate)


def page_all() -> str:
  """GET /transactions

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    # Get account names
    query = s.query(Account)
    query = query.with_entities(Account.id, Account.name)
    accounts: t.DictIntStr = dict(query.all())

    # Get category names
    query = s.query(TransactionCategory)
    query = query.with_entities(TransactionCategory.id,
                                TransactionCategory.name)
    categories: t.DictIntStr = dict(query.all())

    # TODO (WattsUp) Add paging buttons
    page_len = 50
    offset = 0
    page_total = Decimal(0)

    query = s.query(TransactionSplit)
    query = query.where(TransactionSplit.asset_id.is_(None))
    # TODO (WattsUp) Add filters, namely date first
    query = query.order_by(TransactionSplit.date)

    page, count, next_offset = paginate(query, page_len, offset)

    query = query.with_entities(sqlalchemy.func.sum(TransactionSplit.amount))  # pylint: disable=not-callable
    query_total = query.scalar()

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

    ctx: t.DictAny = {
        "page": transactions,
        "count": count,
        "offset": offset,
        "next_offset": next_offset,
        "i_first": offset + 1,
        "i_last": min(offset + page_len, count),
        "page_len": page_len,
        "page_total": page_total,
        "query_total": query_total
    }

  return flask.render_template("transactions/index.html",
                               sidebar=common.ctx_sidebar(),
                               transactions=ctx)


# TODO (WattsUp) Add inline edit for txn
# TODO (WattsUp) Add overlay edit for split transactions

ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/transactions": (page_all, ["GET"])
}
