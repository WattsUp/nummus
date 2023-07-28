"""Create a test Portfolio
"""

import datetime
from decimal import Decimal
import time

import colorama
from colorama import Fore
import numpy as np

from nummus import custom_types as t
from nummus.portfolio import Portfolio
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           AssetValuation, Transaction, TransactionCategory,
                           TransactionSplit)

colorama.init(autoreset=True)

RNG = np.random.default_rng()
NO_RNG = False


def rng_uniform(low: t.Real, high: t.Real, precision: int = 6) -> t.Real:
  """Return a number from a uniform distribution

  Args:
    low: Lower bounds
    high: Upper bounds
    precision: Number of digits to round to

  Returns:
    Random number from distribution
  """
  if NO_RNG:
    return round(Decimal(low + high) / 2, precision)
  return round(Decimal(RNG.uniform(low, high)), precision)


def rng_int(low: int, high: int) -> int:
  """Return an integer from a uniform distribution

  Args:
    low: Lower bounds
    high: Upper bounds

  Returns:
    Random number from distribution
  """
  if NO_RNG:
    return int((low + high) / 2)
  return int(RNG.integers(low, high, endpoint=True))


def rng_normal(loc: t.Real, scale: t.Real, precision: int = 6) -> t.Real:
  """Return a number from a normal distribution

  Args:
    loc: Center of distribution
    scale: Std. dev of distribution
    precision: Number of digits to round to

  Returns:
    Random number from distribution
  """
  if NO_RNG:
    return round(Decimal(loc) / 2, precision)
  return round(Decimal(RNG.normal(loc, scale)), precision)


def rng_choice(choices: t.List[t.Any]) -> t.Any:
  """Return an random selection from a list of choices

  Args:
    choices: List of choices to choose from

  Returns:
    Random choice
  """
  if NO_RNG:
    return choices[0]
  return RNG.choice(choices)


FINAL_AGE = 80
# Base prices on real US prices
BIRTH_YEAR = 1940

BIRTHDAYS: t.DictDate = {"self": datetime.date.today().replace(year=BIRTH_YEAR)}

INTEREST_RATES: t.DictIntReal = {
    y: 10**rng_uniform(-3, -1.3)
    for y in range(BIRTH_YEAR, BIRTH_YEAR + FINAL_AGE + 1)
}

INFLATION_RATES: t.DictIntReal = {
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


def make_accounts(p: Portfolio) -> t.DictInt:
  """Create accounts

  Args:
    p: Portfolio to edit

  Returns:
    Dict{account name: id}
  """
  accounts: t.DictInt = {}
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
    mortgage = Account(name="Monkey Mortgage",
                       institution="Monkey Bank",
                       category=AccountCategory.MORTGAGE)
    retirement = Account(name="401k",
                         institution="Monkey Bank Retirement",
                         category=AccountCategory.INVESTMENT)
    real_estate = Account(name="Real Estate",
                          institution="Real Estate",
                          category=AccountCategory.FIXED)

    accts = [checking, savings, cc_0, cc_1, mortgage, retirement, real_estate]
    s.add_all(accts)
    s.commit()

    accounts["checking"] = checking.id
    accounts["savings"] = savings.id
    accounts["cc_0"] = cc_0.id
    accounts["cc_1"] = cc_1.id
    accounts["mortgage"] = mortgage.id
    accounts["retirement"] = retirement.id
    accounts["real_estate"] = real_estate.id

  print(f"{Fore.GREEN}Created accounts")

  return accounts


def make_assets(p: Portfolio) -> t.DictInt:
  """Create assets to buy and sell

  Args:
    p: Portfolio to edit

  Returns:
    Dict{asset name: id}
  """
  assets: t.DictInt = {}
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
    stocks: t.Dict[str, t.List[t.Union[Asset, t.Real]]] = {
        "growth": [growth, Decimal(100),
                   Decimal(0.07),
                   Decimal(0.2)],
        "value": [value, Decimal(100),
                  Decimal(0.05),
                  Decimal(0.05)],
    }
    real_estate: t.Dict[str, t.List[t.Union[Asset, t.Real]]] = {
        "house_main": [
            house_main,
            Decimal(1.5e3),
            Decimal(0.05),
            Decimal(0.02)
        ],
        "house_second": [
            house_second,
            Decimal(3e3),
            Decimal(0.06),
            Decimal(0.02)
        ],
        "house_third": [
            house_third,
            Decimal(5e3),
            Decimal(0.07),
            Decimal(0.02)
        ],
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
        rate = rng_normal(item[2] / 252, item[3] / Decimal(np.sqrt(252)))
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
        rate = rng_normal(item[2] / 12, item[3] / Decimal(np.sqrt(12)))
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
  buf: t.DictStr = {}
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


def generate_early_savings(p: Portfolio, accts: t.DictInt) -> None:
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
                        total=round(rng_uniform(1, 10), 2),
                        statement="Birthday money")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.INCOME,
                                   subcategory="Other Income")
      s.add_all((txn, txn_split))
    s.commit()
  print(f"{Fore.GREEN}Generated early savings")


def generate_income(p: Portfolio, accts: t.DictInt, assets: t.DictInt) -> None:
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
    _, a_growth_values = a_growth.get_value(a_values_start, a_values_end)
    _, a_value_values = a_value.get_value(a_values_start, a_values_end)

    for age in range(16, min(60, FINAL_AGE) + 1):
      if age <= 22:
        job = "Barista"
        salary = 1.5e3 * (1.03)**(age - 16)
      elif age <= 35:
        job = "Software Engineer"
        salary = 6e3 * (1.05)**(age - 22)
      else:
        job = "Engineering Manager"
        salary = 15e3 * (1.06)**(age - 35)
      salary = Decimal(salary)
      total = round(salary / 24, 2)
      # At age 24, decide to start contributing to retirement
      savings = round(total * Decimal(0.1), 2)
      if age < 24:
        retirement = 0
      else:
        retirement = round(total * Decimal(0.1), 2)
      paycheck = total - savings - retirement

      # Paychecks on the 5th and 20th unless that day falls on a weekend
      def adjust_date(date: datetime.date) -> datetime.datetime:
        if date.weekday() == 5:
          return date - datetime.timedelta(days=1)
        elif date.weekday() == 6:
          return date + datetime.timedelta(days=1)
        return date

      dates: t.Dates = []
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
            cost_growth = round(retirement * Decimal(0.9), 2)
          elif age < 40:
            cost_growth = round(retirement * Decimal(0.5), 2)
          else:
            cost_growth = round(retirement * Decimal(0.1), 2)
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


def generate_housing(p: Portfolio, accts: t.DictInt, assets: t.DictInt) -> None:
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
    _, house_1_values = house_1.get_value(a_values_start, a_values_end)
    _, house_2_values = house_2.get_value(a_values_start, a_values_end)
    _, house_3_values = house_3.get_value(a_values_start, a_values_end)

    savings = s.query(Account).where(Account.id == accts["savings"]).first()

    def buy_house(
        date: datetime.date, house: Asset,
        price: t.Real) -> t.Tuple[t.Real, t.Real, t.Real, t.Real, t.Real]:
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
      closing_costs = round(price * Decimal(0.05), 2)
      max_dp = values[0] - closing_costs
      no_pmi_dp = price * Decimal(0.2)
      if max_dp < no_pmi_dp:
        # Clear out savings to avoid PMI
        down_payment = round(max_dp, 2)
      else:
        # Pay 20% unless there is more than 50k of excess cash
        down_payment = round(max(no_pmi_dp, max_dp - Decimal(50e3)), 2)

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

      pmi = round(Decimal(0.01) * pi * 12, 2)
      pmi_threshold = Decimal(0.8) * price

      s.commit()
      print(f"{Fore.CYAN}  Bought {house.description}")
      return p, r, pi, pmi, pmi_threshold

    def sell_house(date: datetime.date, house: Asset, price: t.Real,
                   balance: t.Real) -> None:
      """Add transactions to sell a house

      Args:
        date: Transaction date
        house: Asset to sell
        price: Price to sell it at
      """
      closing_costs = round(price * Decimal(0.08), 2)

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

      s.commit()
      print(f"{Fore.CYAN}  Sold {house.description}")

    def monthly_payment(date: datetime.date, balance: t.Real, rate: t.Real,
                        payment: t.Real, escrow: t.Real, pmi: t.Real,
                        pmi_threshold: t.Real) -> t.Real:
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

      utilities = max(10, round(payment * rng_normal(0.1, 0.01), 2))

      txn = Transaction(account_id=accts["cc_0"],
                        date=date,
                        total=-utilities,
                        statement="Utilities")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.HOME,
                                   subcategory="Utilities")
      s.add_all((txn, txn_split))

      # Adds a repair cost 25% of the time with an average cost target_price
      # per month
      target_price = payment * Decimal(0.05)
      repair_cost = round(target_price / np.sqrt(rng_uniform(1e-5, 1)), 2)
      if repair_cost > (2 * target_price):
        acct_id = accts["cc_0"]
        if repair_cost > (10 * target_price):
          # Use savings for big repairs
          acct_id = accts["savings"]
        txn = Transaction(account_id=acct_id,
                          date=date + datetime.timedelta(days=rng_int(1, 28)),
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
      dates: t.Dates = []
      for m in range(12):
        date = datetime.date(BIRTH_YEAR + age, m + 1, 1)
        dates.append(date)

      if age < 30:
        # Renting until age 30
        rent = Decimal(71 * (1.03)**(age - 18))
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
          escrow = round(price * Decimal(0.02) / 12, 2)
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
          escrow = round(price * Decimal(0.02) / 12, 2)
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
          escrow = round(price * Decimal(0.02) / 12, 2)
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


def generate_food(p: Portfolio, accts: t.DictInt) -> None:
  """Generate food payments

  Args:
    p: Portfolio to edit
    accts: Account IDs to use
  """
  with p.get_session() as s:
    grocery_stores: t.Strings = [
        "Walmart", "Grocery Outlet", "Safeway", "Fred Meyer", "QFC", "Kroger"
    ]
    restaurants: t.Strings = [
        "Pizza Palace", "Fine Dining R Us", "Italian Garden", "Chinese Kitchen",
        "Burgers and Beef", "Only Spam", "Thai 42", "Fajitas and More"
    ]

    # Never groceries on a Monday, Friday, or Saturday
    def adjust_date(date: datetime.date) -> datetime.datetime:
      if date.weekday() == 0:
        return date + datetime.timedelta(days=rng_int(1, 3))
      elif date.weekday() == 4:
        return date - datetime.timedelta(days=rng_int(1, 3))
      elif date.weekday() == 5:
        return date - datetime.timedelta(days=rng_int(2, 4))
      return date

    grocery_budget = 30
    restaurant_cost = 2
    restaurant_freq = 2
    restaurant_plates = 1

    for age in range(18, FINAL_AGE + 1):
      dates: t.Dates = []
      for m in range(12):
        # Groceries twice a month
        date_0 = datetime.date(BIRTH_YEAR + age, m + 1, 1)
        date_1 = datetime.date(BIRTH_YEAR + age, m + 1, 15)
        dates.append(adjust_date(date_0))
        dates.append(adjust_date(date_1))

      if age == 28:
        # Add a spouse
        grocery_budget = 60
        restaurant_freq = 4
        restaurant_plates = 2
      elif age == 35:
        # Add children
        grocery_budget = 150
        restaurant_freq = 2
        restaurant_plates = 4
      elif age == (35 + 20):
        # Remove children
        grocery_budget = 200
        restaurant_freq = 6
        restaurant_plates = 2

      r = INFLATION_RATES[BIRTH_YEAR + age]
      grocery_budget = grocery_budget * (1 + r)
      restaurant_cost = restaurant_cost * (1 + r)

      acct_id = accts["cc_0"]
      if age > 32:
        # Open a new credit card
        acct_id = accts["cc_1"]

      for date in dates:
        store = rng_choice(grocery_stores)
        total = round(grocery_budget / 2 * rng_normal(1, 0.2), 2)
        if total > 0:
          txn = Transaction(account_id=acct_id,
                            date=date,
                            total=-total,
                            statement=store)
          txn_split = TransactionSplit(parent=txn,
                                       total=txn.total,
                                       payee=store,
                                       category=TransactionCategory.FOOD,
                                       subcategory="Groceries")
          s.add_all((txn, txn_split))

      # Go out to restaurants
      dates: t.Dates = []
      for m in range(12):
        days = RNG.choice(range(1, 29), restaurant_freq, replace=False)
        for day in days:
          date = datetime.date(BIRTH_YEAR + age, m + 1, day)
          restaurant = rng_choice(restaurants)
          total_exp = restaurant_cost * restaurant_plates
          total = round(total_exp * rng_normal(1, 0.2), 2)
          txn = Transaction(account_id=acct_id,
                            date=date,
                            total=-total,
                            statement=restaurant)
          txn_split = TransactionSplit(parent=txn,
                                       total=txn.total,
                                       payee=restaurant,
                                       category=TransactionCategory.FOOD,
                                       subcategory="Restaurant")
          s.add_all((txn, txn_split))

    s.commit()
  print(f"{Fore.GREEN}Generated food")


def add_retirement(p: Portfolio, accts: t.DictInt, assets: t.DictInt) -> None:
  """Perform retirement changeover

  Args:
    p: Portfolio to edit
    accts: Account IDs to use
    assets: Asset IDs to use
  """
  with p.get_session() as s:
    acct = s.query(Account).where(Account.id == accts["retirement"]).first()
    a_growth = s.query(Asset).where(Asset.id == assets["growth"]).first()
    a_value = s.query(Asset).where(Asset.id == assets["value"]).first()
    date_sell = next_month(acct.transactions[-1].date)
    date_transfer = date_sell + datetime.timedelta(days=7)

    _, asset_qty = acct.get_asset_qty(date_sell, date_sell)

    def sell_asset(asset: Asset, qty: t.Real) -> None:
      """Add transactions to sell an Asset

      Args:
        asset: Asset to sell
        qty: Quantity to sell
      """
      _, values = asset.get_value(date_sell, date_sell)
      total = round(qty * values[0], 2)
      txn = Transaction(account_id=accts["retirement"],
                        date=date_sell,
                        total=total,
                        statement="Security Sell")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.INSTRUMENT,
                                   asset=asset,
                                   asset_quantity=-qty)
      s.add_all((txn, txn_split))

      txn = Transaction(account_id=accts["retirement"],
                        date=date_transfer,
                        total=-total,
                        statement="Account Transfer")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.TRANSFER)
      s.add_all((txn, txn_split))

      txn = Transaction(account_id=accts["checking"],
                        date=date_transfer,
                        total=total,
                        statement="Account Transfer")
      txn_split = TransactionSplit(parent=txn,
                                   total=txn.total,
                                   category=TransactionCategory.TRANSFER)
      s.add_all((txn, txn_split))

    sell_asset(a_growth, asset_qty[a_growth.uuid][0])
    sell_asset(a_value, asset_qty[a_value.uuid][0])
    s.commit()


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

    total_interest = Decimal(0)

    while date < end:
      next_date = next_month(date)

      # Interest on the average balance
      i_start = (date - a_values_start).days
      i_end = (next_date - a_values_start).days
      avg_value = (sum(values[i_start:i_end]) / (i_end - i_start) +
                   total_interest)

      if avg_value < 0:
        raise ValueError(f"Account {acct.name} was over-drafted by "
                         f"{avg_value:.2f} on {date}")

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


def add_cc_payments(p: Portfolio, acct_id: int, acct_id_fund: int) -> None:
  """Adds credit card payments to Account

  Args:
    acct_id: Account to generate for
    acct_id_fund: Account to withdraw funds from
  """
  with p.get_session() as s:
    acct = s.query(Account).where(Account.id == acct_id).first()
    acct_fund = s.query(Account).where(Account.id == acct_id_fund).first()
    if len(acct.transactions) == 0:
      print(f"{Fore.RED}No transaction to generate CC payments on for "
            f"{acct.name}")
      return
    date = acct.transactions[0].date
    end = birthday("self", FINAL_AGE)
    a_values_start = datetime.date(BIRTH_YEAR, 1, 1)
    a_values_end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
    _, values, _ = acct.get_value(a_values_start, a_values_end)

    total_payment = Decimal(0)

    while date < end:
      next_date = next_month(date)

      # Interest on the average balance
      i_end = (next_date - a_values_start).days
      balance = round(values[i_end] + total_payment, 2)

      if balance < 0:
        due_date = next_date.replace(day=15)
        txn = Transaction(account=acct,
                          date=due_date,
                          total=-balance,
                          statement="Credit Card Payment")
        txn_split = TransactionSplit(parent=txn,
                                     total=txn.total,
                                     category=TransactionCategory.TRANSFER,
                                     subcategory="Credit Card Payments")
        s.add_all((txn, txn_split))

        txn = Transaction(account=acct_fund,
                          date=due_date,
                          total=balance,
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

  generate_food(p, accts)

  add_retirement(p, accts, assets)

  for name in ["cc_0", "cc_1"]:
    add_cc_payments(p, accts[name], accts["checking"])

  for name in ["checking", "savings"]:
    add_interest(p, accts[name])

  duration = time.perf_counter() - start
  print(f"{Fore.CYAN}Portfolio generation took {duration:.1f}s")

  print_stats(p)


if __name__ == "__main__":
  main()
