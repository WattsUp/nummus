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
NO_RNG = True


def rng_uniform(low: float, high: float) -> float:
  """Return a number from a uniform distribution

  Args:
    low: Lower bounds
    high: Upper bounds

  Returns:
    Random number from distribution
  """
  if NO_RNG:
    return (low + high) / 2
  return RNG.uniform(low, high)


def rng_normal(loc: float, scale: float) -> float:
  """Return a number from a normal distribution

  Args:
    loc: Center of distribution
    scale: Std. dev of distribution

  Returns:
    Random number from distribution
  """
  if NO_RNG:
    return loc
  return RNG.normal(loc, scale)


FINAL_AGE = 80
BIRTH_YEAR = datetime.date.today().year - FINAL_AGE

BIRTHDAYS: t.Dict[str, datetime.date] = {
    "self": datetime.date.today().replace(year=BIRTH_YEAR)
}

INTEREST_RATES: t.Dict[int, float] = {
    y: 10**rng_uniform(-3, -1.3)
    for y in range(BIRTH_YEAR, BIRTH_YEAR + FINAL_AGE + 1)
}

INFLATION_RATES: t.Dict[int, float] = {
    y: rng_normal(0.0376, 0.0278)
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
    house_main = Asset(name="Main St. House",
                       description="House on Main St.",
                       category=AssetCategory.REAL_ESTATE)
    house_second = Asset(name="Second Ave. House",
                         description="House on Second Ave.",
                         category=AssetCategory.REAL_ESTATE)
    house_third = Asset(name="Third Blvd. House",
                        description="House on Third Blvd.",
                        category=AssetCategory.REAL_ESTATE)

    # Name: [Asset, current price, growth mean, growth stddev]
    stocks: t.Dict[str, t.List[t.Union[Asset, float]]] = {
        "growth": [growth, 100, 0.07, 0.2],
        "value": [value, 100, 0.05, 0.05],
    }
    real_estate: t.Dict[str, t.List[t.Union[Asset, float]]] = {
        "house_main": [house_main, 50e3, 0.05, 0.02],
        "house_second": [house_second, 100e3, 0.04, 0.02],
        "house_third": [house_third, 100e3, 0.05, 0.02],
    }
    s.add_all(v[0] for v in stocks.values())
    s.add_all(v[0] for v in real_estate.values())
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
        rate = rng_normal(item[2] / 252, item[3] / np.sqrt(252))
        v = round(item[1] * (1 + rate), 2)

        valuation = AssetValuation(asset=item[0], value=v, date=date)
        s.add(valuation)

        item[1] = v

      date += datetime.timedelta(days=1)
    s.commit()
    print(f"{Fore.CYAN}  Valued stocks")

    # Real estate valued once a month
    date = start
    end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
    while date <= end:
      for item in real_estate.values():
        rate = rng_normal(item[2] / 12, item[3] / np.sqrt(12))
        v = round(item[1] * (1 + rate), 2)

        valuation = AssetValuation(asset=item[0], value=v, date=date)
        s.add(valuation)

        item[1] = v

      y = date.year
      m = date.month
      date = datetime.date(y + m // 12, m % 12 + 1, 1)
    s.commit()
    print(f"{Fore.CYAN}  Valued real estate")

    # dates, values0, _ = growth.get_value(start, end)
    # dates, values1, _ = value.get_value(start, end)
    # with open("stocks.csv", "w", encoding="utf-8") as file:
    #   for d, v0, v1 in zip(dates, values0, values1):
    #     file.write(f"{d},{v0},{v1}\n")

    assets = {k: v[0].id for k, v in stocks.items()}
    for k, v in real_estate.items():
      assets[k] = v[0].id

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
                        total=round(rng_uniform(10, 100), 2),
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

    for age in range(16, min(60, FINAL_AGE) + 1):
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
      savings = round(total * 0.1, 2)
      if age < 24:
        retirement = 0
      else:
        retirement = round(total * 0.1, 2)
      paycheck = total - savings - retirement

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
        txn = Transaction(account_id=accts["savings"],
                          date=date,
                          total=savings,
                          statement=job)
        txn_split = TransactionSplit(parent=txn,
                                     total=txn.total,
                                     category=TransactionCategory.INCOME,
                                     subcategory="Paycheck")
        s.add_all((txn, txn_split))
        if retirement != 0:
          txn = Transaction(account_id=accts["retirement"],
                            date=date,
                            total=retirement,
                            statement=job)
          txn_split = TransactionSplit(parent=txn,
                                       total=txn.total,
                                       category=TransactionCategory.INCOME,
                                       subcategory="Retirement Contribution")
          s.add_all((txn, txn_split))

          # Now buy stocks with that funding
          if age < 30:
            cost_growth = round(retirement * 0.9, 2)
          elif age < 40:
            cost_growth = round(retirement * 0.5, 2)
          else:
            cost_growth = round(retirement * 0.1, 2)
          cost_value = retirement - cost_growth

          a_values_i = (date - a_values_start).days

          qty_growth = round(cost_growth / a_growth_values[a_values_i], 6)
          qty_value = round(cost_value / a_value_values[a_values_i], 6)

          txn = Transaction(account_id=accts["retirement"],
                            date=date,
                            total=-retirement,
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


def generate_housing(p: Portfolio, accts: t.Dict[str, int],
                     assets: t.Dict[str, int]) -> None:
  """Generate housing payments

  Args:
    p: Portfolio to edit
    accts: Account IDs to use
    assets: Asset IDs to use
  """
  with p.get_session() as s:
    house_1 = s.query(Asset).where(Asset.id == assets["house_main"]).first()
    house_2 = s.query(Asset).where(Asset.id == assets["house_second"]).first()
    house_3 = s.query(Asset).where(Asset.id == assets["house_third"]).first()
    a_values_start = datetime.date(BIRTH_YEAR, 1, 1)
    a_values_end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
    _, house_1_values, _ = house_1.get_value(a_values_start, a_values_end)
    _, house_2_values, _ = house_2.get_value(a_values_start, a_values_end)
    _, house_3_values, _ = house_3.get_value(a_values_start, a_values_end)

    savings = s.query(Account).where(Account.id == accts["savings"]).first()

    def buy_house(date: datetime.date, house: Asset,
                  price: float) -> t.Tuple[float, float, float, float, float]:
      """Add transactions to buy a house

      Args:
        date: Transaction date
        house: Asset to buy
        price: Price to buy it at

      Returns:
        (Mortgage principal, monthly interest rate, monthly payment, pmi,
        pmi threshold)
      """
      _, values, _ = savings.get_value(date, date)
      closing_costs = round(price * 0.05, 2)
      down_payment = min(values[0] - closing_costs, round(price * 0.2, 2))

      p = price - down_payment
      r = round(rng_uniform(0.03, 0.1), 4) / 12
      pi = round(p * (r * (1 + r)**360) / ((1 + r)**360 - 1), 2)

      # Pay down payment and closing costs
      txn = Transaction(account_id=accts["savings"],
                        date=date,
                        total=-(down_payment + closing_costs),
                        statement="Home closing")
      txn_dp = TransactionSplit(parent=txn,
                                total=-down_payment,
                                category=TransactionCategory.TRANSFER)
      txn_cc = TransactionSplit(parent=txn,
                                total=-closing_costs,
                                category=TransactionCategory.SERVICES,
                                subcategory="Fees")
      s.add_all((txn, txn_dp, txn_cc))

      # Open a mortgage
      txn = Transaction(account_id=accts["mortgage"],
                        date=date,
                        total=-p,
                        statement="Home closing")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.INSTRUMENT)
      s.add_all((txn, txn_split))

      # Buy the house
      txn = Transaction(account_id=accts["real_estate"],
                        date=date,
                        total=0,
                        statement="Home closing")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.INSTRUMENT,
                                   asset=house,
                                   asset_quantity=1)
      s.add_all((txn, txn_split))

      pmi = round(0.01 * pi * 12, 2)
      pmi_threshold = 0.8 * price

      print(f"{Fore.CYAN}  Bought {house.description}")
      return p, r, pi, pmi, pmi_threshold

    def sell_house(date: datetime.date, house: Asset, price: float,
                   balance: float) -> None:
      """Add transactions to sell a house

      Args:
        date: Transaction date
        house: Asset to sell
        price: Price to sell it at
      """
      closing_costs = round(price * 0.08, 2)

      # Pay down payment and closing costs
      txn = Transaction(account_id=accts["savings"],
                        date=date,
                        total=price - closing_costs,
                        statement="Home closing")
      txn_sell = TransactionSplit(parent=txn,
                                  total=price,
                                  category=TransactionCategory.TRANSFER)
      txn_cc = TransactionSplit(parent=txn,
                                total=-closing_costs,
                                category=TransactionCategory.SERVICES,
                                subcategory="Fees")
      s.add_all((txn, txn_sell, txn_cc))

      # Sell the house
      txn = Transaction(account_id=accts["real_estate"],
                        date=date,
                        total=0,
                        statement="Home closing")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.INSTRUMENT,
                                   asset=house,
                                   asset_quantity=-1)
      s.add_all((txn, txn_split))

      if balance > 0:
        # Close a mortgage
        txn = Transaction(account_id=accts["mortgage"],
                          date=date,
                          total=balance,
                          statement="Home closing")
        txn_split = TransactionSplit(parent=txn,
                                     total=txn.total,
                                     category=TransactionCategory.INSTRUMENT)
        s.add_all((txn, txn_split))

        txn = Transaction(account_id=accts["savings"],
                          date=date,
                          total=-balance,
                          statement="Home closing")
        txn_split = TransactionSplit(parent=txn,
                                     total=txn.total,
                                     category=TransactionCategory.INSTRUMENT)
        s.add_all((txn, txn_split))

      print(f"{Fore.CYAN}  Sold {house.description}")

    def monthly_payment(date: datetime.date, balance: float, rate: float,
                        payment: float, escrow: float, pmi: float,
                        pmi_threshold: float) -> float:
      """Add monthly payment transactions

      Args:
        date: Transaction date
        balance: Mortgage balance
        rate: Monthly interest rate
        payment: Monthly payment
        escrow: Escrow payment
        pmi: Amount of private mortgage insurance
        pmi_threshold: Balance amount that PMI is no longer paid
      """
      i = round(balance * rate, 2)
      p = min(balance, payment - i)
      total = i + p + escrow
      if balance > pmi_threshold:
        total += pmi
      txn = Transaction(account_id=accts["checking"],
                        date=date,
                        total=-total,
                        statement="House payment")
      txn_ti = TransactionSplit(parent=txn,
                                total=-escrow,
                                category=TransactionCategory.SERVICES,
                                subcategory="Fees",
                                description="Taxes and Insurance")
      if p > 0:
        txn_i = TransactionSplit(parent=txn,
                                 total=-i,
                                 category=TransactionCategory.HOME,
                                 subcategory="Rent",
                                 description="Interest")
        txn_p = TransactionSplit(parent=txn,
                                 total=-p,
                                 category=TransactionCategory.TRANSFER,
                                 description="Principal")
        if balance > pmi_threshold:
          txn_pmi = TransactionSplit(parent=txn,
                                     total=-pmi,
                                     category=TransactionCategory.SERVICES,
                                     description="PMI")
          s.add_all((txn, txn_i, txn_p, txn_ti, txn_pmi))
        else:
          s.add_all((txn, txn_i, txn_p, txn_ti))
      else:
        s.add_all((txn, txn_ti))

      if p > 0:
        txn = Transaction(account_id=accts["mortgage"],
                          date=date,
                          total=p,
                          statement="Principal")
        txn_split = TransactionSplit(parent=txn,
                                     total=txn.total,
                                     category=TransactionCategory.TRANSFER)
        s.add_all((txn, txn_split))

      balance -= p

      utilities = max(50, round(payment * rng_normal(0.1, 0.01), 2))

      txn = Transaction(account_id=accts["cc_0"],
                        date=date,
                        total=-utilities,
                        statement="Utilities")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.HOME,
                                   subcategory="Utilities")
      s.add_all((txn, txn_split))

      # Adds a repair cost 25% of the time with an average cost of $400
      # Equates to $100/month
      repair_cost = round(100 / np.sqrt(rng_uniform(1e-5, 1)), 2)
      if repair_cost > 200:
        acct_id = accts["cc_0"]
        if repair_cost > 1000:
          # Use savings for big repairs
          acct_id = accts["savings"]
        txn = Transaction(account_id=acct_id,
                          date=date +
                          datetime.timedelta(days=rng_uniform(1, 28)),
                          total=-repair_cost,
                          statement="Repairs")
        txn_split = TransactionSplit(parent=txn,
                                     total=txn.total,
                                     category=TransactionCategory.HOME,
                                     subcategory="Repairs")
        s.add_all((txn, txn_split))

      return balance

    bought_1 = False
    bought_2 = False
    bought_3 = False

    balance = 0
    rate = 0
    payment = 0
    escrow = 0
    pmi = 0
    pmi_th = 0

    for age in range(18, FINAL_AGE + 1):
      dates: t.List[datetime.date] = []
      for m in range(12):
        date = datetime.date(BIRTH_YEAR + age, m + 1, 1)
        dates.append(date)

      if age < 30:
        # Renting until age 30
        rent = 1000 + 100 * (age - 18)
        for date in dates:
          txn = Transaction(account_id=accts["checking"],
                            date=date,
                            total=-rent,
                            statement="Rent")
          txn_split = TransactionSplit(parent=txn,
                                       total=txn.total,
                                       category=TransactionCategory.HOME,
                                       subcategory="Rent")
          s.add_all((txn, txn_split))

          utilities = round(rent * rng_normal(0.1, 0.01), 2)

          txn = Transaction(account_id=accts["cc_0"],
                            date=date,
                            total=-utilities,
                            statement="Utilities")
          txn_split = TransactionSplit(parent=txn,
                                       total=txn.total,
                                       category=TransactionCategory.HOME,
                                       subcategory="Utilities")
          s.add_all((txn, txn_split))
      elif age < 45:
        # Buy house 1 with 20% down
        if not bought_1:
          date = dates[0]
          a_values_i = (date - a_values_start).days
          price = round(house_1_values[a_values_i], -3)

          balance, rate, payment, pmi, pmi_th = buy_house(date, house_1, price)
          escrow = round(price * 0.02 / 12, 2)
          bought_1 = True

        # Pay monthly payment
        for date in dates:
          balance = monthly_payment(date, balance, rate, payment, escrow, pmi,
                                    pmi_th)

        # Escrow increases each year
        r = max(0, INTEREST_RATES[date.year])
        escrow = round(escrow * (1 + r), 2)
      elif age < 60:
        # Buy house 2 with proceeds of house 1
        if not bought_2:
          date = dates[0]
          a_values_i = (date - a_values_start).days

          # Sell house 1
          price = round(house_1_values[a_values_i], -3)
          sell_house(date, house_1, price, balance)

          # Buy house 2
          price = round(house_2_values[a_values_i], -3)

          balance, rate, payment, pmi, pmi_th = buy_house(date, house_2, price)
          escrow = round(price * 0.02 / 12, 2)
          bought_2 = True

        # Pay monthly payment
        for date in dates:
          balance = monthly_payment(date, balance, rate, payment, escrow, pmi,
                                    pmi_th)

        # Escrow increases each year
        r = max(0, INTEREST_RATES[date.year])
        escrow = round(escrow * (1 + r), 2)
      else:
        # Buy house 2 with proceeds of house 1
        if not bought_3:
          date = dates[0]
          a_values_i = (date - a_values_start).days

          # Sell house 2
          price = round(house_2_values[a_values_i], -3)
          sell_house(date, house_2, price, balance)

          # Buy house 3
          price = round(house_3_values[a_values_i], -3)

          balance, rate, payment, pmi, pmi_th = buy_house(date, house_3, price)
          escrow = round(price * 0.02 / 12, 2)
          bought_3 = True

        # Pay monthly payment
        for date in dates:
          balance = monthly_payment(date, balance, rate, payment, escrow, pmi,
                                    pmi_th)

        # Escrow increases each year
        r = max(0, INTEREST_RATES[date.year])
        escrow = round(escrow * (1 + r), 2)

    s.commit()
  print(f"{Fore.GREEN}Generated housing")


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
    a_values_start = datetime.date(BIRTH_YEAR, 1, 1)
    a_values_end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
    _, values, _ = acct.get_value(a_values_start, a_values_end)

    total_interest = 0

    while date < end:
      next_date = next_month(date)

      # Interest on the average balance
      i_start = (date - a_values_start).days
      i_end = (next_date - a_values_start).days
      avg_value = (sum(values[i_start:i_end]) / (i_end - i_start) +
                   total_interest)

      if avg_value < 0:
        raise ValueError(f"Account {acct.name} was over-drafted by "
                         f"{avg_value:.2f}")

      rate = INTEREST_RATES[date.year]
      interest = round(rate / 12 * avg_value, 2)

      if interest > 0:
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
      total_interest += interest

    s.commit()
    print(f"{Fore.GREEN}Added interest for {acct.name}")


def add_cc_payments(p: Portfolio, acct_id: int) -> None:
  """Adds credit card payments to Account

  Args:
    acct_id: Account to generate for
  """
  with p.get_session() as s:
    acct = s.query(Account).where(Account.id == acct_id).first()
    if len(acct.transactions) == 0:
      print(f"{Fore.RED}No transaction to generate CC payments on for "
            f"{acct.name}")
      return
    date = acct.transactions[0].date
    end = birthday("self", FINAL_AGE)
    a_values_start = datetime.date(BIRTH_YEAR, 1, 1)
    a_values_end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
    _, values, _ = acct.get_value(a_values_start, a_values_end)

    total_payment = 0

    while date < end:
      next_date = next_month(date)

      # Interest on the average balance
      i_end = (next_date - a_values_start).days
      balance = round(values[i_end] + total_payment, 2)

      if balance < 0:
        txn = Transaction(account=acct,
                          date=next_date.replace(day=15),
                          total=-balance,
                          statement="Credit Card Payment")
        txn_split = TransactionSplit(parent=txn,
                                     total=txn.total,
                                     category=TransactionCategory.TRANSFER,
                                     subcategory="Credit Card Payments")
        s.add_all((txn, txn_split))

      date = next_date
      total_payment += -balance

    s.commit()
    print(f"{Fore.GREEN}Added CC payments for {acct.name}")


def main() -> None:
  """Main program entry
  """
  start = time.perf_counter()
  p = Portfolio.create("portfolio.db")

  accts = make_accounts(p)
  assets = make_assets(p)

  generate_early_savings(p, accts)

  generate_income(p, accts, assets)

  generate_housing(p, accts, assets)

  for name in ["cc_0", "cc_1"]:
    add_cc_payments(p, accts[name])

  for name in ["checking", "savings"]:
    add_interest(p, accts[name])

  duration = time.perf_counter() - start
  print(f"{Fore.CYAN}Portfolio generation took {duration:.1f}s")

  print_stats(p)


if __name__ == "__main__":
  main()
