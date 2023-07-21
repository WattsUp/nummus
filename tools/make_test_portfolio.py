"""Create a test Portfolio
"""

import typing as t

import datetime
import time

import colorama
from colorama import Fore
import numpy as np

from nummus.portfolio import Portfolio
from nummus.models import (Account, AccountCategory, Transaction,
                           TransactionCategory, TransactionSplit)

colorama.init(autoreset=True)

# TODO (WattsUp) Create a portfolio with 50 years of data
# ~1000 transactions/yr
# ~100 stock transactions/yr
# Try to make it semi-realistic

RNG = np.random.default_rng()

BIRTH_YEAR = 2000
FINAL_AGE = 75

BIRTHDAYS: t.Dict[str, datetime.date] = {
    "self": datetime.date.today().replace(year=BIRTH_YEAR)
}

INTEREST_RATES: t.Dict[int, float] = {
    y: 10**RNG.uniform(-3, -1.3)
    for y in range(BIRTH_YEAR, BIRTH_YEAR + FINAL_AGE + 1)
}


def birthday(name: str, age: int) -> datetime.date:
  """Get the birthday of an individual at an age

  Args:
    name: Name of person, found in BIRTHDAYS
    age: Age of person

  Returns:
    BIRTHDAYS[name] + age
  """
  year = BIRTHDAYS[name].year + age
  return BIRTHDAYS[name].replace(year=year)


def next_month(date: datetime.date) -> datetime.date:
  """Get the first day of the next month of a date

  Args:
    date: Reference date

  Returns:
    First day of the next month
  """
  y = date.year
  m = date.month
  return datetime.date(y + m // 12, m % 12 + 1, 1)


def make_accounts(p: Portfolio) -> t.Dict[str, int]:
  """Create accounts

  Args:
    p: Portfolio to edit

  Returns:
    Dict{account name: id}
  """
  accounts: t.Dict[str, int] = {}
  with p.get_session() as s:
    checking = Account(name="Checking",
                       institution="Monkey Bank",
                       category=AccountCategory.CASH)
    savings = Account(name="Savings",
                      institution="Monkey Bank",
                      category=AccountCategory.CASH)
    cc_0 = Account(name="Banana VISA",
                   institution="Monkey Bank",
                   category=AccountCategory.CREDIT)
    cc_1 = Account(name="Peanut Credit",
                   institution="PB Loans",
                   category=AccountCategory.CREDIT)
    loan = Account(name="Personal Loans",
                   institution="Personal",
                   category=AccountCategory.LOAN)
    mortgage = Account(name="Monkey Mortgage",
                       institution="Monkey Bank",
                       category=AccountCategory.MORTGAGE)
    investment = Account(name="Fruit Trading",
                         institution="Monkey Bank",
                         category=AccountCategory.INVESTMENT)
    retirement = Account(name="401k",
                         institution="Monkey Bank Retirement",
                         category=AccountCategory.INVESTMENT)
    real_estate = Account(name="Real Estate",
                          institution="Real Estate",
                          category=AccountCategory.FIXED)

    s.add_all((checking, savings, cc_0, cc_1, loan, mortgage, investment,
               retirement, real_estate))
    s.commit()

    accounts["checking"] = checking.id
    accounts["savings"] = savings.id
    accounts["cc_0"] = cc_0.id
    accounts["cc_1"] = cc_1.id
    accounts["loan"] = loan.id
    accounts["mortgage"] = mortgage.id
    accounts["investment"] = investment.id
    accounts["retirement"] = retirement.id
    accounts["real_estate"] = real_estate.id

  print(f"{Fore.GREEN}Created accounts")

  return accounts


def print_stats(p: Portfolio) -> None:
  """Print statistics on Portfolio

  Args:
    p: Portfolio to report
  """
  buf: t.Dict[str, str] = {}
  with p.get_session() as s:
    first_txn = s.query(Transaction).order_by(Transaction.date).first()
    last_txn = s.query(Transaction).order_by(Transaction.date.desc()).first()

    if first_txn is None:
      print(f"{Fore.RED}No Transactions")
      return

    death_day = birthday("self", FINAL_AGE)

    n_accounts = s.query(Account).count()
    buf["# of Accounts"] = n_accounts
    net_worth = 0
    for acct in s.query(Account).all():
      _, values, _ = acct.get_value(death_day, death_day)
      v = values[0]
      net_worth += v
      buf[f"Acct '{acct.name}' final"] = f"${v:15,.3f}"
    buf["Net worth final"] = f"${net_worth:15,.3f}"

    n_transactions = s.query(Transaction).count()
    buf["# of Transactions"] = n_transactions

    buf["First Txn"] = first_txn.date
    buf["Last Txn"] = last_txn.date
    days = (last_txn.date - first_txn.date).days
    years = days / 365.25
    buf["# of Txn/year"] = f"{n_transactions / years:.1f}"

    buf["DB Size"] = f"{p.path.stat().st_size / 1e6:.1f}MB"

    key_len = max(len(k) for k in buf) + 1

    for k, v in buf.items():
      print(f"{k:{key_len}}{v}")


def generate_early_savings(p: Portfolio, accts: t.Dict[str, int]) -> None:
  """Generate early savings transactions, namely birthday money

  Args:
    p: Portfolio to edit
    accts: Account IDs to use
  """
  with p.get_session() as s:
    for age in range(8, 18):
      date = birthday("self", age)
      txn = Transaction(account_id=accts["savings"],
                        date=date,
                        total=round(RNG.uniform(10, 100), 2),
                        statement="Birthday money")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.INCOME,
                                   subcategory="Other Income")
      s.add_all((txn, txn_split))
    s.commit()
  print(f"{Fore.GREEN}Generated early savings")


def generate_income(p: Portfolio, accts: t.Dict[str, int]) -> None:
  """Generate income from working, stopping at retirement

  Args:
    p: Portfolio to edit
    accts: Account IDs to use
  """
  with p.get_session() as s:
    for age in range(16, 65):
      if age <= 22:
        job = "Barista"
        salary = 20e3 + 2e3 * (age - 16)
      elif age <= 35:
        job = "Software Engineer"
        salary = 70e3 + 5e3 * (age - 22)
      else:
        job = "Engineering Manager"
        salary = 175e3 + 6e3 * (age - 35)
      total = round(salary / 24, 2)
      # At age 24, decide to start contributing to retirement
      if age < 24:
        savings = 0
        paycheck = total
      else:
        savings = round(total * 0.1, 2)
        paycheck = total - savings

      # Paychecks on the 5th and 20th unless that day falls on a weekend
      def adjust_date(date: datetime.date) -> datetime.datetime:
        if date.weekday() == 5:
          return date - datetime.timedelta(days=1)
        elif date.weekday() == 6:
          return date + datetime.timedelta(days=1)
        return date

      dates: t.List[datetime.date] = []
      for m in range(12):
        date_0 = datetime.date(BIRTH_YEAR + age, m + 1, 5)
        date_1 = datetime.date(BIRTH_YEAR + age, m + 1, 20)

        dates.append(adjust_date(date_0))
        dates.append(adjust_date(date_1))

      for date in dates:
        txn = Transaction(account_id=accts["checking"],
                          date=date,
                          total=paycheck,
                          statement=job)
        txn_split = TransactionSplit(parent=txn,
                                     total=txn.total,
                                     category=TransactionCategory.INCOME,
                                     subcategory="Paycheck")
        s.add_all((txn, txn_split))
        if savings != 0:
          txn = Transaction(account_id=accts["retirement"],
                            date=date,
                            total=savings,
                            statement=job)
          txn_split = TransactionSplit(parent=txn,
                                       total=txn.total,
                                       category=TransactionCategory.INCOME,
                                       subcategory="Retirement Contribution")
          s.add_all((txn, txn_split))

    s.commit()
  print(f"{Fore.GREEN}Generated income")


def add_interest(p: Portfolio, acct_id: int) -> None:
  """Adds dividend/interest to Account

  Args:
    acct_id: Account to generate for
  """
  with p.get_session() as s:
    acct = s.query(Account).where(Account.id == acct_id).first()
    if len(acct.transactions) == 0:
      print(f"{Fore.RED}No transaction to generate interest on for {acct.name}")
      return
    date = acct.transactions[0].date
    end = birthday("self", FINAL_AGE)

    while date < end:
      next_date = next_month(date)

      # Interest on the average balance
      _, values, _ = acct.get_value(date, next_date)
      avg_value = sum(values[:-1]) / len(values[:-1])

      rate = INTEREST_RATES[date.year]
      interest = round(rate / 12 * avg_value, 2)

      txn = Transaction(account=acct,
                        date=next_date,
                        total=interest,
                        statement="Dividend/interest")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.INCOME,
                                   subcategory="Interest")
      s.add_all((txn, txn_split))

      date = next_date

    s.commit()
    print(f"{Fore.GREEN}Added interest for {acct.name}")


def main() -> None:
  """Main program entry
  """
  start = time.perf_counter()
  p = Portfolio.create("portfolio.db")

  accts = make_accounts(p)

  generate_early_savings(p, accts)

  generate_income(p, accts)

  for name in ["checking", "savings"]:
    add_interest(p, accts[name])

  duration = time.perf_counter() - start
  print(f"{Fore.CYAN}Portfolio generation took {duration:.1f}s")

  print_stats(p)


if __name__ == "__main__":
  main()
