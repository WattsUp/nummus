"""Defines for custom types.

Adds custom types to typing
"""

import datetime
import decimal
import pathlib
import typing as t
from typing import *  # noqa: F403

from sqlalchemy import orm

Date = datetime.date
Dates = t.List[Date]
Ints = t.List[int]
IntOrStr = t.Union[int, str]
Paths = t.List[pathlib.Path]
Real = decimal.Decimal
Reals = t.List[Real]
Strings = t.List[str]

DictAny = t.Dict[str, t.Any]
DictDate = t.Dict[str, Date]
DictInt = t.Dict[str, int]
DictReal = t.Dict[str, Real]
DictReals = t.Dict[str, Reals]
DictStr = t.Dict[str, str]
DictStrings = t.Dict[str, Strings]
DictTuple = t.Dict[str, t.Tuple[t.Any, t.Any]]

DictIntReal = t.Dict[int, Real]
DictIntReals = t.Dict[int, Reals]
DictIntStr = t.Dict[int, str]

JSONVal = t.Union[str, Real, int, bool, "JSONArray", "JSONObj"]
JSONArray = t.List[JSONVal]
JSONObj = t.Dict[str, JSONVal]

StrToObj = t.Callable[[str], object]

ORMBool = orm.Mapped[bool]
ORMBoolOpt = orm.Mapped[t.Optional[bool]]
ORMDate = orm.Mapped[datetime.date]
ORMDateOpt = orm.Mapped[t.Optional[datetime.date]]
ORMInt = orm.Mapped[int]
ORMIntOpt = orm.Mapped[t.Optional[int]]
ORMStr = orm.Mapped[str]
ORMStrOpt = orm.Mapped[t.Optional[str]]
ORMReal = orm.Mapped[Real]
ORMRealOpt = orm.Mapped[t.Optional[Real]]
