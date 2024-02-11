from __future__ import annotations

import csv
import datetime
import io
from unittest import mock

from nummus import portfolio
from nummus.commands import create_, export_
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
            create_.create(path_db, None, force=False, no_encrypt=True)
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

        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            rc = export_.export(p, path_csv, start=None, end=None)
        self.assertEqual(rc, 0)
        self.assertTrue(path_csv.exists(), "CSV file does not exist")
        with path_csv.open("r", encoding="utf-8") as file:
            line = file.readline()
            self.assertEqual(line, ",".join(header) + "\n")
            reader = csv.reader(file)
            rows = list(reader)
            self.assertEqual(rows, [])

        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)
        yesterday_ord = yesterday.toordinal()

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
                date_ord=yesterday_ord,
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
                date_ord=today_ord,
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
                date_ord=today_ord,
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

        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            rc = export_.export(p, path_csv, start=None, end=None)
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

        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            rc = export_.export(p, path_csv, start=today, end=today)
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
