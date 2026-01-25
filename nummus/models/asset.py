"""Asset model for storing an individual item with dynamic worth."""

from __future__ import annotations

import datetime
import operator
from collections import defaultdict
from decimal import Decimal
from typing import override, TYPE_CHECKING

import yfinance
import yfinance.exceptions
from sqlalchemy import CheckConstraint, ForeignKey, func, Index, orm, UniqueConstraint

from nummus import exceptions as exc
from nummus import sql, utils
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
)
from nummus.models.currency import Currency, DEFAULT_CURRENCY
from nummus.models.transaction import TransactionSplit
from nummus.models.utils import update_rows

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
    FOREX = 11

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
        currency: Currency this asset is valued in

    """

    __tablename__ = "asset"
    __table_id__ = 0x00000000

    name: ORMStr = orm.mapped_column(unique=True)
    description: ORMStrOpt
    category: orm.Mapped[AssetCategory] = orm.mapped_column(SQLEnum(AssetCategory))
    interpolate: ORMBool = orm.mapped_column(default=False)
    ticker: ORMStrOpt = orm.mapped_column(unique=True)
    currency: orm.Mapped[Currency] = orm.mapped_column(SQLEnum(Currency))

    __table_args__ = (
        *string_column_args("name"),
        *string_column_args("description"),
        # No short check, since there are valid single letter tickers
        *string_column_args("ticker", short_check=False),
    )

    _SEARCH_PROPERTIES = ("ticker", "name")

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
        start_ord: int,
        end_ord: int,
        ids: Iterable[int] | None = None,
    ) -> dict[int, list[Decimal]]:
        """Get the value of all Assets from start to end date.

        Args:
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
        query = Asset.query(Asset.id_).where(Asset.interpolate)
        if ids is not None:
            query = query.where(Asset.id_.in_(ids))
        interpolated_assets: set[int] = {r[0] for r in sql.yield_(query)}

        # Get latest Valuation before or including start date
        query = (
            AssetValuation.query(
                AssetValuation.asset_id,
                func.max(AssetValuation.date_ord),
                AssetValuation.value,
            )
            .where(AssetValuation.date_ord <= start_ord)
            .group_by(AssetValuation.asset_id)
        )
        if ids is not None:
            query = query.where(AssetValuation.asset_id.in_(ids))
        for a_id, date_ord, v in sql.yield_(query):
            i = date_ord - start_ord
            valuations_assets[a_id] = [(i, v)]

        if start_ord != end_ord:
            # Transactions between start and end
            query = AssetValuation.query(
                AssetValuation.asset_id,
                AssetValuation.date_ord,
                AssetValuation.value,
            ).where(
                AssetValuation.date_ord <= end_ord,
                AssetValuation.date_ord > start_ord,
            )
            if ids is not None:
                query = query.where(AssetValuation.asset_id.in_(ids))

            for a_id, date_ord, v in sql.yield_(query):
                i = date_ord - start_ord
                valuations_assets[a_id].append((i, v))

        # Get interpolation point for assets with interpolation
        query = (
            AssetValuation.query(
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
        for a_id, date_ord, v in sql.yield_(query):
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
        # Not reusing get_value_all is faster by ~2ms,
        # not worth maintaining two almost identical implementations
        return self.get_value_all(start_ord, end_ord, [self.id_])[self.id_]

    def update_splits(self) -> None:
        """Recalculate adjusted TransactionSplit.asset_quantity based on all splits.

        Does not commit changes, call s.commit() afterwards.
        """
        # This function is best here but need to avoid circular imports
        from nummus.models.transaction import TransactionSplit  # noqa: PLC0415

        multiplier = Decimal(1)
        splits: list[tuple[int, Decimal]] = []

        query = (
            AssetSplit.query(AssetSplit.date_ord, AssetSplit.multiplier)
            .where(AssetSplit.asset_id == self.id_)
            .order_by(AssetSplit.date_ord.desc())
        )

        for s_date_ord, s_multiplier in sql.yield_(query):
            # Compound splits as we go
            multiplier *= s_multiplier
            splits.append((s_date_ord, multiplier))
        splits.reverse()
        try:
            multiplier = splits[0][1]
        except IndexError:
            multiplier = Decimal(1)

        query = (
            TransactionSplit.query()
            .where(
                TransactionSplit.asset_id == self.id_,
                TransactionSplit._asset_qty_unadjusted.isnot(None),  # noqa: SLF001
            )
            .order_by(TransactionSplit.date_ord)
        )

        sum_unadjusted = Decimal()
        sum_adjusted = Decimal()
        for t_split in sql.yield_(query):
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

        # Date when quantity is zero
        date_ord_zero: int | None = None
        date_ord_non_zero: int | None = None
        current_qty = Decimal()

        periods_zero: list[tuple[int | None, int | None]] = []

        query = (
            TransactionSplit.query(
                TransactionSplit.date_ord,
                TransactionSplit.asset_quantity,
            )
            .where(TransactionSplit.asset_id == self.id_)
            .order_by(TransactionSplit.date_ord)
        )
        if not sql.any_(query):
            # No transactions, prune all
            return (
                AssetValuation.query()
                .where(AssetValuation.asset_id == self.id_)
                .delete()
            )

        for date_ord, qty in sql.yield_(query):
            if TYPE_CHECKING:
                # Ensured by query and constraints
                assert qty is not None
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
        n_deleted = 0
        for date_ord_sell, date_ord_buy in periods_zero:
            trim_start: int | None = None
            trim_end: int | None = None
            if date_ord_sell is not None:
                # Get date of oldest valuation after or on the sell
                query = AssetValuation.query(func.min(AssetValuation.date_ord)).where(
                    AssetValuation.asset_id == self.id_,
                    AssetValuation.date_ord >= date_ord_sell,
                )
                trim_start = sql.scalar(query)

            if date_ord_buy is not None:
                # Get date of most recent valuation or on before the buy
                query = AssetValuation.query(func.max(AssetValuation.date_ord)).where(
                    AssetValuation.asset_id == self.id_,
                    AssetValuation.date_ord <= date_ord_buy,
                )
                trim_end = sql.scalar(query)

            if trim_start is None and trim_end is None:
                # Can happen if no valuations exist before/after a transaction
                continue

            query = AssetValuation.query().where(AssetValuation.asset_id == self.id_)
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

        """
        if self.ticker is None:
            raise exc.NoAssetWebSourceError

        today = datetime.datetime.now(datetime.UTC).date()
        today_ord = today.toordinal()

        query = TransactionSplit.query(
            func.min(TransactionSplit.date_ord),
            func.max(TransactionSplit.date_ord),
        )
        # If asset is an INDEX, look at all transactions
        if self.category == AssetCategory.INDEX:
            query = query.where(TransactionSplit.asset_id.isnot(None))
            through_today = True
        elif self.category == AssetCategory.FOREX:
            through_today = True
        else:
            query = query.where(TransactionSplit.asset_id == self.id_)
        start_ord, end_ord = sql.one(query)
        if not start_ord or not end_ord:
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
            self.currency = Currency(yf_ticker.info["currency"])
        except Exception as e:
            # yfinance raises Exception if no data found
            raise exc.AssetWebError(e) from e

        valuations: dict[int, float] = utils.pd_series_to_dict(
            raw["Close"],  # type: ignore[attr-defined]
        )

        query = AssetValuation.query().where(AssetValuation.asset_id == self.id_)
        update_rows(
            AssetValuation,
            query,
            "date_ord",
            {
                k: {"value": Decimal(v), "asset_id": self.id_}
                for k, v in valuations.items()
                if start_ord <= k <= end_ord
            },
        )

        splits: dict[int, float] = utils.pd_series_to_dict(
            raw.loc[raw["Stock Splits"] != 0]["Stock Splits"],  # type: ignore[attr-defined]
        )

        query = AssetSplit.query().where(AssetSplit.asset_id == self.id_)
        update_rows(
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
                AssetSector.query().where(AssetSector.asset_id == self.id_).delete()
                return
            weights = {USSector(sector): Decimal(1)}

        query = AssetSector.query().where(AssetSector.asset_id == self.id_)
        update_rows(
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
        name: str,
        start_ord: int,
        end_ord: int,
    ) -> list[Decimal]:
        """Get the TWRR for an index from start to end date.

        Args:
            name: Name of index
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)

        Returns:
            list[price ratios]

        Raises:
            ProtectedObjectNotFoundError: If index is not found

        """
        try:
            a_id = sql.one(Asset.query(Asset.id_).where(Asset.name == name))
        except exc.NoResultFound as e:
            msg = f"Could not find asset index {name}"
            raise exc.ProtectedObjectNotFoundError(msg) from e
        values = cls.get_value_all(start_ord, end_ord, ids=[a_id])[a_id]
        cost_basis = values[0]
        return utils.twrr(values, [v - cost_basis for v in values])

    @classmethod
    def add_indices(cls) -> None:
        """Add Asset indices used for performance comparison."""
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
            cls.create(
                name=item["name"],
                description=item["description"],
                category=AssetCategory.INDEX,
                interpolate=False,
                ticker=ticker,
                currency=DEFAULT_CURRENCY,
            )

    def autodetect_interpolate(self) -> None:
        """Autodetect if Asset needs interpolation.

        Does not commit changes, call s.commit() afterwards.
        """
        query = (
            AssetValuation.query(AssetValuation.date_ord)
            .where(AssetValuation.asset_id == self.id_)
            .order_by(AssetValuation.date_ord)
        )
        date_ords = [r[0] for r in sql.yield_(query)]
        has_dailys = any(
            (date_ords[i] - date_ords[i - 1]) == 1 for i in range(1, len(date_ords))
        )
        # Don't interpolate if there are dailys or if there is only one AssetValuation
        self.interpolate = not has_dailys and len(date_ords) > 1

    @classmethod
    def create_forex(
        cls,
        base: Currency,
        others: set[Currency],
    ) -> None:
        """Create foreign exchange rate assets.

        Args:
            base: Base currency to get FOREX referenced to
            others: Other currencys to get

        """
        if base in others:
            others.discard(base)

        query = Asset.query(Asset.ticker).where(
            Asset.category == AssetCategory.FOREX,
            Asset.ticker.is_not(None),
        )
        existing: set[str] = set()
        for (ticker,) in sql.yield_(query):
            if TYPE_CHECKING:
                # Ensured by query
                assert ticker is not None
            existing.add(ticker)

        for other in others:
            ticker = f"{other.name}{base.name}=X"
            if ticker in existing:
                existing.discard(ticker)
                continue

            cls.create(
                name=f"{other.name} to {base.name}",
                description=f"Exchange rate from {other.pretty} to {base.pretty}",
                category=AssetCategory.FOREX,
                ticker=ticker,
                currency=base,
            )

            existing.discard(ticker)

        # existing has unused FOREX assets
        # TODO (WattsUp): #463 Handle when accounts hold FOREX
        query = Asset.query(Asset.id_).where(Asset.ticker.in_(existing))
        to_delete = {r[0] for r in sql.yield_(query)}
        AssetValuation.query().where(AssetValuation.asset_id.in_(to_delete)).delete()
        AssetSplit.query().where(AssetSplit.asset_id.in_(to_delete)).delete()
        AssetSector.query().where(AssetSector.asset_id.in_(to_delete)).delete()
        Asset.query().where(Asset.id_.in_(to_delete)).delete()

    @classmethod
    def get_forex(
        cls,
        start_ord: int,
        end_ord: int,
        base: Currency,
        currencies: Iterable[Currency] | None = None,
    ) -> dict[Currency, list[Decimal]]:
        """Get foreign exchange rate over time.

        Args:
            start_ord: First date ordinal to evaluate
            end_ord: Last date ordinal to evaluate (inclusive)
            base: Base currency to exchange to
            currencies: Filter which currencies to get

        Returns:
            dict{
                currency: [exchange rates]
            }

            Multiply value in other by exchange rate to get base value
            see utils.element_multiply

        """
        currencies = currencies or [*Currency]
        currencies_by_ticker: dict[str | None, Currency] = {
            f"{other.name}{base.name}=X": other for other in currencies
        }
        # null ticker filtered out by query
        query = Asset.query(Asset.id_, Asset.ticker).where(
            Asset.category == AssetCategory.FOREX,
            Asset.currency == base,
        )
        query = query.where(Asset.ticker.in_(currencies_by_ticker))
        assets = sql.to_dict(query)

        values = cls.get_value_all(start_ord, end_ord, assets.keys())

        forex: dict[Currency, list[Decimal]] = defaultdict(
            lambda: [Decimal(1)] * (end_ord - start_ord + 1),
        )

        for a_id, exchange in values.items():
            ticker = assets[a_id]
            currency = currencies_by_ticker[ticker]
            forex[currency] = exchange

        return forex
