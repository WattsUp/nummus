"""Account controllers
"""

import datetime

import flask
import sqlalchemy.exc

from nummus import portfolio, web_utils
from nummus import custom_types as t
from nummus.controllers import common
from nummus.models import Account, AccountCategory


def edit(path_uuid: str) -> str:
  """GET & POST /h/accounts/a/<account_uuid>/edit

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  with p.get_session() as s:
    acct: Account = web_utils.find(s, Account, path_uuid)

    _, values, _ = acct.get_value(today, today)
    v = values[0]

    if flask.request.method == "GET":
      ctx: t.DictAny = {
          "uuid": acct.uuid,
          "name": acct.name,
          "institution": acct.institution,
          "category": acct.category,
          "category_type": AccountCategory,
          "value": v,
          "closed": acct.closed,
          "updated_days_ago": (today - acct.updated_on).days,
          "opened_days_ago": (today - acct.opened_on).days,
      }

      return flask.render_template("accounts/edit.html", account=ctx)

    form = flask.request.form
    institution = form["institution"].strip()
    name = form["name"].strip()
    category = web_utils.parse_enum(form["category"], AccountCategory)
    closed = "closed" in form

    try:
      if closed and v != 0:
        raise ValueError("Cannot close Account with non-zero balance")

      # Make the changes
      acct.institution = institution
      acct.name = name
      acct.category = category
      acct.closed = closed
      s.commit()
    except (sqlalchemy.exc.IntegrityError, ValueError) as e:
      return common.error(e)

    return common.overlay_swap(events=["update-account"])


ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/h/accounts/a/<path:path_uuid>/edit": (edit, ["GET", "POST"])
}
