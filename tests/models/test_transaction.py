from __future__ import annotations

import datetime
from decimal import Decimal

from nummus import exceptions as exc
from nummus import models
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from nummus.models.base import Decimal9
from tests.base import TestBase


class TestTransaction(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.CASH,
            closed=False,
            emergency=False,
        )
        s.add(acct)
        s.commit()

        d = {
            "account_id": acct.id_,
            "date_ord": today_ord,
            "amount": self.random_decimal(-1, 1),
            "statement": self.random_string(),
        }

        txn = Transaction(**d)
        s.add(txn)
        s.commit()

        self.assertEqual(txn.account_id, acct.id_)
        self.assertEqual(txn.date_ord, d["date_ord"])
        self.assertEqual(txn.amount, d["amount"])
        self.assertEqual(txn.statement, d["statement"])
        self.assertFalse(txn.locked, "Transaction is unexpectedly locked")
        self.assertFalse(txn.linked, "Transaction is unexpectedly linked")

        # Can link
        txn.linked = True
        s.commit()

        # Can lock
        txn.locked = True
        s.commit()

        # Cannot lock an unlinked transaction
        txn.linked = False
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()


class TestTransactionSplit(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.CASH,
            closed=False,
            emergency=False,
        )
        s.add(acct)
        s.commit()

        asset = Asset(name="bananas", category=AssetCategory.ITEM)
        s.add(asset)
        s.commit()

        categories = TransactionCategory.add_default(s)
        t_cat = categories["Uncategorized"]

        d = {
            "account_id": acct.id_,
            "date_ord": today_ord,
            "amount": self.random_decimal(-1, 1),
            "statement": self.random_string(),
        }

        txn = Transaction(**d)
        s.add(txn)
        s.commit()

        d = {
            "amount": self.random_decimal(-1, 1),
            "parent": txn,
            "category_id": t_cat.id_,
        }

        t_split_0 = TransactionSplit(**d)

        s.add(t_split_0)
        s.commit()
        self.assertEqual(t_split_0.parent, txn)
        self.assertEqual(t_split_0.parent_id, txn.id_)
        self.assertEqual(t_split_0.category_id, t_cat.id_)
        self.assertIsNone(t_split_0.asset_id)
        self.assertIsNone(t_split_0.asset_quantity)
        self.assertIsNone(t_split_0.asset_quantity_unadjusted)
        self.assertEqual(t_split_0.amount, d["amount"])
        self.assertEqual(t_split_0.date_ord, txn.date_ord)
        self.assertEqual(t_split_0.locked, txn.locked)
        self.assertEqual(t_split_0.account_id, acct.id_)

        d = {
            "amount": self.random_decimal(-1, 0),
            "payee": self.random_string(),
            "description": self.random_string(),
            "category_id": t_cat.id_,
            "tag": self.random_string(),
            "asset_id": asset.id_,
            "asset_quantity_unadjusted": self.random_decimal(-1, 1, precision=9),
            "parent": txn,
        }

        t_split_1 = TransactionSplit(**d)
        s.add(t_split_1)
        s.commit()
        self.assertEqual(t_split_1.parent, txn)
        self.assertEqual(t_split_1.parent_id, txn.id_)
        self.assertEqual(t_split_1.category_id, t_cat.id_)
        self.assertEqual(t_split_1.asset_id, asset.id_)
        self.assertEqual(t_split_1.asset_quantity, d["asset_quantity_unadjusted"])
        self.assertEqual(
            t_split_1.asset_quantity_unadjusted,
            d["asset_quantity_unadjusted"],
        )
        self.assertEqual(t_split_1.amount, d["amount"])
        self.assertEqual(t_split_1.payee, d["payee"])
        self.assertEqual(t_split_1.description, d["description"])
        self.assertEqual(t_split_1.tag, d["tag"])
        self.assertEqual(t_split_1.date_ord, txn.date_ord)
        self.assertEqual(t_split_1.locked, txn.locked)
        self.assertEqual(t_split_1.account_id, acct.id_)

        # Zero amounts are bad
        t_split_0.amount = Decimal(0)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # Short strings are bad
        self.assertRaises(exc.InvalidORMValueError, setattr, t_split_0, "payee", "a")

        # Set an not an Transaction
        self.assertRaises(TypeError, setattr, t_split_0, "parent", self.random_string())

        # Set parent_id directly
        self.assertRaises(
            exc.ParentAttributeError,
            setattr,
            t_split_0,
            "parent_id",
            txn.id_,
        )

    def test_asset_quantity(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.CASH,
            closed=False,
            emergency=False,
        )
        s.add(acct)
        s.commit()

        categories = TransactionCategory.add_default(s)
        t_cat = categories["Uncategorized"]

        qty = self.random_decimal(10, 100, precision=9)
        txn = Transaction(
            account_id=acct.id_,
            date_ord=today_ord,
            statement=self.random_string(),
            amount=10,
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=10,
            asset_quantity_unadjusted=qty,
            category_id=t_cat.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        self.assertEqual(t_split.asset_quantity_unadjusted, qty)
        self.assertEqual(t_split.asset_quantity, qty)

        multiplier = self.random_decimal(1, 10)
        t_split.adjust_asset_quantity(multiplier)
        self.assertEqual(t_split.asset_quantity_unadjusted, qty)
        self.assertEqual(t_split.asset_quantity, Decimal9.truncate(qty * multiplier))

        t_split.asset_quantity_unadjusted = None
        s.commit()

        self.assertIsNone(t_split.asset_quantity)

        self.assertRaises(
            exc.NonAssetTransactionError,
            t_split.adjust_asset_quantity,
            multiplier,
        )
