"""Account controllers
"""

import flask

from nummus import portfolio, web_utils
from nummus.models import Account


def edit_account(path_uuid: str) -> str:
  """GET & POST /h/accounts/<account_uuid>/edit

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    acct: Account = web_utils.find(s, Account, path_uuid)
    print(acct)

  if flask.request.method == "POST":
    print(flask.request.form)

  return flask.render_template("accounts/edit.html")
