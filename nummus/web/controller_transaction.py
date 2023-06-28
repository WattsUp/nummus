"""Transaction API Controller
"""

from typing import Dict, List

import datetime

import connexion
import flask

from nummus import portfolio
from nummus.models import Transaction, TransactionCategory, TransactionSplit
from nummus.web import common


def create() -> flask.Response:
  """POST /api/transaction

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  req: Dict[str, object] = flask.request.json
  account_uuid = req["account_uuid"]
  date = datetime.date.fromisoformat(req["date"])
  locked = req["locked"]
  statement = req["statement"]
  total = req["total"]

  req_splits: List[Dict[str, object]] = []
  for split in req["splits"]:
    split: Dict[str, object]
    req_splits.append({
        "total": split["total"],
        "sales_tax": split.get("sales_tax"),
        "payee": split.get("payee"),
        "description": split.get("description"),
        "category": TransactionCategory.parse(split.get("category")),
        "subcategory": split.get("subcategory"),
        "tag": split.get("tag"),
        "asset_uuid": split.get("asset_uuid"),
        "asset_quantity": split.get("asset_quantity")
    })

  if len(req_splits) < 1:
    raise connexion.exceptions.BadRequestProblem(
        detail="Transaction must have at least one TransactionSplit")

  with p.get_session() as s:
    a = common.find_account(s, account_uuid)
    t = Transaction(account=a,
                    date=date,
                    total=total,
                    statement=statement,
                    locked=locked)
    s.add(t)
    for d in req_splits:
      asset_uuid = d.pop("asset_uuid")
      asset = None if asset_uuid is None else common.find_asset(s, asset_uuid)
      t_split = TransactionSplit(parent=t, asset=asset, **d)
      s.add(t_split)
    s.commit()
    return flask.jsonify(t)


def get(transaction_uuid: str) -> flask.Response:
  """GET /api/transaction/{transaction_uuid}

  Args:
    transaction_uuid: UUID of Transaction to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    t = common.find_transaction(s, transaction_uuid)
    return flask.jsonify(t)


def update(transaction_uuid: str) -> flask.Response:
  """PUT /api/transaction/{transaction_uuid}

  Args:
    transaction_uuid: UUID of Transaction to update

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    t = common.find_transaction(s, transaction_uuid)

    req: Dict[str, object] = flask.request.json
    d: Dict[str, object] = {}
    a = common.find_account(s, req["account_uuid"])
    d["account_id"] = a.id
    d["date"] = datetime.date.fromisoformat(req["date"])
    d["total"] = req["total"]
    d["statement"] = req["statement"]
    d["locked"] = req["locked"]

    req_splits: List[Dict[str, object]] = req["splits"]
    n_split = len(req_splits)
    if n_split < 1:
      raise connexion.exceptions.BadRequestProblem(
          detail="Transaction must have at least one TransactionSplit")

    n_split_current = len(t.splits)
    if n_split > n_split_current:
      splits = [
          TransactionSplit(parent=t, total=0)
          for _ in range(n_split - n_split_current)
      ]
      s.add_all(splits)
    elif n_split < n_split_current:
      # Mark the excess ones for deletion
      for t_split in t.splits[n_split:]:
        s.delete(t_split)

    for t_split, req_split in zip(t.splits, req_splits):
      d_split: Dict[str, object] = {}
      d_split["total"] = req_split["total"]
      d_split["sales_tax"] = req_split.get("sales_tax")
      d_split["payee"] = req_split.get("payee")
      d_split["description"] = req_split.get("description")
      d_split["category"] = TransactionCategory.parse(req_split.get("category"))
      d_split["subcategory"] = req_split.get("subcategory")
      d_split["tag"] = req_split.get("tag")

      asset_uuid = req_split.get("asset_uuid")
      asset_id = (None if asset_uuid is None else common.find_asset(
          s, asset_uuid).id)
      d_split["asset_id"] = asset_id
      d_split["asset_quantity"] = req_split.get("asset_quantity")

      t_split.update(d_split)

    t.update(d)
    s.commit()
    return flask.jsonify(t)


def delete(transaction_uuid: str) -> flask.Response:
  """DELETE /api/transaction/{transaction_uuid}

  Args:
    transaction_uuid: UUID of Transaction to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    t = common.find_transaction(s, transaction_uuid)

    response = flask.jsonify(t)

    # Delete the splits as well
    for t_split in t.splits:
      s.delete(t_split)
    s.delete(t)
    s.commit()
    return response


def get_all() -> flask.Response:
  """GET /api/transactions

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  args: Dict[str, object] = flask.request.args.to_dict()
  filter_category = TransactionCategory.parse(args.get("category"))

  with p.get_session() as s:
    # Get by splits
    query = s.query(TransactionSplit)
    if filter_category is not None:
      query = query.where(TransactionSplit.category == filter_category)

    transactions: Dict[str, Transaction] = {}
    # Return a list of the unique transactions with at least one split matching
    # the criteria
    for t_split in query.all():
      t = t_split.parent
      transactions[t.id] = t

    response = {"transactions": list(transactions.values())}
    return flask.jsonify(response)
