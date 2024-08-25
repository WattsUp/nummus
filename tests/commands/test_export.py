from __future__ import annotations

import argparse
import csv
import datetime
import io
from unittest import mock

from nummus import portfolio
from nummus.commands import create, export
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


class TestExport(TestBase):
    def test_export(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_csv = path_db.with_suffix(".csv")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertFalse(path_csv.exists(), "CSV file does exist")
        p = portfolio.Portfolio(path_db, None)

        header = [
            "Date",
            "Account",
            "Payee",
            "Description",
            "Category",
            "Tag",
            "Amount",
        ]

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = export.Export(path_db, None, path_csv, start=None, end=None)
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            rc = c.run()
        self.assertEqual(rc, 0)
        self.assertTrue(path_csv.exists(), "CSV file does not exist")
        with path_csv.open("r", encoding="utf-8") as file:
            line = file.readline()
            self.assertEqual(line, ",".join(header) + "\n")
            reader = csv.reader(file)
            rows = list(reader)
            self.assertEqual(rows, [])

        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

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

            a = Asset(name="Banana Inc.", category=AssetCategory.ITEM)
            s.add(a)
            s.commit()

            txn_0 = Transaction(
                account_id=acct_0.id_,
                date=yesterday,
                amount=100,
                statement="Banana Store",
            )
            t_split_0 = TransactionSplit(
                amount=txn_0.amount,
                parent=txn_0,
                payee="Banana Store",
                description="Paycheck",
                category_id=categories["Paychecks/Salary"],
                tag="Engineer",
            )
            s.add_all((txn_0, t_split_0))
            s.commit()

            txn_1 = Transaction(
                account_id=acct_0.id_,
                date=today,
                amount=-10,
                statement="Grocery Store",
            )
            t_split_1 = TransactionSplit(
                amount=txn_1.amount,
                parent=txn_1,
                category_id=categories["Groceries"],
            )
            s.add_all((txn_1, t_split_1))
            s.commit()

            txn_2 = Transaction(
                account_id=acct_0.id_,
                date=today,
                amount=-10,
                statement="Banana Store",
            )
            t_split_2 = TransactionSplit(
                amount=txn_2.amount,
                parent=txn_2,
                asset_id=a.id_,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn_2, t_split_2))
            s.commit()

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = export.Export(path_db, None, path_csv, start=None, end=None)
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            rc = c.run()
        self.assertEqual(rc, 0)
        self.assertTrue(path_csv.exists(), "CSV file does not exist")
        with path_csv.open("r", encoding="utf-8") as file:
            line = file.readline()
            self.assertEqual(line, ",".join(header) + "\n")
            reader = csv.reader(file)
            rows = list(reader)
            target = [
                [
                    yesterday.isoformat(),
                    "Monkey Bank Checking",
                    "Banana Store",
                    "Paycheck",
                    "Paychecks/Salary",
                    "Engineer",
                    "$100.00",
                ],
                [
                    today.isoformat(),
                    "Monkey Bank Checking",
                    "",
                    "",
                    "Groceries",
                    "",
                    "-$10.00",
                ],
            ]
            self.assertEqual(rows, target)

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = export.Export(path_db, None, path_csv, start=today, end=today)
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            rc = c.run()
        self.assertEqual(rc, 0)
        self.assertTrue(path_csv.exists(), "CSV file does not exist")
        with path_csv.open("r", encoding="utf-8") as file:
            line = file.readline()
            self.assertEqual(line, ",".join(header) + "\n")
            reader = csv.reader(file)
            rows = list(reader)
            target = [
                [
                    today.isoformat(),
                    "Monkey Bank Checking",
                    "",
                    "",
                    "Groceries",
                    "",
                    "-$10.00",
                ],
            ]
            self.assertEqual(rows, target)

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

        cmd_class = export.Export
        sub = subparsers.add_parser(
            cmd_class.NAME,
            help=cmd_class.HELP,
            description=cmd_class.DESCRIPTION,
        )
        cmd_class.setup_args(sub)

        command_line = [cmd_class.NAME, str(path_db.with_suffix(".csv"))]
        args = parser.parse_args(args=command_line)
        args_d = vars(args)
        args_d["path_db"] = path_db
        args_d["path_password"] = None
        cmd: str = args_d.pop("cmd")
        self.assertEqual(cmd, cmd_class.NAME)

        # Make sure all args from parse_args are given to constructor
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            cmd_class(**args_d)
