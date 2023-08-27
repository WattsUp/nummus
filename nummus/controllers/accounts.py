"""Account controllers
"""

import datetime

import flask

from nummus import portfolio, web_utils
from nummus import custom_types as t
from nummus.models import Account, AccountCategory


def edit_account(path_uuid: str) -> str:
  """GET & POST /h/accounts/<account_uuid>/edit

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  with p.get_session() as s:
    acct: Account = web_utils.find(s, Account, path_uuid)

    if flask.request.method == "POST":
      form = flask.request.form
      institution = form["institution"]
      name = form["name"]
      category = web_utils.parse_enum(form["category"], AccountCategory)

      # Make the changes
      acct.institution = institution
      acct.name = name
      acct.category = category
      s.commit()

      response = flask.make_response("")
      response.headers["HX-Trigger"] = "accountUpdate"
      return response

    _, values, _ = acct.get_value(today, today)
    v = values[0]

    ctx: t.DictAny = {
        "uuid": acct.uuid,
        "name": acct.name,
        "institution": acct.institution,
        "category": acct.category,
        "category_type": AccountCategory,
        "value": v,
        "updated_days_ago": (today - acct.updated_on).days,
        "opened_days_ago": (today - acct.opened_on).days
    }

  return flask.render_template("accounts/edit.html", account=ctx)
