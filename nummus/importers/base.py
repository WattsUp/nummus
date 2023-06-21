"""Base importer interfaces
"""

from typing import Dict, List, Union

from abc import ABC, abstractmethod
import datetime


class TransactionImporter(ABC):
  """Importer that imports transactions
  """

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
  def run(self) -> List[Dict[str, Union[str, float, datetime.date, object]]]:
    """Run importer

    Returns:
      List of transaction as dictionaries, key mapping to Transaction
      properties. Accounts and Assets referred to by name since ID is unknown
      here
    """
    pass  # pragma: no cover
