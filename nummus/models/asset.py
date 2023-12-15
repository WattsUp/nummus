"""Asset model for storing an individual item with dynamic worth."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy
from sqlalchemy import orm

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus.models.base import Base, BaseEnum, Decimal6


class AssetSplit(Base):
    """Asset Split model for storing a split of an asset on a specific date.

    Attributes:
        asset_uri: Asset unique identifier
        date_ord: Date ordinal of split
        multiplier: Multiplier of split, qty = qty_unadjusted * multiplier
    """

    __table_id__ = 0x20000000

    asset_id: t.ORMInt = orm.mapped_column(sqlalchemy.ForeignKey("asset.id_"))
    multiplier: t.ORMReal = orm.mapped_column(Decimal6)
    date_ord: t.ORMInt


class AssetValuation(Base):
    """Asset Valuation model for storing a value of an asset on a specific date.

    Attributes:
        asset_uri: Asset unique identifier
        date_ord: Date ordinal of valuation
        value: Value of assert
    """

    __table_id__ = 0x30000000

    asset_id: t.ORMInt = orm.mapped_column(sqlalchemy.ForeignKey("asset.id_"))
    value: t.ORMReal = orm.mapped_column(Decimal6)
    date_ord: t.ORMInt


class AssetCategory(BaseEnum):
    """Categories of Assets."""

    CASH = 1
    SECURITY = 2
    REAL_ESTATE = 3
    VEHICLE = 4
    ITEM = 5


class Asset(Base):
    """Asset model for storing an individual item with dynamic worth.

    Attributes:
        uri: Asset unique identifier
        name: Name of Asset
        description: Description of Asset
        category: Type of Asset
        unit: Unit name for an individual Asset (ex: shares)
        tag: Unique tag linked across datasets
    """

    __table_id__ = 0x40000000

    name: t.ORMStr
    description: t.ORMStrOpt
    category: orm.Mapped[AssetCategory]
    unit: t.ORMStrOpt
    tag: t.ORMStrOpt
    img_suffix: t.ORMStrOpt

    @property
    def image_name(self) -> str | None:
        """Get name of Asset's image, None if it doesn't exist."""
        s = self.img_suffix
        if s is None:
            return None
        return f"{self.uri}{s}"

    def get_value(self, start_ord: int, end_ord: int) -> tuple[t.Ints, t.Reals]:
        """Get the value of Asset from start to end date.

        Args:
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            List[date ordinals], list[values]
        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        # TODO (Bradley): Add optional spline interpolation for
        # infrequently valued assets

        # Get latest Valuation before or including start date
        query = s.query(AssetValuation)
        query = query.with_entities(
            AssetValuation.value,
            sqlalchemy.func.max(AssetValuation.date_ord),
        )
        query = query.where(AssetValuation.asset_id == self.id_)
        query = query.where(AssetValuation.date_ord <= start_ord)
        iv = query.scalar()
        value = iv or Decimal(0)

        date_ord = start_ord + 1
        date_ords: t.Ints = [start_ord]
        values: t.Reals = [value]

        if start_ord == end_ord:
            return date_ords, values

        # Valuations between start and end
        query = s.query(AssetValuation)
        query = query.with_entities(AssetValuation.date_ord, AssetValuation.value)
        query = query.where(AssetValuation.asset_id == self.id_)
        query = query.where(AssetValuation.date_ord <= end_ord)
        query = query.where(AssetValuation.date_ord > start_ord)
        query = query.order_by(AssetValuation.date_ord)

        for v_date_ord, v_value in query.all():
            v_date_ord: int
            v_value: Decimal

            while date_ord < v_date_ord:
                values.append(value)
                date_ords.append(date_ord)
                date_ord += 1
            value = v_value
        while date_ord <= end_ord:
            values.append(value)
            date_ords.append(date_ord)
            date_ord += 1
        return date_ords, values

    @classmethod
    def get_value_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: t.Ints | None = None,
    ) -> tuple[t.Ints, t.DictIntReals]:
        """Get the value of all Assets from start to end date.

        Args:
            s: SQL session to use
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)
            ids: Limit results to specific Assets by ID

        Returns:
            (List[date ordinals], dict{Asset.id_: list[values]})
        """
        values: t.DictIntReal = {a_id: Decimal(0) for a_id, in s.query(Asset.id_).all()}

        if ids is not None:
            values = {a_id: v for a_id, v in values.items() if a_id in ids}

        # Get latest Valuation before or including start date
        query = s.query(AssetValuation)
        query = query.with_entities(
            AssetValuation.asset_id,
            AssetValuation.value,
            sqlalchemy.func.max(AssetValuation.date_ord),
        )
        query = query.where(AssetValuation.date_ord <= start_ord)
        if ids is not None:
            query = query.where(AssetValuation.asset_id.in_(ids))
        query = query.group_by(AssetValuation.asset_id)
        for a_id, iv, _ in query.all():
            a_id: int
            iv: Decimal
            values[a_id] = iv

        date_ord = start_ord + 1
        date_ords: t.Ints = [start_ord]
        assets_values: t.DictIntReals = {a_id: [v] for a_id, v in values.items()}

        if start_ord == end_ord:
            return date_ords, assets_values

        def next_day(current: int) -> int:
            """Push currents into the lists."""
            for a_id, v in values.items():
                assets_values[a_id].append(v)
            date_ords.append(current)
            return current + 1

        # Transactions between start and end
        query = s.query(AssetValuation)
        query = query.with_entities(
            AssetValuation.asset_id,
            AssetValuation.date_ord,
            AssetValuation.value,
        )
        query = query.where(AssetValuation.date_ord <= end_ord)
        query = query.where(AssetValuation.date_ord > start_ord)
        if ids is not None:
            query = query.where(AssetValuation.asset_id.in_(ids))
        query = query.order_by(AssetValuation.date_ord)

        for a_id, v_date_ord, v in query.all():
            a_id: int
            v_date_ord: int
            v: Decimal
            while date_ord < v_date_ord:
                date_ord = next_day(date_ord)

            values[a_id] = v

        while date_ord <= end_ord:
            date_ord = next_day(date_ord)

        return date_ords, assets_values

    def update_splits(self) -> None:
        """Recalculate adjusted TransactionSplit.asset_quantity based on all splits."""
        # This function is best here but need to avoid circular imports

        from nummus.models import TransactionSplit

        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        multiplier = Decimal(1)
        splits: list[tuple[int, t.Real]] = []

        query = s.query(AssetSplit)
        query = query.with_entities(AssetSplit.date_ord, AssetSplit.multiplier)
        query = query.where(AssetSplit.asset_id == self.id_)
        query = query.order_by(AssetSplit.date_ord.desc())

        for s_date_ord, s_multiplier in query.all():
            s_date_ord: int
            s_multiplier: Decimal
            # Compound splits as we go
            multiplier = multiplier * s_multiplier
            splits.append((s_date_ord, multiplier))

        query = s.query(TransactionSplit)
        query = query.where(TransactionSplit.asset_id == self.id_)
        query = query.order_by(TransactionSplit.date_ord.desc())

        multiplier = Decimal(1)
        for t_split in query.all():
            # Query whole object okay, need to set things
            t_split: TransactionSplit
            # If txn is before the split, update the multiplier
            while len(splits) >= 1 and t_split.date_ord < splits[0][0]:
                multiplier = splits.pop(0)[1]
            t_split.adjust_asset_quantity(multiplier)
