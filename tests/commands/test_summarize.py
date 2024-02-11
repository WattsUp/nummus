from __future__ import annotations

import datetime
import io
import shutil
import textwrap
from decimal import Decimal
from unittest import mock

from nummus import portfolio
from nummus.commands import create_, summarize_
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestSummarize(TestBase):
    def test_summarize(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create_.create(path_db, None, force=False, no_encrypt=True)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        target = {
            "n_accounts": 0,
            "n_assets": 0,
            "n_transactions": 0,
            "n_valuations": 0,
            "net_worth": Decimal(0),
            "accounts": [],
            "total_asset_value": Decimal(0),
            "assets": [],
            "db_size": path_db.stat().st_size,
        }
        result = summarize_._get_summary(p)  # noqa: SLF001
        self.assertEqual(result, target)

        today = datetime.date.today()
        today_ord = today.toordinal()

        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            acct_0 = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                emergency=False,
            )
            acct_1 = Account(
                name="Monkey Bank Credit",
                institution="Monkey Bank",
                category=AccountCategory.CREDIT,
                closed=False,
                emergency=False,
            )
            s.add_all((acct_0, acct_1))
            s.commit()

            acct_0_id = acct_0.id_
            acct_1_id = acct_1.id_

            a_banana = Asset(name="Banana", category=AssetCategory.ITEM)
            a_apple_0 = Asset(name="Apple", category=AssetCategory.REAL_ESTATE)
            a_apple_1 = Asset(
                name="Tech Company",
                description="Apples and Bananas",
                category=AssetCategory.STOCKS,
                ticker="APPLE",
            )
            s.add_all((a_banana, a_apple_0, a_apple_1))
            s.commit()

            a_apple_0_id = a_apple_0.id_
            a_apple_1_id = a_apple_1.id_

            txn_0 = Transaction(
                account_id=acct_0.id_,
                date_ord=today_ord - 1,
                amount=100,
                statement="Banana Store",
            )
            t_split_0 = TransactionSplit(
                amount=txn_0.amount,
                parent=txn_0,
                asset_id=a_apple_0.id_,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn_0, t_split_0))
            s.commit()

            txn_1 = Transaction(
                account_id=acct_0.id_,
                date_ord=today_ord,
                amount=-10,
                statement="Banana Store",
            )
            t_split_1 = TransactionSplit(
                amount=txn_1.amount,
                parent=txn_1,
                asset_id=a_apple_1.id_,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn_1, t_split_1))
            s.commit()

            txn_2 = Transaction(
                account_id=acct_0.id_,
                date_ord=today_ord,
                amount=-10,
                statement="Banana Store",
            )
            t_split_2 = TransactionSplit(
                amount=txn_2.amount,
                parent=txn_2,
                category_id=categories["Uncategorized"],
            )
            s.add_all((txn_2, t_split_2))
            s.commit()

            av = AssetValuation(
                asset_id=a_apple_0.id_,
                date_ord=today_ord - 1,
                value=37,
            )
            s.add(av)
            s.commit()
            v_apple_0 = av.value * (t_split_0.asset_quantity or 0)
            profit_apple_0 = v_apple_0 + 100

            av = AssetValuation(
                asset_id=a_apple_1.id_,
                date_ord=today_ord - 1,
                value=14,
            )
            s.add(av)
            s.commit()
            v_apple_1 = av.value * (t_split_1.asset_quantity or 0)
            profit_apple_1 = v_apple_1 - 10

        value = 100 - 10 - 10 + v_apple_0 + v_apple_1
        target = {
            "n_accounts": 2,
            "n_assets": 3,
            "n_transactions": 3,
            "n_valuations": 2,
            "net_worth": value,
            "accounts": [
                {
                    "name": "Monkey Bank Checking",
                    "institution": "Monkey Bank",
                    "category": "Cash",
                    "value": value,
                    "age": "1 days",
                    "profit": profit_apple_0 + profit_apple_1,
                },
                {
                    "name": "Monkey Bank Credit",
                    "institution": "Monkey Bank",
                    "category": "Credit",
                    "value": Decimal(0),
                    "age": "0 days",
                    "profit": Decimal(0),
                },
            ],
            "total_asset_value": v_apple_0 + v_apple_1,
            "assets": [
                {
                    "name": "Apple",
                    "description": None,
                    "value": v_apple_0,
                    "profit": profit_apple_0,
                    "category": "Real estate",
                    "ticker": None,
                },
                {
                    "name": "Tech Company",
                    "description": "Apples and Bananas",
                    "value": v_apple_1,
                    "profit": profit_apple_1,
                    "category": "Stocks",
                    "ticker": "APPLE",
                },
            ],
            "db_size": path_db.stat().st_size,
        }
        result = summarize_._get_summary(p)  # noqa: SLF001
        self.assertEqual(result, target)

        # Sell a_apple_1 and close credit account
        with p.get_session() as s:
            txn_1 = Transaction(
                account_id=acct_0_id,
                date_ord=today_ord,
                amount=10,
                statement="Banana Store",
            )
            t_split_1 = TransactionSplit(
                amount=txn_1.amount,
                parent=txn_1,
                asset_id=a_apple_0_id,
                asset_quantity_unadjusted=-1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn_1, t_split_1))
            s.commit()

            acct = s.query(Account).where(Account.id_ == acct_1_id).one()
            acct.closed = True
            s.commit()

            av = AssetValuation(
                asset_id=a_apple_1_id,
                date_ord=today_ord,
                value=0,
            )
            s.add(av)
            s.commit()

        value += 10 - v_apple_0 - v_apple_1
        target = {
            "n_accounts": 2,
            "n_assets": 3,
            "n_transactions": 4,
            "n_valuations": 3,
            "net_worth": value,
            "accounts": [
                {
                    "name": "Monkey Bank Checking",
                    "institution": "Monkey Bank",
                    "category": "Cash",
                    "value": value,
                    "age": "1 days",
                    "profit": Decimal(100),
                },
            ],
            "total_asset_value": Decimal(0),
            "assets": [],
            "db_size": path_db.stat().st_size,
        }
        result = summarize_._get_summary(p)  # noqa: SLF001
        self.assertEqual(result, target)

    def test_print_summary(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create_.create(path_db, None, force=False, no_encrypt=True)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")

        original_terminal_size = shutil.get_terminal_size
        try:
            shutil.get_terminal_size = lambda: (80, 24)

            p_dict = {
                "n_accounts": 1,
                "n_assets": 1,
                "n_transactions": 1,
                "n_valuations": 1,
                "net_worth": Decimal(90),
                "accounts": [
                    {
                        "name": "Monkey Bank Checking",
                        "institution": "Monkey Bank",
                        "category": "Cash",
                        "value": Decimal(90),
                        "age": "1 days",
                        "profit": Decimal(0),
                    },
                ],
                "total_asset_value": Decimal(14),
                "assets": [
                    {
                        "name": "Apple",
                        "description": "",
                        "value": Decimal(14),
                        "profit": Decimal(0),
                        "category": "Real estate",
                        "ticker": None,
                    },
                ],
                "db_size": 1024 * 10,
            }
            p_dict: summarize_._Summary

            target = textwrap.dedent(
                """\
            Portfolio file size is 10.2KB/10.0KiB
            There is 1 account, 1 of which is currently open
            ╭──────────────────────┬─────────────┬──────────┬────────┬────────┬────────╮
            │         Name         │ Institution │ Category │ Value  │ Profit │  Age   │
            ╞══════════════════════╪═════════════╪══════════╪════════╪════════╪════════╡
            │ Monkey Bank Checking │ Monkey Bank │ Cash     │ $90.00 │  $0.00 │ 1 days │
            ╞══════════════════════╪═════════════╪══════════╪════════╪════════╪════════╡
            │ Total                │             │          │ $90.00 │        │        │
            ╰──────────────────────┴─────────────┴──────────┴────────┴────────┴────────╯
            There is 1 asset, 1 of which is currently held
            ╭───────┬─────────────┬─────────────┬────────┬────────┬────────╮
            │ Name  │ Description │    Class    │ Ticker │ Value  │ Profit │
            ╞═══════╪═════════════╪═════════════╪════════╪════════╪════════╡
            │ Apple │             │ Real estate │        │ $14.00 │  $0.00 │
            ╞═══════╪═════════════╪═════════════╪════════╪════════╪════════╡
            │ Total │             │             │        │ $14.00 │        │
            ╰───────┴─────────────┴─────────────┴────────┴────────┴────────╯
            There is 1 asset valuation
            There is 1 transaction
            """,
            )
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                summarize_._print_summary(p_dict)  # noqa: SLF001
            fake_stdout = fake_stdout.getvalue()
            self.assertEqual(fake_stdout, target)

            p_dict = {
                "n_accounts": 2,
                "n_assets": 3,
                "n_transactions": 4,
                "n_valuations": 5,
                "net_worth": Decimal(90),
                "accounts": [
                    {
                        "name": "Monkey Bank Checking",
                        "institution": "Monkey Bank",
                        "category": "Cash",
                        "value": Decimal(90),
                        "age": "1 days",
                        "profit": Decimal(0),
                    },
                    {
                        "name": "Monkey Bank Credit",
                        "institution": "Monkey Bank",
                        "category": "Credit",
                        "value": Decimal(0),
                        "age": "1 days",
                        "profit": Decimal(0),
                    },
                ],
                "total_asset_value": Decimal(114),
                "assets": [
                    {
                        "name": "Apple",
                        "description": "Tech company",
                        "value": Decimal(14),
                        "profit": Decimal(0),
                        "category": "Real estate",
                        "ticker": None,
                    },
                    {
                        "name": "Banana",
                        "description": None,
                        "value": Decimal(100),
                        "profit": Decimal(0),
                        "category": "Stocks",
                        "ticker": "BANANA",
                    },
                ],
                "db_size": 1024 * 10,
            }

            target = textwrap.dedent(
                """\
            Portfolio file size is 10.2KB/10.0KiB
            There are 2 accounts, 2 of which are currently open
            ╭──────────────────────┬─────────────┬──────────┬────────┬────────┬────────╮
            │         Name         │ Institution │ Category │ Value  │ Profit │  Age   │
            ╞══════════════════════╪═════════════╪══════════╪════════╪════════╪════════╡
            │ Monkey Bank Checking │ Monkey Bank │ Cash     │ $90.00 │  $0.00 │ 1 days │
            │ Monkey Bank Credit   │ Monkey Bank │ Credit   │  $0.00 │  $0.00 │ 1 days │
            ╞══════════════════════╪═════════════╪══════════╪════════╪════════╪════════╡
            │ Total                │             │          │ $90.00 │        │        │
            ╰──────────────────────┴─────────────┴──────────┴────────┴────────┴────────╯
            There are 3 assets, 2 of which are currently held
            ╭────────┬──────────────┬─────────────┬────────┬─────────┬────────╮
            │  Name  │ Description  │    Class    │ Ticker │  Value  │ Profit │
            ╞════════╪══════════════╪═════════════╪════════╪═════════╪════════╡
            │ Apple  │ Tech company │ Real estate │        │  $14.00 │  $0.00 │
            │ Banana │              │ Stocks      │ BANANA │ $100.00 │  $0.00 │
            ╞════════╪══════════════╪═════════════╪════════╪═════════╪════════╡
            │ Total  │              │             │        │ $114.00 │        │
            ╰────────┴──────────────┴─────────────┴────────┴─────────┴────────╯
            There are 5 asset valuations
            There are 4 transactions
            """,
            )
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                summarize_._print_summary(p_dict)  # noqa: SLF001
            fake_stdout = fake_stdout.getvalue()
            self.assertEqual(fake_stdout, target)
        finally:
            shutil.get_terminal_size = original_terminal_size
