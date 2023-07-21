"""Create a test Portfolio
"""

import typing as t

import datetime
import time

import colorama
from colorama import Fore
import numpy as np

from nummus.portfolio import Portfolio
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           AssetValuation, Transaction, TransactionCategory,
                           TransactionSplit)

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


def make_assets(p: Portfolio) -> t.Dict[str, int]:
  """Create assets to buy and sell

  Args:
    p: Portfolio to edit

  Returns:
    Dict{asset name: id}
  """
  assets: t.Dict[str, int] = {}
  with p.get_session() as s:
    growth = Asset(name="GROWTH",
                   description="Growth ETF",
                   category=AssetCategory.SECURITY)
    value = Asset(name="VALUE",
                  description="Value ETF",
                  category=AssetCategory.SECURITY)

    # Name: [Asset, current price, growth mean, growth stddev]
    stocks: t.Dict[str, t.List[t.Union[Asset, float]]] = {
        "growth": [growth, 100, 0.1, 0.2],
        "value": [value, 100, 0.05, 0.05]
    }
    s.add_all(v[0] for v in stocks.values())
    s.commit()

    # TODO (WattsUp) Add stock splits

    start = datetime.date(BIRTH_YEAR, 1, 1)
    date = start
    end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
    while date <= end:
      # Skip weekends
      w = date.weekday()
      if w == 5:
        date += datetime.timedelta(days=2)
      elif w == 6:
        date += datetime.timedelta(days=1)

      for item in stocks.values():
        rate = RNG.normal(item[2] / 252, item[3] / np.sqrt(252))
        v = round(item[1] * (1 + rate), 2)

        valuation = AssetValuation(asset=item[0], value=v, date=date)
        s.add(valuation)

        item[1] = v

      date += datetime.timedelta(days=1)
    s.commit()

    # dates, values0, _ = growth.get_value(start, end)
    # dates, values1, _ = value.get_value(start, end)
    # with open("stocks.csv", "w", encoding="utf-8") as file:
    #   for d, v0, v1 in zip(dates, values0, values1):
    #     file.write(f"{d},{v0},{v1}\n")

    assets = {k: v[0].id for k, v in stocks.items()}

  print(f"{Fore.GREEN}Created assets")

  return assets


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
      _, values, assets = acct.get_value(death_day, death_day)
      v = values[0]
      net_worth += v
      buf[f"Acct '{acct.name}' final"] = f"${v:15,.3f}"
      for asset_uuid, a_values in assets.items():
        asset = s.query(Asset).where(Asset.uuid == asset_uuid).first()
        v = a_values[0]
        buf[f"  Asset '{asset.name}' final"] = f"${v:15,.3f}"

    buf["Net worth final"] = f"${net_worth:15,.3f}"

    n_transactions = s.query(Transaction).count()
    buf["# of Transactions"] = n_transactions

    buf["First Txn"] = first_txn.date
    buf["Last Txn"] = last_txn.date
    days = (last_txn.date - first_txn.date).days
    years = days / 365.25
    buf["# of Txn/year"] = f"{n_transactions / years:.1f}"

    n_asset_valuations = s.query(AssetValuation).count()
    buf["# of Valuations"] = n_asset_valuations

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


def generate_income(p: Portfolio, accts: t.Dict[str, int],
                    assets: t.Dict[str, int]) -> None:
  """Generate income from working, stopping at retirement

  Args:
    p: Portfolio to edit
    accts: Account IDs to use
    assets: Asset IDs to use
  """
  with p.get_session() as s:
    a_growth = s.query(Asset).where(Asset.id == assets["growth"]).first()
    a_value = s.query(Asset).where(Asset.id == assets["value"]).first()
    a_values_start = datetime.date(BIRTH_YEAR, 1, 1)
    a_values_end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
    _, a_growth_values, _ = a_growth.get_value(a_values_start, a_values_end)
    _, a_value_values, _ = a_value.get_value(a_values_start, a_values_end)

    for age in range(16, min(65, FINAL_AGE)):
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

          # Now buy stocks with that funding
          if age < 35:
            cost_growth = round(savings * 0.9, 2)
          elif age < 45:
            cost_growth = round(savings * 0.5, 2)
          else:
            cost_growth = round(savings * 0.1, 2)
          cost_value = savings - cost_growth

          a_values_i = (date - a_values_start).days

          qty_growth = round(cost_growth / a_growth_values[a_values_i], 6)
          qty_value = round(cost_value / a_value_values[a_values_i], 6)

          txn = Transaction(account_id=accts["retirement"],
                            date=date,
                            total=-savings,
                            statement=job)
          txn_split_0 = TransactionSplit(
              parent=txn,
              total=-cost_growth,
              category=TransactionCategory.INSTRUMENT,
              asset=a_growth,
              asset_quantity=qty_growth)
          txn_split_1 = TransactionSplit(
              parent=txn,
              total=-cost_value,
              category=TransactionCategory.INSTRUMENT,
              asset=a_value,
              asset_quantity=qty_value)
          s.add_all((txn, txn_split_0, txn_split_1))

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
  assets = make_assets(p)

  generate_early_savings(p, accts)

  generate_income(p, accts, assets)

  for name in ["checking", "savings"]:
    add_interest(p, accts[name])

  duration = time.perf_counter() - start
  print(f"{Fore.CYAN}Portfolio generation took {duration:.1f}s")

  print_stats(p)


if __name__ == "__main__":
  main()
