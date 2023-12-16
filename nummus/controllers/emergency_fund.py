"""Emergency Savings controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import flask

from nummus import portfolio, utils
from nummus.controllers import common
from nummus.models import Account, Budget

if TYPE_CHECKING:
    from nummus import custom_types as t


def ctx_page() -> t.DictAny:
    """Get the context to build the emergency fund page.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    today = datetime.date.today()
    today_ord = today.toordinal()
    start = utils.date_add_months(today, -8)
    start_ord = start.toordinal()

    with p.get_session() as s:
        b = s.query(Budget).order_by(Budget.date_ord.desc()).first()
        if b is None:
            return {"no_budget": True}
        b_amount = -b.amount  # Budgets are negative

        # Get liquid account ids
        query = s.query(Account).where(Account.emergency.is_(True))
        accts = query.all()
        acct_ids = [acct.id_ for acct in accts]

        _, acct_values = Account.get_value_all(s, start_ord, today_ord, ids=acct_ids)

        balances = [sum(x) for x in zip(*acct_values.values(), strict=True)]

        acct_info: t.DictAny = {}
        for acct in accts:
            if acct.closed:
                continue
            acct_info[acct.uri] = {
                "name": acct.name,
                "institution": acct.institution,
                "balance": acct_values[acct.id_][-1],
            }
        acct_info = dict(
            sorted(acct_info.items(), key=lambda item: -item[1]["balance"]),
        )

    # Current target is latest target rounded to 2 sig figs
    target_low = Decimal(f"{b_amount * 3:.2g}")
    target_high = Decimal(f"{b_amount * 6:.2g}")
    current = balances[-1]

    # Compute the number of months in savings
    months = int(current // b_amount)

    return {
        "chart": {
            "dates": [d.isoformat() for d in utils.range_date(start_ord, today_ord)],
            "balances": balances,
            "target_high": target_high,
            "target_low": target_low,
        },
        "current": current,
        "target_high": target_high,
        "target_low": target_low,
        "budget": b_amount,
        "months": months,
        "delta_low": target_low - current,
        "delta_high": current - target_high,
        "accts": acct_info,
    }


def page() -> str:
    """GET /emergency-fund.

    Returns:
        string HTML response
    """
    return common.page(
        "emergency-fund/index-content.jinja",
        e_fund=ctx_page(),
    )


ROUTES: t.Routes = {
    "/emergency-fund": (page, ["GET"]),
}
