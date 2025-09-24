from __future__ import annotations

import datetime
import functools
import random
import shutil
import string
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import override, TYPE_CHECKING

import flask
import pytest
import yfinance
from sqlalchemy import orm, pool

from nummus import global_config, sql, utils, web
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetSector,
    AssetSplit,
    AssetValuation,
    base_uri,
    BudgetAssignment,
    BudgetGroup,
    Label,
    LabelLink,
    Target,
    TargetPeriod,
    TargetType,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    USSector,
)
from nummus.portfolio import Portfolio
from tests.mock_yfinance import MockTicker

if TYPE_CHECKING:
    import time_machine


def id_func(val: object) -> str | None:
    if isinstance(val, datetime.date):
        return val.isoformat()
    if isinstance(val, Iterable | Decimal | Path):
        return str(val)
    if callable(val):
        return val.__name__
    return None


class RandomStringGenerator:

    @classmethod
    def __call__(cls, length: int = 20) -> str:
        return "".join(random.choice(string.ascii_letters) for _ in range(length))


@pytest.fixture(scope="session")
def rand_str_generator() -> RandomStringGenerator:
    """Return a random string generator.

    Returns:
        RandomStringGenerator

    """
    return RandomStringGenerator()


@pytest.fixture
def rand_str(rand_str_generator: RandomStringGenerator) -> str:
    """Return a random string.

    Returns:
        Random string with 20 characters

    """
    return rand_str_generator()


class RandomRealGenerator:

    @classmethod
    def __call__(
        cls,
        low: str | float | Decimal = 0.1,
        high: str | float | Decimal = 1,
        precision: int = 6,
    ) -> Decimal:
        d_low = round(Decimal(low), precision)
        d_high = round(Decimal(high), precision)
        x = random.uniform(float(d_low), float(d_high))
        return min(max(round(Decimal(x), precision), d_low), d_high)


@pytest.fixture(scope="session")
def rand_real_generator() -> RandomRealGenerator:
    """Return a random decimal generator.

    Returns:
        RandomRealGenerator

    """
    return RandomRealGenerator()


@pytest.fixture
def rand_real(rand_real_generator: RandomRealGenerator) -> Decimal:
    """Return a random decimal [0, 1].

    Returns:
        Real number between [0, 1] with 6 digits

    """
    return rand_real_generator()


@pytest.fixture(autouse=True)
def sql_engine_args() -> None:
    """Change all engines to NullPool so timing isn't an issue."""
    # Needed specifically for DatabaseIntegrity test
    sql._ENGINE_ARGS["poolclass"] = pool.NullPool


class EmptyPortfolioGenerator:

    def __init__(
        self,
        tmp_path_factory: pytest.TempPathFactory,
        rand_str_generator: RandomStringGenerator,
        key: str | None,
    ) -> None:
        # Create the portfolio once, then copy the file each time called
        self._path = tmp_path_factory.mktemp("data") / "portfolio.db"
        self._rand_str_generator = rand_str_generator
        self._key = key
        Portfolio.create(self._path, key)

    def __call__(self) -> tuple[Portfolio, str | None]:
        tmp_path = self._path.with_name(f"{self._rand_str_generator()}.db")
        shutil.copyfile(self._path, tmp_path)
        if self._key is not None:
            # copy salt too
            shutil.copyfile(
                self._path.with_suffix(".nacl"),
                tmp_path.with_suffix(".nacl"),
            )
        return Portfolio(tmp_path, self._key), self._key


@pytest.fixture(scope="session")
def empty_portfolio_generator(
    tmp_path_factory: pytest.TempPathFactory,
    rand_str_generator: RandomStringGenerator,
) -> EmptyPortfolioGenerator:
    """Return an empty portfolio generator.

    Returns:
        EmptyPortfolio generator

    """
    return EmptyPortfolioGenerator(tmp_path_factory, rand_str_generator, None)


@pytest.fixture(scope="session")
def empty_portfolio_encrypted_generator(
    tmp_path_factory: pytest.TempPathFactory,
    rand_str_generator: RandomStringGenerator,
) -> EmptyPortfolioGenerator:
    """Return an empty portfolio generator.

    Returns:
        EmptyPortfolio generator

    """
    return EmptyPortfolioGenerator(
        tmp_path_factory,
        rand_str_generator,
        rand_str_generator(),
    )


@pytest.fixture
def empty_portfolio(empty_portfolio_generator: EmptyPortfolioGenerator) -> Portfolio:
    """Return an empty portfolio.

    Returns:
        Portfolio

    """
    return empty_portfolio_generator()[0]


@pytest.fixture
def empty_portfolio_encrypted(
    empty_portfolio_encrypted_generator: EmptyPortfolioGenerator,
) -> tuple[Portfolio, str]:
    """Return an empty encrypted portfolio.

    Returns:
        tuple(Portfolio, key)

    """
    p, key = empty_portfolio_encrypted_generator()
    assert key is not None
    return p, key


@pytest.fixture
def session(empty_portfolio: Portfolio) -> orm.Session:
    """Create SQL session.

    Returns:
        Session generator

    """
    return orm.Session(sql.get_engine(empty_portfolio.path, None))


@pytest.fixture(autouse=True)
def uri_cipher() -> None:
    """Generate a URI cipher."""
    base_uri._CIPHER = base_uri.Cipher.generate()


@pytest.fixture(autouse=True)
def clear_config_cache() -> None:
    """Clear global config cache."""
    global_config._CACHE.clear()


@pytest.fixture(scope="session")
def today() -> datetime.date:
    """Get today's date.

    Returns:
        today datetime.date

    """
    return datetime.datetime.now(datetime.UTC).date()


@pytest.fixture(scope="session")
def today_ord(today: datetime.date) -> int:
    """Get today's date ordinal.

    Returns:
        today as ordinal

    """
    return today.toordinal()


@pytest.fixture(scope="session")
def tomorrow(today: datetime.date) -> datetime.date:
    """Get tomorrow's date.

    Returns:
        tomorrow datetime.date

    """
    return today + datetime.timedelta(days=1)


@pytest.fixture(scope="session")
def tomorrow_ord(tomorrow: datetime.date) -> int:
    """Get tomorrow's date ordinal.

    Returns:
        tomorrow as ordinal

    """
    return tomorrow.toordinal()


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
def account(session: orm.Session, rand_str_generator: RandomStringGenerator) -> Account:
    """Create an Account.

    Returns:
        Checking Account, not closed, budgeted

    """
    acct = Account(
        name="Monkey bank checking",
        institution="Monkey bank",
        category=AccountCategory.CASH,
        closed=False,
        budgeted=True,
        number=rand_str_generator(),
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
        # capital case for HTML header check
        name="Monkey bank savings",
        institution="Monkey bank",
        category=AccountCategory.CASH,
        closed=False,
        budgeted=False,
        number="1234",
    )
    session.add(acct)
    session.commit()
    return acct


@pytest.fixture
def account_investments(session: orm.Session) -> Account:
    """Create an Account.

    Returns:
        Investments Account, not closed, not budgeted

    """
    acct = Account(
        name="Monkey bank investments",
        institution="Monkey bank",
        category=AccountCategory.INVESTMENT,
        closed=False,
        budgeted=False,
        number="1235",
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
def labels(session: orm.Session) -> dict[str, int]:
    """Get labels.

    Returns:
        dict{name: label id}

    """
    labels = {"engineer", "fruit", "apartments 4 U"}
    session.add_all(Label(name=name) for name in labels)
    session.commit()
    return {name: id_ for id_, name in Label.map_name(session).items()}


@pytest.fixture
def asset(session: orm.Session) -> Asset:
    """Create an stock Asset.

    Returns:
        Banana Incorporated, STOCKS

    """
    asset = Asset(
        name="Banana incorporated",
        category=AssetCategory.STOCKS,
        ticker="BANANA",
        description="Banana Incorporated makes bananas",
    )
    session.add(asset)
    session.commit()
    return asset


@pytest.fixture
def asset_etf(session: orm.Session) -> Asset:
    """Create an ETF stock Asset.

    Returns:
        Banana ETF, STOCKS

    """
    asset = Asset(
        name="Banana ETF",
        category=AssetCategory.STOCKS,
        ticker="BANANA_ETF",
        description="Banana ETF",
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
    v = AssetValuation(asset_id=asset.id_, date_ord=today_ord, value=2)
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
def asset_sectors(
    session: orm.Session,
    asset: Asset,
) -> tuple[AssetSector, AssetSector]:
    """Create two AssetSectors.

    Returns:
        20% BASIC_MATERIALS, 80% TECHNOLOGY

    """
    s0 = AssetSector(
        asset_id=asset.id_,
        sector=USSector.BASIC_MATERIALS,
        weight=Decimal("0.2"),
    )
    s1 = AssetSector(
        asset_id=asset.id_,
        sector=USSector.TECHNOLOGY,
        weight=Decimal("0.8"),
    )
    session.add_all((s0, s1))
    session.commit()
    return s0, s1


@pytest.fixture
def budget_group(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
) -> BudgetGroup:
    """Create a BudgetGroup.

    Returns:
        BudgetGroup with position 0

    """
    g = BudgetGroup(name=rand_str_generator(), position=0)
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
    labels: dict[str, int],
) -> list[Transaction]:
    # Fund account on 3 days before today
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=3),
        amount=100,
        statement=rand_str_generator(),
        payee="Monkey Bank",
        cleared=True,
    )
    t_split_0 = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        category_id=categories["other income"],
    )
    session.add_all((txn, t_split_0))

    # Buy asset on 2 days before today
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=2),
        amount=-10,
        statement=rand_str_generator(),
        payee="Monkey Bank",
        cleared=True,
    )
    t_split_1 = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        asset_id=asset.id_,
        asset_quantity_unadjusted=10,
        category_id=categories["securities traded"],
    )
    session.add_all((txn, t_split_1))

    # Sell asset tomorrow
    txn = Transaction(
        account_id=account.id_,
        date=today + datetime.timedelta(days=1),
        amount=50,
        statement=rand_str_generator(),
        payee="Monkey Bank",
        cleared=True,
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
        payee="Monkey Bank",
        cleared=True,
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

    session.add(LabelLink(label_id=labels["engineer"], t_split_id=t_split_0.id_))
    session.add(LabelLink(label_id=labels["engineer"], t_split_id=t_split_1.id_))
    session.commit()
    return session.query(Transaction).order_by(Transaction.date_ord).all()


@pytest.fixture
def transactions_spending(
    today: datetime.date,
    rand_str_generator: RandomStringGenerator,
    session: orm.Session,
    account: Account,
    account_savings: Account,
    asset: Asset,
    categories: dict[str, int],
    labels: dict[str, int],
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

    t_split_id = (
        session.query(TransactionSplit.id_)
        .where(TransactionSplit.category_id == categories["rent"])
        .one()[0]
    )
    session.add(LabelLink(label_id=labels["apartments 4 U"], t_split_id=t_split_id))
    session.commit()

    return session.query(Transaction).order_by(Transaction.date_ord).all()


@pytest.fixture(autouse=True)
def mock_yfinance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock yfinance with MockTicker."""
    monkeypatch.setattr(yfinance, "Ticker", MockTicker)


@pytest.fixture(scope="session")
def data_path() -> Path:
    """Get path to data directory.

    Returns:
        Path to test data

    """
    return Path(__file__).with_name("data")


@pytest.fixture
def utc() -> datetime.datetime:
    """Get current time in UTC.

    Returns:
        datetime

    """
    return datetime.datetime.now(datetime.UTC)


@pytest.fixture
def utc_frozen(
    utc: datetime.datetime,
    time_machine: time_machine.TimeMachineFixture,
) -> datetime.datetime:
    """Get current time in UTC and freeze it.

    Returns:
        datetime

    """
    time_machine.move_to(utc, tick=False)
    return utc


class FlaskAppGenerator:

    def __init__(
        self,
        generator: EmptyPortfolioGenerator,
    ) -> None:
        class MockExtension(web.FlaskExtension):
            @override
            @classmethod
            def _open_portfolio(cls, config: flask.Config) -> Portfolio:
                _ = config
                return generator()[0]

        self._ext = MockExtension()

        path_root = Path(web.__file__).parent.resolve()
        self._flask_app = flask.Flask(__name__, root_path=str(path_root))
        self._flask_app.debug = True
        self._ext.init_app(self._flask_app)

        # Needed by test_change_redirect
        self._flask_app.add_url_rule(
            "/redirect",
            "redirect",
            functools.partial(flask.redirect, "/"),
        )

    def __call__(self, p: Portfolio) -> flask.Flask:
        # Just swap out portfolio reference, quicker than making a new app
        # Since all use the same empty_portfolio_generator,
        # the SECRET_KEY will be identical
        web.ext._portfolio = p
        return self._flask_app


@pytest.fixture(scope="session")
def flask_app_generator(
    empty_portfolio_generator: EmptyPortfolioGenerator,
) -> FlaskAppGenerator:
    """Return an flask app generator.

    Returns:
        FlaskAppGenerator

    """
    return FlaskAppGenerator(empty_portfolio_generator)


@pytest.fixture(scope="session")
def flask_app_encrypted_generator(
    empty_portfolio_encrypted_generator: EmptyPortfolioGenerator,
) -> FlaskAppGenerator:
    """Return an flask app generator.

    Returns:
        FlaskAppGenerator

    """
    return FlaskAppGenerator(empty_portfolio_encrypted_generator)


@pytest.fixture
def flask_app(
    flask_app_generator: FlaskAppGenerator,
    empty_portfolio: Portfolio,
) -> flask.Flask:
    """Create flask app for EmptyPortfolio.

    Returns:
        Flask

    """
    return flask_app_generator(empty_portfolio)


@pytest.fixture
def flask_app_encrypted(
    flask_app_encrypted_generator: FlaskAppGenerator,
    empty_portfolio_encrypted: tuple[Portfolio, str],
) -> flask.Flask:
    """Create flask app for EmptyPortfolio.

    Returns:
        Flask

    """
    return flask_app_encrypted_generator(empty_portfolio_encrypted[0])


@pytest.fixture
def budget_assignments(
    month: datetime.date,
    month_ord: int,
    session: orm.Session,
    categories: dict[str, int],
) -> list[BudgetAssignment]:
    """Create BudgetAssignments.

    Returns:
        [
            BudgetAssignment this month for $50 of groceries,
            BudgetAssignment this month for $100 of emergency fund,
            BudgetAssignment next month for $2000 of rent,
        ]

    """
    b = BudgetAssignment(
        month_ord=month_ord,
        amount=Decimal(50),
        category_id=categories["groceries"],
    )
    session.add(b)
    b = BudgetAssignment(
        month_ord=month_ord,
        amount=Decimal(100),
        category_id=categories["emergency fund"],
    )
    session.add(b)
    b = BudgetAssignment(
        month_ord=utils.date_add_months(month, 1).toordinal(),
        amount=Decimal(2000),
        category_id=categories["rent"],
    )
    session.add(b)
    session.commit()
    return list(session.query(BudgetAssignment).all())


@pytest.fixture
def budget_target(
    session: orm.Session,
    categories: dict[str, int],
) -> Target:
    """Create a budget target.

    Returns:
        Target for Emergency Fund, $1000, no due date

    """
    target = Target(
        category_id=categories["emergency fund"],
        amount=Decimal(1000),
        type_=TargetType.BALANCE,
        period=TargetPeriod.ONCE,
        repeat_every=0,
    )
    session.add(target)
    session.commit()
    return target
