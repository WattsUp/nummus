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
            "category": AssetCategory.SECURITY,
            "unit": self.random_string(),
            "tag": self.random_string(),
            "img_suffix": self.random_string(),
        }

        a = Asset(**d)
        s.add(a)
        s.commit()

        self.assertEqual(a.name, d["name"])
        self.assertEqual(a.description, d["description"])
        self.assertEqual(a.category, d["category"])
        self.assertEqual(a.unit, d["unit"])
        self.assertEqual(a.tag, d["tag"])
        self.assertEqual(a.img_suffix, d["img_suffix"])
        self.assertEqual(a.image_name, f"{a.uri}{d['img_suffix']}")

        a.img_suffix = None
        self.assertIsNone(a.image_name)

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

    def test_add_valuations(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        d = {
            "name": self.random_string(),
            "description": self.random_string(),
            "category": AssetCategory.SECURITY,
            "unit": self.random_string(),
            "tag": self.random_string(),
            "img_suffix": self.random_string(),
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
            "category": AssetCategory.SECURITY,
            "unit": self.random_string(),
            "tag": self.random_string(),
            "img_suffix": self.random_string(),
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

    def test_update_splits(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday_ord = today_ord - 1

        multiplier_0 = round(self.random_decimal(1, 10))
        multiplier_1 = round(self.random_decimal(1, 10))
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

        self.assertEqual(t_split_0.asset_quantity, 1 * multiplier)
        self.assertEqual(t_split_1.asset_quantity, 1)

        r_assets = acct.get_asset_qty(yesterday_ord, today_ord)
        r_values = r_assets[a.id_]
        target_values = [multiplier, multiplier + 1]
        self.assertEqual(r_values, target_values)

        _, r_assets = acct.get_value(yesterday_ord, today_ord)
        r_values = r_assets[a.id_]
        target_values = [value_yesterday, value_yesterday + value_today]
        self.assertEqual(r_values, target_values)
