from __future__ import annotations

import datetime

from nummus import models
from nummus.models import Account, AccountCategory, Transaction


def test_init_properties() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.datetime.now().astimezone().date()

    acct = Account(
        name=self.random_string(),
        institution=self.random_string(),
        category=AccountCategory.CASH,
        closed=False,
        budgeted=False,
    )
    s.add(acct)
    s.commit()

    d = {
        "account_id": acct.id_,
        "date": today,
        "amount": self.random_decimal(-1, 1),
        "statement": self.random_string(),
        "payee": self.random_string(),
    }

    txn = Transaction(**d)
    s.add(txn)
    s.commit()

    assert txn.account_id == acct.id_
    assert txn.date_ord == today.toordinal()
    assert txn.date == today
    assert txn.amount == d["amount"]
    assert txn.statement == d["statement"]
    assert txn.payee == d["payee"]
    self.assertFalse(txn.cleared, "Transaction is unexpectedly cleared")

    # Can clear
    txn.cleared = True
    s.commit()
