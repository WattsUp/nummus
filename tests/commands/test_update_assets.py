from __future__ import annotations

import datetime
import io
from unittest import mock

from colorama import Fore

from nummus import portfolio
from nummus.commands import create, update_assets
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestUpdateAssets(TestBase):
    def test_update_assets(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        today = datetime.date.today()

        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            # Create assets
            a = Asset(name="Banana Inc.", category=AssetCategory.ITEM)
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                emergency=False,
            )

            s.add_all((a, acct))
            s.commit()
            a_id = a.id_
            acct_id = acct.id_

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
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))
            s.commit()
            a.update_splits()
            s.commit()

        first_valuation_date = date - datetime.timedelta(days=7)
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = update_assets.UpdateAssets(path_db, None)
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("sys.stderr", new=io.StringIO()) as _,
        ):
            rc = c.run()

        self.assertNotEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.YELLOW}No assets were updated"
        self.assertEqual(fake_stdout[: len(target)], target)

        with p.get_session() as s:
            a = s.query(Asset).where(Asset.id_ == a_id).one()
            a.ticker = "BANANA"
            s.commit()

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = update_assets.UpdateAssets(path_db, None)
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("sys.stderr", new=io.StringIO()) as _,
        ):
            rc = c.run()

        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Asset Banana Inc. (BANANA) updated from "
            f"{first_valuation_date} to {today}"
        )
        self.assertEqual(fake_stdout[: len(target)], target)

        # Sell asset so it should not include today
        last_valuation_date = date + datetime.timedelta(days=7)
        with p.get_session() as s:
            txn = Transaction(
                account_id=acct_id,
                date_ord=date_ord,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id,
                asset_quantity_unadjusted=-1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))
            s.commit()

            a = s.query(Asset).where(Asset.id_ == a_id).one()
            a.update_splits()
            s.commit()

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = update_assets.UpdateAssets(path_db, None)
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("sys.stderr", new=io.StringIO()) as _,
        ):
            rc = c.run()

        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Asset Banana Inc. (BANANA) updated from "
            f"{first_valuation_date} to {last_valuation_date}"
        )
        self.assertEqual(fake_stdout[: len(target)], target)

        # Have a bad ticker
        with p.get_session() as s:
            a = s.query(Asset).where(Asset.id_ == a_id).one()
            a.ticker = "ORANGE"
            s.commit()

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = update_assets.UpdateAssets(path_db, None)
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("sys.stderr", new=io.StringIO()) as _,
        ):
            rc = c.run()

        self.assertNotEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.RED}Asset Banana Inc. (ORANGE) failed to update. "
            "Error: BANANA: No timezone found, symbol may be delisted"
        )
        self.assertEqual(fake_stdout[: len(target)], target)
