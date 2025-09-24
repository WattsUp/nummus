"""Create a test Portfolio."""

from __future__ import annotations

import datetime
import time
from decimal import Decimal
from typing import TypeVar

import colorama
import numpy as np
from colorama import Fore

from nummus import commands, health_checks
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetSplit,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from nummus.portfolio import Portfolio

colorama.init(autoreset=True)

RNG = np.random.default_rng()
NO_RNG = False


def rng_uniform(
    low: Decimal | float,
    high: Decimal | float,
    precision: int = 6,
) -> Decimal:
    """Return a number from a uniform distribution.

    Args:
        low: Lower bounds
        high: Upper bounds
        precision: Number of digits to round to

    Returns:
        Random number from distribution
    """
    low_d = Decimal(low)
    high_d = Decimal(high)
    if NO_RNG:
        return round(Decimal(low_d + high_d) / 2, precision)
    return round(Decimal(RNG.uniform(float(low), float(high))), precision)


def rng_int(low: int, high: int) -> int:
    """Return an integer from a uniform distribution.

    Args:
        low: Lower bounds
        high: Upper bounds

    Returns:
        Random number from distribution
    """
    if NO_RNG:
        return int((low + high) / 2)
    return int(RNG.integers(low, high, endpoint=True))


def rng_normal(
    loc: Decimal | float,
    scale: Decimal | float,
    precision: int = 6,
) -> Decimal:
    """Return a number from a normal distribution.

    Args:
        loc: Center of distribution
        scale: Std. dev of distribution
        precision: Number of digits to round to

    Returns:
        Random number from distribution
    """
    if NO_RNG:
        return round(Decimal(loc) / 2, precision)
    return round(Decimal(RNG.normal(float(loc), float(scale))), precision)


T = TypeVar("T")


def rng_choice(choices: list[T]) -> T:
    """Return an random selection from a list of choices.

    Args:
        choices: List of choices to choose from

    Returns:
        Random choice
    """
    if NO_RNG:
        return choices[0]
    return RNG.choice(choices)  # type: ignore[attr-defined]


FINAL_AGE = 80
# Base prices on real US prices
BIRTH_YEAR = 1940

BIRTHDAYS: dict[str, datetime.date] = {
    "self": datetime.date.today().replace(year=BIRTH_YEAR),
}

INTEREST_RATES: dict[int, Decimal] = {
    y: 10 ** rng_uniform(Decimal(-3), Decimal("-1.3"))
    for y in range(BIRTH_YEAR, BIRTH_YEAR + FINAL_AGE + 1)
}

INFLATION_RATES: dict[int, Decimal] = {
    y: rng_normal(Decimal("0.0376"), Decimal("0.0278"))
    for y in range(BIRTH_YEAR, BIRTH_YEAR + FINAL_AGE + 1)
}


def birthday(name: str, age: int) -> datetime.date:
    """Get the birthday of an individual at an age.

    Args:
        name: Name of person, found in BIRTHDAYS
        age: Age of person

    Returns:
        BIRTHDAYS[name] + age
    """
    year = BIRTHDAYS[name].year + age
    return BIRTHDAYS[name].replace(year=year)


def next_month(date: datetime.date) -> datetime.date:
    """Get the first day of the next month of a date.

    Args:
        date: Reference date

    Returns:
        First day of the next month
    """
    y = date.year
    m = date.month
    return datetime.date(y + m // 12, m % 12 + 1, 1)


def make_accounts(p: Portfolio) -> dict[str, int]:
    """Create accounts.

    Args:
        p: Portfolio to edit

    Returns:
        Dict{account name: id}
    """
    accounts: dict[str, int] = {}
    with p.begin_session() as s:
        checking = Account(
            name="Checking",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
            number="MB-1234",
            budgeted=True,
        )
        savings = Account(
            name="Savings",
            institution="Monkey Bank",
            category=AccountCategory.CASH,
            closed=False,
            number="MB-1235",
            budgeted=True,
        )
        cc_0 = Account(
            name="Banana VISA",
            institution="Monkey Bank",
            category=AccountCategory.CREDIT,
            closed=False,
            number="MB-1236",
            budgeted=True,
        )
        cc_1 = Account(
            name="Peanut Credit",
            institution="PB Loans",
            category=AccountCategory.CREDIT,
            closed=False,
            number="PB-1234",
            budgeted=True,
        )
        mortgage = Account(
            name="Monkey Mortgage",
            institution="Monkey Bank",
            category=AccountCategory.MORTGAGE,
            closed=False,
            number="MB-4234",
            budgeted=False,
        )
        retirement = Account(
            name="401k",
            institution="Monkey Bank Retirement",
            category=AccountCategory.INVESTMENT,
            closed=False,
            number="MBR-1234",
            budgeted=False,
        )
        real_estate = Account(
            name="Real Estate",
            institution="Real Estate",
            category=AccountCategory.FIXED,
            closed=False,
            budgeted=False,
        )

        accts = [checking, savings, cc_0, cc_1, mortgage, retirement, real_estate]
        s.add_all(accts)
        s.flush()

        accounts["checking"] = checking.id_
        accounts["savings"] = savings.id_
        accounts["cc_0"] = cc_0.id_
        accounts["cc_1"] = cc_1.id_
        accounts["mortgage"] = mortgage.id_
        accounts["retirement"] = retirement.id_
        accounts["real_estate"] = real_estate.id_

    print(f"{Fore.GREEN}Created accounts")

    return accounts


def make_assets(p: Portfolio) -> dict[str, int]:
    """Create assets to buy and sell.

    Args:
        p: Portfolio to edit

    Returns:
        Dict{asset name: id}
    """
    assets: dict[str, int] = {}
    with p.begin_session() as s:
        growth = Asset(
            name="GROWTH",
            description="Growth ETF",
            category=AssetCategory.STOCKS,
        )
        value = Asset(
            name="VALUE",
            description="Value ETF",
            category=AssetCategory.STOCKS,
        )
        house_main = Asset(
            name="Main St. House",
            description="House on Main St.",
            category=AssetCategory.REAL_ESTATE,
            interpolate=True,
        )
        house_second = Asset(
            name="Second Ave. House",
            description="House on Second Ave.",
            category=AssetCategory.REAL_ESTATE,
            interpolate=True,
        )
        house_third = Asset(
            name="Third Blvd. House",
            description="House on Third Blvd.",
            category=AssetCategory.REAL_ESTATE,
            interpolate=True,
        )
        # Don't add AssetValuations so update-assets command can
        sp500 = Asset(
            name="S&P 500 ETF",
            description="Average of the 500 largest publicly traded companies",
            category=AssetCategory.STOCKS,
            ticker="SPY",
        )
        # Add Apple so stock splits can be tested
        apple = Asset(
            name="Apple Inc.",
            description="Technology company making phones, personal computers, etc.",
            category=AssetCategory.STOCKS,
            ticker="AAPL",
        )

        # Name: [Asset, current price, growth mean, growth stddev]
        stocks: dict[str, tuple[Asset, Decimal, Decimal, Decimal]] = {
            "growth": (growth, Decimal(100), Decimal("0.07"), Decimal("0.2")),
            "value": (value, Decimal(100), Decimal("0.05"), Decimal("0.05")),
        }
        real_estate: dict[str, tuple[Asset, Decimal, Decimal, Decimal]] = {
            "house_main": (
                house_main,
                Decimal("1.5e3"),
                Decimal("0.05"),
                Decimal("0.02"),
            ),
            "house_second": (
                house_second,
                Decimal("3e3"),
                Decimal("0.06"),
                Decimal("0.02"),
            ),
            "house_third": (
                house_third,
                Decimal("5e3"),
                Decimal("0.07"),
                Decimal("0.02"),
            ),
        }
        s.add_all(v[0] for v in stocks.values())
        s.add_all(v[0] for v in real_estate.values())
        s.add_all((sp500, apple))
        s.flush()

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
            date_ord = date.toordinal()

            for key, item in list(stocks.items()):
                a: Asset = item[0]
                current: Decimal = item[1]
                mean: Decimal = item[2]
                stddev: Decimal = item[3]

                rate = rng_normal(mean / 252, stddev / Decimal(np.sqrt(252)))
                v = round(current * (1 + rate), 2)

                valuation = AssetValuation(asset_id=a.id_, value=v, date_ord=date_ord)
                s.add(valuation)

                stocks[key] = (a, v, mean, stddev)

            date += datetime.timedelta(days=1)
        s.flush()
        print(f"{Fore.CYAN}  Valued stocks")

        # Real estate valued once a month
        date = start
        end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
        while date <= end:
            date_ord = date.toordinal()
            for key, item in list(real_estate.items()):
                a: Asset = item[0]
                current: Decimal = item[1]
                mean: Decimal = item[2]
                stddev: Decimal = item[3]

                rate = rng_normal(mean / 12, stddev / Decimal(np.sqrt(12)))
                v = round(current * (1 + rate), 2)

                valuation = AssetValuation(asset_id=a.id_, value=v, date_ord=date_ord)
                s.add(valuation)

                real_estate[key] = (a, v, mean, stddev)

            y = date.year
            m = date.month
            date = datetime.date(y + m // 12, m % 12 + 1, 1)
        s.flush()
        print(f"{Fore.CYAN}  Valued real estate")

        assets = {k: v[0].id_ for k, v in stocks.items()}
        for k, v in real_estate.items():
            assets[k] = v[0].id_
        assets["S&P 500"] = sp500.id_
        assets["Apple Inc."] = apple.id_

    print(f"{Fore.GREEN}Created assets")

    return assets


def generate_early_savings(p: Portfolio, accts: dict[str, int]) -> None:
    """Generate early savings transactions, namely birthday money.

    Args:
        p: Portfolio to edit
        accts: Account IDs to use
    """
    with p.begin_session() as s:
        categories = {cat.name: cat for cat in s.query(TransactionCategory).all()}

        acct: Account = s.query(Account).where(Account.id_ == accts["savings"]).one()
        for age in range(8, 18):
            date = birthday("self", age)
            txn = Transaction(
                account_id=acct.id_,
                date=date,
                amount=round(rng_uniform(Decimal(1), Decimal(10)), 2),
                statement="Birthday money",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                payee="Family member",
                category_id=categories["Other Income"].id_,
                description=txn.statement,
            )
            s.add_all((txn, txn_split))
    print(f"{Fore.GREEN}Generated early savings")


def generate_income(
    p: Portfolio,
    accts: dict[str, int],
    assets: dict[str, int],
) -> None:
    """Generate income from working, stopping at retirement.

    Args:
        p: Portfolio to edit
        accts: Account IDs to use
        assets: Asset IDs to use
    """
    with p.begin_session() as s:
        categories = {cat.name: cat for cat in s.query(TransactionCategory).all()}

        a_growth: Asset = s.query(Asset).where(Asset.id_ == assets["growth"]).one()
        a_value: Asset = s.query(Asset).where(Asset.id_ == assets["value"]).one()
        a_values_start = datetime.date(BIRTH_YEAR, 1, 1)
        a_values_end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
        a_values_start_ord = a_values_start.toordinal()
        a_values_end_ord = a_values_end.toordinal()
        a_growth_values = a_growth.get_value(a_values_start_ord, a_values_end_ord)
        a_value_values = a_value.get_value(a_values_start_ord, a_values_end_ord)

        acct_savings: Account = (
            s.query(Account).where(Account.id_ == accts["savings"]).one()
        )
        acct_checking: Account = (
            s.query(Account).where(Account.id_ == accts["checking"]).one()
        )
        acct_retirement: Account = (
            s.query(Account).where(Account.id_ == accts["retirement"]).one()
        )

        for age in range(16, min(60, FINAL_AGE) + 1):
            if age <= 22:
                job = "Barista"
                salary = 1.5e3 * (1.03) ** (age - 16)
            elif age <= 35:
                job = "Software Engineer"
                salary = 6e3 * (1.05) ** (age - 22)
            else:
                job = "Engineering Manager"
                salary = 15e3 * (1.06) ** (age - 35)
            salary = Decimal(salary)
            amount = round(salary / 24, 2)
            # At age 24, decide to start contributing to retirement
            savings = round(amount * Decimal("0.1"), 2)
            retirement = 0 if age < 24 else round(amount * Decimal("0.1"), 2)
            paycheck = amount - savings - retirement

            # Paychecks on the 5th and 20th unless that day falls on a weekend
            def adjust_date(date: datetime.date) -> datetime.date:
                if date.weekday() == 5:
                    return date - datetime.timedelta(days=1)
                if date.weekday() == 6:
                    return date + datetime.timedelta(days=1)
                return date

            dates: list[datetime.date] = []
            for m in range(12):
                date_0 = datetime.date(BIRTH_YEAR + age, m + 1, 5)
                date_1 = datetime.date(BIRTH_YEAR + age, m + 1, 20)

                dates.append(adjust_date(date_0))
                dates.append(adjust_date(date_1))

            for date in dates:
                date_ord = date.toordinal()
                txn = Transaction(
                    account_id=acct_checking.id_,
                    date=date,
                    amount=paycheck,
                    statement=job,
                    locked=True,
                    linked=True,
                )
                txn_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    payee="Employer",
                    category_id=categories["Paychecks/Salary"].id_,
                    description=txn.statement,
                )
                s.add_all((txn, txn_split))
                txn = Transaction(
                    account_id=acct_savings.id_,
                    date=date,
                    amount=savings,
                    statement=job,
                    locked=True,
                    linked=True,
                )
                txn_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    payee="Employer",
                    category_id=categories["Paychecks/Salary"].id_,
                    description=txn.statement,
                )
                s.add_all((txn, txn_split))
                if retirement != 0:
                    txn = Transaction(
                        account_id=acct_retirement.id_,
                        date=date,
                        amount=retirement,
                        statement=job,
                        locked=True,
                        linked=True,
                    )
                    txn_split = TransactionSplit(
                        parent=txn,
                        amount=txn.amount,
                        payee="Employer",
                        category_id=categories["Retirement Contributions"].id_,
                        description=txn.statement,
                    )
                    s.add_all((txn, txn_split))

                    # Now buy stocks with that funding
                    if age < 30:
                        cost_growth = round(retirement * Decimal("0.9"), 2)
                    elif age < 40:
                        cost_growth = round(retirement * Decimal("0.5"), 2)
                    else:
                        cost_growth = round(retirement * Decimal("0.1"), 2)
                    cost_value = retirement - cost_growth

                    a_values_i = (date - a_values_start).days

                    if a_growth_values[a_values_i] > 500:
                        # Do a 4:1 stock split
                        m = 4
                        print(f"{Fore.YELLOW}{a_growth.name} {m}:1 split on {date}")
                        split = AssetSplit(
                            asset_id=a_growth.id_,
                            date_ord=date_ord,
                            multiplier=m,
                        )
                        s.add(split)

                        # Adjust all prices
                        query = s.query(AssetValuation)
                        query = query.where(AssetValuation.asset_id == a_growth.id_)
                        for v in query.all():
                            v: AssetValuation
                            v.value = v.value / m

                        a_growth_values = [round(v / m, 6) for v in a_growth_values]

                    if a_value_values[a_values_i] > 500:
                        # Do a 4:1 stock split
                        m = 4
                        print(f"{Fore.YELLOW}{a_value.name} {m}:1 split on {date}")
                        split = AssetSplit(
                            asset_id=a_value.id_,
                            date_ord=date_ord,
                            multiplier=m,
                        )
                        s.add(split)

                        # Adjust all prices
                        query = s.query(AssetValuation)
                        query = query.where(AssetValuation.asset_id == a_value.id_)
                        for v in query.all():
                            v: AssetValuation
                            v.value = v.value / m

                        a_value_values = [round(v / m, 6) for v in a_value_values]

                    qty_growth = round(cost_growth / a_growth_values[a_values_i], 6)
                    qty_value = round(cost_value / a_value_values[a_values_i], 6)

                    txn = Transaction(
                        account_id=acct_retirement.id_,
                        date=date,
                        amount=-retirement,
                        statement=job,
                        locked=True,
                        linked=True,
                    )
                    txn_split_0 = TransactionSplit(
                        parent=txn,
                        amount=-cost_growth,
                        category_id=categories["Securities Traded"].id_,
                        asset_id=a_growth.id_,
                        asset_quantity_unadjusted=qty_growth,
                        payee="Monkey Bank Retirement",
                        description=txn.statement,
                    )
                    txn_split_1 = TransactionSplit(
                        parent=txn,
                        amount=-cost_value,
                        category_id=categories["Securities Traded"].id_,
                        asset_id=a_value.id_,
                        asset_quantity_unadjusted=qty_value,
                        payee="Monkey Bank Retirement",
                        description=txn.statement,
                    )
                    s.add_all((txn, txn_split_0, txn_split_1))

        s.flush()

        a_growth.update_splits()
        a_value.update_splits()

    print(f"{Fore.GREEN}Generated income")


def generate_housing(
    p: Portfolio,
    accts: dict[str, int],
    assets: dict[str, int],
) -> None:
    """Generate housing payments.

    Args:
        p: Portfolio to edit
        accts: Account IDs to use
        assets: Asset IDs to use
    """
    with p.begin_session() as s:
        categories = {cat.name: cat for cat in s.query(TransactionCategory).all()}

        house_1: Asset = (
            s.query(Asset).where(Asset.id_ == assets["house_main"]).scalar()
        )
        house_2: Asset = (
            s.query(Asset).where(Asset.id_ == assets["house_second"]).scalar()
        )
        house_3: Asset = (
            s.query(Asset).where(Asset.id_ == assets["house_third"]).scalar()
        )
        a_values_start = datetime.date(BIRTH_YEAR, 1, 1)
        a_values_end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
        a_values_start_ord = a_values_start.toordinal()
        a_values_end_ord = a_values_end.toordinal()
        house_1_values = house_1.get_value(a_values_start_ord, a_values_end_ord)
        house_2_values = house_2.get_value(a_values_start_ord, a_values_end_ord)
        house_3_values = house_3.get_value(a_values_start_ord, a_values_end_ord)

        acct_savings: Account = (
            s.query(Account).where(Account.id_ == accts["savings"]).scalar()
        )
        acct_checking: Account = (
            s.query(Account).where(Account.id_ == accts["checking"]).scalar()
        )
        acct_mortgage: Account = (
            s.query(Account).where(Account.id_ == accts["mortgage"]).scalar()
        )
        acct_real_estate: Account = (
            s.query(Account).where(Account.id_ == accts["real_estate"]).scalar()
        )
        acct_cc_0: Account = (
            s.query(Account).where(Account.id_ == accts["cc_0"]).scalar()
        )

        def buy_house(
            date: datetime.date,
            house: Asset,
            price: Decimal,
        ) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
            """Add transactions to buy a house.

            Args:
                date: Transaction date
                house: Asset to buy
                price: Price to buy it at

            Returns:
                (Mortgage principal, monthly interest rate, monthly payment, pmi,
                pmi threshold)
            """
            date_ord = date.toordinal()
            values, _, _ = acct_savings.get_value(date_ord, date_ord)
            closing_costs = round(price * Decimal("0.05"), 2)
            max_dp = values[0] - closing_costs
            no_pmi_dp = price * Decimal("0.2")
            if max_dp < no_pmi_dp:
                # Clear out savings to avoid PMI
                down_payment = round(max_dp, 2)
            else:
                # Pay 20% unless there is more than 50k of excess cash
                down_payment = round(max(no_pmi_dp, max_dp - Decimal("50e3")), 2)
            down_payment = min(down_payment, round(price, 2))

            p = price - down_payment
            r = round(rng_uniform(Decimal("0.03"), Decimal("0.1")), 4) / 12
            pi = round(p * (r * (1 + r) ** 360) / ((1 + r) ** 360 - 1), 2)

            # Pay down payment and closing costs
            txn = Transaction(
                account_id=acct_savings.id_,
                date=date,
                amount=-(down_payment + closing_costs),
                statement="Home closing",
                locked=True,
                linked=True,
            )
            txn_dp = TransactionSplit(
                parent=txn,
                amount=-down_payment,
                category_id=categories["Transfers"].id_,
                payee="Monkey Bank",
                description="Down payment",
            )
            txn_cc = TransactionSplit(
                parent=txn,
                amount=-closing_costs,
                category_id=categories["Service Charge/Fees"].id_,
                payee="Monkey Bank",
                description="Closing costs",
            )
            s.add_all((txn, txn_dp, txn_cc))

            # Open a mortgage
            txn = Transaction(
                account_id=acct_mortgage.id_,
                date=date,
                amount=-p,
                statement="Home closing",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["Transfers"].id_,
                payee="Monkey Bank",
                description=txn.statement,
            )
            s.add_all((txn, txn_split))

            # Buy the house
            txn = Transaction(
                account_id=acct_real_estate.id_,
                date=date,
                amount=price,
                statement="Mortgage funding",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["Transfers"].id_,
                payee="Previous owner",
                description=txn.statement,
            )
            s.add_all((txn, txn_split))
            txn = Transaction(
                account_id=acct_real_estate.id_,
                date=date,
                amount=-price,
                statement="Home closing",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["Securities Traded"].id_,
                asset_id=house.id_,
                asset_quantity_unadjusted=1,
                payee="Previous owner",
                description=txn.statement,
            )
            s.add_all((txn, txn_split))

            pmi = round(Decimal("0.01") * pi * 12, 2)
            pmi_threshold = Decimal("0.8") * price

            s.flush()
            print(f"{Fore.CYAN}  Bought {house.description}")
            return p, r, pi, pmi, pmi_threshold

        def sell_house(
            date: datetime.date,
            house: Asset,
            price: Decimal,
            balance: Decimal,
        ) -> None:
            """Add transactions to sell a house.

            Args:
                date: Transaction date
                house: Asset to sell
                price: Price to sell it at
                balance: Remaining mortgage balance
            """
            closing_costs = round(price * Decimal("0.08"), 2)

            # Pay down payment and closing costs
            txn = Transaction(
                account_id=acct_savings.id_,
                date=date,
                amount=price - closing_costs,
                statement="Home closing",
                locked=True,
                linked=True,
            )
            txn_sell = TransactionSplit(
                parent=txn,
                amount=price,
                category_id=categories["Transfers"].id_,
                payee="Next owner",
                description="House sell",
            )
            txn_cc = TransactionSplit(
                parent=txn,
                amount=-closing_costs,
                category_id=categories["Service Charge/Fees"].id_,
                payee="Monkey Bank",
                description="Closing costs",
            )
            s.add_all((txn, txn_sell, txn_cc))

            # Sell the house
            txn = Transaction(
                account_id=acct_real_estate.id_,
                date=date,
                amount=price,
                statement="Home closing",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["Securities Traded"].id_,
                asset_id=house.id_,
                asset_quantity_unadjusted=-1,
                payee="Monkey Bank",
                description=txn.statement,
            )
            s.add_all((txn, txn_split))
            # Sell the house
            txn = Transaction(
                account_id=acct_real_estate.id_,
                date=date,
                amount=-price,
                statement="Transfer",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["Transfers"].id_,
                payee="Monkey Bank",
                description=txn.statement,
            )
            s.add_all((txn, txn_split))

            if balance > 0:
                # Close a mortgage
                txn = Transaction(
                    account_id=acct_mortgage.id_,
                    date=date,
                    amount=balance,
                    statement="Home closing",
                    locked=True,
                    linked=True,
                )
                txn_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    category_id=categories["Transfers"].id_,
                    payee="Monkey Bank",
                    description=txn.statement,
                )
                s.add_all((txn, txn_split))

                txn = Transaction(
                    account_id=acct_savings.id_,
                    date=date,
                    amount=-balance,
                    statement="Home closing",
                    locked=True,
                    linked=True,
                )
                txn_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    category_id=categories["Transfers"].id_,
                    payee="Monkey Bank",
                    description=txn.statement,
                )
                s.add_all((txn, txn_split))

            s.flush()
            print(f"{Fore.CYAN}  Sold {house.description}")

        def monthly_payment(
            date: datetime.date,
            balance: Decimal,
            rate: Decimal,
            payment: Decimal,
            escrow: Decimal,
            pmi: Decimal,
            pmi_threshold: Decimal,
        ) -> Decimal:
            """Add monthly payment transactions.

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
            amount = i + p + escrow
            if balance > pmi_threshold:
                amount += pmi
            txn = Transaction(
                account_id=acct_checking.id_,
                date=date,
                amount=-amount,
                statement="House payment",
                locked=True,
                linked=True,
            )
            txn_ti = TransactionSplit(
                parent=txn,
                amount=-escrow,
                category_id=categories["Service Charge/Fees"].id_,
                description="Taxes and Insurance",
                payee="Monkey Bank",
            )
            if p > 0:
                txn_i = TransactionSplit(
                    parent=txn,
                    amount=-i,
                    category_id=categories["Rent"].id_,
                    description="Interest",
                    payee="Monkey Bank",
                )
                txn_p = TransactionSplit(
                    parent=txn,
                    amount=-p,
                    category_id=categories["Transfers"].id_,
                    description="Principal",
                    payee="Monkey Bank",
                )
                if balance > pmi_threshold:
                    txn_pmi = TransactionSplit(
                        parent=txn,
                        amount=-pmi,
                        category_id=categories["Service Change/Fees"].id_,
                        description="PMI",
                        payee="Monkey Bank",
                    )
                    s.add_all((txn, txn_i, txn_p, txn_ti, txn_pmi))
                else:
                    s.add_all((txn, txn_i, txn_p, txn_ti))
            else:
                s.add_all((txn, txn_ti))

            if p > 0:
                txn = Transaction(
                    account_id=acct_mortgage.id_,
                    date=date,
                    amount=p,
                    statement="Principal",
                    locked=True,
                    linked=True,
                )
                txn_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    category_id=categories["Transfers"].id_,
                    payee="Monkey Bank",
                    description=txn.statement,
                )
                s.add_all((txn, txn_split))

            balance -= p

            utilities = max(
                10,
                round(payment * rng_normal(Decimal("0.1"), Decimal("0.01")), 2),
            )

            txn = Transaction(
                account_id=acct_cc_0.id_,
                date=date,
                amount=-utilities,
                statement="Utilities",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["Utilities"].id_,
                payee="Monkey Electric",
                description=txn.statement,
            )
            s.add_all((txn, txn_split))

            # Adds a repair cost 25% of the time with an average cost target_price
            # per month
            target_price = payment * Decimal("0.05")
            repair_cost = round(
                target_price / (rng_uniform(1e-5, 1) ** Decimal("0.5")), 2
            )
            if repair_cost > (2 * target_price):
                acct = acct_cc_0
                if repair_cost > (10 * target_price):
                    # Use savings for big repairs
                    acct = acct_savings
                txn = Transaction(
                    account_id=acct.id_,
                    date=date + datetime.timedelta(days=rng_int(1, 28)),
                    amount=-repair_cost,
                    statement="Repairs",
                    locked=True,
                    linked=True,
                )
                txn_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    category_id=categories["Home Maintenance"].id_,
                    payee="Home Depot",
                    description=txn.statement,
                )
                s.add_all((txn, txn_split))

            return balance

        bought_1 = False
        bought_2 = False
        bought_3 = False

        balance = Decimal()
        rate = Decimal()
        payment = Decimal()
        escrow = Decimal()
        pmi = Decimal()
        pmi_th = Decimal()

        for age in range(18, FINAL_AGE + 1):
            dates: list[datetime.date] = []
            year = BIRTH_YEAR + age
            for m in range(12):
                date = datetime.date(year, m + 1, 1)
                dates.append(date)

            if age < 30:
                # Renting until age 30
                rent = Decimal(71 * (1.03) ** (age - 18))
                for date in dates:
                    txn = Transaction(
                        account_id=acct_checking.id_,
                        date=date,
                        amount=-rent,
                        statement="Rent",
                        locked=True,
                        linked=True,
                    )
                    txn_split = TransactionSplit(
                        parent=txn,
                        amount=txn.amount,
                        category_id=categories["Rent"].id_,
                        payee="Monkey Rentals",
                        description=txn.statement,
                    )
                    s.add_all((txn, txn_split))

                    utilities = round(rent * rng_normal(0.1, 0.01), 2)

                    txn = Transaction(
                        account_id=acct_cc_0.id_,
                        date=date,
                        amount=-utilities,
                        statement="Utilities",
                        locked=True,
                        linked=True,
                    )
                    txn_split = TransactionSplit(
                        parent=txn,
                        amount=txn.amount,
                        category_id=categories["Utilities"].id_,
                        payee="Monkey Electric",
                        description=txn.statement,
                    )
                    s.add_all((txn, txn_split))
            elif age < 45:
                # Buy house 1 with 20% down
                if not bought_1:
                    date = dates[0]
                    a_values_i = (date - a_values_start).days
                    price = round(house_1_values[a_values_i], -3)

                    balance, rate, payment, pmi, pmi_th = buy_house(
                        date,
                        house_1,
                        price,
                    )
                    escrow = round(price * Decimal("0.02") / 12, 2)
                    bought_1 = True

                # Pay monthly payment
                for date in dates:
                    balance = monthly_payment(
                        date,
                        balance,
                        rate,
                        payment,
                        escrow,
                        pmi,
                        pmi_th,
                    )

                # Escrow increases each year
                r = max(0, INTEREST_RATES[year])
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

                    balance, rate, payment, pmi, pmi_th = buy_house(
                        date,
                        house_2,
                        price,
                    )
                    escrow = round(price * Decimal("0.02") / 12, 2)
                    bought_2 = True

                # Pay monthly payment
                for date in dates:
                    balance = monthly_payment(
                        date,
                        balance,
                        rate,
                        payment,
                        escrow,
                        pmi,
                        pmi_th,
                    )

                # Escrow increases each year
                r = max(0, INTEREST_RATES[year])
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

                    balance, rate, payment, pmi, pmi_th = buy_house(
                        date,
                        house_3,
                        price,
                    )
                    escrow = round(price * Decimal("0.02") / 12, 2)
                    bought_3 = True

                # Pay monthly payment
                for date in dates:
                    balance = monthly_payment(
                        date,
                        balance,
                        rate,
                        payment,
                        escrow,
                        pmi,
                        pmi_th,
                    )

                # Escrow increases each year
                r = max(0, INTEREST_RATES[year])
                escrow = round(escrow * (1 + r), 2)

    print(f"{Fore.GREEN}Generated housing")


def generate_food(p: Portfolio, accts: dict[str, int]) -> None:
    """Generate food payments.

    Args:
        p: Portfolio to edit
        accts: Account IDs to use
    """
    with p.begin_session() as s:
        categories = {cat.name: cat for cat in s.query(TransactionCategory).all()}

        acct_cc_0: Account = (
            s.query(Account).where(Account.id_ == accts["cc_0"]).scalar()
        )
        acct_cc_1: Account = (
            s.query(Account).where(Account.id_ == accts["cc_1"]).scalar()
        )
        grocery_stores: list[str] = [
            "Walmart",
            "Grocery Outlet",
            "Safeway",
            "Fred Meyer",
            "QFC",
            "Kroger",
        ]
        restaurants: list[str] = [
            "Pizza Palace",
            "Fine Dining R Us",
            "Italian Garden",
            "Chinese Kitchen",
            "Burgers and Beef",
            "Only Spam",
            "Thai 42",
            "Fajitas and More",
        ]

        # Never groceries on a Monday, Friday, or Saturday
        def adjust_date(date: datetime.date) -> datetime.date:
            if date.weekday() == 0:
                return date + datetime.timedelta(days=rng_int(1, 3))
            if date.weekday() == 4:
                return date - datetime.timedelta(days=rng_int(1, 3))
            if date.weekday() == 5:
                return date - datetime.timedelta(days=rng_int(2, 4))
            return date

        grocery_budget = 30
        restaurant_cost = 2
        restaurant_freq = 2
        restaurant_plates = 1

        for age in range(18, FINAL_AGE + 1):
            dates: list[datetime.date] = []
            year = BIRTH_YEAR + age
            for m in range(12):
                # Groceries twice a month
                date_0 = datetime.date(year, m + 1, 1)
                date_1 = datetime.date(year, m + 1, 15)
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

            acct = acct_cc_0
            if age > 32:
                # Open a new credit card
                acct = acct_cc_1

            for date in dates:
                store = rng_choice(grocery_stores)
                amount = round(grocery_budget / 2 * rng_normal(1, 0.2), 2)
                if amount > 0:
                    txn = Transaction(
                        account_id=acct.id_,
                        date=date,
                        amount=-amount,
                        statement=store,
                        locked=True,
                        linked=True,
                    )
                    txn_split = TransactionSplit(
                        parent=txn,
                        amount=txn.amount,
                        payee=store,
                        category_id=categories["Groceries"].id_,
                        description="Groceries",
                    )
                    s.add_all((txn, txn_split))

            # Go out to restaurants
            dates: list[datetime.date] = []
            for m in range(12):
                days = RNG.choice(range(1, 29), restaurant_freq, replace=False)
                for day in days:
                    date = datetime.date(BIRTH_YEAR + age, m + 1, day)
                    restaurant = rng_choice(restaurants)
                    total_exp = restaurant_cost * restaurant_plates
                    amount = round(total_exp * rng_normal(1, 0.2), 2)
                    txn = Transaction(
                        account_id=acct.id_,
                        date=date,
                        amount=-amount,
                        statement=restaurant,
                        locked=True,
                        linked=True,
                    )
                    txn_split = TransactionSplit(
                        parent=txn,
                        amount=txn.amount,
                        payee=restaurant,
                        category_id=categories["Restaurants"].id_,
                        description="Dining out",
                    )
                    s.add_all((txn, txn_split))

    print(f"{Fore.GREEN}Generated food")


def add_retirement(p: Portfolio, accts: dict[str, int], assets: dict[str, int]) -> None:
    """Perform retirement changeover.

    Args:
        p: Portfolio to edit
        accts: Account IDs to use
        assets: Asset IDs to use
    """
    with p.begin_session() as s:
        categories = {cat.name: cat for cat in s.query(TransactionCategory).all()}

        acct_checking: Account = (
            s.query(Account).where(Account.id_ == accts["checking"]).scalar()
        )
        acct_retirement: Account = (
            s.query(Account).where(Account.id_ == accts["retirement"]).scalar()
        )
        a_growth: Asset = s.query(Asset).where(Asset.id_ == assets["growth"]).scalar()
        a_value: Asset = s.query(Asset).where(Asset.id_ == assets["value"]).scalar()
        date_sell = next_month(
            datetime.date.fromordinal(acct_retirement.updated_on_ord or 0),
        )
        date_transfer = date_sell + datetime.timedelta(days=7)
        date_sell_ord = date_sell.toordinal()

        asset_qty = acct_retirement.get_asset_qty(date_sell_ord, date_sell_ord)

        def sell_asset(asset: Asset, qty: Decimal) -> None:
            """Add transactions to sell an Asset.

            Args:
                asset: Asset to sell
                qty: Quantity to sell
            """
            values = asset.get_value(date_sell_ord, date_sell_ord)
            amount = round(qty * values[0], 2)
            txn = Transaction(
                account_id=acct_retirement.id_,
                date=date_sell,
                amount=amount,
                statement="Security Sell",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["Securities Traded"].id_,
                asset_id=asset.id_,
                asset_quantity_unadjusted=-qty,
                payee="Monkey Bank Retirement",
                description=txn.statement,
            )
            s.add_all((txn, txn_split))

            txn = Transaction(
                account_id=acct_retirement.id_,
                date=date_transfer,
                amount=-amount,
                statement="Account Transfer",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["Transfers"].id_,
                payee="Monkey Bank Retirement",
                description=txn.statement,
            )
            s.add_all((txn, txn_split))

            txn = Transaction(
                account_id=acct_checking.id_,
                date=date_transfer,
                amount=amount,
                statement="Account Transfer",
                locked=True,
                linked=True,
            )
            txn_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["Transfers"].id_,
                payee="Monkey Bank Retirement",
                description=txn.statement,
            )
            s.add_all((txn, txn_split))

        sell_asset(a_growth, asset_qty[a_growth.id_][0])
        sell_asset(a_value, asset_qty[a_value.id_][0])
        s.flush()

        # Buy 1 share of AAPL on 2001-01-03 for $99.50 with a Y2K bonus
        # World was ending, so boss gave a bonus, sure... idk lore
        txn = Transaction(
            account_id=acct_retirement.id_,
            date=datetime.date(1999, 12, 31),
            amount=Decimal("99.50"),
            statement="Y2K Bonus",
            locked=True,
            linked=True,
        )
        txn_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=categories["Retirement Contributions"].id_,
            payee="My Favorite Boss",
            description=txn.statement,
        )
        s.add_all((txn, txn_split))
        txn = Transaction(
            account_id=acct_retirement.id_,
            date=datetime.date(2000, 1, 3),
            amount=Decimal("-99.50"),
            statement="Security Buy",
            locked=True,
            linked=True,
        )
        txn_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=categories["Securities Traded"].id_,
            asset_id=assets["Apple Inc."],
            asset_quantity_unadjusted=1,
            payee="Monkey Bank Retirement",
            description=txn.statement,
        )
        s.add_all((txn, txn_split))


def add_interest(p: Portfolio, acct_id: int) -> None:
    """Adds dividend/interest to Account.

    Args:
        p: Portfolio to edit
        acct_id: Account to generate for
    """
    with p.begin_session() as s:
        categories = {cat.name: cat for cat in s.query(TransactionCategory).all()}

        acct: Account = s.query(Account).where(Account.id_ == acct_id).scalar()
        date = datetime.date.fromordinal(acct.opened_on_ord or 0)
        if date is None:
            print(f"{Fore.RED}No transaction to generate interest on for {acct.name}")
            return
        end = birthday("self", FINAL_AGE)
        a_values_start = datetime.date(BIRTH_YEAR, 1, 1)
        a_values_end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
        a_values_start_ord = a_values_start.toordinal()
        a_values_end_ord = a_values_end.toordinal()
        values, _, _ = acct.get_value(a_values_start_ord, a_values_end_ord)

        total_interest = Decimal()

        while date < end:
            next_date = next_month(date)

            # Interest on the average balance
            i_start = (date - a_values_start).days
            i_end = (next_date - a_values_start).days
            avg_value = (
                Decimal(sum(values[i_start:i_end]) / (i_end - i_start)) + total_interest
            )

            if avg_value < 0:
                msg = (
                    f"Account {acct.name} was over-drafted by {avg_value:.2f} on {date}"
                )
                raise ValueError(msg)

            rate = INTEREST_RATES[date.year]
            interest: Decimal = round(rate / 12 * avg_value, 2)

            if interest > 0:
                txn = Transaction(
                    account_id=acct.id_,
                    date=next_date,
                    amount=interest,
                    statement="Interest",
                    locked=True,
                    linked=True,
                )
                txn_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    category_id=categories["Interest"].id_,
                    payee=acct.name,
                    description=txn.statement,
                )
                s.add_all((txn, txn_split))

            date = next_date
            total_interest += interest

        print(f"{Fore.GREEN}Added interest for {acct.name}")


def add_cc_payments(p: Portfolio, acct_id: int, acct_id_fund: int) -> None:
    """Adds credit card payments to Account.

    Args:
        p: Portfolio to edit
        acct_id: Account to generate for
        acct_id_fund: Account to withdraw funds from
    """
    with p.begin_session() as s:
        categories = {cat.name: cat for cat in s.query(TransactionCategory).all()}

        acct: Account = s.query(Account).where(Account.id_ == acct_id).scalar()
        acct_fund: Account = (
            s.query(Account).where(Account.id_ == acct_id_fund).scalar()
        )
        date = datetime.date.fromordinal(acct.opened_on_ord or 0)
        if date is None:
            print(
                f"{Fore.RED}No transaction to generate CC payments on for {acct.name}",
            )
            return
        end = birthday("self", FINAL_AGE)
        a_values_start = datetime.date(BIRTH_YEAR, 1, 1)
        a_values_end = datetime.date(BIRTH_YEAR + FINAL_AGE, 12, 31)
        a_values_start_ord = a_values_start.toordinal()
        a_values_end_ord = a_values_end.toordinal()
        values, _, _ = acct.get_value(a_values_start_ord, a_values_end_ord)

        total_payment = Decimal()

        while date < end:
            next_date = next_month(date)

            # Interest on the average balance
            i_end = (next_date - a_values_start).days
            if i_end >= len(values):
                break
            balance = round(values[i_end] + total_payment, 2)

            if balance < 0:
                due_date = next_date.replace(day=15)
                txn = Transaction(
                    account_id=acct.id_,
                    date=due_date,
                    amount=-balance,
                    statement="Credit Card Payment",
                    locked=True,
                    linked=True,
                )
                txn_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    category_id=categories["Credit Card Payments"].id_,
                    payee="Monkey Bank",
                    description=txn.statement,
                )
                s.add_all((txn, txn_split))

                txn = Transaction(
                    account_id=acct_fund.id_,
                    date=due_date,
                    amount=balance,
                    statement="Credit Card Payment",
                    locked=True,
                    linked=True,
                )
                txn_split = TransactionSplit(
                    parent=txn,
                    amount=txn.amount,
                    category_id=categories["Credit Card Payments"].id_,
                    payee="Monkey Bank",
                    description=txn.statement,
                )
                s.add_all((txn, txn_split))

            date = next_date
            total_payment += -balance

        print(f"{Fore.GREEN}Added CC payments for {acct.name}")


def main() -> None:
    """Main program entry."""
    start = time.perf_counter()
    p = Portfolio.create("portfolio.db")

    # Add words to the dictionary
    words = {
        "PB",
        "St.",
        "Ave.",
        "Blvd.",
        "S&P",
        "Italian",
        "Chinese",
        "Thai",
        "Kroger",
        "Safeway",
        "Fred",
        "Meyer",
        "QFC",
        "Walmart",
        "Barista",
        "Y2K",
    }
    with p.begin_session() as s:
        health_checks.Typos.ignore(s, words)

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

    values = {
        Account.id_to_uri(accts["real_estate"]),
    }
    with p.begin_session() as s:
        health_checks.EmptyFields.ignore(s, values)

    duration = time.perf_counter() - start
    print(f"{Fore.CYAN}Portfolio generation took {duration:.1f}s")

    commands.Summarize(p.path, None, include_all=False)


if __name__ == "__main__":
    main()
