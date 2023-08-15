"""Asset API Controller
"""

import datetime

import flask

from nummus import portfolio
from nummus import custom_types as t
from nummus.models import Asset, AssetCategory, AssetValuation
from nummus.web import common
from nummus.web.common import HTTPError


def create() -> flask.Response:
  """POST /api/assets

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  req: t.JSONObj = flask.request.json
  name = str(req["name"])
  description = req.get("description")
  category = common.parse_enum(req["category"], AssetCategory)
  unit = req.get("unit")
  tag = req.get("tag")

  with p.get_session() as s:
    a = Asset(name=name,
              description=description,
              category=category,
              unit=unit,
              tag=tag)
    s.add(a)
    s.commit()
    return flask.jsonify(a), 201, {"Location": f"/api/assets/{a.uuid}"}


def get(asset_uuid: str) -> flask.Response:
  """GET /api/assets/{asset_uuid}

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
  """PUT /api/assets/{asset_uuid}

  Args:
    asset_uuid: UUID of Asset to update

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_asset(s, asset_uuid)

    req: t.JSONObj = flask.request.json
    d: t.JSONObj = {}
    d["name"] = req["name"]
    d["institution"] = req.get("description")
    d["category"] = common.parse_enum(req["category"], AssetCategory)
    d["unit"] = req.get("unit")
    d["tag"] = req.get("tag")

    a.update(d)
    s.commit()
    return flask.jsonify(a)


def delete(asset_uuid: str) -> flask.Response:
  """DELETE /api/assets/{asset_uuid}

  Args:
    asset_uuid: UUID of Asset to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_asset(s, asset_uuid)

    # Delete the valuations as well

    query = s.query(AssetValuation)
    query = query.where(AssetValuation.asset_id == a.id)
    query.delete()
    s.commit()

    s.delete(a)
    s.commit()
    return None


def get_all() -> flask.Response:
  """GET /api/assets

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  args: t.JSONObj = flask.request.args.to_dict()
  limit = int(args.get("limit", 50))
  offset = int(args.get("offset", 0))
  search = args.get("search")
  filter_category = common.parse_enum(args.get("category"), AssetCategory)

  with p.get_session() as s:
    query = s.query(Asset)
    if filter_category is not None:
      query = query.where(Asset.category == filter_category)

    query = common.search(query, Asset, search)

    page, count, next_offset = common.paginate(query, limit, offset)
    response = {"assets": page, "count": count, "next_offset": next_offset}
    return flask.jsonify(response)


def get_image(asset_uuid: str) -> flask.Response:
  """GET /api/assets/{asset_uuid}/image

  Args:
    asset_uuid: UUID of Asset to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_asset(s, asset_uuid)
    img_name = a.image_name
    if img_name is None:
      raise HTTPError(404,
                      detail=f"Asset image {asset_uuid} not found in Portfolio")
    img = p.image_path.joinpath(img_name)
    if not img.exists():
      raise HTTPError(404,
                      detail=f"Asset image {asset_uuid} not found in Portfolio")
    return flask.send_file(img)


def update_image(asset_uuid: str) -> flask.Response:
  """PUT /api/assets/{asset_uuid}/image

  Args:
    asset_uuid: UUID of Asset to find

  Returns:
    JSON response, see api.yaml for details
  """
  suffix = common.validate_image_upload(flask.request)

  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_asset(s, asset_uuid)
    a.img_suffix = suffix

    img = p.image_path.joinpath(a.image_name)
    with open(img, "wb") as file:
      file.write(flask.request.get_data())

    s.commit()
    return None


def delete_image(asset_uuid: str) -> flask.Response:
  """DELETE /api/assets/{asset_uuid}/image

  Args:
    asset_uuid: UUID of Asset to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_asset(s, asset_uuid)

    img_name = a.image_name
    if img_name is None:
      raise HTTPError(404,
                      detail=f"Asset image {asset_uuid} not found in Portfolio")
    img = p.image_path.joinpath(img_name)
    if img.exists():
      img.unlink()

    a.img_suffix = None

    s.commit()
    return None


def get_value(asset_uuid: str) -> flask.Response:
  """GET /api/assets/{asset_uuid}/value

  Args:
    asset_uuid: UUID of Asset to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.JSONObj = flask.request.args.to_dict()
  start = common.parse_date(args.get("start", today))
  end = common.parse_date(args.get("end", today))
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    a = common.find_asset(s, asset_uuid)

    dates, values = a.get_value(start, end)
    response = {"values": values, "dates": dates}
    return flask.jsonify(response)
