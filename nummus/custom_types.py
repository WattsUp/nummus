"""Defines for custom types.

Adds custom types to typing
"""
from __future__ import annotations

import datetime
import decimal
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Union

from sqlalchemy import orm

_ = Sequence

Date = datetime.date
Dates = list[Date]
Ints = list[int]
Paths = list[Path]
Real = decimal.Decimal
Reals = list[Real]
Strings = list[str]
Routes = dict[str, tuple[Callable, Strings]]

DictAny = dict[str, Any]
DictDate = dict[str, Date]
DictInt = dict[str, int]
DictReal = dict[str, Real]
DictReals = dict[str, Reals]
DictStr = dict[str, str]
DictStrings = dict[str, Strings]
DictTuple = dict[str, tuple[Any, Any]]

DictIntReal = dict[int, Real]
DictIntReals = dict[int, Reals]
DictIntStr = dict[int, str]

JSONVal = Union[str, Real, int, bool, "JSONArray", "JSONObj"]
JSONArray = list[JSONVal]
JSONObj = dict[str, JSONVal]

StrToObj = Callable[[str], object]

ORMBool = orm.Mapped[bool]
ORMBoolOpt = orm.Mapped[bool | None]
ORMDate = orm.Mapped[datetime.date]
ORMDateOpt = orm.Mapped[datetime.date | None]
ORMInt = orm.Mapped[int]
ORMIntOpt = orm.Mapped[int | None]
ORMStr = orm.Mapped[str]
ORMStrOpt = orm.Mapped[str | None]
ORMReal = orm.Mapped[Real]
ORMRealOpt = orm.Mapped[Real | None]
