"""Asset API Controller
"""

from typing import Dict

import flask

from nummus import portfolio
from nummus.models import Asset, AssetCategory
from nummus.web import common


def create() -> flask.Response:
  """POST /api/asset

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  req: Dict[str, object] = flask.request.json
  name = str(req["name"])
  description = req.get("description")
  category = common.parse_enum(req["category"], AssetCategory)
  unit = req.get("unit")
  tag = req.get("tag")

  a = Asset(name=name,
            description=description,
            category=category,
            unit=unit,
            tag=tag)
  with p.get_session() as s:
    s.add(a)
    s.commit()
    return flask.jsonify(a)


def get(asset_uuid: str) -> flask.Response:
  """GET /api/asset/{asset_uuid}

  Args:
    asset_uuid: UUID of Asset to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_asset(s, asset_uuid)
    return flask.jsonify(a)


def update(asset_uuid: str) -> flask.Response:
  """PUT /api/asset/{asset_uuid}

  Args:
    asset_uuid: UUID of Asset to update

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_asset(s, asset_uuid)

    req: Dict[str, object] = flask.request.json
    d: Dict[str, object] = {}
    d["name"] = req["name"]
    d["institution"] = req.get("description")
    d["category"] = common.parse_enum(req["category"], AssetCategory)
    d["unit"] = req.get("unit")
    d["tag"] = req.get("tag")

    a.update(d)
    s.commit()
    return flask.jsonify(a)


def delete(asset_uuid: str) -> flask.Response:
  """DELETE /api/asset/{asset_uuid}

  Args:
    asset_uuid: UUID of Asset to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_asset(s, asset_uuid)

    response = flask.jsonify(a)

    # Delete the valuations as well
    for v in a.valuations:
      s.delete(v)
    s.delete(a)
    s.commit()
    return response


def get_all() -> flask.Response:
  """GET /api/assets

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  args: Dict[str, object] = flask.request.args.to_dict()
  limit = int(args.get("limit", 50))
  offset = int(args.get("offset", 0))
  search = args.get("search")
  filter_category = common.parse_enum(args.get("category"), AssetCategory)

  with p.get_session() as s:
    query = s.query(Asset)
    if filter_category is not None:
      query = query.where(Asset.category == filter_category)

    query = common.search(s, query, Asset, search)

    page, count, next_offset = common.paginate(query, limit, offset)
    response = {"assets": page, "count": count, "next_offset": next_offset}
    return flask.jsonify(response)
