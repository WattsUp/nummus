from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus import utils
from nummus.controllers import base
from nummus.models import Account, AssetValuation
from tests import conftest

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import orm


def test_find(session: orm.Session, account: Account) -> None:
    assert base.find(session, Account, account.uri) == account


def test_find_404(session: orm.Session) -> None:
    with pytest.raises(exc.http.NotFound):
        base.find(session, Account, Account.id_to_uri(0))


def test_find_400(session: orm.Session) -> None:
    with pytest.raises(exc.http.BadRequest):
        base.find(session, Account, "fake")


@pytest.mark.parametrize(
    ("period", "months"),
    [
        ("1m", -1),
        ("6m", -6),
        ("1yr", -12),
        ("max", None),
    ],
)
def test_parse_period(today: datetime.date, period: str, months: int | None) -> None:
    start = None if months is None else utils.date_add_months(today, months)
    assert base.parse_period(period) == (start, today)


def test_parse_period_ytd(today: datetime.date) -> None:
    start = datetime.date(today.year, 1, 1)
    assert base.parse_period("ytd") == (start, today)


def test_parse_period_400() -> None:
    with pytest.raises(exc.http.BadRequest):
        base.parse_period("")


def test_date_labels_days(today: datetime.date) -> None:
    start = today - datetime.timedelta(days=utils.DAYS_IN_WEEK)
    result = base.date_labels(start.toordinal(), today.toordinal())
    assert result.labels[0] == start.isoformat()
    assert result.labels[-1] == today.isoformat()
    assert result.mode == "days"


@pytest.mark.parametrize(
    ("months", "mode"),
    [
        (-1, "weeks"),
        (-3, "months"),
        (-24, "years"),
    ],
)
def test_date_labels(today: datetime.date, months: int, mode: str) -> None:
    start = utils.date_add_months(today, months)
    result = base.date_labels(start.toordinal(), today.toordinal())
    assert result.labels[0] == start.isoformat()
    assert result.labels[-1] == today.isoformat()
    assert result.mode == mode


def test_ctx_to_json() -> None:
    ctx: dict[str, object] = {"number": Decimal("1234.1234")}
    assert base.ctx_to_json(ctx) == '{"number":1234.12}'


def test_ctx_to_json_unknown_type() -> None:
    class Fake:
        pass

    with pytest.raises(TypeError):
        base.ctx_to_json({"fake": Fake()})


@pytest.mark.parametrize(
    "func",
    [
        base.validate_string,
        base.validate_real,
        base.validate_int,
        base.validate_date,
    ],
    ids=conftest.id_func,
)
def test_validate_required(func: Callable) -> None:
    assert func("", is_required=True) == "Required"


@pytest.mark.parametrize("s", ["", "abc"])
def test_validate_string(s: str) -> None:
    assert not base.validate_string(s)


def test_validate_string_short() -> None:
    assert base.validate_string("a", check_length=True) == "2 characters required"


def test_validate_string_no_session() -> None:
    with pytest.raises(TypeError):
        base.validate_string("abc", no_duplicates=Account.name)


def test_validate_string_duplicate(session: orm.Session, account: Account) -> None:
    err = base.validate_string(
        account.name,
        session=session,
        no_duplicates=Account.name,
    )
    assert err == "Must be unique"


def test_validate_string_duplicate_self(session: orm.Session, account: Account) -> None:
    err = base.validate_string(
        account.name,
        session=session,
        no_duplicates=Account.name,
        no_duplicate_wheres=[Account.id_ != account.id_],
    )
    assert not err


@pytest.mark.parametrize("s", ["", "2025-01-01"])
@pytest.mark.parametrize("max_future", [7, 0, None])
def test_validate_date(s: str, max_future: int | None) -> None:
    assert not base.validate_date(s, max_future=max_future)


@pytest.mark.parametrize(
    "func",
    [
        base.validate_real,
        base.validate_int,
        base.validate_date,
    ],
    ids=conftest.id_func,
)
def test_validate_unable_to_parse(func: Callable) -> None:
    assert func("a") == "Unable to parse"


@pytest.mark.parametrize(
    ("max_future", "target"),
    [
        (7, "Only up to 7 days in advance"),
        (0, "Cannot be in the future"),
        (None, ""),
    ],
)
def test_validate_date_future(max_future: int | None, target: str) -> None:
    assert base.validate_date("2190-01-01", max_future=max_future) == target


def test_validate_date_duplicate(
    session: orm.Session,
    asset_valuation: AssetValuation,
) -> None:
    err = base.validate_date(
        asset_valuation.date.isoformat(),
        session=session,
        no_duplicates=AssetValuation.date_ord,
    )
    assert err == "Must be unique"


@pytest.mark.parametrize("s", ["0.1", "1.0", "-1*(-2)"])
@pytest.mark.parametrize("is_positive", [True, False])
def test_validate_real(s: str, is_positive: bool) -> None:
    assert not base.validate_real(s, is_positive=is_positive)


@pytest.mark.parametrize("s", ["0", "-1.0", "-1*2"])
def test_validate_real_not_positive(s: str) -> None:
    assert base.validate_real(s, is_positive=True) == "Must be positive"


@pytest.mark.parametrize("is_positive", [True, False])
def test_validate_int(is_positive: bool) -> None:
    assert not base.validate_int("1", is_positive=is_positive)


@pytest.mark.parametrize("s", ["0", "-1"])
def test_validate_int_not_positive(s: str) -> None:
    assert base.validate_int(s, is_positive=True) == "Must be positive"
