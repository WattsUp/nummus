"""Account model for storing a financial account."""

from __future__ import annotations

import datetime
import re
import shlex
import string
from collections import defaultdict
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import CheckConstraint, event, ForeignKey, orm
from typing_extensions import override

from nummus import exceptions as exc
from nummus import utils
from nummus.models.base import (
    Base,
    Decimal6,
    Decimal9,
    ORMBool,
    ORMInt,
    ORMIntOpt,
    ORMReal,
    ORMRealOpt,
    ORMStr,
    ORMStrOpt,
    string_column_args,
    YIELD_PER,
)
from nummus.models.transaction_category import TransactionCategory

if TYPE_CHECKING:
    from decimal import Decimal


class TransactionSplit(Base):
    """TransactionSplit model for storing an exchange of cash for an asset (or none).

    Every Transaction has at least one TransactionSplit.

    Attributes:
        id: TransactionSplit unique identifier
        uri: TransactionSplit unique identifier
        amount: Amount amount of cash exchanged. Positive indicated Account
            increases in value (inflow)
        memo: Memo of exchange
        tag: Unique tag linked across datasets
        text_fields: Join of all text fields for searching
        category: Type of Transaction
        parent: Parent Transaction
        date_ord: Date ordinal on which Transaction occurred
        locked: True only allows manually editing, False allows automatic changes
            (namely auto labeling field based on similar Transactions)
        linked: True when transaction has been imported from a bank source, False
            indicates transaction was manually created
        account: Account that owns this Transaction
        asset: Asset exchanged for cash, primarily for instrument transactions
        asset_quantity: Number of units of Asset exchanged, Positive indicates
            Account gained Assets (inflow)
    """

    __table_id__ = 0x00000000

    amount: ORMReal = orm.mapped_column(
        Decimal6,
        CheckConstraint(
            "amount != 0",
            "transaction_split.amount must be non-zero",
        ),
    )
    payee: ORMStrOpt
    memo: ORMStrOpt
    tag: ORMStrOpt

    text_fields: ORMStrOpt

    category_id: ORMInt = orm.mapped_column(ForeignKey("transaction_category.id_"))

    parent_id: ORMInt = orm.mapped_column(ForeignKey("transaction.id_"))
    date_ord: ORMInt
    month_ord: ORMInt
    locked: ORMBool
    linked: ORMBool
    account_id: ORMInt = orm.mapped_column(ForeignKey("account.id_"))

    asset_id: ORMIntOpt = orm.mapped_column(ForeignKey("asset.id_"))
    asset_quantity: ORMRealOpt = orm.mapped_column(Decimal9)
    _asset_qty_unadjusted: ORMRealOpt = orm.mapped_column(Decimal9)

    __table_args__ = (
        *string_column_args("payee"),
        *string_column_args("memo"),
        *string_column_args("tag"),
        *string_column_args("text_fields"),
        CheckConstraint(
            "(asset_quantity IS NOT NULL) == (_asset_qty_unadjusted IS NOT NULL)",
            name="asset_quantity and unadjusted must be same null state",
        ),
    )

    @orm.validates("payee", "memo", "tag", "text_fields")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validates string fields satisfy constraints."""
        return self.clean_strings(key, field, short_check=key != "ticker")

    @orm.validates("amount", "asset_quantity", "_asset_qty_unadjusted")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validates decimal fields satisfy constraints."""
        return self.clean_decimals(key, field)

    @override
    def __setattr__(self, name: str, value: object) -> None:
        if name in [
            "parent_id",
            "date_ord",
            "month_ord",
            "payee",
            "locked",
            "linked",
            "account_id",
        ]:
            msg = (
                "Call TransactionSplit.parent = Transaction. "
                "Do not set parent properties directly"
            )
            raise exc.ParentAttributeError(msg)
        if name == "asset_quantity":
            msg = (
                "Call TransactionSplit.asset_quantity_unadjusted = x. "
                "Do not set property directly"
            )
            raise exc.ComputedColumnError(msg)
        if name == "text_fields":
            msg = (
                "TransactionSplit.text_fields set automatically. "
                "Do not set property directly"
            )
            raise exc.ComputedColumnError(msg)

        super().__setattr__(name, value)

        # update text_fields
        if name in ("payee", "memo", "tag"):
            field = [self.payee, self.memo, self.tag]
            text_fields = " ".join(f for f in field if f).lower()
            super().__setattr__("text_fields", text_fields)

    @property
    def asset_quantity_unadjusted(self) -> Decimal | None:
        """Number of units of Asset exchanged.

        Positive indicates Account gained Assets (inflow), unadjusted for splits.
        """
        return self._asset_qty_unadjusted

    @asset_quantity_unadjusted.setter
    def asset_quantity_unadjusted(self, qty: Decimal | None) -> None:
        if qty is None:
            self._asset_qty_unadjusted = None
            super().__setattr__("asset_quantity", None)
            return
        self._asset_qty_unadjusted = qty

        # Also set adjusted quantity with 1x multiplier
        super().__setattr__("asset_quantity", qty)

    def adjust_asset_quantity(self, multiplier: Decimal) -> None:
        """Set adjusted asset quantity.

        Args:
            multiplier: Adjusted = unadjusted * multiplier
        """
        qty = self.asset_quantity_unadjusted
        if qty is None:
            raise exc.NonAssetTransactionError
        super().__setattr__("asset_quantity", qty * multiplier)

    def adjust_asset_quantity_residual(self, residual: Decimal) -> None:
        """Adjust asset quantity from a residual.

        Args:
            residual: Error amount in asset_quantity
        """
        qty = self.asset_quantity
        if qty is None:
            raise exc.NonAssetTransactionError
        super().__setattr__("asset_quantity", qty - residual)

    @property
    def parent(self) -> Transaction:
        """Parent Transaction."""
        s = orm.object_session(self)
        if s is None:
            raise exc.UnboundExecutionError
        query = s.query(Transaction).where(Transaction.id_ == self.parent_id)
        return query.one()

    @parent.setter
    def parent(self, parent: Transaction) -> None:
        if parent.id_ is None:
            self._parent_tmp = parent
            return
        super().__setattr__("parent_id", parent.id_)
        super().__setattr__("date_ord", parent.date_ord)
        super().__setattr__("month_ord", parent.month_ord)
        super().__setattr__("payee", parent.payee)
        super().__setattr__("locked", parent.locked)
        super().__setattr__("linked", parent.linked)
        super().__setattr__("account_id", parent.account_id)

    @classmethod
    def search(
        cls,
        query: orm.Query[TransactionSplit],
        search_str: str,
        category_names: dict[int, str] | None = None,
    ) -> list[int] | None:
        """Search TransactionSplit text fields.

        Args:
            query: Original query, could be partially filtered
            search_str: String to search
            category_names: Provide category_names to save an extra query

        Returns:
            Ordered list of matches, from best to worst
            or None if search_str is invalid
        """
        # Clean a bit
        for s in string.punctuation:
            if s not in '"+-':
                search_str = search_str.replace(s, " ")
        for s in string.digits:
            search_str = search_str.replace(s, " ")

        # Replace +- not following a space with a space
        # Skip +- at start
        search_str = re.sub(r"(?<!^)(?<! )[+-]", " ", search_str)

        search_str = search_str.strip().lower()

        if len(search_str) < utils.MIN_STR_LEN:
            return None

        # If unbalanced quote, remove right most one
        n = search_str.count('"')
        if (n % 2) == 1:
            i = search_str.rfind('"')
            search_str = search_str[:i] + search_str[i + 1 :]

        # tokenize search_str
        tokens_must: set[str] = set()
        tokens_can: set[str] = set()
        tokens_not: set[str] = set()

        for raw in shlex.split(search_str):
            if raw[0] == "+":
                dest = tokens_must
                token = raw[1:]
            elif raw[0] == "-":
                dest = tokens_not
                token = raw[1:]
            else:
                dest = tokens_can
                token = raw

            token = re.sub(r"  +", " ", token.strip())
            if token:
                dest.add(token)

        category_names = category_names or TransactionCategory.map_name(query.session)

        # Add tokens_must as an OR for each
        for token in tokens_must:
            clauses_or: list[sqlalchemy.ColumnExpressionArgument] = []
            categories = {
                cat_id
                for cat_id, cat_name in category_names.items()
                if token in cat_name
            }
            if categories:
                clauses_or.append(TransactionSplit.category_id.in_(categories))
            clauses_or.append(TransactionSplit.text_fields.ilike(f"%{token}%"))
            query = query.where(sqlalchemy.or_(*clauses_or))

        # Add tokens_not as an NAND for each
        for token in tokens_not:
            categories = {
                cat_id
                for cat_id, cat_name in category_names.items()
                if token in cat_name
            }
            if categories:
                query = query.where(TransactionSplit.category_id.not_in(categories))
            query = query.where(TransactionSplit.text_fields.not_ilike(f"%{token}%"))

        query_modified = query.with_entities(
            TransactionSplit.id_,
            TransactionSplit.date_ord,
            TransactionSplit.category_id,
            TransactionSplit.text_fields,
        ).order_by(None)

        full_texts: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for (
            t_id,
            date_ord,
            cat_id,
            text_fields,
        ) in query_modified.yield_per(YIELD_PER):
            t_id: int
            date_ord: int
            cat_id: int
            text_fields: str | None

            full_text = f"{category_names[cat_id]} {text_fields or ''}"

            # Clean a bit
            for s in string.punctuation:
                full_text = full_text.replace(s, "")
            for s in string.digits:
                full_text = full_text.replace(s, "")

            full_texts[full_text].append((t_id, date_ord))

        # Flatten into list[id, n token matches, date_ord]
        matches: list[tuple[int, int, int]] = []
        for full_text, ids in full_texts.items():
            # No tokens_can should return all so set n to non-zero
            n = sum(full_text.count(token) for token in tokens_can) if tokens_can else 1
            if n != 0:
                for t_id, date_ord in ids:
                    matches.append((t_id, n, date_ord))

        # Sort by n token matches then date
        matches = sorted(matches, key=lambda item: (item[1], item[2]), reverse=True)
        return [item[0] for item in matches]


@event.listens_for(TransactionSplit, "before_insert")
def before_insert_transaction_split(
    mapper: orm.Mapper,  # noqa: ARG001
    connection: sqlalchemy.Connection,  # noqa: ARG001
    target: TransactionSplit,
) -> None:
    """Handle event before insert of TransactionSplit.

    Args:
        mapper: Unused
        connection: Unused
        target: TransactionSplit being inserted
    """
    # If TransactionSplit has parent_tmp set, move it to real parent
    if hasattr(target, "_parent_tmp"):
        target.parent = target._parent_tmp  # noqa: SLF001
        delattr(target, "_parent_tmp")


class Transaction(Base):
    """Transaction model for storing an exchange of cash for an asset (or none).

    Every Transaction has at least one TransactionSplit.

    Attributes:
        id: Transaction unique identifier
        uri: Transaction unique identifier
        account: Account that owns this Transaction
        date_ord: Date ordinal on which Transaction occurred
        amount: Amount amount of cash exchanged. Positive indicated Account
            increases in value (inflow)
        statement: Text appearing on Account statement
        payee: Name of payee (for outflow)/payer (for inflow)
        locked: True only allows manually editing, False allows automatic changes
            (namely auto labeling field based on similar Transactions)
        linked: True when transaction has been imported from a bank source, False
            indicates transaction was manually created
        splits: List of TransactionSplits
    """

    __table_id__ = 0x00000000

    account_id: ORMInt = orm.mapped_column(ForeignKey("account.id_"))

    date_ord: ORMInt
    month_ord: ORMInt
    amount: ORMReal = orm.mapped_column(Decimal6)
    statement: ORMStr
    payee: ORMStrOpt
    locked: ORMBool = orm.mapped_column(default=False)
    linked: ORMBool = orm.mapped_column(default=False)

    similar_txn_id: ORMIntOpt = orm.mapped_column(ForeignKey("transaction.id_"))

    splits: orm.Mapped[list[TransactionSplit]] = orm.relationship()

    __table_args__ = (
        *string_column_args("statement"),
        *string_column_args("payee"),
        CheckConstraint(
            "linked or not locked",
            "Transaction cannot be locked until linked",
        ),
    )

    @orm.validates("statement", "payee")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validates string fields satisfy constraints."""
        return self.clean_strings(key, field, short_check=key != "ticker")

    @orm.validates("amount")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validates decimal fields satisfy constraints."""
        return self.clean_decimals(key, field)

    @property
    def date(self) -> datetime.date:
        """Date on which Transaction occurred."""
        return datetime.date.fromordinal(self.date_ord)

    @date.setter
    def date(self, d: datetime.date) -> None:
        """Set date of Transaction."""
        self.date_ord = d.toordinal()
        self.month_ord = utils.start_of_month(d).toordinal()
