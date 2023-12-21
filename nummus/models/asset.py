"""Asset model for storing an individual item with dynamic worth."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy
from sqlalchemy import orm

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus import utils
from nummus.models.base import Base, BaseEnum, Decimal6, YIELD_PER


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

    @classmethod
    def get_value_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: t.Ints | set[int] | None = None,
    ) -> t.DictIntReals:
        """Get the value of all Assets from start to end date.

        Args:
            s: SQL session to use
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)
            ids: Limit results to specific Assets by ID

        Returns:
            dict{Asset.id_: list[values]}
        """
        n = end_ord - start_ord + 1

        # Get a list of valuations (date offset, value) for each Asset
        valuations_assets: dict[int, list[tuple[int, t.Real]]] = {}
        if ids is not None:
            valuations_assets = {a_id: [] for a_id in ids}
        else:
            valuations_assets = {a_id: [] for a_id, in s.query(Asset.id_).all()}

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
        for a_id, v, _ in query.all():
            a_id: int
            v: Decimal
            valuations_assets[a_id] = [(0, v)]

        if start_ord != end_ord:
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

            for a_id, date_ord, v in query.yield_per(YIELD_PER):
                a_id: int
                date_ord: int
                v: Decimal

                i = date_ord - start_ord

                try:
                    valuations_assets[a_id].append((i, v))
                except KeyError:  # pragma: no cover
                    # Should not happen cause delta_accounts is initialized with all
                    valuations_assets[a_id] = [(i, v)]

        # TODO (WattsUp): Add optional linear interpolation here

        assets_values: t.DictIntReals = {}
        for a_id, valuations in valuations_assets.items():
            valuations_sorted = sorted(valuations, key=lambda item: item[0])
            assets_values[a_id] = utils.interpolate_step(valuations_sorted, n)

        return assets_values

    def get_value(self, start_ord: int, end_ord: int) -> t.Reals:
        """Get the value of Asset from start to end date.

        Args:
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            list[values]
        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        # Not reusing get_value_all is faster by ~2ms,
        # not worth maintaining two almost identical implementations

        return self.get_value_all(s, start_ord, end_ord, [self.id_])[self.id_]

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
