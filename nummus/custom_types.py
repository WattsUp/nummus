"""Defines for custom types

Adds custom types to typing
"""

from typing import *  # pylint: disable=wildcard-import, unused-wildcard-import

import datetime
import decimal
import pathlib

from sqlalchemy import orm

Date = datetime.date
Dates = List[Date]
Ints = List[int]
IntOrStr = Union[int, str]
Paths = List[pathlib.Path]
Real = decimal.Decimal
Reals = List[Real]
Strings = List[str]

DictAny = Dict[str, Any]
DictDate = Dict[str, Date]
DictInt = Dict[str, int]
DictReal = Dict[str, Real]
DictReals = Dict[str, Reals]
DictStr = Dict[str, str]
DictStrings = Dict[str, Strings]
DictTuple = Dict[str, Tuple[Any, Any]]

DictIntReal = Dict[int, Real]
DictIntStr = Dict[int, str]

JSONVal = Union[str, Real, int, bool, "JSONArray", "JSONObj"]
JSONArray = List[JSONVal]
JSONObj = Dict[str, JSONVal]

StrToObj = Callable[[str], object]

ORMBool = orm.Mapped[bool]
ORMBoolOpt = orm.Mapped[Optional[bool]]
ORMDate = orm.Mapped[datetime.date]
ORMDateOpt = orm.Mapped[Optional[datetime.date]]
ORMInt = orm.Mapped[int]
ORMIntOpt = orm.Mapped[Optional[int]]
ORMStr = orm.Mapped[str]
ORMStrOpt = orm.Mapped[Optional[str]]
ORMReal = orm.Mapped[Real]
ORMRealOpt = orm.Mapped[Optional[Real]]
