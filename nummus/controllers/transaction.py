"""Transaction controllers
"""

import flask

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

    page_len = 50

    query = s.query(TransactionSplit)
    query = query.where(TransactionSplit.asset_id.is_(None))
    query = query.order_by(TransactionSplit.date)
    page, count, offset = paginate(query, page_len, 0)

    transactions: t.List[t.DictAny] = []
    for t_split in page:
      t_split_ctx = ctx_transaction_split(t_split)
      t_split_ctx["account"] = accounts[t_split_ctx["account_id"]]
      t_split_ctx["category"] = categories[t_split_ctx["category_id"]]

      transactions.append(t_split_ctx)

    ctx: t.DictAny = {
        "page": transactions,
        "count": count,
        "offset": offset,
        "page_len": page_len
    }

  return flask.render_template("transactions/index.html",
                               sidebar=common.ctx_sidebar(),
                               transactions=ctx)


def ctx_transaction_split(t_split: TransactionSplit) -> t.DictAny:
  """Get context for a TransactionSplit

  Args:
    t_split: Transaction to get context for

  Returns:
    Dictionary HTML context
  """
  return {
      "uuid": t_split.uuid,
      "date": t_split.date,
      "account_id": t_split.account_id,
      "payee": t_split.payee,
      "description": t_split.description,
      "category_id": t_split.category_id,
      "tag": t_split.tag,
      "amount": t_split.amount,
      "asset_id": t_split.asset_id,
      "asset_qty": t_split.asset_quantity,
      "asset_qty_unadjusted": t_split.asset_quantity_unadjusted
  }


ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/transactions": (page_all, ["GET"])
}
