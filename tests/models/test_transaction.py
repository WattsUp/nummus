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

        self.assertEqual(txn.account_id, acct.id_)
        self.assertEqual(txn.date_ord, today.toordinal())
        self.assertEqual(txn.date, today)
        self.assertEqual(txn.amount, d["amount"])
        self.assertEqual(txn.statement, d["statement"])
        self.assertEqual(txn.payee, d["payee"])
        self.assertFalse(txn.cleared, "Transaction is unexpectedly cleared")

        # Can clear
        txn.cleared = True
        s.commit()


class TestTransactionSplit(TestBase):
    def test_init_properties(self) -> None:
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

        asset = Asset(name="bananas", category=AssetCategory.ITEM)
        s.add(asset)
        s.commit()

        categories = TransactionCategory.add_default(s)
        t_cat = categories["uncategorized"]

        payee = self.random_string()
        d = {
            "account_id": acct.id_,
            "date": today,
            "amount": self.random_decimal(-1, 1),
            "statement": self.random_string(),
            "payee": payee,
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
        self.assertEqual(t_split_0.payee, txn.payee)
        self.assertEqual(t_split_0.cleared, txn.cleared)
        self.assertEqual(t_split_0.account_id, acct.id_)
        self.assertEqual(t_split_0.text_fields, payee.lower())

        d = {
            "amount": self.random_decimal(-1, 0),
            "memo": self.random_string(),
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
        self.assertEqual(t_split_1.payee, txn.payee)
        self.assertEqual(t_split_1.memo, d["memo"])
        self.assertEqual(t_split_1.tag, d["tag"])
        self.assertEqual(t_split_1.date_ord, txn.date_ord)
        self.assertEqual(t_split_1.cleared, txn.cleared)
        self.assertEqual(t_split_1.account_id, acct.id_)
        self.assertEqual(
            t_split_1.text_fields,
            f"{txn.payee} {d['memo']} {d['tag']}".lower(),
        )

        # Zero amounts are bad
        t_split_0.amount = Decimal(0)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # Short strings are bad
        self.assertRaises(exc.InvalidORMValueError, setattr, t_split_0, "memo", "a")

        # Set parent_id directly
        self.assertRaises(
            exc.ParentAttributeError,
            setattr,
            t_split_0,
            "parent_id",
            txn.id_,
        )

        # Set asset_quantity directly
        self.assertRaises(
            exc.ComputedColumnError,
            setattr,
            t_split_1,
            "asset_quantity",
            None,
        )

        # Set text_fields directly
        self.assertRaises(
            exc.ComputedColumnError,
            setattr,
            t_split_1,
            "text_fields",
            None,
        )

        # Cannot have asset_quantity and _asset_qty_unadjusted be set and unset
        t_split_1._asset_qty_unadjusted = None  # noqa: SLF001
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

    def test_asset_quantity(self) -> None:
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

        categories = TransactionCategory.add_default(s)
        t_cat = categories["uncategorized"]

        qty = self.random_decimal(10, 100, precision=9)
        txn = Transaction(
            account_id=acct.id_,
            date=today,
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
        qty_adj = Decimal9.truncate(qty * multiplier) or Decimal(0)
        self.assertEqual(t_split.asset_quantity, qty_adj)

        residual = Decimal("0.1")
        t_split.adjust_asset_quantity_residual(residual)
        self.assertEqual(t_split.asset_quantity_unadjusted, qty)
        self.assertEqual(t_split.asset_quantity, qty_adj - residual)

        t_split.asset_quantity_unadjusted = None
        s.commit()

        self.assertIsNone(t_split.asset_quantity)

        self.assertRaises(
            exc.NonAssetTransactionError,
            t_split.adjust_asset_quantity,
            multiplier,
        )

        self.assertRaises(
            exc.NonAssetTransactionError,
            t_split.adjust_asset_quantity_residual,
            multiplier,
        )

    def test_search(self) -> None:
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

        categories = TransactionCategory.add_default(s)
        s.commit()
        t_cat_0 = categories["uncategorized"]
        t_cat_1 = categories["general merchandise"]

        payee = self.random_string()
        memo_0 = self.random_string()
        memo_1 = self.random_string()
        memo = f"{memo_0} {memo_1}"
        tag = self.random_string()

        txn = Transaction(
            account_id=acct.id_,
            date=today,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
            payee=payee,
        )
        s.add(txn)
        s.commit()

        t_split_0 = TransactionSplit(
            parent=txn,
            amount=self.random_decimal(-1, 1),
            category_id=t_cat_0.id_,
            memo=memo_0,
        )
        t_split_1 = TransactionSplit(
            parent=txn,
            amount=self.random_decimal(-1, 1),
            category_id=t_cat_1.id_,
            memo=memo,
            tag=tag,
        )
        s.add_all((t_split_0, t_split_1))
        s.commit()

        query = s.query(TransactionSplit)

        result = TransactionSplit.search(query, f'"{memo}"')
        target = [t_split_1.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, f'"{memo}')
        target = [t_split_1.id_, t_split_0.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, memo)
        target = [t_split_1.id_, t_split_0.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, payee)
        target = [t_split_0.id_, t_split_1.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, tag)
        target = [t_split_1.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, "Uncategorized")
        target = [t_split_0.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, f"{payee} {memo_1}")
        target = [t_split_1.id_, t_split_0.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, f"{payee} +{memo_1}")
        target = [t_split_1.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, f"{payee} -{memo_1}")
        target = [t_split_0.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, '"    "')
        target = [t_split_0.id_, t_split_1.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, f"{payee} +Uncategorized")
        target = [t_split_0.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, "+Uncategorized")
        target = [t_split_0.id_]
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, '+Uncategorized +"General merchandise"')
        target = []
        self.assertEqual(result, target)

        result = TransactionSplit.search(query, '-Uncategorized -"General merchandise"')
        target = []
        self.assertEqual(result, target)

    def test_find_similar(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.datetime.now().astimezone().date()

        categories = TransactionCategory.add_default(s)
        s.commit()
        categories = {k: v.id_ for k, v in categories.items()}

        acct_0 = Account(
            name="Monkey Bank Checking",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
            budgeted=True,
        )
        acct_1 = Account(
            name="Monkey Bank Credit",
            institution="Monkey Bank",
            category=AccountCategory.CREDIT,
            closed=False,
            budgeted=True,
        )
        s.add_all((acct_0, acct_1))
        s.flush()

        txn_0 = Transaction(
            account_id=acct_0.id_,
            date=today,
            amount=100,
            statement="Banana Store",
        )
        t_split_0 = TransactionSplit(
            amount=txn_0.amount,
            parent=txn_0,
            category_id=categories["uncategorized"],
        )

        s.add_all((txn_0, t_split_0))
        s.flush()

        txn_1 = Transaction(
            account_id=acct_0.id_,
            date=today,
            amount=100,
            statement="Banana Store",
        )
        t_split_1 = TransactionSplit(
            amount=txn_1.amount,
            parent=txn_1,
            category_id=categories["uncategorized"],
        )
        s.add_all((txn_1, t_split_1))
        s.flush()

        txn_2 = Transaction(
            account_id=acct_1.id_,
            date=today,
            amount=100,
            statement="Banana Store",
        )
        t_split_2 = TransactionSplit(
            amount=txn_2.amount,
            parent=txn_2,
            category_id=categories["uncategorized"],
        )
        s.add_all((txn_2, t_split_2))
        s.flush()

        # txn_0 and txn_1 have same statement and same account
        result = txn_0.find_similar(set_property=False)
        self.assertEqual(result, txn_1.id_)

        # set_property=False means it isn't cached
        self.assertIsNone(txn_0.similar_txn_id)

        # txn_1 amount is outside limits, should match txn_2
        txn_1.amount = Decimal(10)
        s.flush()
        result = txn_0.find_similar(set_property=False)
        self.assertEqual(result, txn_2.id_)

        # txn_2 amount is outside limits but further away, should match txn_1
        txn_2.amount = Decimal(9)
        s.flush()
        result = txn_0.find_similar(set_property=False)
        self.assertEqual(result, txn_1.id_)

        # Different statement, both outside amount range
        txn_0.statement = "Gas station 1234"
        s.flush()
        result = txn_0.find_similar(set_property=False)
        self.assertIsNone(result)

        # No fuzzy matches at all and no amounts close
        txn_0.amount = Decimal(1000)
        s.flush()
        result = txn_0.find_similar(set_property=False)
        self.assertIsNone(result)

        # No fuzzy matches at all but amount if close enough
        # txn_2 is closer but txn_1 is same account
        txn_0.amount = Decimal(8)
        s.flush()
        result = txn_0.find_similar(set_property=False)
        self.assertEqual(result, txn_1.id_)

        # Make fuzzy close, txn_1 is same account so more points
        txn_1.statement = "Gas station 5678"
        txn_2.statement = "gas station 90"
        txn_1.amount = Decimal(9)
        s.flush()
        result = txn_0.find_similar(set_property=False)
        self.assertEqual(result, txn_1.id_)

        # Cannot match if a split has an asset_linked
        t_split_1.category_id = categories["securities traded"]
        s.flush()
        result = txn_0.find_similar(set_property=False)
        self.assertEqual(result, txn_2.id_)

        t_split_2.category_id = categories["securities traded"]
        s.flush()
        result = txn_0.find_similar(set_property=False)
        self.assertIsNone(result)

        t_split_1.category_id = categories["uncategorized"]
        t_split_2.category_id = categories["uncategorized"]
        s.flush()

        # txn_2 is closer so more points being closer
        txn_2.amount = Decimal("8.5")
        txn_2.account_id = acct_0.id_
        s.flush()
        result = txn_0.find_similar(set_property=True)
        self.assertEqual(result, txn_2.id_)
        self.assertEqual(txn_0.similar_txn_id, txn_2.id_)

        # Even though txn_1 is exact statement match, cache is used
        txn_1.statement = "Gas station 1234"
        s.flush()
        result = txn_0.find_similar(set_property=True)
        self.assertEqual(result, txn_2.id_)
        self.assertEqual(txn_0.similar_txn_id, txn_2.id_)

        # Force not using cache will update similar
        result = txn_0.find_similar(set_property=True, cache_ok=False)
        self.assertEqual(result, txn_1.id_)
        self.assertEqual(txn_0.similar_txn_id, txn_1.id_)
