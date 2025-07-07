from __future__ import annotations

import datetime
import random
import shutil
import string
from collections.abc import Iterable
from decimal import Decimal

import pytest
import yfinance
from sqlalchemy import orm, pool

from nummus import global_config, sql
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetSplit,
    AssetValuation,
    base_uri,
    BudgetGroup,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from nummus.portfolio import Portfolio
from tests.mock_yfinance import MockTicker


def id_func(val: object) -> str | None:
    if isinstance(val, datetime.date):
        return val.isoformat()
    if isinstance(val, Iterable):
        return str(val)
    return None


class RandomStringGenerator:

    @classmethod
    def __call__(cls, length: int = 20) -> str:
        return "".join(random.choice(string.ascii_letters) for _ in range(length))


@pytest.fixture(scope="session")
def rand_str_generator() -> RandomStringGenerator:
    """Returns a random string generator.

    Returns:
        RandomStringGenerator
    """
    return RandomStringGenerator()


@pytest.fixture
def rand_str(rand_str_generator: RandomStringGenerator) -> str:
    """Returns a random string.

    Returns:
        Random string with 20 characters
    """
    return rand_str_generator()


class RandomRealGenerator:

    @classmethod
    def __call__(
        cls,
        low: str | float | Decimal = 0,
        high: str | float | Decimal = 1,
        precision: int = 6,
    ) -> Decimal:
        d_low = round(Decimal(low), precision)
        d_high = round(Decimal(high), precision)
        x = random.uniform(float(d_low), float(d_high))
        return min(max(round(Decimal(x), precision), d_low), d_high)


@pytest.fixture(scope="session")
def rand_real_generator() -> RandomRealGenerator:
    """Returns a random decimal generator.

    Returns:
        RandomRealGenerator
    """
    return RandomRealGenerator()


@pytest.fixture
def rand_real(rand_real_generator: RandomRealGenerator) -> Decimal:
    """Returns a random decimal [0, 1].

    Returns:
        Real number between [0, 1] with 6 digits
    """
    return rand_real_generator()


# TODO (WattsUp): Maybe not needed?
@pytest.fixture
def sql_engine_args() -> None:
    """Change all engines to NullPool so timing isn't an issue."""
    sql._ENGINE_ARGS["poolclass"] = pool.NullPool  # noqa: SLF001


class EmptyPortfolioGenerator:

    def __init__(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        # Create the portfolio once, then copy the file each time called
        self._path = tmp_path_factory.mktemp("data") / "portfolio.db"
        Portfolio.create(self._path)

    def __call__(self) -> Portfolio:
        tmp_path = self._path.with_name(f"{RandomStringGenerator()}.db")
        shutil.copyfile(self._path, tmp_path)
        return Portfolio(tmp_path, None)


@pytest.fixture(scope="session")
def empty_portfolio_generator(
    tmp_path_factory: pytest.TempPathFactory,
) -> EmptyPortfolioGenerator:
    """Returns an empty portfolio generator.

    Returns:
        EmptyPortfolio generator
    """
    return EmptyPortfolioGenerator(tmp_path_factory)


@pytest.fixture
def empty_portfolio(empty_portfolio_generator: EmptyPortfolioGenerator) -> Portfolio:
    """Returns an empty portfolio.

    Returns:
        Portfolio
    """
    return empty_portfolio_generator()


@pytest.fixture
def session(empty_portfolio_generator: EmptyPortfolioGenerator) -> orm.Session:
    """Create SQL session.

    Returns:
        Session generator
    """
    return orm.Session(sql.get_engine(empty_portfolio_generator().path, None))


@pytest.fixture(autouse=True)
def uri_cipher() -> None:
    """Generate a URI cipher."""
    base_uri._CIPHER = base_uri.Cipher.generate()  # noqa: SLF001


@pytest.fixture(autouse=True)
def clear_config_cache() -> None:
    """Clear global config cache."""
    global_config._CACHE.clear()  # noqa: SLF001


@pytest.fixture(scope="session")
def today() -> datetime.date:
    """Get today's date.

    Returns:
        today datetime.date
    """
    return datetime.datetime.now().astimezone().date()


@pytest.fixture(scope="session")
def today_ord(today: datetime.date) -> int:
    """Get today's date ordinal.

    Returns:
        today as ordinal
    """
    return today.toordinal()


@pytest.fixture(scope="session")
def month(today: datetime.date) -> datetime.date:
    """Get today's month.

    Returns:
        month datetime.date
    """
    return today.replace(day=1)


@pytest.fixture(scope="session")
def month_ord(month: datetime.date) -> int:
    """Get today's month ordinal.

    Returns:
        month as ordinal
    """
    return month.toordinal()


@pytest.fixture
def account(session: orm.Session) -> Account:
    """Create an Account.

    Returns:
        Checking Account, not closed, budgeted
    """
    acct = Account(
        name="Monkey Bank Checking",
        institution="Monkey Bank",
        category=AccountCategory.CASH,
        closed=False,
        budgeted=True,
    )
    session.add(acct)
    session.commit()
    return acct


@pytest.fixture
def account_savings(session: orm.Session) -> Account:
    """Create an Account.

    Returns:
        Savings Account, not closed, not budgeted
    """
    acct = Account(
        name="Monkey Bank Savings",
        institution="Monkey Bank",
        category=AccountCategory.CASH,
        closed=False,
        budgeted=False,
    )
    session.add(acct)
    session.commit()
    return acct


@pytest.fixture
def categories(session: orm.Session) -> dict[str, int]:
    """Get default categories.

    Returns:
        dict{name: category id}
    """
    return {name: id_ for id_, name in TransactionCategory.map_name(session).items()}


@pytest.fixture
def asset(session: orm.Session) -> Asset:
    """Create an stock Asset.

    Returns:
        Banana Inc., STOCKS
    """
    asset = Asset(
        name="Banana Inc.",
        category=AssetCategory.STOCKS,
        ticker="BANANA",
    )
    session.add(asset)
    session.commit()
    return asset


@pytest.fixture
def asset_valuation(
    session: orm.Session,
    asset: Asset,
    today_ord: int,
) -> AssetValuation:
    """Create an AssetValuation.

    Returns:
        AssetValuation on today of $10
    """
    v = AssetValuation(asset_id=asset.id_, date_ord=today_ord, value=10)
    session.add(v)
    session.commit()
    return v


@pytest.fixture
def asset_split(
    session: orm.Session,
    asset: Asset,
    today_ord: int,
) -> AssetSplit:
    """Create an AssetSplit.

    Returns:
        AssetSplit on today of 10:1
    """
    v = AssetSplit(asset_id=asset.id_, date_ord=today_ord, multiplier=10)
    session.add(v)
    session.commit()
    return v


@pytest.fixture
def budget_group(session: orm.Session, rand_str: str) -> BudgetGroup:
    """Create a BudgetGroup.

    Returns:
        BudgetGroup with position 0
    """
    g = BudgetGroup(name=rand_str, position=0)
    session.add(g)
    session.commit()
    return g


@pytest.fixture
def transactions(
    today: datetime.date,
    rand_str_generator: RandomStringGenerator,
    session: orm.Session,
    account: Account,
    asset: Asset,
    categories: dict[str, int],
) -> list[Transaction]:
    # Fund account on 3 days before today
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=3),
        amount=100,
        statement=rand_str_generator(),
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        category_id=categories["other income"],
        tag="engineer",
    )
    session.add_all((txn, t_split))

    # Buy asset on 2 days before today
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=2),
        amount=-10,
        statement=rand_str_generator(),
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        asset_id=asset.id_,
        asset_quantity_unadjusted=10,
        category_id=categories["securities traded"],
        tag="engineer",
    )
    session.add_all((txn, t_split))

    # Sell asset tomorrow
    txn = Transaction(
        account_id=account.id_,
        date=today + datetime.timedelta(days=1),
        amount=50,
        statement=rand_str_generator(),
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        asset_id=asset.id_,
        asset_quantity_unadjusted=-5,
        category_id=categories["securities traded"],
        memo="for rent",
    )
    session.add_all((txn, t_split))

    # Sell remaining next week
    txn = Transaction(
        account_id=account.id_,
        date=today + datetime.timedelta(days=7),
        amount=50,
        statement=rand_str_generator(),
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        asset_id=asset.id_,
        asset_quantity_unadjusted=-5,
        category_id=categories["securities traded"],
        memo="rent transfer",
    )
    session.add_all((txn, t_split))

    session.commit()
    return session.query(Transaction).all()


@pytest.fixture
def transactions_spending(
    today: datetime.date,
    rand_str_generator: RandomStringGenerator,
    session: orm.Session,
    account: Account,
    account_savings: Account,
    asset: Asset,
    categories: dict[str, int],
) -> list[Transaction]:
    statement_income = rand_str_generator()
    statement_groceries = rand_str_generator()
    statement_rent = rand_str_generator()
    specs = [
        (account, Decimal(100), statement_income, "other income"),
        (account, Decimal(100), statement_income, "other income"),
        (account, Decimal(120), statement_income, "other income"),
        (account, Decimal(-10), statement_groceries, "groceries"),
        (account, Decimal(-10), statement_groceries + " other word", "groceries"),
        (account, Decimal(-50), statement_rent, "rent"),
        (account, Decimal(1000), rand_str_generator(), "other income"),
        (account_savings, Decimal(100), statement_income, "other income"),
    ]
    for acct, amount, statement, category in specs:
        txn = Transaction(
            account_id=acct.id_,
            date=today,
            amount=amount,
            statement=statement,
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=categories[category],
        )
        session.add_all((txn, t_split))

    txn = Transaction(
        account_id=account.id_,
        date=today,
        amount=-50,
        statement=statement_rent + " other word",
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        asset_id=asset.id_,
        asset_quantity_unadjusted=10,
        category_id=categories["securities traded"],
    )
    session.add_all((txn, t_split))

    session.commit()
    return session.query(Transaction).all()


@pytest.fixture(autouse=True)
def mock_yfinance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock yfinance with MockTicker."""
    monkeypatch.setattr(yfinance, "Ticker", MockTicker)
