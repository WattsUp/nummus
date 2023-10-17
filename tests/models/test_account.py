from __future__ import annotations

import datetime

from nummus import models
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from tests.base import TestBase


class TestAccount(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        d = {
            "name": self.random_string(),
            "institution": self.random_string(),
            "category": AccountCategory.CASH,
            "closed": False,
        }

        acct = Account(**d)
        s.add(acct)
        s.commit()

        self.assertEqual(d["name"], acct.name)
        self.assertEqual(d["institution"], acct.institution)
        self.assertEqual(d["category"], acct.category)
        self.assertEqual(d["closed"], acct.closed)
        self.assertIsNone(acct.opened_on)
        self.assertIsNone(acct.updated_on)

        # Short strings are bad
        self.assertRaises(ValueError, setattr, acct, "name", "ab")

    def test_add_transactions(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()

        d = {
            "name": self.random_string(),
            "institution": self.random_string(),
            "category": AccountCategory.CASH,
            "closed": False,
        }

        acct = Account(**d)
        s.add(acct)
        s.commit()

        self.assertIsNone(acct.opened_on)
        self.assertIsNone(acct.updated_on)

        # Transaction are sorted by date

        t_today = Transaction(
            account_id=acct.id_,
            date=today,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        s.add(t_today)
        s.commit()

        self.assertEqual(today, acct.opened_on)
        self.assertEqual(today, acct.updated_on)

        t_before = Transaction(
            account_id=acct.id_,
            date=today - datetime.timedelta(days=1),
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        s.add(t_before)
        s.commit()

        self.assertEqual(t_before.date, acct.opened_on)
        self.assertEqual(today, acct.updated_on)

        t_after = Transaction(
            account_id=acct.id_,
            date=today + datetime.timedelta(days=1),
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        s.add(t_after)
        s.commit()

        self.assertEqual(t_before.date, acct.opened_on)
        self.assertEqual(t_after.date, acct.updated_on)

    def test_get_asset_qty(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
        )
        assets: list[Asset] = []
        for _ in range(3):
            new_asset = Asset(
                name=self.random_string(),
                category=AssetCategory.SECURITY,
            )
            assets.append(new_asset)
        t_cat = TransactionCategory(
            name="Securities Traded",
            group=TransactionCategoryGroup.OTHER,
            locked=False,
        )
        s.add(t_cat)
        s.add(acct)
        s.add_all(assets)
        s.commit()

        target_dates = [(today + datetime.timedelta(days=i)) for i in range(-3, 3 + 1)]
        target_qty = {}

        result_dates, result_qty = acct.get_asset_qty(target_dates[0], target_dates[-1])
        self.assertEqual(target_dates, result_dates)
        self.assertEqual(target_qty, result_qty)

        # Fund account on first day
        txn = Transaction(
            account_id=acct.id_,
            date=target_dates[1],
            amount=self.random_decimal(10, 100),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(parent=txn, amount=txn.amount, category_id=t_cat.id_)
        s.add_all((txn, t_split))
        s.commit()

        # Buy asset[0] on the second day
        q0 = self.random_decimal(0, 10)
        txn = Transaction(
            account_id=acct.id_,
            date=target_dates[1],
            amount=self.random_decimal(-10, -1),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            asset_id=assets[0].id_,
            asset_quantity_unadjusted=q0,
            category_id=t_cat.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        target_qty = {assets[0].id_: [0, q0, q0, q0, q0, q0, q0]}

        result_dates, result_qty = acct.get_asset_qty(target_dates[0], target_dates[-1])
        self.assertEqual(target_dates, result_dates)
        self.assertEqual(target_qty, result_qty)

        # Sell asset[0] on the last day
        q1 = self.random_decimal(0, 10)
        txn = Transaction(
            account_id=acct.id_,
            date=target_dates[-1],
            amount=self.random_decimal(1, 10),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            asset_id=assets[0].id_,
            asset_quantity_unadjusted=-q1,
            category_id=t_cat.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        target_qty = {assets[0].id_: [0, q0, q0, q0, q0, q0, q0 - q1]}

        result_dates, result_qty = acct.get_asset_qty(target_dates[0], target_dates[-1])
        self.assertEqual(target_dates, result_dates)
        self.assertEqual(target_qty, result_qty)

        # Buy asset[1] on today
        q2 = self.random_decimal(0, 10)
        txn = Transaction(
            account_id=acct.id_,
            date=today,
            amount=self.random_decimal(-10, -1),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            asset_id=assets[1].id_,
            asset_quantity_unadjusted=q2,
            category_id=t_cat.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        target_qty = {assets[0].id_: [0, q0, q0, q0], assets[1].id_: [0, 0, 0, q2]}

        result_dates, result_qty = acct.get_asset_qty(target_dates[0], today)
        self.assertEqual(target_dates[0:4], result_dates)
        self.assertEqual(target_qty, result_qty)

        # Test single value
        target_qty = {assets[0].id_: [q0], assets[1].id_: [q2]}
        result_dates, result_qty = acct.get_asset_qty(today, today)
        self.assertListEqual([today], result_dates)
        self.assertEqual(target_qty, result_qty)

        # Test single value
        future = target_dates[-1] + datetime.timedelta(days=1)
        target_qty = {assets[0].id_: [q0 - q1], assets[1].id_: [q2]}
        result_dates, result_qty = acct.get_asset_qty(future, future)
        self.assertListEqual([future], result_dates)
        self.assertEqual(target_qty, result_qty)

    def test_get_value(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
        )
        assets: list[Asset] = []
        for _ in range(3):
            new_asset = Asset(
                name=self.random_string(),
                category=AssetCategory.SECURITY,
            )
            assets.append(new_asset)
        s.add(acct)
        s.add_all(assets)
        s.commit()

        categories = TransactionCategory.add_default(s)
        t_cat = categories["Uncategorized"]

        target_dates = [(today + datetime.timedelta(days=i)) for i in range(-3, 3 + 1)]
        target_values = [0] * 7
        target_assets = {}
        start = target_dates[0]
        end = target_dates[-1]

        r_dates, r_values, r_assets = acct.get_value(start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual(target_values, r_values)
        self.assertEqual(target_assets, r_assets)

        r_dates, r_values = Account.get_value_all(s, start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual({acct.id_: target_values}, r_values)

        r_dates, r_values = Account.get_value_all(s, start, end, ids=[acct.id_])
        self.assertEqual(target_dates, r_dates)
        self.assertEqual({acct.id_: target_values}, r_values)

        r_dates, r_values = Account.get_value_all(s, start, end, ids=[-100])
        self.assertEqual(target_dates, r_dates)
        self.assertEqual({}, r_values)

        # Fund account on first day
        t_fund = self.random_decimal(10, 100)
        txn = Transaction(
            account_id=acct.id_,
            date=target_dates[1],
            amount=t_fund,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(parent=txn, amount=txn.amount, category_id=t_cat.id_)
        s.add_all((txn, t_split))
        s.commit()

        target_values = [0, t_fund, t_fund, t_fund, t_fund, t_fund, t_fund]

        r_dates, r_values, r_assets = acct.get_value(start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual(target_values, r_values)
        self.assertEqual(target_assets, r_assets)

        r_dates, r_values = Account.get_value_all(s, start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual({acct.id_: target_values}, r_values)

        # Buy asset[0] on the second day
        t0 = self.random_decimal(-10, -1)
        q0 = self.random_decimal(0, 10)
        txn = Transaction(
            account_id=acct.id_,
            date=target_dates[1],
            amount=t0,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            asset_id=assets[0].id_,
            asset_quantity_unadjusted=q0,
            category_id=t_cat.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        target_values = [
            0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
        ]
        target_assets = {assets[0].id_: [0] * 7}

        r_dates, r_values, r_assets = acct.get_value(start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual(target_values, r_values)
        self.assertEqual(target_assets, r_assets)

        r_dates, r_values = Account.get_value_all(s, start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual({acct.id_: target_values}, r_values)

        # Sell asset[0] on the last day
        t1 = self.random_decimal(1, 10)
        txn = Transaction(
            account_id=acct.id_,
            date=target_dates[-1],
            amount=t1,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            asset_id=assets[0].id_,
            asset_quantity_unadjusted=-q0,
            category_id=t_cat.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        target_values = [
            0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0 + t1,
        ]
        target_assets = {assets[0].id_: [0] * 7}

        r_dates, r_values, r_assets = acct.get_value(start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual(target_values, r_values)
        self.assertEqual(target_assets, r_assets)

        r_dates, r_values = Account.get_value_all(s, start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual({acct.id_: target_values}, r_values)

        # Add valuations to Asset
        prices = self.random_decimal(1, 10, size=len(target_dates))
        for date, p in zip(target_dates, prices, strict=True):
            v = AssetValuation(asset_id=assets[0].id_, date=date, value=p)
            s.add(v)
        s.commit()

        asset_values = [
            round(p * q, 6)
            for p, q in zip(prices, [0, q0, q0, q0, q0, q0, 0], strict=True)
        ]
        target_values = [
            c + v for c, v in zip(target_values, asset_values, strict=True)
        ]
        target_assets = {assets[0].id_: asset_values}

        r_dates, r_values, r_assets = acct.get_value(start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual(target_values, r_values)
        self.assertEqual(target_assets, r_assets)

        r_dates, r_values = Account.get_value_all(s, start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual({acct.id_: target_values}, r_values)

        # Test single value
        r_dates, r_values, r_assets = acct.get_value(today, today)
        self.assertEqual([today], r_dates)
        self.assertEqual([target_values[3]], r_values)
        self.assertEqual({assets[0].id_: [asset_values[3]]}, r_assets)

        r_dates, r_values = Account.get_value_all(s, today, today)
        self.assertEqual([today], r_dates)
        self.assertEqual({acct.id_: [target_values[3]]}, r_values)

        # Test single value
        future = target_dates[-1] + datetime.timedelta(days=1)
        r_dates, r_values, r_assets = acct.get_value(future, future)
        self.assertEqual([future], r_dates)
        self.assertEqual([target_values[-1]], r_values)
        self.assertEqual({}, r_assets)

        r_dates, r_values = Account.get_value_all(s, future, future)
        self.assertEqual([future], r_dates)
        self.assertEqual({acct.id_: [target_values[-1]]}, r_values)

    def test_get_cash_flow(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
        )
        s.add(acct)
        s.commit()

        categories = TransactionCategory.add_default(s)
        t_cat_fund = categories["Transfers"]
        t_cat_trade = categories["Securities Traded"]

        target_dates = [(today + datetime.timedelta(days=i)) for i in range(-3, 3 + 1)]
        target_categories = {cat.id_: [0] * 7 for cat in categories.values()}
        start = target_dates[0]
        end = target_dates[-1]

        r_dates, r_categories = acct.get_cash_flow(start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual(target_categories, r_categories)

        # Fund account on second day
        t_fund = self.random_decimal(10, 100)
        txn = Transaction(
            account_id=acct.id_,
            date=target_dates[1],
            amount=t_fund,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=t_cat_fund.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        target_categories[t_cat_fund.id_][1] += t_fund

        r_dates, r_categories = acct.get_cash_flow(start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual(target_categories, r_categories)

        # Buy something on the second day
        t0 = self.random_decimal(-10, -1)
        txn = Transaction(
            account_id=acct.id_,
            date=target_dates[1],
            amount=t0,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=t_cat_trade.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        target_categories[t_cat_trade.id_][1] += t0

        r_dates, r_categories = acct.get_cash_flow(start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual(target_categories, r_categories)

        # Sell something on the last day
        t1 = self.random_decimal(1, 10)
        txn = Transaction(
            account_id=acct.id_,
            date=target_dates[-1],
            amount=t1,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=t_cat_trade.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        target_categories[t_cat_trade.id_][-1] += t1

        r_dates, r_categories = acct.get_cash_flow(start, end)
        self.assertEqual(target_dates, r_dates)
        self.assertEqual(target_categories, r_categories)

        # Test single value
        r_dates, r_categories = acct.get_cash_flow(today, today)
        self.assertEqual([today], r_dates)
        self.assertEqual(
            {cat: [v[3]] for cat, v in target_categories.items()},
            r_categories,
        )

        r_dates, r_categories = acct.get_cash_flow(end, end)
        self.assertEqual([end], r_dates)
        self.assertEqual(
            {cat: [v[-1]] for cat, v in target_categories.items()},
            r_categories,
        )
