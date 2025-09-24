"""Asset model for storing an individual item with dynamic worth."""

from __future__ import annotations

import datetime
import operator
from collections import defaultdict
from decimal import Decimal
from typing import override, TYPE_CHECKING

import pandas as pd
import yfinance
import yfinance.exceptions
from sqlalchemy import CheckConstraint, ForeignKey, func, Index, orm, UniqueConstraint

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
    SQLEnum,
    string_column_args,
    YIELD_PER,
)
from nummus.models.transaction import TransactionSplit
from nummus.models.utils import obj_session, query_count, update_rows

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class USSector(BaseEnum):
    """US Sector enumeration."""

    BASIC_MATERIALS = 1
    COMMUNICATION_SERVICES = 2
    CONSUMER_CYCLICAL = 3
    CONSUMER_DEFENSIVE = 4
    ENERGY = 5
    FINANCIAL_SERVICES = 6
    HEALTHCARE = 7
    INDUSTRIALS = 8
    REAL_ESTATE = 9
    TECHNOLOGY = 10
    UTILITIES = 11

    @override
    @classmethod
    def lut(cls) -> Mapping[str, BaseEnum]:
        return {
            "realestate": USSector.REAL_ESTATE,
        }


class AssetSector(Base):
    """Asset Sector model for storing relating Asset to USSector.

    Attributes:
        asset_id: Asset unique identifier
        sector: USSector
        weight: Amount of Asset that is this USSector

    """

    __tablename__ = "asset_sector"
    __table_id__ = None

    asset_id: ORMInt = orm.mapped_column(ForeignKey("asset.id_"))
    sector: orm.Mapped[USSector] = orm.mapped_column(SQLEnum(USSector))
    weight: ORMReal = orm.mapped_column(Decimal6)

    __table_args__ = (
        UniqueConstraint("asset_id", "sector"),
        CheckConstraint(
            "weight > 0",
            "asset_sector.weight must be positive",
        ),
        Index("asset_sector_asset_id", "asset_id"),
    )


class AssetSplit(Base):
    """Asset Split model for storing a split of an asset on a specific date.

    Attributes:
        asset_uri: Asset unique identifier
        date_ord: Date ordinal of split
        multiplier: Multiplier of split, qty = qty_unadjusted * multiplier

    """

    __tablename__ = "asset_split"
    __table_id__ = None

    asset_id: ORMInt = orm.mapped_column(ForeignKey("asset.id_"))
    multiplier: ORMReal = orm.mapped_column(Decimal6)
    date_ord: ORMInt

    __table_args__ = (
        UniqueConstraint("asset_id", "date_ord"),
        CheckConstraint(
            "multiplier > 0",
            "asset_split.multiplier must be positive",
        ),
        Index("asset_split_asset_id", "asset_id"),
    )

    @orm.validates("multiplier")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validate decimal fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_decimals(key, field)

    @property
    def date(self) -> datetime.date:
        """Date on which Transaction occurred."""
        return datetime.date.fromordinal(self.date_ord)


class AssetValuation(Base):
    """Asset Valuation model for storing a value of an asset on a specific date.

    Attributes:
        asset_uri: Asset unique identifier
        date_ord: Date ordinal of valuation
        value: Value of assert

    """

    __tablename__ = "asset_valuation"
    __table_id__ = 0x00000000

    asset_id: ORMInt = orm.mapped_column(ForeignKey("asset.id_"))
    date_ord: ORMInt
    value: ORMReal = orm.mapped_column(Decimal6)

    __table_args__ = (
        UniqueConstraint("asset_id", "date_ord"),
        CheckConstraint(
            "value >= 0",
            "asset_valuation.value must be zero or positive",
        ),
        Index("asset_valuation_asset_id", "asset_id"),
        Index("asset_valuation_date_ord", "date_ord"),
    )

    @orm.validates("value")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validate decimal fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_decimals(key, field)

    @property
    def date(self) -> datetime.date:
        """Date on which Transaction occurred."""
        return datetime.date.fromordinal(self.date_ord)


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

    __tablename__ = "asset"
    __table_id__ = 0x00000000

    name: ORMStr = orm.mapped_column(unique=True)
    description: ORMStrOpt
    category: orm.Mapped[AssetCategory] = orm.mapped_column(SQLEnum(AssetCategory))
    interpolate: ORMBool = orm.mapped_column(default=False)
    ticker: ORMStrOpt = orm.mapped_column(unique=True)

    __table_args__ = (
        *string_column_args("name"),
        *string_column_args("description"),
        # No short check, since there are valid single letter tickers
        *string_column_args("ticker", short_check=False),
    )

    @orm.validates("name", "description", "ticker")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validate string fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_strings(key, field, short_check=key != "ticker")

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
            dict{Asset.id_: list[values]} with defaultdict
            Assets with zero values omitted

        """
        n = end_ord - start_ord + 1

        # Get a list of valuations (date offset, value) for each Asset
        valuations_assets: dict[int, list[tuple[int, Decimal]]] = defaultdict(list)
        query = s.query(Asset.id_).where(Asset.interpolate)
        if ids is not None:
            query = query.where(Asset.id_.in_(ids))
        interpolated_assets: set[int] = {r[0] for r in query.all()}

        # Get latest Valuation before or including start date
        query = (
            s.query(AssetValuation)
            .with_entities(
                AssetValuation.asset_id,
                func.max(AssetValuation.date_ord),
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
                valuations_assets[a_id].append((i, v))

        # Get interpolation point for assets with interpolation
        query = (
            s.query(AssetValuation)
            .with_entities(
                AssetValuation.asset_id,
                func.min(AssetValuation.date_ord),
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

        assets_values: dict[int, list[Decimal]] = defaultdict(lambda: [Decimal()] * n)
        for a_id, valuations in valuations_assets.items():
            valuations_sorted = sorted(valuations, key=operator.itemgetter(0))
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
        s = obj_session(self)

        # Not reusing get_value_all is faster by ~2ms,
        # not worth maintaining two almost identical implementations

        return self.get_value_all(s, start_ord, end_ord, [self.id_])[self.id_]

    def update_splits(self) -> None:
        """Recalculate adjusted TransactionSplit.asset_quantity based on all splits.

        Does not commit changes, call s.commit() afterwards.
        """
        # This function is best here but need to avoid circular imports
        from nummus.models import TransactionSplit  # noqa: PLC0415

        s = obj_session(self)

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
            multiplier *= s_multiplier
            splits.append((s_date_ord, multiplier))
        splits.reverse()
        try:
            multiplier = splits[0][1]
        except IndexError:
            multiplier = Decimal(1)

        query = (
            s.query(TransactionSplit)
            .where(
                TransactionSplit.asset_id == self.id_,
                TransactionSplit._asset_qty_unadjusted.isnot(None),  # noqa: SLF001
            )
            .order_by(TransactionSplit.date_ord)
        )

        sum_unadjusted = Decimal()
        sum_adjusted = Decimal()
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
            sum_unadjusted += t_split.asset_quantity_unadjusted or Decimal()
            sum_adjusted += t_split.asset_quantity or Decimal()
            if sum_unadjusted == 0:
                # sum_adjusted is an error term, use to make sum of adjusted zero out
                t_split.adjust_asset_quantity_residual(sum_adjusted)
                # Zero out error term since it has been dealt with
                sum_adjusted = 0

    def prune_valuations(self) -> int:
        """Remove valuations that are not needed due to zero quantity being held.

        Does not commit changes, call s.commit() afterwards.

        Returns:
            Number of AssetValuations pruned

        """
        if self.category == AssetCategory.INDEX:
            # If asset is an INDEX, do not prune
            return 0
        s = obj_session(self)

        # Date when quantity is zero
        date_ord_zero: int | None = None
        date_ord_non_zero: int | None = None
        current_qty = Decimal()

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
        if query_count(query) == 0:
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

        return self._delete_valuations(periods_zero)

    def _delete_valuations(
        self,
        periods_zero: list[tuple[int | None, int | None]],
    ) -> int:
        """Delete valuations during periods where zero assets are held.

        Args:
            periods_zero: list[(date_ord_sell, date_ord_buy)]

        Returns:
            Number of valuations deleted

        """
        s = obj_session(self)
        n_deleted = 0
        for date_ord_sell, date_ord_buy in periods_zero:
            trim_start: int | None = None
            trim_end: int | None = None
            if date_ord_sell is not None:
                # Get date of oldest valuation after or on the sell
                query = s.query(func.min(AssetValuation.date_ord)).where(
                    AssetValuation.asset_id == self.id_,
                    AssetValuation.date_ord >= date_ord_sell,
                )
                trim_start = query.scalar()

            if date_ord_buy is not None:
                # Get date of most recent valuation or on before the buy
                query = s.query(func.max(AssetValuation.date_ord)).where(
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

        Args:
            through_today: True will force end date to today (for when currently
                holding any quantity)

        Returns:
            Updated range (start date, end date)
            Might be None if there are no Transactions for this Asset

        Raises:
            NoAssetWebSourceError: If Asset has no ticker
            AssetWebError: If failed to download data
            TypeError: If returned DataFrame indices aren't Timestamps

        """
        if self.ticker is None:
            raise exc.NoAssetWebSourceError

        s = obj_session(self)

        today = datetime.datetime.now(datetime.UTC).date()
        today_ord = today.toordinal()

        query = s.query(TransactionSplit).with_entities(
            func.min(TransactionSplit.date_ord),
            func.max(TransactionSplit.date_ord),
        )
        # If asset is an INDEX, look at all transactions
        if self.category == AssetCategory.INDEX:
            query = query.where(TransactionSplit.asset_id.isnot(None))
            through_today = True
        else:
            query = query.where(TransactionSplit.asset_id == self.id_)
        start_ord, end_ord = query.one()
        start_ord: int | None
        end_ord: int | None
        if start_ord is None or end_ord is None:
            return None, None

        start_ord -= utils.DAYS_IN_WEEK
        end_ord = today_ord if through_today else end_ord + utils.DAYS_IN_WEEK

        start = datetime.date.fromordinal(start_ord)
        end = datetime.date.fromordinal(end_ord)

        yf_ticker = yfinance.Ticker(self.ticker)
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

        valuations: dict[int, float] = {}
        for k, v in raw["Close"].items():
            if not isinstance(k, pd.Timestamp):
                raise TypeError
            valuations[k.to_pydatetime().date().toordinal()] = float(v)

        query = s.query(AssetValuation).where(AssetValuation.asset_id == self.id_)
        update_rows(
            s,
            AssetValuation,
            query,
            "date_ord",
            {
                k: {"value": Decimal(v), "asset_id": self.id_}
                for k, v in valuations.items()
                if start_ord <= k <= end_ord
            },
        )

        raw_splits = raw.loc[raw["Stock Splits"] != 0]["Stock Splits"]
        splits: dict[int, float] = {
            k.to_pydatetime().date().toordinal(): v for k, v in raw_splits.items()
        }
        query = s.query(AssetSplit).where(AssetSplit.asset_id == self.id_)
        update_rows(
            s,
            AssetSplit,
            query,
            "date_ord",
            {
                k: {"multiplier": Decimal(v), "asset_id": self.id_}
                for k, v in splits.items()
            },
        )

        # Run update_splits to fix transactions
        self.update_splits()

        return start, end

    def update_sectors(self) -> None:
        """Update AssetSector from web sources.

        Raises:
            NoAssetWebSourceError: If Asset has no ticker

        """
        if self.ticker is None:
            raise exc.NoAssetWebSourceError

        s = obj_session(self)

        yf_ticker = yfinance.Ticker(self.ticker)
        funds = yf_ticker.funds_data
        try:
            weights = {
                USSector(sector): Decimal(weight)
                for sector, weight in funds.sector_weightings.items()
                if weight
            }
        except yfinance.exceptions.YFDataException:
            # Not a fund
            sector = yf_ticker.info.get("sector")
            if sector is None:
                s.query(AssetSector).where(AssetSector.asset_id == self.id_).delete()
                return
            weights = {USSector(sector): Decimal(1)}

        query = s.query(AssetSector).where(AssetSector.asset_id == self.id_)
        update_rows(
            s,
            AssetSector,
            query,
            "sector",
            {
                sector: {"asset_id": self.id_, "weight": v}
                for sector, v in weights.items()
            },
        )

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

        Raises:
            ProtectedObjectNotFoundError: If index is not found

        """
        try:
            a_id = s.query(Asset.id_).where(Asset.name == name).one()[0]
        except exc.NoResultFound as e:
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

        """
        indices: dict[str, dict[str, str]] = {
            "^GSPC": {
                "name": "S&P 500",
                "description": (
                    "A stock market index tracking the stock performance of "
                    "500 of the largest companies listed on stock exchanges "
                    "in the United States"
                ),
            },
            "^DJI": {
                "name": "Dow Jones Industrial Average",
                "description": (
                    "A stock market index tracking the stock performance of "
                    "30 prominent companies listed on stock exchanges in the "
                    "United States"
                ),
            },
            "^BUK100P": {
                "name": "Cboe UK 100",
                "description": (
                    "A stock market index tracking the stock performance of "
                    "100 of the largest companies listed on stock exchanges "
                    "in the United Kingdom"
                ),
            },
            "^N225": {
                "name": "Nikkel Index",
                "description": "A stock market index for the Tokyo Stock Exchange",
            },
            "^N100": {
                "name": "Euronext 100 Index",
                "description": (
                    "A stock market index tracking the stock performance of "
                    "100 of the largest companies listed on Euronext"
                ),
            },
            "^HSI": {  # codespell:ignore
                "name": "Hang Seng Index",
                "description": (
                    "A freefloat-adjusted market-capitalization-weighted "
                    "stock-market index in Hong Kong"
                ),
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

    def autodetect_interpolate(self) -> None:
        """Autodetect if Asset needs interpolation.

        Does not commit changes, call s.commit() afterwards.
        """
        s = obj_session(self)

        query = (
            s.query(AssetValuation.date_ord)
            .where(AssetValuation.asset_id == self.id_)
            .order_by(AssetValuation.date_ord)
        )
        date_ords = [r[0] for r in query.yield_per(YIELD_PER)]
        has_dailys = any(
            (date_ords[i] - date_ords[i - 1]) == 1 for i in range(1, len(date_ords))
        )
        # Don't interpolate if there are dailys or if there is only one AssetValuation
        self.interpolate = not has_dailys and len(date_ords) > 1
