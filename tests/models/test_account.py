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
            "emergency": False,
        }

        acct = Account(**d)

        # Unbound to a session will raise UnboundExecutionError
        self.assertRaises(exc.UnboundExecutionError, getattr, acct, "opened_on_ord")
        self.assertRaises(exc.UnboundExecutionError, getattr, acct, "updated_on_ord")

        s.add(acct)
        s.commit()

        self.assertEqual(acct.name, d["name"])
        self.assertEqual(acct.institution, d["institution"])
        self.assertEqual(acct.category, d["category"])
        self.assertEqual(acct.closed, d["closed"])
        self.assertEqual(acct.emergency, d["emergency"])
        self.assertIsNone(acct.opened_on_ord)
        self.assertIsNone(acct.updated_on_ord)

        # Short strings are bad
        self.assertRaises(exc.InvalidORMValueError, setattr, acct, "name", "ab")

    def test_add_transactions(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        d = {
            "name": self.random_string(),
            "institution": self.random_string(),
            "category": AccountCategory.CASH,
            "closed": False,
            "emergency": False,
        }

        acct = Account(**d)
        s.add(acct)
        s.commit()

        self.assertIsNone(acct.opened_on_ord)
        self.assertIsNone(acct.updated_on_ord)

        # Transaction are sorted by date

        t_today = Transaction(
            account_id=acct.id_,
            date_ord=today_ord,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        s.add(t_today)
        s.commit()

        self.assertEqual(acct.opened_on_ord, today_ord)
        self.assertEqual(acct.updated_on_ord, today_ord)

        t_before = Transaction(
            account_id=acct.id_,
            date_ord=today_ord - 1,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        s.add(t_before)
        s.commit()

        self.assertEqual(acct.opened_on_ord, t_before.date_ord)
        self.assertEqual(acct.updated_on_ord, today_ord)

        t_after = Transaction(
            account_id=acct.id_,
            date_ord=today_ord + 1,
            amount=self.random_decimal(-1, 1),
            statement=self.random_string(),
        )
        s.add(t_after)
        s.commit()

        self.assertEqual(acct.opened_on_ord, t_before.date_ord)
        self.assertEqual(acct.updated_on_ord, t_after.date_ord)

    def test_get_asset_qty(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
            emergency=False,
        )
        assets: list[Asset] = []
        for _ in range(3):
            new_asset = Asset(
                name=self.random_string(),
                category=AssetCategory.STOCKS,
            )
            assets.append(new_asset)
        t_cat = TransactionCategory(
            name="Securities Traded",
            group=TransactionCategoryGroup.OTHER,
            locked=False,
            is_profit_loss=False,
        )

        # Unbound to a session will raise UnboundExecutionError
        self.assertRaises(
            exc.UnboundExecutionError,
            acct.get_asset_qty,
            today_ord,
            today_ord,
        )

        s.add(t_cat)
        s.add(acct)
        s.add_all(assets)
        s.commit()

        target_qty = {}
        start = today_ord - 3
        end = today_ord + 3

        result_qty = acct.get_asset_qty(start, end)
        self.assertEqual(result_qty, target_qty)
        result_qty = Account.get_asset_qty_all(s, start, end)
        self.assertEqual(result_qty, {acct.id_: target_qty})

        # Fund account on second day
        txn = Transaction(
            account_id=acct.id_,
            date_ord=start + 1,
            amount=self.random_decimal(10, 100),
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=t_cat.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        # Buy asset[0] on the second day
        q0 = self.random_decimal(0, 10)
        txn = Transaction(
            account_id=acct.id_,
            date_ord=start + 1,
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

        target_qty = {assets[0].id_: [Decimal(0), q0, q0, q0, q0, q0, q0]}

        result_qty = acct.get_asset_qty(start, end)
        self.assertEqual(result_qty, target_qty)
        result_qty = Account.get_asset_qty_all(s, start, end)
        self.assertEqual(result_qty, {acct.id_: target_qty})

        # Sell asset[0] on the last day
        q1 = self.random_decimal(0, 10)
        txn = Transaction(
            account_id=acct.id_,
            date_ord=end,
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

        result_qty = acct.get_asset_qty(start, end)
        self.assertEqual(result_qty, target_qty)
        result_qty = Account.get_asset_qty_all(s, start, end)
        self.assertEqual(result_qty, {acct.id_: target_qty})

        # Buy asset[1] on today
        q2 = self.random_decimal(0, 10)
        txn = Transaction(
            account_id=acct.id_,
            date_ord=today_ord,
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

        result_qty = acct.get_asset_qty(start, today_ord)
        self.assertEqual(result_qty, target_qty)
        result_qty = Account.get_asset_qty_all(s, start, today_ord)
        self.assertEqual(result_qty, {acct.id_: target_qty})

        # Test single value
        target_qty = {assets[0].id_: [q0], assets[1].id_: [q2]}
        result_qty = acct.get_asset_qty(today_ord, today_ord)
        self.assertEqual(result_qty, target_qty)
        result_qty = Account.get_asset_qty_all(s, today_ord, today_ord)
        self.assertEqual(result_qty, {acct.id_: target_qty})

        # Test single value
        future = end + 1
        target_qty = {assets[0].id_: [q0 - q1], assets[1].id_: [q2]}
        result_qty = acct.get_asset_qty(future, future)
        self.assertEqual(result_qty, target_qty)
        result_qty = Account.get_asset_qty_all(s, future, future)
        self.assertEqual(result_qty, {acct.id_: target_qty})

        # Create an unrelated account
        acct_unrelated = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
            emergency=False,
        )
        s.add(acct_unrelated)
        s.commit()
        txn = Transaction(
            account_id=acct_unrelated.id_,
            date_ord=today_ord,
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

        # Unchanged get get_asset_qty
        result_qty = acct.get_asset_qty(start, today_ord)
        self.assertEqual(result_qty, target_qty)

        # But all will have changed
        result_qty = Account.get_asset_qty_all(s, start, today_ord)
        self.assertEqual(
            result_qty,
            {acct.id_: target_qty, acct_unrelated.id_: {assets[1].id_: [0, 0, 0, q2]}},
        )

    def test_get_value(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
            emergency=False,
        )
        assets: list[Asset] = []
        for _ in range(3):
            new_asset = Asset(
                name=self.random_string(),
                category=AssetCategory.STOCKS,
            )
            assets.append(new_asset)

        # Unbound to a session will raise UnboundExecutionError
        self.assertRaises(
            exc.UnboundExecutionError,
            acct.get_value,
            today_ord,
            today_ord,
        )

        s.add(acct)
        s.add_all(assets)
        s.commit()

        categories = TransactionCategory.add_default(s)
        categories = {name: t_cat.id_ for name, t_cat in categories.items()}

        target_values = [0] * 7
        target_profit = [0] * 7
        target_assets = {}
        start = today_ord - 3
        end = today_ord + 3

        r_values, r_profit, r_assets = acct.get_value(start, end)
        self.assertEqual(r_values, target_values)
        self.assertEqual(r_profit, target_profit)
        self.assertEqual(r_assets, target_assets)

        r_values, r_profit, r_assets = Account.get_value_all(s, start, end)
        self.assertEqual(r_values, {acct.id_: target_values})
        self.assertEqual(r_profit, {acct.id_: target_profit})
        self.assertEqual(r_assets, target_assets)

        r_values, r_profit, r_assets = Account.get_value_all(
            s,
            start,
            end,
            ids=[acct.id_],
        )
        self.assertEqual(r_values, {acct.id_: target_values})
        self.assertEqual(r_profit, {acct.id_: target_profit})
        self.assertEqual(r_assets, target_assets)

        r_values, r_profit, r_assets = Account.get_value_all(s, start, end, ids=[])
        self.assertEqual(r_values, {})
        self.assertEqual(r_profit, {})
        self.assertEqual(r_assets, {})

        # Fund account on second day with interest
        t_fund = self.random_decimal(10, 100)
        t_fund = 100
        txn = Transaction(
            account_id=acct.id_,
            date_ord=start + 1,
            amount=t_fund,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=categories["Interest"],
        )
        s.add_all((txn, t_split))
        s.commit()

        target_values = [0, t_fund, t_fund, t_fund, t_fund, t_fund, t_fund]
        target_profit = [0, t_fund, t_fund, t_fund, t_fund, t_fund, t_fund]

        r_values, r_profit, r_assets = acct.get_value(start, end)
        self.assertEqual(r_values, target_values)
        self.assertEqual(r_profit, target_profit)
        self.assertEqual(r_assets, target_assets)

        r_values, r_profit, r_assets = Account.get_value_all(s, start, end)
        self.assertEqual(r_values, {acct.id_: target_values})
        self.assertEqual(r_profit, {acct.id_: target_profit})
        self.assertEqual(r_assets, target_assets)

        # Profit on second day should be equal to interest amount
        r_values, r_profit, r_assets = acct.get_value(start + 1, start + 1)
        self.assertEqual(r_values, [target_values[1]])
        self.assertEqual(r_profit, [target_profit[1]])
        self.assertEqual(r_assets, target_assets)

        # Profit on third day should be zero
        r_values, r_profit, r_assets = acct.get_value(start + 2, start + 2)
        self.assertEqual(r_values, [target_values[2]])
        self.assertEqual(r_profit, [0])
        self.assertEqual(r_assets, target_assets)

        # Buy asset[0] on the second day
        t0 = self.random_decimal(-10, -1)
        t0 = -10
        q0 = self.random_decimal(0, 10)
        q0 = 1
        txn = Transaction(
            account_id=acct.id_,
            date_ord=start + 1,
            amount=t0,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            asset_id=assets[0].id_,
            asset_quantity_unadjusted=q0,
            category_id=categories["Securities Traded"],
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
        # Buying an asset worth zero is loss
        target_profit = [
            0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
        ]
        target_assets = {assets[0].id_: [0] * 7}

        r_values, r_profit, r_assets = acct.get_value(start, end)
        self.assertEqual(r_values, target_values)
        self.assertEqual(r_profit, target_profit)
        self.assertEqual(r_assets, target_assets)

        r_values, r_profit, r_assets = Account.get_value_all(s, start, end)
        self.assertEqual(r_values, {acct.id_: target_values})
        self.assertEqual(r_profit, {acct.id_: target_profit})
        self.assertEqual(r_assets, target_assets)

        # Sell asset[0] on the second to last day
        t1 = self.random_decimal(1, 10)
        t1 = 9
        txn = Transaction(
            account_id=acct.id_,
            date_ord=end - 1,
            amount=t1,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            asset_id=assets[0].id_,
            asset_quantity_unadjusted=-q0,
            category_id=categories["Securities Traded"],
        )
        s.add_all((txn, t_split))
        s.commit()

        target_values = [
            0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0 + t1,
            t_fund + t0 + t1,
        ]
        target_profit = [
            0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0,
            t_fund + t0 + t1,
            t_fund + t0 + t1,
        ]
        target_assets = {assets[0].id_: [0] * 7}

        r_values, r_profit, r_assets = acct.get_value(start, end)
        self.assertEqual(r_values, target_values)
        self.assertEqual(r_profit, target_profit)
        self.assertEqual(r_assets, target_assets)

        r_values, r_profit, r_assets = Account.get_value_all(s, start, end)
        self.assertEqual(r_values, {acct.id_: target_values})
        self.assertEqual(r_profit, {acct.id_: target_profit})
        self.assertEqual(r_assets, target_assets)

        # Add valuations to Asset
        prices = [self.random_decimal(1, 10) for _ in range(7)]
        prices = list(range(7))
        for i, p in enumerate(prices):
            v = AssetValuation(
                asset_id=assets[0].id_,
                date_ord=start + i,
                value=p,
            )
            s.add(v)
        s.commit()

        # No rounding cause UI will round anyways, and unrounded is more factual
        asset_values = [
            p * q for p, q in zip(prices, [0, q0, q0, q0, q0, 0, 0], strict=True)
        ]
        target_values = [
            c + v for c, v in zip(target_values, asset_values, strict=True)
        ]
        target_profit = [
            c + v for c, v in zip(target_profit, asset_values, strict=True)
        ]
        target_assets = {assets[0].id_: asset_values}

        r_values, r_profit, r_assets = acct.get_value(start, end)
        self.assertEqual(r_values, target_values)
        self.assertEqual(r_profit, target_profit)
        self.assertEqual(r_assets, target_assets)

        r_values, r_profit, r_assets = Account.get_value_all(s, start, end)
        self.assertEqual(r_values, {acct.id_: target_values})
        self.assertEqual(r_profit, {acct.id_: target_profit})
        self.assertEqual(r_assets, target_assets)

        # Profit on day of asset trade should be valid too
        r_values, r_profit, r_assets = acct.get_value(start + 1, start + 1)
        self.assertEqual(r_values, [target_values[1]])
        self.assertEqual(r_profit, [t_fund + t0 + asset_values[1]])
        self.assertEqual(r_assets, {assets[0].id_: [asset_values[1]]})

        # Profit on day after of asset trade should be valid too
        r_values, r_profit, r_assets = acct.get_value(start + 2, start + 2)
        self.assertEqual(r_values, [target_values[2]])
        self.assertEqual(r_profit, [0])
        self.assertEqual(r_assets, {assets[0].id_: [asset_values[2]]})

        # Profit on day of asset sell should be valid too
        r_values, r_profit, r_assets = acct.get_value(end - 1, end - 1)
        self.assertEqual(r_values, [target_values[5]])
        self.assertEqual(r_profit, [t1 - q0 * prices[5]])
        self.assertEqual(r_assets, {assets[0].id_: [asset_values[5]]})

        # Transactions not included in profit & loss affect value but not profit
        t2 = self.random_decimal(1, 10)
        txn = Transaction(
            account_id=acct.id_,
            date_ord=start,
            amount=t2,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=categories["Other Income"],
        )
        s.add_all((txn, t_split))
        t3 = self.random_decimal(-10, -1)
        txn = Transaction(
            account_id=acct.id_,
            date_ord=end,
            amount=t3,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=categories["Groceries"],
        )
        s.add_all((txn, t_split))
        s.commit()

        target_values = [t + t2 for t in target_values]
        target_values[-1] += t3
        r_values, r_profit, r_assets = acct.get_value(start, end)
        self.assertEqual(r_values, target_values)
        self.assertEqual(r_profit, target_profit)
        self.assertEqual(r_assets, target_assets)

        # Test single value
        r_values, r_profit, r_assets = acct.get_value(today_ord, today_ord)
        self.assertEqual(r_values, [target_values[3]])
        self.assertEqual(r_profit, [0])
        self.assertEqual(r_assets, {assets[0].id_: [asset_values[3]]})

        r_values, r_profit, r_assets = Account.get_value_all(s, today_ord, today_ord)
        self.assertEqual(r_values, {acct.id_: [target_values[3]]})
        self.assertEqual(r_profit, {acct.id_: [0]})
        self.assertEqual(r_assets, {assets[0].id_: [asset_values[3]]})

        # Test single value
        future = end + 1
        r_values, r_profit, r_assets = acct.get_value(future, future)
        self.assertEqual(r_values, [target_values[-1]])
        self.assertEqual(r_profit, [0])
        self.assertEqual(r_assets, {})

        r_values, r_profit, r_assets = Account.get_value_all(s, future, future)
        self.assertEqual(r_values, {acct.id_: [target_values[-1]]})
        self.assertEqual(r_profit, {acct.id_: [0]})
        self.assertEqual(r_assets, {})

        # Create an unrelated account
        acct_unrelated = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
            emergency=False,
        )
        s.add(acct_unrelated)
        s.commit()
        txn = Transaction(
            account_id=acct_unrelated.id_,
            date_ord=end,
            amount=t0,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            asset_id=assets[1].id_,
            asset_quantity_unadjusted=q0,
            category_id=categories["Securities Traded"],
        )
        s.add_all((txn, t_split))
        s.commit()

        # Unchanged get value
        r_values, r_profit, r_assets = Account.get_value_all(
            s,
            future,
            future,
            ids=[acct.id_],
        )
        self.assertEqual(r_values, {acct.id_: [target_values[-1]]})
        self.assertEqual(r_profit, {acct.id_: [0]})
        self.assertEqual(r_assets, {})

        # Add a day trade
        txn = Transaction(
            account_id=acct_unrelated.id_,
            date_ord=end,
            amount=t1,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            asset_id=assets[1].id_,
            asset_quantity_unadjusted=-q0,
            category_id=categories["Securities Traded"],
        )
        s.add_all((txn, t_split))
        s.commit()

        # Day trade profit should be valid
        r_values, r_profit, r_assets = acct_unrelated.get_value(end, end)
        self.assertEqual(r_values, [t0 + t1])
        self.assertEqual(r_profit, [t0 + t1])
        self.assertEqual(r_assets, {})

    def test_get_cash_flow(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        acct = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
            emergency=False,
        )

        # Unbound to a session will raise UnboundExecutionError
        self.assertRaises(exc.UnboundExecutionError, acct.get_cash_flow, today, today)

        s.add(acct)
        s.commit()

        categories = TransactionCategory.add_default(s)
        t_cat_fund = categories["Transfers"]
        t_cat_trade = categories["Securities Traded"]

        target_categories = {cat.id_: [Decimal(0)] * 7 for cat in categories.values()}
        start = today_ord - 3
        end = today_ord + 3

        r_categories = acct.get_cash_flow(start, end)
        self.assertEqual(r_categories, target_categories)
        r_categories = Account.get_cash_flow_all(s, start, end)
        self.assertEqual(r_categories, target_categories)

        # Fund account on second day
        t_fund = self.random_decimal(10, 100)
        txn = Transaction(
            account_id=acct.id_,
            date_ord=start + 1,
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

        r_categories = acct.get_cash_flow(start, end)
        self.assertEqual(r_categories, target_categories)
        r_categories = Account.get_cash_flow_all(s, start, end)
        self.assertEqual(r_categories, target_categories)

        # Buy something on the second day
        t0 = self.random_decimal(-10, -1)
        txn = Transaction(
            account_id=acct.id_,
            date_ord=start + 1,
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

        r_categories = acct.get_cash_flow(start, end)
        self.assertEqual(r_categories, target_categories)
        r_categories = Account.get_cash_flow_all(s, start, end)
        self.assertEqual(r_categories, target_categories)

        # Sell something on the last day
        t1 = self.random_decimal(1, 10)
        txn = Transaction(
            account_id=acct.id_,
            date_ord=end,
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

        r_categories = acct.get_cash_flow(start, end)
        self.assertEqual(r_categories, target_categories)
        r_categories = Account.get_cash_flow_all(s, start, end)
        self.assertEqual(r_categories, target_categories)

        # Test single value
        r_categories = acct.get_cash_flow(today_ord, today_ord)
        self.assertEqual(
            r_categories,
            {cat: [v[3]] for cat, v in target_categories.items()},
        )

        r_categories = acct.get_cash_flow(end, end)
        self.assertEqual(
            r_categories,
            {cat: [v[-1]] for cat, v in target_categories.items()},
        )

        # Create an unrelated account
        acct_unrelated = Account(
            name=self.random_string(),
            institution=self.random_string(),
            category=AccountCategory.INVESTMENT,
            closed=False,
            emergency=False,
        )
        s.add(acct_unrelated)
        s.commit()
        txn = Transaction(
            account_id=acct_unrelated.id_,
            date_ord=end,
            amount=t1,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=t_cat_fund.id_,
        )
        s.add_all((txn, t_split))
        s.commit()

        # Unchanged get get_cash_flow
        r_categories = acct.get_cash_flow(start, end)
        self.assertEqual(r_categories, target_categories)

        # But all will have changed
        target_categories[t_cat_fund.id_][-1] += t1
        r_categories = Account.get_cash_flow_all(s, start, end)
        self.assertEqual(r_categories, target_categories)
