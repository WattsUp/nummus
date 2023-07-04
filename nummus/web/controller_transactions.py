"""Transaction API Controller
"""

from typing import Dict, List

import datetime

import flask

from nummus import portfolio
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           Transaction, TransactionCategory, TransactionSplit)
from nummus.web import common
from nummus.web.common import HTTPError


def create() -> flask.Response:
  """POST /api/transactions

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  req: Dict[str, object] = flask.request.json
  account_uuid = req["account_uuid"]
  date = common.parse_date(req["date"])
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
        "category": (common.parse_enum(split.get("category"),
                                       TransactionCategory)),
        "subcategory": split.get("subcategory"),
        "tag": split.get("tag"),
        "asset_uuid": split.get("asset_uuid"),
        "asset_quantity": split.get("asset_quantity")
    })

  if len(req_splits) < 1:
    raise HTTPError(422,
                    detail="Transaction must have at least one "
                    "TransactionSplit")

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
    return flask.jsonify(t), 201, {"Location": f"/api/transactions/{t.uuid}"}


def get(transaction_uuid: str) -> flask.Response:
  """GET /api/transactions/{transaction_uuid}

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
  """PUT /api/transactions/{transaction_uuid}

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
    d["date"] = common.parse_date(req["date"])
    d["total"] = req["total"]
    d["statement"] = req["statement"]
    d["locked"] = req["locked"]

    req_splits: List[Dict[str, object]] = req["splits"]
    n_split = len(req_splits)
    if n_split < 1:
      raise HTTPError(422,
                      detail="Transaction must have at least one "
                      "TransactionSplit")

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
      d_split["category"] = common.parse_enum(req_split.get("category"),
                                              TransactionCategory)
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
  """DELETE /api/transactions/{transaction_uuid}

  Args:
    transaction_uuid: UUID of Transaction to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    t = common.find_transaction(s, transaction_uuid)

    # Delete the splits as well
    for t_split in t.splits:
      s.delete(t_split)
    s.delete(t)
    s.commit()
    return None


def get_all(request_args: Dict[str, object] = None) -> flask.Response:
  """GET /api/transactions

  Args:
    request_args: Override flask.request.args

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  if request_args is None:
    args = flask.request.args.to_dict()
  else:
    args = request_args

  start = common.parse_date(args.get("start"))
  end = common.parse_date(args.get("end", today))
  sort: str = args.get("sort", "oldest")
  limit = int(args.get("limit", 50))
  offset = int(args.get("offset", 0))
  search: str = args.get("search")
  category = common.parse_enum(args.get("category"), TransactionCategory)
  subcategory: str = args.get("subcategory")
  tag: str = args.get("tag")
  locked: str = args.get("locked")
  account_uuid: str = args.get("account")
  account_category = common.parse_enum(args.get("account_category"),
                                       AccountCategory)
  asset_uuid: str = args.get("asset")
  asset_category = common.parse_enum(args.get("asset_category"), AssetCategory)

  with p.get_session() as s:
    query = s.query(TransactionSplit).join(Transaction)
    query = query.where(Transaction.date <= end)
    if start is not None:
      if end <= start:
        raise HTTPError(422, detail="End date must be after Start date")
      query = query.where(Transaction.date >= start)
    if category is not None:
      query = query.where(TransactionSplit.category == category)
    if subcategory is not None:
      query = query.where(TransactionSplit.subcategory == subcategory)
    if tag is not None:
      query = query.where(TransactionSplit.tag == tag)
    if locked is not None:
      locked_bool = locked.lower() == "true"
      query = query.where(Transaction.locked == locked_bool)
    if account_uuid is not None:
      a = common.find_account(s, account_uuid)
      query = query.where(Transaction.account_id == a.id)
    if account_category is not None:
      query = query.join(Account)
      query = query.where(Account.category == account_category)
    if asset_uuid is not None:
      a = common.find_asset(s, asset_uuid)
      query = query.where(TransactionSplit.asset_id == a.id)
    if asset_category is not None:
      query = query.join(Asset)
      query = query.where(Asset.category == asset_category)

    if search is None:
      # Apply ordering
      # Sort by date, then parent, then id
      if sort == "oldest":
        query = query.order_by(Transaction.date, TransactionSplit.parent_id,
                               TransactionSplit.id)
      else:
        query = query.order_by(Transaction.date.desc(),
                               TransactionSplit.parent_id, TransactionSplit.id)
    else:
      # Apply search, will order by best match
      query = common.search(query, TransactionSplit, search)

    page, count, next_offset = common.paginate(query, limit, offset)
    response = {
        "transactions": page,
        "count": count,
        "next_offset": next_offset
    }
    return flask.jsonify(response)
