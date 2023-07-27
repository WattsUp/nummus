"""Base importer interfaces
"""

import typing as t

from abc import ABC, abstractmethod
import datetime
from decimal import Decimal

TransactionDict = t.Dict[str, t.Union[str, Decimal, datetime.date, object]]


class TransactionImporter(ABC):
  """Importer that imports transactions
  """

  def __init__(self, path: str = None, buf: bytes = None) -> None:
    """Initialize Transaction Importer

    Args:
      Provide one or the other
      path: Path to file
      buf: Contents of file
    """
    super().__init__()

    if buf is not None:
      self._buf = buf
    elif path is not None:
      with open(path, "rb") as file:
        self._buf = file.read()
    else:
      raise ValueError("Must provide path or buffer")

  @classmethod
  @abstractmethod
  def is_importable(cls, name: str, buf: bytes) -> bool:
    """Test if file is importable for this Importer

    Args:
      name: Name of file to import
      buf: Contents of file
    """
    pass  # pragma: no cover

  @abstractmethod
  def run(self) -> t.List[TransactionDict]:
    """Run importer

    Returns:
      List of transaction as dictionaries, key mapping to Transaction
      properties. Accounts and Assets referred to by name since ID is unknown
      here
    """
    pass  # pragma: no cover
