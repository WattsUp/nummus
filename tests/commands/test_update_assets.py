from __future__ import annotations

import argparse
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
            # Delete index assets
            s.query(Asset).delete()
            s.commit()

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
            txn = Transaction(
                account_id=acct.id_,
                date=date,
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
        target = (
            f"{Fore.YELLOW}No assets were updated, "
            "add a ticker to an Asset to download market data\n"
        )
        self.assertEqual(fake_stdout, target)

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
            f"{first_valuation_date} to {today}\n"
        )
        self.assertEqual(fake_stdout, target)

        # Sell asset so it should not include today
        last_valuation_date = date + datetime.timedelta(days=7)
        with p.get_session() as s:
            txn = Transaction(
                account_id=acct_id,
                date=date,
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
            f"{first_valuation_date} to {last_valuation_date}\n"
        )
        self.assertEqual(fake_stdout, target)

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
            "Error: ORANGE: No timezone found, symbol may be delisted\n"
        )
        self.assertEqual(fake_stdout, target)

    def test_args(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        self.assertTrue(path_db.exists(), "Portfolio does not exist")

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(
            dest="cmd",
            metavar="<command>",
            required=True,
        )

        cmd_class = update_assets.UpdateAssets
        sub = subparsers.add_parser(
            cmd_class.NAME,
            help=cmd_class.HELP,
            description=cmd_class.DESCRIPTION,
        )
        cmd_class.setup_args(sub)

        command_line = [cmd_class.NAME]
        args = parser.parse_args(args=command_line)
        args_d = vars(args)
        args_d["path_db"] = path_db
        args_d["path_password"] = None
        cmd: str = args_d.pop("cmd")
        self.assertEqual(cmd, cmd_class.NAME)

        # Make sure all args from parse_args are given to constructor
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            cmd_class(**args_d)
