"""Asset model for storing an individual item with dynamic worth."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy
from sqlalchemy import orm

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus import utils
from nummus.models.base import Base, BaseEnum, Decimal6, YIELD_PER
from nummus.models.transaction import TransactionSplit


class AssetSplit(Base):
    """Asset Split model for storing a split of an asset on a specific date.

    Attributes:
        asset_uri: Asset unique identifier
        date_ord: Date ordinal of split
        multiplier: Multiplier of split, qty = qty_unadjusted * multiplier
    """

    # No __table_id__ because this is not user accessible

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

    # No __table_id__ because this is not user accessible

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
        interpolate: True will interpolate valuations with a linear function, for
            sparsely (monthly) valued assets
    """

    __table_id__ = 0x40000000

    name: t.ORMStr
    description: t.ORMStrOpt
    category: orm.Mapped[AssetCategory]
    unit: t.ORMStrOpt
    tag: t.ORMStrOpt
    img_suffix: t.ORMStrOpt
    interpolate: t.ORMBool = orm.mapped_column(default=False)

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
        interpolated_assets: set[int] = set()
        query = s.query(Asset).with_entities(Asset.id_, Asset.interpolate)
        if ids is not None:
            query = query.where(Asset.id_.in_(ids))
        for a_id, interpolate in query.all():
            a_id: int
            interpolate: bool
            valuations_assets[a_id] = []
            if interpolate:
                interpolated_assets.add(a_id)

        # Get latest Valuation before or including start date
        query = (
            s.query(AssetValuation)
            .with_entities(
                AssetValuation.asset_id,
                sqlalchemy.func.max(AssetValuation.date_ord),
                AssetValuation.value,
            )
            .where(AssetValuation.date_ord <= start_ord)
            .group_by(AssetValuation.asset_id)
        )
        if ids is not None:
            query = query.where(AssetValuation.asset_id.in_(ids))
        for a_id, date_ord, v in query.all():
            a_id: int
            date_ord: int
            v: Decimal
            i = date_ord - start_ord
            valuations_assets[a_id] = [(i, v)]

        if start_ord != end_ord:
            # Transactions between start and end
            query = (
                s.query(AssetValuation)
                .with_entities(
                    AssetValuation.asset_id,
                    AssetValuation.date_ord,
                    AssetValuation.value,
                )
                .where(
                    AssetValuation.date_ord <= end_ord,
                    AssetValuation.date_ord > start_ord,
                )
            )
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

        # Get interpolation point for assets with interpolation
        query = (
            s.query(AssetValuation)
            .with_entities(
                AssetValuation.asset_id,
                sqlalchemy.func.min(AssetValuation.date_ord),
                AssetValuation.value,
            )
            .where(
                AssetValuation.date_ord > end_ord,
                AssetValuation.asset_id.in_(interpolated_assets),
            )
            .group_by(AssetValuation.asset_id)
        )
        for a_id, date_ord, v in query.all():
            a_id: int
            date_ord: int
            v: Decimal
            i = date_ord - start_ord
            valuations_assets[a_id].append((i, v))

        assets_values: t.DictIntReals = {}
        for a_id, valuations in valuations_assets.items():
            valuations_sorted = sorted(valuations, key=lambda item: item[0])
            if a_id in interpolated_assets:
                assets_values[a_id] = utils.interpolate_linear(valuations_sorted, n)
            else:
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

        query = (
            s.query(AssetSplit)
            .with_entities(AssetSplit.date_ord, AssetSplit.multiplier)
            .where(AssetSplit.asset_id == self.id_)
            .order_by(AssetSplit.date_ord.desc())
        )

        for s_date_ord, s_multiplier in query.all():
            s_date_ord: int
            s_multiplier: Decimal
            # Compound splits as we go
            multiplier = multiplier * s_multiplier
            splits.append((s_date_ord, multiplier))

        query = (
            s.query(TransactionSplit)
            .where(TransactionSplit.asset_id == self.id_)
            .order_by(TransactionSplit.date_ord.desc())
        )

        multiplier = Decimal(1)
        for t_split in query.all():
            # Query whole object okay, need to set things
            t_split: TransactionSplit
            # If txn is before the split, update the multiplier
            while len(splits) >= 1 and t_split.date_ord < splits[0][0]:
                multiplier = splits.pop(0)[1]
            t_split.adjust_asset_quantity(multiplier)

    def prune_valuations(self) -> int:
        """Remove valuations that are not needed due to zero quantity being held.

        Does not commit changes, call s.commit() afterwards.

        Returns:
            Number of AssetValuations pruned
        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        # Date when quantity is zero
        date_ord_zero: int | None = None
        date_ord_non_zero: int | None = None
        current_qty = Decimal(0)

        periods_zero: list[tuple[int | None, int | None]] = []

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.date_ord,
                TransactionSplit._asset_qty_int,  # noqa: SLF001
                TransactionSplit._asset_qty_frac,  # noqa: SLF001
            )
            .where(TransactionSplit.asset_id == self.id_)
            .order_by(TransactionSplit.date_ord)
        )
        if query.count() == 0:
            # No transactions, prune all
            return (
                s.query(AssetValuation)
                .where(AssetValuation.asset_id == self.id_)
                .delete()
            )

        for date_ord, qty_i, qty_f in query.yield_per(YIELD_PER):
            date_ord: int
            qty_i: int
            qty_f: Decimal

            if current_qty == 0:
                # Bought some, record the period when zero
                date_ord_non_zero = date_ord
                periods_zero.append((date_ord_zero, date_ord_non_zero))
                date_ord_zero = None
            current_qty += qty_i + qty_f
            if current_qty == 0:
                # Went back to zero
                date_ord_zero = date_ord
                date_ord_non_zero = None
        # Add last zero period if ended with zero
        if current_qty == 0 and date_ord_zero is not None:
            periods_zero.append((date_ord_zero, date_ord_non_zero))

        n_deleted = 0
        for date_ord_sell, date_ord_buy in periods_zero:
            trim_start: int | None = None
            trim_end: int | None = None
            if date_ord_sell is not None:
                # Get date of oldest valuation after the sell
                query = s.query(sqlalchemy.func.min(AssetValuation.date_ord)).where(
                    AssetValuation.asset_id == self.id_,
                    AssetValuation.date_ord > date_ord_sell,
                )
                trim_start = query.scalar()

            if date_ord_buy is not None:
                # Get date of most recent valuation before the buy
                query = s.query(sqlalchemy.func.max(AssetValuation.date_ord)).where(
                    AssetValuation.asset_id == self.id_,
                    AssetValuation.date_ord < date_ord_buy,
                )
                trim_end = query.scalar()

            if trim_start is None and trim_end is None:
                # Can happen if no valuations exist before/after a transaction
                continue

            query = s.query(AssetValuation).where(AssetValuation.asset_id == self.id_)
            if trim_start:
                query = query.where(AssetValuation.date_ord > trim_start)
            if trim_end:
                query = query.where(AssetValuation.date_ord < trim_end)
            n_deleted += query.delete()

        return n_deleted
