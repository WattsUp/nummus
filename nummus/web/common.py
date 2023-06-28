"""Transaction API Controller
"""

from typing import Type

import datetime
import uuid

import connexion
from sqlalchemy import orm

from nummus.models import (Account, Asset, BaseEnum, Budget, Transaction)


def find_account(s: orm.Session, query: str) -> Account:
  """Find the matching Account by UUID

  Args:
    s: SQL session to search
    query: Account UUID to find, will clean first

  Returns:
    Account

  Raises:
    BadRequestProblem if UUID is malformed
    ProblemException if Account is not found
  """
  # Clean
  account_uuid = str(parse_uuid(query))
  a = s.query(Account).where(Account.uuid == account_uuid).first()
  if a is None:
    raise connexion.exceptions.ProblemException(
        status=404, detail=f"Account {account_uuid} not found in Portfolio")
  return a


def find_asset(s: orm.Session, query: str) -> Asset:
  """Find the matching Asset by UUID

  Args:
    s: SQL session to search
    query: Asset UUID to find, will clean first

  Returns:
    Asset

  Raises:
    BadRequestProblem if UUID is malformed
    ProblemException if Asset is not found
  """
  # Clean
  asset_uuid = str(parse_uuid(query))
  a = s.query(Asset).where(Asset.uuid == asset_uuid).first()
  if a is None:
    raise connexion.exceptions.ProblemException(
        status=404, detail=f"Asset {asset_uuid} not found in Portfolio")
  return a


def find_budget(s: orm.Session, query: str) -> Budget:
  """Find the matching Budget by UUID

  Args:
    s: SQL session to search
    query: Budget UUID to find, will clean first

  Returns:
    Budget

  Raises:
    BadRequestProblem if UUID is malformed
    ProblemException if Budget is not found
  """
  # Clean
  asset_uuid = str(parse_uuid(query))
  a = s.query(Budget).where(Budget.uuid == asset_uuid).first()
  if a is None:
    raise connexion.exceptions.ProblemException(
        status=404, detail=f"Budget {asset_uuid} not found in Portfolio")
  return a


def find_transaction(s: orm.Session, query: str) -> Transaction:
  """Find the matching Transaction by UUID

  Args:
    s: SQL session to search
    query: Transaction UUID to find, will clean first

  Returns:
    Transaction

  Raises:
    BadRequestProblem if UUID is malformed
    ProblemException if Transaction is not found
  """
  # Clean
  transaction_uuid = str(parse_uuid(query))
  t = s.query(Transaction).where(Transaction.uuid == transaction_uuid).first()
  if t is None:
    raise connexion.exceptions.ProblemException(
        status=404,
        detail=f"Transaction{transaction_uuid} not found in Portfolio")
  return t


def parse_uuid(s: str) -> uuid.UUID:
  """Parse a string to UUID

  Args:
    s: String to parse

  Returns:
    Parsed UUID

  Raises:
    BadRequestProblem if UUID is malformed
  """
  try:
    return uuid.UUID(s)
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Badly formed UUID: {s}, {e}") from e


def parse_date(s: str) -> datetime.date:
  """Parse a string in ISO format to date

  Args:
    s: String to parse

  Returns:
    Parsed date

  Raises:
    BadRequestProblem if date is malformed
  """
  try:
    return datetime.date.fromisoformat(s)
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Badly formed date: {s}, {e}") from e


def parse_enum(s: str, cls: Type[BaseEnum]) -> BaseEnum:
  """Parse a string in an enum

  Args:
    s: String to parse

  Returns:
    Parsed enum

  Raises:
    BadRequestProblem if enum is unknown
  """
  try:
    return cls.parse(s)
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Unknown {cls.__name__}: {s}, {e}") from e
