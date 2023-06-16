"""Database models
"""

from sqlalchemy import exc, orm  # pylint: disable=unused-imports

from nummus.models.base import Base
from nummus.models.asset import AssetValuation, Asset


def metadata_create_all(session: orm.Session) -> None:
  """Create all tables for nummus models

  Creates tables then commits

  Args:
    session: Session to create tables for
  """
  tables = [AssetValuation.__table__, Asset.__table__]
  Base.metadata.create_all(session.get_bind(), tables)
  session.commit()
