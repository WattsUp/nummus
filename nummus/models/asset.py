"""Asset model for storing an individual item with dynamic worth."""

from __future__ import annotations

import datetime
import re
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy
import yfinance as yf
from sqlalchemy import orm
from typing_extensions import override

from nummus import exceptions as exc
from nummus import utils
from nummus.models.base import (
    Base,
    BaseEnum,
    Decimal6,
    ORMBool,
    ORMInt,
    ORMReal,
    ORMStr,
    ORMStrOpt,
    YIELD_PER,
)
from nummus.models.transaction import TransactionSplit

if TYPE_CHECKING:
    from collections.abc import Iterable

_RE_ASSET_TICKER = re.compile(r"^[\$\^]?[A-Z][A-Z0-9.]*(-[A-Z]+)?$")


class AssetSplit(Base):
    """Asset Split model for storing a split of an asset on a specific date.

    Attributes:
        asset_uri: Asset unique identifier
        date_ord: Date ordinal of split
        multiplier: Multiplier of split, qty = qty_unadjusted * multiplier
    """

    # No __table_id__ because this is not user accessible

    asset_id: ORMInt = orm.mapped_column(sqlalchemy.ForeignKey("asset.id_"))
    multiplier: ORMReal = orm.mapped_column(Decimal6)
    date_ord: ORMInt

    @orm.validates("multiplier")
    @override
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        return super().validate_decimals(key, field)


class AssetValuation(Base):
    """Asset Valuation model for storing a value of an asset on a specific date.

    Attributes:
        asset_uri: Asset unique identifier
        date_ord: Date ordinal of valuation
        value: Value of assert
    """

    # No __table_id__ because this is not user accessible

    asset_id: ORMInt = orm.mapped_column(sqlalchemy.ForeignKey("asset.id_"))
    value: ORMReal = orm.mapped_column(Decimal6)
    date_ord: ORMInt

    @orm.validates("value")
    @override
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        return super().validate_decimals(key, field)


class AssetCategory(BaseEnum):
    """Categories of Assets."""

    CASH = 1

    STOCKS = 2
    BONDS = 3
    COMMODITIES = 4
    FUTURES = 5
    CRYPTOCURRENCY = 6
    INDEX = 7

    REAL_ESTATE = 8
    VEHICLE = 9
    ITEM = 10


class Asset(Base):
    """Asset model for storing an individual item with dynamic worth.

    Attributes:
        uri: Asset unique identifier
        name: Name of Asset
        description: Description of Asset
        category: Type of Asset
        interpolate: True will interpolate valuations with a linear function, for
            sparsely (monthly) valued assets
        ticker: Name of exchange ticker to fetch prices for. If no ticker then
            valuations must be manually entered
    """

    __table_id__ = 0x40000000

    name: ORMStr = orm.mapped_column(unique=True)
    description: ORMStrOpt
    category: orm.Mapped[AssetCategory]
    interpolate: ORMBool = orm.mapped_column(default=False)
    ticker: ORMStrOpt = orm.mapped_column(unique=True)

    # NOT ticker, since there are valid single letter tickers
    # NOT unit, since there are valid single letter units: ea
    @orm.validates("name", "description", "tag")
    @override
    def validate_strings(self, key: str, field: str | None) -> str | None:
        return super().validate_strings(key, field)

    @orm.validates("ticker")
    def validate_ticker(self, _: str, field: str | None) -> str | None:
        """Validates ticker is UPPERCASE.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        Raises:
            InvalidORMValueError if field is not uppercase.
        """
        if field is None or field in ["", "[blank]"]:
            return None
        if not _RE_ASSET_TICKER.match(field):
            msg = (
                "Asset ticker must be uppercase letters and numbers only, "
                "optional ^ or $ prefix"
            )
            raise exc.InvalidORMValueError(msg)

        return field

    @classmethod
    def get_value_all(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        ids: Iterable[int] | None = None,
    ) -> dict[int, list[Decimal]]:
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
        valuations_assets: dict[int, list[tuple[int, Decimal]]] = {}
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

        assets_values: dict[int, list[Decimal]] = {}
        for a_id, valuations in valuations_assets.items():
            valuations_sorted = sorted(valuations, key=lambda item: item[0])
            if a_id in interpolated_assets:
                assets_values[a_id] = utils.interpolate_linear(valuations_sorted, n)
            else:
                assets_values[a_id] = utils.interpolate_step(valuations_sorted, n)

        return assets_values

    def get_value(self, start_ord: int, end_ord: int) -> list[Decimal]:
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
        """Recalculate adjusted TransactionSplit.asset_quantity based on all splits.

        Does not commit changes, call s.commit() afterwards.
        """
        # This function is best here but need to avoid circular imports

        from nummus.models import TransactionSplit

        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        multiplier = Decimal(1)
        splits: list[tuple[int, Decimal]] = []

        query = (
            s.query(AssetSplit)
            .with_entities(AssetSplit.date_ord, AssetSplit.multiplier)
            .where(AssetSplit.asset_id == self.id_)
            .order_by(AssetSplit.date_ord.desc())
        )

        for s_date_ord, s_multiplier in query.yield_per(YIELD_PER):
            s_date_ord: int
            s_multiplier: Decimal
            # Compound splits as we go
            multiplier = multiplier * s_multiplier
            splits.append((s_date_ord, multiplier))
        splits.reverse()
        try:
            multiplier = splits[0][1]
        except IndexError:
            multiplier = Decimal(1)

        query = (
            s.query(TransactionSplit)
            .where(TransactionSplit.asset_id == self.id_)
            .order_by(TransactionSplit.date_ord)
        )

        sum_unadjusted = Decimal(0)
        sum_adjusted = Decimal(0)
        for t_split in query.yield_per(YIELD_PER):
            # Query whole object okay, need to set things
            t_split: TransactionSplit
            # If txn is on/after the split, update the multiplier
            while len(splits) >= 1 and t_split.date_ord >= splits[0][0]:
                splits.pop(0)
                try:
                    multiplier = splits[0][1]
                except IndexError:
                    multiplier = Decimal(1)
            t_split.adjust_asset_quantity(multiplier)
            sum_unadjusted += t_split.asset_quantity_unadjusted or Decimal(0)
            sum_adjusted += t_split.asset_quantity or Decimal(0)
            if sum_unadjusted == 0:
                # sum_adjusted is an error term, use to make sum of adjusted zero out
                t_split.asset_quantity = (t_split.asset_quantity or 0) - sum_adjusted
                # Zero out error term since it has been dealt with
                sum_adjusted = 0

    def prune_valuations(self) -> int:
        """Remove valuations that are not needed due to zero quantity being held.

        Does not commit changes, call s.commit() afterwards.

        Returns:
            Number of AssetValuations pruned
        """
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError
        if self.category == AssetCategory.INDEX:
            # If asset is an INDEX, do not prune
            return 0

        # Date when quantity is zero
        date_ord_zero: int | None = None
        date_ord_non_zero: int | None = None
        current_qty = Decimal(0)

        periods_zero: list[tuple[int | None, int | None]] = []

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.date_ord,
                TransactionSplit.asset_quantity,
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

        for date_ord, qty in query.yield_per(YIELD_PER):
            date_ord: int
            qty: Decimal

            if current_qty == 0:
                # Bought some, record the period when zero
                date_ord_non_zero = date_ord
                periods_zero.append((date_ord_zero, date_ord_non_zero))
                date_ord_zero = None
            current_qty += qty
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
                # Get date of oldest valuation after or on the sell
                query = s.query(sqlalchemy.func.min(AssetValuation.date_ord)).where(
                    AssetValuation.asset_id == self.id_,
                    AssetValuation.date_ord >= date_ord_sell,
                )
                trim_start = query.scalar()

            if date_ord_buy is not None:
                # Get date of most recent valuation or on before the buy
                query = s.query(sqlalchemy.func.max(AssetValuation.date_ord)).where(
                    AssetValuation.asset_id == self.id_,
                    AssetValuation.date_ord <= date_ord_buy,
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

    def update_valuations(
        self,
        *,
        through_today: bool,
    ) -> tuple[datetime.date | None, datetime.date | None]:
        """Update valuations from web sources.

        Does not commit changes, call s.commit() afterwards.

        Args:
            through_today: True will force end date to today (for when currently
                holding any quantity)

        Returns:
            Updated range (start date, end date)
            Might be None if there are no Transactions for this Asset

        Raises:
            NoAssetWebSourceError if Asset has no ticker
            AssetWebError if failed to download data
        """
        if self.ticker is None:
            raise exc.NoAssetWebSourceError

        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError

        today = datetime.date.today()
        today_ord = today.toordinal()

        query = s.query(TransactionSplit).with_entities(
            sqlalchemy.func.min(TransactionSplit.date_ord),
            sqlalchemy.func.max(TransactionSplit.date_ord),
        )
        # If asset is an INDEX, look at all transactions
        if self.category == AssetCategory.INDEX:
            query = query.where(TransactionSplit.asset_id.isnot(None))
            through_today = True
        else:
            query = query.where(TransactionSplit.asset_id == self.id_)
        start_ord, end_ord = query.one()
        start_ord: int
        end_ord: int
        if start_ord is None or end_ord is None:
            return None, None

        start_ord = start_ord - utils.DAYS_IN_WEEK
        end_ord = end_ord + utils.DAYS_IN_WEEK
        if through_today:
            end_ord = today_ord

        start = datetime.date.fromordinal(start_ord)
        end = datetime.date.fromordinal(end_ord)

        yf_ticker = yf.Ticker(self.ticker)
        try:
            # Need to fetch all the way to today to get all splits
            raw = yf_ticker.history(
                start=start,
                end=today,
                actions=True,
                raise_errors=True,
            )
        except Exception as e:
            # yfinance raises Exception if no data found
            raise exc.AssetWebError(e) from e

        # Update AssetValuations, reuse existing when possible
        raw_close = raw["Close"]
        n_close = len(raw_close)
        i = 0
        query = s.query(AssetValuation).where(AssetValuation.asset_id == self.id_)
        for valuation in query.yield_per(YIELD_PER):
            if i >= n_close:
                # Delete excess valuations
                s.delete(valuation)
                continue
            # Pyright doesn't like the pandas dataframe typing
            dt: datetime.datetime = raw_close.index[i].to_pydatetime()  # type: ignore[attr-defined]
            if dt.date() > end:
                # Skip to end if date > end
                i = n_close
                s.delete(valuation)
                continue
            price: float = raw_close.iat[i]

            valuation.date_ord = dt.date().toordinal()
            valuation.value = Decimal(price)

            i += 1

        while i < n_close:
            # Add any missing ones
            dt: datetime.datetime = raw_close.index[i].to_pydatetime()  # type: ignore[attr-defined]
            if dt.date() > end:
                # Skip to end if date > end
                break
            price: float = raw_close.iat[i]

            valuation = AssetValuation(
                asset_id=self.id_,
                date_ord=dt.date().toordinal(),
                value=Decimal(price),
            )
            s.add(valuation)

            i += 1

        # Update AssetSplits, reuse existing when possible
        raw_splits = raw.loc[raw["Stock Splits"] != 0]["Stock Splits"]
        n_splits = len(raw_splits)
        i = 0
        query = s.query(AssetSplit).where(AssetSplit.asset_id == self.id_)
        for split in query.yield_per(YIELD_PER):
            if i >= n_splits:
                # Delete excess splits
                s.delete(split)
                continue
            dt: datetime.datetime = raw_splits.index[i].to_pydatetime()
            multiplier: float = raw_splits.iat[i]

            split.date_ord = dt.date().toordinal()
            split.multiplier = Decimal(multiplier)

            i += 1

        while i < n_splits:
            # Add any missing ones
            dt: datetime.datetime = raw_splits.index[i].to_pydatetime()
            multiplier: float = raw_splits.iat[i]

            split = AssetSplit(
                asset_id=self.id_,
                date_ord=dt.date().toordinal(),
                multiplier=Decimal(multiplier),
            )
            s.add(split)

            i += 1

        # Run update_splits to fix transactions
        self.update_splits()

        return start, end

    @classmethod
    def index_twrr(
        cls,
        s: orm.Session,
        name: str,
        start_ord: int,
        end_ord: int,
    ) -> list[Decimal]:
        """Get the TWRR for an index from start to end date.

        Args:
            s: SQL session to use
            name: Name of index
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            list[price ratios]
        """
        try:
            a_id = s.query(Asset.id_).where(Asset.name == name).one()[0]
        except exc.NoResultFound as e:  # pragma: no cover
            msg = f"Could not find asset index {name}"
            raise exc.ProtectedObjectNotFoundError(msg) from e
        values = cls.get_value_all(s, start_ord, end_ord, ids=[a_id])[a_id]
        cost_basis = values[0]
        return utils.twrr(values, [v - cost_basis for v in values])

    @classmethod
    def add_indices(cls, s: orm.Session) -> None:
        """Add Asset indices used for performance comparison.

        Args:
            s: SQL session to use

        Returns:
            list[price ratios]
        """
        indices: dict[str, dict[str, str]] = {
            "^GSPC": {
                "name": "S&P 500",
                "description": "A stock market index tracking the stock performance of "
                "500 of the largest companies listed on stock exchanges in the United "
                "States",
            },
            "^DJI": {
                "name": "Dow Jones Industrial Average",
                "description": "A stock market index tracking the stock performance of "
                "30 prominent companies listed on stock exchanges in the United States",
            },
            "^BUK100P": {
                "name": "Cboe UK 100",
                "description": "A stock market index tracking the stock performance of "
                "100 of the largest companies listed on stock exchanges in the United "
                "Kingdom",
            },
            "^N225": {
                "name": "Nikkel Index",
                "description": "A stock market index for the Tokyo Stock Exchange",
            },
            "^N100": {
                "name": "Euronext 100 Index",
                "description": "A stock market index tracking the stock performance of "
                "100 of the largest companies listed on Euronext",
            },
            "^HSI": {
                "name": "Hang Seng Index",
                "description": "A freefloat-adjusted market-capitalization-weighted "
                "stock-market index in Hong Kong",
            },
        }
        for ticker, item in indices.items():
            a = Asset(
                name=item["name"],
                description=item["description"],
                category=AssetCategory.INDEX,
                interpolate=False,
                ticker=ticker,
            )
            s.add(a)
        s.commit()
