"""Asset model for storing an individual item with dynamic worth."""

from __future__ import annotations

import datetime
from decimal import Decimal

import sqlalchemy
from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models.base import Base, BaseEnum, Decimal6

ORMAsset = orm.Mapped["Asset"]
ORMAssetOpt = orm.Mapped[t.Optional["Asset"]]
ORMAssetCat = orm.Mapped["AssetCategory"]
ORMAssetCatOpt = orm.Mapped[t.Optional["AssetCategory"]]
ORMAssetVal = orm.Mapped["AssetValuation"]
ORMAssetValList = orm.Mapped[t.List["AssetValuation"]]
ORMAssetValOpt = orm.Mapped[t.Optional["AssetValuation"]]

DictStrAsset = t.Dict[str, "Asset"]


class AssetSplit(Base):
    """Asset Split model for storing a split of an asset on a specific date.

    Attributes:
        asset_uuid: Asset unique identifier
        date: Date of split
        multiplier: Multiplier of split, qty = qty_unadjusted * multiplier
    """

    asset_id: t.ORMInt = orm.mapped_column(sqlalchemy.ForeignKey("asset.id"))
    multiplier: t.ORMReal = orm.mapped_column(Decimal6)
    date: t.ORMDate


class AssetValuation(Base):
    """Asset Valuation model for storing a value of an asset on a specific date.

    Attributes:
        asset_uuid: Asset unique identifier
        date: Date of valuation
        value: Value of assert
    """

    asset_id: t.ORMInt = orm.mapped_column(sqlalchemy.ForeignKey("asset.id"))
    value: t.ORMReal = orm.mapped_column(Decimal6)
    date: t.ORMDate


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
        uuid: Asset unique identifier
        name: Name of Asset
        description: Description of Asset
        category: Type of Asset
        unit: Unit name for an individual Asset (ex: shares)
        tag: Unique tag linked across datasets
    """

    name: t.ORMStr
    description: t.ORMStrOpt
    category: ORMAssetCat
    unit: t.ORMStrOpt
    tag: t.ORMStrOpt
    img_suffix: t.ORMStrOpt

    @property
    def image_name(self) -> str:
        """Get name of Asset's image, None if it doesn't exist."""
        s = self.img_suffix
        if s is None:
            return None
        return f"{self.uuid}{s}"

    def get_value(self, start: t.Date, end: t.Date) -> t.Tuple[t.Dates, t.Reals]:
        """Get the value of Asset from start to end date.

        Args:
            start: First date to evaluate
            end: Last date to evaluate (inclusive)

        Returns:
            List[dates], list[values]
        """
        s = orm.object_session(self)

        # Get latest Valuation before or including start date
        query = s.query(AssetValuation)
        query = query.with_entities(
            AssetValuation.value, sqlalchemy.func.max(AssetValuation.date)
        )  # pylint: disable=not-callable
        query = query.where(AssetValuation.asset_id == self.id)
        query = query.where(AssetValuation.date <= start)
        iv = query.scalar()
        value = iv or Decimal(0)

        date = start + datetime.timedelta(days=1)
        dates: t.Dates = [start]
        values: t.Reals = [value]

        if start == end:
            return dates, values

        # Valuations between start and end
        query = s.query(AssetValuation)
        query = query.with_entities(AssetValuation.date, AssetValuation.value)
        query = query.where(AssetValuation.asset_id == self.id)
        query = query.where(AssetValuation.date <= end)
        query = query.where(AssetValuation.date > start)
        query = query.order_by(AssetValuation.date)

        for v_date, v_value in query.all():
            v_date: datetime.date
            v_value: Decimal
            # Don't need thanks SQL filters
            # if t_split.date > end:
            #   continue
            while date < v_date:
                values.append(value)
                dates.append(date)
                date += datetime.timedelta(days=1)
            value = v_value
        while date <= end:
            values.append(value)
            dates.append(date)
            date += datetime.timedelta(days=1)
        return dates, values

    @classmethod
    def get_value_all(
        cls,
        s: orm.Session,
        start: t.Date,
        end: t.Date,
        uuids: t.Strings = None,
        ids: t.Ints = None,
    ) -> t.Tuple[t.Dates, t.DictIntReals]:
        """Get the value of all Assets from start to end date.

        Args:
            s: SQL session to use
            start: First date to evaluate
            end: Last date to evaluate (inclusive)
            uuids: Limit results to specific Assets by UUID
            ids: Limit results to specific Assets by ID

        Returns:
            (List[dates], dict{Asset.id: list[values]})
        """
        assets = Asset.map_uuid(s)
        values: t.DictIntReal = {a_id: Decimal(0) for a_id in assets}

        if uuids is not None:
            ids = [a_id for a_id, a_uuid in assets.items() if a_uuid in uuids]
        if ids is not None:
            values = {a_id: v for a_id, v in values.items() if a_id in ids}

        # Get latest Valuation before or including start date
        query = s.query(AssetValuation)
        query = query.with_entities(
            AssetValuation.asset_id,
            AssetValuation.value,
            sqlalchemy.func.max(AssetValuation.date),
        )  # pylint: disable=not-callable
        query = query.where(AssetValuation.date <= start)
        if ids is not None:
            query = query.where(AssetValuation.asset_id.in_(ids))
        query = query.group_by(AssetValuation.asset_id)
        for a_id, iv, _ in query.all():
            a_id: int
            iv: Decimal
            values[a_id] = iv

        date = start + datetime.timedelta(days=1)
        dates: t.Dates = [start]
        assets_values: t.DictIntReals = {a_id: [v] for a_id, v in values.items()}

        if start == end:
            return dates, assets_values

        def next_day(current: datetime.date) -> datetime.date:
            """Push currents into the lists."""
            for a_id, v in values.items():
                assets_values[a_id].append(v)
            dates.append(current)
            return current + datetime.timedelta(days=1)

        # Transactions between start and end
        query = s.query(AssetValuation)
        query = query.with_entities(
            AssetValuation.asset_id, AssetValuation.date, AssetValuation.value
        )
        query = query.where(AssetValuation.date <= end)
        query = query.where(AssetValuation.date > start)
        if ids is not None:
            query = query.where(AssetValuation.asset_id.in_(ids))
        query = query.order_by(AssetValuation.date)

        for a_id, v_date, v in query.all():
            a_id: int
            v_date: datetime.date
            v: Decimal
            while date < v_date:
                date = next_day(date)

            values[a_id] = v

        while date <= end:
            date = next_day(date)

        return dates, assets_values

    def update_splits(self) -> None:
        """Recalculate adjusted TransactionSplit.asset_quantity based on all splits."""
        # This function is best here but need to avoid circular imports

        from nummus.models import (
            TransactionSplit,  # pylint: disable=import-outside-toplevel
        )

        s = orm.object_session(self)

        multiplier = Decimal(1)
        splits: t.List[t.Tuple[t.Date, t.Real]] = []

        query = s.query(AssetSplit)
        query = query.with_entities(AssetSplit.date, AssetSplit.multiplier)
        query = query.where(AssetSplit.asset_id == self.id)
        query = query.order_by(AssetSplit.date.desc())

        for s_date, s_multiplier in query.all():
            s_date: datetime.date
            s_multiplier: Decimal
            # Compound splits as we go
            multiplier = multiplier * s_multiplier
            splits.append((s_date, multiplier))

        query = s.query(TransactionSplit)
        query = query.where(TransactionSplit.asset_id == self.id)
        query = query.order_by(TransactionSplit.date.desc())

        multiplier = Decimal(1)
        for t_split in query.all():
            # Query whole object okay, need to set things
            t_split: TransactionSplit
            # If txn is before the split, update the multiplier
            while len(splits) >= 1 and t_split.date < splits[0][0]:
                multiplier = splits.pop(0)[1]
            t_split.adjust_asset_quantity(multiplier)
