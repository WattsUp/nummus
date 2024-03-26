from __future__ import annotations

import datetime
from decimal import Decimal

import sqlalchemy.exc

from nummus import exceptions as exc
from nummus import models
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetSplit,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from tests.base import TestBase


class TestAssetSplit(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        a = Asset(name=self.random_string(), category=AssetCategory.CASH)
        s.add(a)
        s.commit()

        d = {
            "asset_id": a.id_,
            "multiplier": self.random_decimal(1, 10),
            "date_ord": today_ord,
        }

        v = AssetSplit(**d)
        s.add(v)
        s.commit()

        self.assertEqual(v.asset_id, d["asset_id"])
        self.assertEqual(v.multiplier, d["multiplier"])
        self.assertEqual(v.date_ord, d["date_ord"])


class TestAssetValuation(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        a = Asset(name=self.random_string(), category=AssetCategory.CASH)
        s.add(a)
        s.commit()

        d = {
            "asset_id": a.id_,
            "value": self.random_decimal(0, 1),
            "date_ord": today_ord,
        }

        v = AssetValuation(**d)
        s.add(v)
        s.commit()

        self.assertEqual(v.asset_id, d["asset_id"])
        self.assertEqual(v.value, d["value"])
        self.assertEqual(v.date_ord, d["date_ord"])


class TestAsset(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        d = {
            "name": self.random_string(),
            "description": self.random_string(),
            "category": AssetCategory.STOCKS,
            "ticker": self.random_string().upper(),
        }

        a = Asset(**d)
        s.add(a)
        s.commit()

        self.assertEqual(a.name, d["name"])
        self.assertEqual(a.description, d["description"])
        self.assertEqual(a.category, d["category"])

        d = {
            "asset_id": a.id_,
            "value": self.random_decimal(0, 1),
            "date_ord": today_ord,
        }

        v = AssetValuation(**d)
        s.add(v)
        s.commit()

        s.delete(a)

        # Cannot delete Parent before all children
        self.assertRaises(sqlalchemy.exc.IntegrityError, s.commit)
        s.rollback()  # Undo the attempt

        s.delete(v)
        s.commit()
        s.delete(a)
        s.commit()

        result = s.query(Asset).all()
        self.assertEqual(result, [])
        result = s.query(AssetValuation).all()
        self.assertEqual(result, [])

        # Short strings are bad
        self.assertRaises(exc.InvalidORMValueError, setattr, a, "name", "a")

        # But not for ticker
        a.ticker = "AB"
        s.commit()

        # Lower case ticker is bad
        self.assertRaises(exc.InvalidORMValueError, setattr, a, "ticker", "Ab")

        # Spaces are bad
        self.assertRaises(exc.InvalidORMValueError, setattr, a, "ticker", "A B")

        # Caret, dollar sign, and a dash okay
        a.ticker = "^AB"
        s.commit()

        a.ticker = "$AB"
        s.commit()

        a.ticker = "$A-B"
        s.commit()

        # Other places for these symbols are not okay
        self.assertRaises(exc.InvalidORMValueError, setattr, a, "ticker", "AB^")
        self.assertRaises(exc.InvalidORMValueError, setattr, a, "ticker", "AB$")
        self.assertRaises(exc.InvalidORMValueError, setattr, a, "ticker", "AB-")
        self.assertRaises(exc.InvalidORMValueError, setattr, a, "ticker", "AB--C")
        self.assertRaises(exc.InvalidORMValueError, setattr, a, "ticker", "-AB")

        # None is okay
        a.ticker = None
        s.commit()

    def test_add_valuations(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        d = {
            "name": self.random_string(),
            "description": self.random_string(),
            "category": AssetCategory.STOCKS,
        }

        a = Asset(**d)
        s.add(a)
        s.commit()

        v_today = AssetValuation(
            asset_id=a.id_,
            date_ord=today_ord,
            value=self.random_decimal(-1, 1),
        )
        s.add(v_today)
        s.commit()

    def test_get_value(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()
        tomorrow_ord = today_ord + 1

        d = {
            "name": self.random_string(),
            "description": self.random_string(),
            "category": AssetCategory.STOCKS,
        }

        a = Asset(**d)

        # Unbound to a session will raise UnboundExecutionError
        self.assertRaises(
            exc.UnboundExecutionError,
            a.get_value,
            today_ord,
            today_ord,
        )

        s.add(a)
        s.commit()

        v_today = AssetValuation(
            asset_id=a.id_,
            date_ord=today_ord,
            value=self.random_decimal(-1, 1),
        )
        v_before = AssetValuation(
            asset_id=a.id_,
            date_ord=today_ord - 2,
            value=self.random_decimal(-1, 1),
        )
        v_after = AssetValuation(
            asset_id=a.id_,
            date_ord=today_ord + 2,
            value=self.random_decimal(-1, 1),
        )
        s.add_all((v_today, v_before, v_after))
        s.commit()

        target_values = [
            0,
            v_before.value,
            v_before.value,
            v_today.value,
            v_today.value,
            v_after.value,
            v_after.value,
        ]
        start = today_ord - 3
        end = today_ord + 3

        r_values = a.get_value(start, end)
        self.assertEqual(r_values, target_values)

        r_values = Asset.get_value_all(s, start, end)
        self.assertEqual(r_values, {a.id_: target_values})

        r_values = Asset.get_value_all(s, start, end, ids=[a.id_])
        self.assertEqual(r_values, {a.id_: target_values})

        r_values = Asset.get_value_all(s, start, end, ids=[])
        self.assertEqual(r_values, {})

        # Test single value
        r_values = a.get_value(today_ord, today_ord)
        self.assertEqual(r_values, [v_today.value])

        r_values = Asset.get_value_all(s, today_ord, today_ord)
        self.assertEqual(r_values, {a.id_: [v_today.value]})

        # Test single value
        r_values = a.get_value(tomorrow_ord, tomorrow_ord)
        self.assertEqual(r_values, [v_today.value])

        r_values = Asset.get_value_all(s, tomorrow_ord, tomorrow_ord)
        self.assertEqual(r_values, {a.id_: [v_today.value]})

        # Test single value
        long_ago = today_ord - 7
        r_values = a.get_value(long_ago, long_ago)
        self.assertEqual(r_values, [Decimal(0)])

        r_values = Asset.get_value_all(s, long_ago, long_ago)
        self.assertEqual(r_values, {a.id_: [Decimal(0)]})

        # Test interpolation
        a.interpolate = True
        s.commit()

        v_before.value = Decimal(1)
        v_today.value = Decimal(3)
        v_after.value = Decimal(7)

        # Should interpolate to point after the end
        target_values = [
            0,
            Decimal(1),
            Decimal(2),
            Decimal(3),
            Decimal(5),
        ]
        r_values = a.get_value(start, end - 2)
        self.assertEqual(r_values, target_values)

        # Should interpolate to point before the end
        target_values = [
            Decimal(1),
            Decimal(2),
            Decimal(3),
            Decimal(5),
        ]
        r_values = a.get_value(start + 1, end - 2)
        self.assertEqual(r_values, target_values)

        # Should keep last value flat after the end
        target_values = [
            0,
            Decimal(1),
            Decimal(2),
            Decimal(3),
            Decimal(5),
            Decimal(7),
            Decimal(7),
        ]
        r_values = a.get_value(start, end)
        self.assertEqual(r_values, target_values)

    def test_update_splits(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday_ord = today_ord - 1

        multiplier_0 = 10
        multiplier_1 = 7
        multiplier = multiplier_0 * multiplier_1
        value_today = self.random_decimal(1, 10)
        value_yesterday = value_today * multiplier

        # Create assets and accounts
        a = Asset(name="BANANA", category=AssetCategory.ITEM)
        acct = Account(
            name="Monkey Bank Checking",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
            emergency=False,
        )

        # Unbound to a session will raise UnboundExecutionError
        self.assertRaises(exc.UnboundExecutionError, a.update_splits)

        s.add_all((a, acct))
        s.commit()

        t_cat = TransactionCategory(
            name="Securities Traded",
            group=TransactionCategoryGroup.OTHER,
            locked=False,
            is_profit_loss=False,
        )
        s.add(t_cat)
        s.commit()

        v = AssetValuation(
            asset_id=a.id_,
            date_ord=today_ord - 100,
            value=value_today,
        )
        s.add(v)
        s.commit()

        # Splits are done after hours
        # A split on today means trading occurs at yesterday / multiplier pricing
        txn_0 = Transaction(
            account_id=acct.id_,
            date_ord=yesterday_ord,
            amount=value_yesterday,
            statement=self.random_string(),
        )
        t_split_0 = TransactionSplit(
            amount=txn_0.amount,
            parent=txn_0,
            asset_id=a.id_,
            asset_quantity_unadjusted=1,
            category_id=t_cat.id_,
        )
        s.add_all((txn_0, t_split_0))

        txn_1 = Transaction(
            account_id=acct.id_,
            date_ord=today_ord,
            amount=value_today,
            statement=self.random_string(),
        )
        t_split_1 = TransactionSplit(
            amount=txn_1.amount,
            parent=txn_1,
            asset_id=a.id_,
            asset_quantity_unadjusted=1,
            category_id=t_cat.id_,
        )
        s.add_all((txn_1, t_split_1))

        s.commit()

        # Do split updates
        a.update_splits()
        s.commit()

        self.assertEqual(t_split_0.asset_quantity_unadjusted, 1)
        self.assertEqual(t_split_1.asset_quantity_unadjusted, 1)

        self.assertEqual(t_split_0.asset_quantity, 1)
        self.assertEqual(t_split_1.asset_quantity, 1)

        r_assets = acct.get_asset_qty(yesterday_ord, today_ord)
        r_values = r_assets[a.id_]
        target_values = [1, 2]
        self.assertEqual(r_values, target_values)

        # Multiple splits that need be included on the first valuation
        split_0 = AssetSplit(
            asset_id=a.id_,
            date_ord=today_ord,
            multiplier=multiplier_0,
        )
        split_1 = AssetSplit(
            asset_id=a.id_,
            date_ord=today_ord,
            multiplier=multiplier_1,
        )
        s.add_all((split_0, split_1))
        s.commit()

        # Do split updates
        a.update_splits()
        s.commit()

        self.assertEqual(t_split_0.asset_quantity_unadjusted, 1)
        self.assertEqual(t_split_1.asset_quantity_unadjusted, 1)

        self.assertEqual(t_split_0.asset_quantity, 1 * multiplier)
        self.assertEqual(t_split_1.asset_quantity, 1)

        r_assets = acct.get_asset_qty(yesterday_ord, today_ord)
        r_values = r_assets[a.id_]
        target_values = [multiplier, multiplier + 1]
        self.assertEqual(r_values, target_values)

        _, _, r_assets = acct.get_value(yesterday_ord, today_ord)
        r_values = r_assets[a.id_]
        target_values = [value_yesterday, value_yesterday + value_today]
        self.assertEqual(r_values, target_values)

        # Non-integer splits should preserve summing to zero
        txn_0 = Transaction(
            account_id=acct.id_,
            date_ord=today_ord - 7,
            amount=10,
            statement=self.random_string(),
        )
        qty = Decimal("1.234567891")
        t_split_0 = TransactionSplit(
            amount=txn_0.amount,
            parent=txn_0,
            asset_id=a.id_,
            asset_quantity_unadjusted=qty,
            category_id=t_cat.id_,
        )
        s.add_all((txn_0, t_split_0))
        s.commit()
        self.assertEqual(t_split_0.asset_quantity_unadjusted, qty)

        qty_1 = -qty / 2
        txn_1 = Transaction(
            account_id=acct.id_,
            date_ord=today_ord - 6,
            amount=10,
            statement=self.random_string(),
        )
        t_split_1 = TransactionSplit(
            amount=txn_1.amount,
            parent=txn_1,
            asset_id=a.id_,
            asset_quantity_unadjusted=qty_1,
            category_id=t_cat.id_,
        )
        s.add_all((txn_1, t_split_1))
        s.commit()
        qty_1 = t_split_1.asset_quantity_unadjusted or 0

        txn_1 = Transaction(
            account_id=acct.id_,
            date_ord=today_ord - 6,
            amount=10,
            statement=self.random_string(),
        )
        t_split_1 = TransactionSplit(
            amount=txn_1.amount,
            parent=txn_1,
            asset_id=a.id_,
            asset_quantity_unadjusted=-qty - qty_1,
            category_id=t_cat.id_,
        )
        s.add_all((txn_1, t_split_1))
        s.commit()

        # Do split updates
        a.update_splits()
        s.commit()

        r_assets = acct.get_asset_qty(today_ord - 7, today_ord - 6)
        r_values = r_assets[a.id_]
        target_values = [qty * multiplier, 0]
        self.assertEqual(r_values, target_values)

        # Add non-integer split
        multiplier_2 = Decimal(1000) / 1281
        split_2 = AssetSplit(
            asset_id=a.id_,
            date_ord=today_ord,
            multiplier=multiplier_2,
        )
        s.add(split_2)
        s.commit()
        multiplier_2 = split_2.multiplier

        # Do split updates
        a.update_splits()
        s.commit()

        r_assets = acct.get_asset_qty(today_ord - 7, today_ord - 6)
        r_values = r_assets[a.id_]
        target_values = [round(qty * multiplier * multiplier_2, 9), 0]
        self.assertEqual(r_values, target_values)

    def test_prune_valuations(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        # Create assets and accounts
        a = Asset(name="BANANA", category=AssetCategory.ITEM)
        acct = Account(
            name="Monkey Bank Checking",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
            emergency=False,
        )
        t_cat = TransactionCategory(
            name="Securities Traded",
            group=TransactionCategoryGroup.OTHER,
            locked=False,
            is_profit_loss=False,
        )

        # Unbound to a session will raise UnboundExecutionError
        self.assertRaises(exc.UnboundExecutionError, a.prune_valuations)

        s.add_all((a, acct, t_cat))
        s.commit()

        for i in range(-3, 3 + 1):
            av = AssetValuation(
                asset_id=a.id_,
                date_ord=today_ord + i,
                value=self.random_decimal(-1, 1),
            )
            s.add(av)
        s.commit()

        n = s.query(AssetValuation).count()
        self.assertEqual(n, 7)

        n_deleted = a.prune_valuations()
        self.assertEqual(n_deleted, 7)

        # No transactions should prune all
        n = s.query(AssetValuation).count()
        self.assertEqual(n, 0)

        # prune_valuations doesn't commit so rollback should work
        s.rollback()
        n = s.query(AssetValuation).count()
        self.assertEqual(n, 7)

        # Add a transaction before first day
        txn_0 = Transaction(
            account_id=acct.id_,
            date_ord=today_ord - 4,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        t_split_0 = TransactionSplit(
            amount=txn_0.amount,
            parent=txn_0,
            asset_id=a.id_,
            asset_quantity_unadjusted=2,
            category_id=t_cat.id_,
        )
        s.add_all((txn_0, t_split_0))
        s.commit()

        # None to delete
        n_deleted = a.prune_valuations()
        self.assertEqual(n_deleted, 0)

        txn_0.date_ord = today_ord
        t_split_0.date_ord = today_ord
        s.commit()

        n_deleted = a.prune_valuations()
        self.assertEqual(n_deleted, 3)

        # Should be left with one valuation on and all after
        n = s.query(AssetValuation).count()
        self.assertEqual(n, 4)
        date_ord = s.query(sqlalchemy.func.min(AssetValuation.date_ord)).scalar()
        self.assertEqual(date_ord, today_ord)
        date_ord = s.query(sqlalchemy.func.max(AssetValuation.date_ord)).scalar()
        self.assertEqual(date_ord, today_ord + 3)

        # None to delete
        n_deleted = a.prune_valuations()
        self.assertEqual(n_deleted, 0)

        s.rollback()

        # Add sell some today
        txn_0 = Transaction(
            account_id=acct.id_,
            date_ord=today_ord,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        t_split_0 = TransactionSplit(
            amount=txn_0.amount,
            parent=txn_0,
            asset_id=a.id_,
            asset_quantity_unadjusted=-1,
            category_id=t_cat.id_,
        )
        s.add_all((txn_0, t_split_0))
        s.commit()

        # And remaining tomorrow
        txn_0 = Transaction(
            account_id=acct.id_,
            date_ord=today_ord + 1,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        t_split_0 = TransactionSplit(
            amount=txn_0.amount,
            parent=txn_0,
            asset_id=a.id_,
            asset_quantity_unadjusted=-1,
            category_id=t_cat.id_,
        )
        s.add_all((txn_0, t_split_0))
        s.commit()

        n_deleted = a.prune_valuations()
        self.assertEqual(n_deleted, 5)

        # Should be left with one valuation on and one after
        n = s.query(AssetValuation).count()
        self.assertEqual(n, 2)
        date_ord = s.query(sqlalchemy.func.min(AssetValuation.date_ord)).scalar()
        self.assertEqual(date_ord, today_ord)
        date_ord = s.query(sqlalchemy.func.max(AssetValuation.date_ord)).scalar()
        self.assertEqual(date_ord, today_ord + 1)
        s.rollback()

        # Buy and sell some on the last day
        txn_0 = Transaction(
            account_id=acct.id_,
            date_ord=today_ord + 3,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        t_split_0 = TransactionSplit(
            amount=txn_0.amount,
            parent=txn_0,
            asset_id=a.id_,
            asset_quantity_unadjusted=1,
            category_id=t_cat.id_,
        )
        s.add_all((txn_0, t_split_0))
        s.commit()
        txn_0 = Transaction(
            account_id=acct.id_,
            date_ord=today_ord + 3,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        t_split_0 = TransactionSplit(
            amount=txn_0.amount,
            parent=txn_0,
            asset_id=a.id_,
            asset_quantity_unadjusted=-1,
            category_id=t_cat.id_,
        )
        s.add_all((txn_0, t_split_0))
        s.commit()

        n_deleted = a.prune_valuations()
        self.assertEqual(n_deleted, 4)

        # Should be left with one valuation on, one after, and on last
        n = s.query(AssetValuation).count()
        self.assertEqual(n, 3)
        date_ord = s.query(sqlalchemy.func.min(AssetValuation.date_ord)).scalar()
        self.assertEqual(date_ord, today_ord)
        date_ord = s.query(sqlalchemy.func.max(AssetValuation.date_ord)).scalar()
        self.assertEqual(date_ord, today_ord + 3)
        s.rollback()

        # Indices should not be pruned
        a = Asset(name="Banana Index", category=AssetCategory.INDEX)
        s.add(a)
        s.commit()
        for i in range(-3, 3 + 1):
            av = AssetValuation(
                asset_id=a.id_,
                date_ord=today_ord + i,
                value=self.random_decimal(-1, 1),
            )
            s.add(av)
        s.commit()

        n_deleted = a.prune_valuations()
        self.assertEqual(n_deleted, 0)

        n = s.query(AssetValuation).where(AssetValuation.asset_id == a.id_).count()
        self.assertEqual(n, 7)

    def test_update_valuations(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        # Create assets and accounts
        a = Asset(name="Banana Inc.", category=AssetCategory.ITEM)
        acct = Account(
            name="Monkey Bank Checking",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
            emergency=False,
        )
        t_cat = TransactionCategory(
            name="Securities Traded",
            group=TransactionCategoryGroup.OTHER,
            locked=False,
            is_profit_loss=False,
        )

        # No ticker should fail
        self.assertRaises(
            exc.NoAssetWebSourceError,
            a.update_valuations,
            through_today=False,
        )

        a.ticker = "ORANGE"

        # Unbound error still
        self.assertRaises(
            exc.UnboundExecutionError,
            a.update_valuations,
            through_today=False,
        )

        s.add_all((a, acct, t_cat))
        s.commit()

        # No transactions should skip updating
        r_start, r_end = a.update_valuations(through_today=False)
        self.assertIsNone(r_start)
        self.assertIsNone(r_end)

        # Add a transaction
        date = datetime.date(2023, 5, 1)
        date_ord = date.toordinal()
        txn = Transaction(
            account_id=acct.id_,
            date_ord=date_ord,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            amount=txn.amount,
            parent=txn,
            asset_id=a.id_,
            asset_quantity_unadjusted=-1,
            category_id=t_cat.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        # Wrong ticker raises an error
        self.assertRaises(
            exc.AssetWebError,
            a.update_valuations,
            through_today=False,
        )

        a.ticker = "BANANA"
        s.commit()

        # Should update a week before and after and all splits
        r_start, r_end = a.update_valuations(through_today=False)
        s.commit()
        self.assertEqual(r_start, date - datetime.timedelta(days=7))
        self.assertEqual(r_end, date + datetime.timedelta(days=7))

        # There are 11 weekdays within date±7days
        n = s.query(AssetValuation).where(AssetValuation.asset_id == a.id_).count()
        self.assertEqual(n, 11)

        # Check price is correct
        target = Decimal(date_ord)
        v = (
            s.query(AssetValuation)
            .where(
                AssetValuation.asset_id == a.id_,
                AssetValuation.date_ord == date_ord,
            )
            .one()
        )
        v_id = v.id_
        self.assertEqual(v.value, target)

        target = Decimal(date_ord + 1)
        v = (
            s.query(AssetValuation)
            .where(
                AssetValuation.asset_id == a.id_,
                AssetValuation.date_ord == date_ord + 1,
            )
            .one()
        )
        self.assertEqual(v.value, target)

        # Check split is correct
        split = (
            s.query(AssetSplit)
            .where(
                AssetSplit.asset_id == a.id_,
                AssetSplit.date_ord == date_ord,
            )
            .one()
        )
        split_id = split.id_
        self.assertEqual(split.multiplier, Decimal("1.1"))

        # Check all splits up to today got imported
        # Every Monday so once a week
        last_monday = today - datetime.timedelta(days=today.weekday())
        split = (
            s.query(AssetSplit)
            .where(AssetSplit.asset_id == a.id_)
            .order_by(AssetSplit.date_ord.desc())
            .first()
        )
        self.assertEqual(split and split.date_ord, last_monday.toordinal())

        # Number of Mondays between date and today
        target = (today_ord - (date_ord - 7)) // 7 + 1
        n = s.query(AssetSplit).where(AssetSplit.asset_id == a.id_).count()
        self.assertEqual(n, target)

        # Currently holding some, download through today
        r_start, r_end = a.update_valuations(through_today=True)
        s.commit()
        self.assertEqual(r_start, date - datetime.timedelta(days=7))
        self.assertEqual(r_end, today)

        # Newest AssetValuation should be today or Friday
        last_weekday = today - datetime.timedelta(days=max(0, today.weekday() - 4))
        v = (
            s.query(AssetValuation)
            .where(AssetValuation.asset_id == a.id_)
            .order_by(AssetValuation.date_ord.desc())
            .first()
        )
        self.assertEqual(v and v.date_ord, last_weekday.toordinal())

        # Should have reused existing rows
        n = s.query(AssetValuation).where(AssetValuation.id_ == v_id).count()
        self.assertEqual(n, 1)
        n = s.query(AssetSplit).where(AssetSplit.id_ == split_id).count()
        self.assertEqual(n, 1)

        # Move transaction forward so it'll have to delete valuations and splits
        date = datetime.date(2023, 10, 2)
        date_ord = date.toordinal()
        txn.date_ord = date_ord
        t_split.date_ord = date_ord
        s.commit()

        r_start, r_end = a.update_valuations(through_today=False)
        s.commit()
        self.assertEqual(r_start, date - datetime.timedelta(days=7))
        self.assertEqual(r_end, date + datetime.timedelta(days=7))

        # There are 11 weekdays within date±7days
        n = s.query(AssetValuation).where(AssetValuation.asset_id == a.id_).count()
        self.assertEqual(n, 11)

        # Check split is correct
        split = (
            s.query(AssetSplit)
            .where(
                AssetSplit.asset_id == a.id_,
                AssetSplit.date_ord == date_ord,
            )
            .one()
        )
        split_id = split.id_
        self.assertEqual(split.multiplier, Decimal("1.1"))

        # Number of Mondays between date and today
        target = (today_ord - (date_ord - 7)) // 7 + 1
        n = s.query(AssetSplit).where(AssetSplit.asset_id == a.id_).count()
        self.assertEqual(n, target)

        # Should have still reused existing rows
        n = s.query(AssetValuation).where(AssetValuation.id_ == v_id).count()
        self.assertEqual(n, 1)
        n = s.query(AssetSplit).where(AssetSplit.id_ == split_id).count()
        self.assertEqual(n, 1)

        # Add index which should be updated through today
        a = Asset(name="Banana Index", category=AssetCategory.INDEX, ticker="^BANANA")
        s.add(a)
        s.commit()

        r_start, r_end = a.update_valuations(through_today=False)
        s.commit()
        self.assertEqual(r_start, date - datetime.timedelta(days=7))
        self.assertEqual(r_end, today)

    def test_index_twrr(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        # Add index which should be updated through today
        a = Asset(name="Banana Index", category=AssetCategory.INDEX, ticker="^BANANA")
        s.add(a)
        s.commit()

        av = AssetValuation(
            asset_id=a.id_,
            date_ord=today_ord - 1,
            value=Decimal(1),
        )
        s.add(av)
        av = AssetValuation(
            asset_id=a.id_,
            date_ord=today_ord,
            value=Decimal(2),
        )
        s.add(av)
        s.commit()

        target = [
            Decimal(0),
            Decimal(0),
            Decimal(1),
        ]
        result = Asset.index_twrr(s, "Banana Index", today_ord - 2, today_ord)
        self.assertEqual(result, target)

    def test_add_indices(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        Asset.add_indices(s)

        n = s.query(Asset).count()
        self.assertEqual(n, 6)

        # They should all be indices
        n = s.query(Asset).where(Asset.category == AssetCategory.INDEX).count()
        self.assertEqual(n, 6)
