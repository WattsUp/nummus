"""Transaction API Controller
"""

import uuid

import connexion
from sqlalchemy import orm

from nummus.models import Account, Asset, Transaction


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
  try:
    account_uuid = str(uuid.UUID(query))
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Badly formed UUID: {query}") from e
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
  try:
    asset_uuid = str(uuid.UUID(query))
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Badly formed UUID: {query}") from e
  a = s.query(Asset).where(Asset.uuid == asset_uuid).first()
  if a is None:
    raise connexion.exceptions.ProblemException(
        status=404, detail=f"Asset {asset_uuid} not found in Portfolio")
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
  try:
    transaction_uuid = str(uuid.UUID(query))
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Badly formed UUID: {query}") from e
  t = s.query(Transaction).where(Transaction.uuid == transaction_uuid).first()
  if t is None:
    raise connexion.exceptions.ProblemException(
        status=404,
        detail=f"Transaction{transaction_uuid} not found in Portfolio")
  return t
