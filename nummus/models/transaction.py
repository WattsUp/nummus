"""Account model for storing a financial account."""

from __future__ import annotations

import datetime
import operator
import re
import string
from collections import defaultdict
from typing import override, TYPE_CHECKING

import sqlalchemy
from rapidfuzz import process
from sqlalchemy import CheckConstraint, event, ForeignKey, Index, orm

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
from nummus.models.label import Label, LabelLink
from nummus.models.transaction_category import TransactionCategory
from nummus.models.utils import obj_session

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy import Row


class TransactionSplit(Base):
    """TransactionSplit model for storing an exchange of cash for an asset (or none).

    Every Transaction has at least one TransactionSplit.

    Attributes:
        id: TransactionSplit unique identifier
        uri: TransactionSplit unique identifier
        amount: Amount amount of cash exchanged. Positive indicated Account
            increases in value (inflow)
        memo: Memo of exchange
        text_fields: Join of all text fields for searching
        category: Type of Transaction
        parent: Parent Transaction
        date_ord: Date ordinal on which Transaction occurred
        cleared: True when transaction has been imported from a bank source, False
            indicates transaction was manually created
        account: Account that owns this Transaction
        asset: Asset exchanged for cash, primarily for instrument transactions
        asset_quantity: Number of units of Asset exchanged, Positive indicates
            Account gained Assets (inflow)

    """

    __tablename__ = "transaction_split"
    __table_id__ = 0x00000000

    amount: ORMReal = orm.mapped_column(Decimal6)
    payee: ORMStrOpt
    memo: ORMStrOpt

    text_fields: ORMStrOpt

    category_id: ORMInt = orm.mapped_column(ForeignKey("transaction_category.id_"))

    parent_id: ORMInt = orm.mapped_column(ForeignKey("transaction.id_"))
    date_ord: ORMInt
    month_ord: ORMInt
    cleared: ORMBool
    account_id: ORMInt = orm.mapped_column(ForeignKey("account.id_"))

    asset_id: ORMIntOpt = orm.mapped_column(ForeignKey("asset.id_"))
    asset_quantity: ORMRealOpt = orm.mapped_column(Decimal9)
    _asset_qty_unadjusted: ORMRealOpt = orm.mapped_column(Decimal9)

    __table_args__ = (
        *string_column_args("payee"),
        *string_column_args("memo"),
        *string_column_args("text_fields"),
        CheckConstraint(
            "(asset_quantity IS NOT NULL) == (_asset_qty_unadjusted IS NOT NULL)",
            name="asset_quantity and unadjusted must be same null state",
        ),
        CheckConstraint(
            "amount != 0",
            "transaction_split.amount must be non-zero",
        ),
        Index("transaction_split_category_id", "category_id"),
        Index("transaction_split_parent_id", "parent_id"),
        Index("transaction_split_account_id", "account_id"),
        Index("transaction_split_asset_id", "asset_id"),
        Index("transaction_split_date_ord", "date_ord"),
    )

    @orm.validates("payee", "memo", "text_fields")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validate string fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_strings(key, field)

    @orm.validates("amount", "asset_quantity", "_asset_qty_unadjusted")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validate decimal fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_decimals(key, field)

    @override
    def __setattr__(self, name: str, value: object) -> None:
        if name in {
            "parent_id",
            "date_ord",
            "month_ord",
            "payee",
            "cleared",
            "account_id",
        }:
            msg = (
                "Call TransactionSplit.parent = Transaction. "
                f"Do not set parent property '{name}' directly"
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
        if name == "memo":
            self._update_text_fields()

    def _update_text_fields(self) -> None:
        """Update text_fields."""
        field = [self.payee, self.memo]
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

        Raises:
            NonAssetTransactionError: If transaction does not have
                asset_quantity_unadjusted

        """
        qty = self.asset_quantity_unadjusted
        if qty is None:
            raise exc.NonAssetTransactionError
        super().__setattr__("asset_quantity", qty * multiplier)

    def adjust_asset_quantity_residual(self, residual: Decimal) -> None:
        """Adjust asset quantity from a residual.

        Args:
            residual: Error amount in asset_quantity

        Raises:
            NonAssetTransactionError: If transaction does not have
                asset_quantity_unadjusted

        """
        qty = self.asset_quantity
        if qty is None:
            raise exc.NonAssetTransactionError
        super().__setattr__("asset_quantity", qty - residual)

    @property
    def parent(self) -> Transaction:
        """Parent Transaction."""
        s = obj_session(self)
        query = s.query(Transaction).where(Transaction.id_ == self.parent_id)
        return query.one()

    @parent.setter
    def parent(self, parent: Transaction) -> None:
        if parent.id_ is None:
            self.parent_tmp = parent
            return
        super().__setattr__("parent_id", parent.id_)
        super().__setattr__("date_ord", parent.date_ord)
        super().__setattr__("month_ord", parent.month_ord)
        super().__setattr__("payee", parent.payee)
        super().__setattr__("cleared", parent.cleared)
        super().__setattr__("account_id", parent.account_id)
        self._update_text_fields()

    @property
    def date(self) -> datetime.date:
        """Date on which Transaction occurred."""
        return datetime.date.fromordinal(self.date_ord)

    @classmethod
    def search(
        cls,
        query: orm.Query[TransactionSplit],
        search_str: str,
        category_names: dict[int, str] | None = None,
        label_names: dict[int, str] | None = None,
    ) -> list[int]:
        """Search TransactionSplit text fields.

        Args:
            query: Original query, could be partially filtered
            search_str: String to search
            category_names: Provide category_names to save an extra query
            label_names: Provide label_names to save an extra query

        Returns:
            Ordered list of matches, from best to worst

        """
        query = query.join(LabelLink, full=True)
        tokens_must, tokens_can, tokens_not = utils.tokenize_search_str(search_str)

        category_names = category_names or TransactionCategory.map_name(query.session)
        label_names = label_names or Label.map_name(query.session)
        label_names = {k: v.lower() for k, v in label_names.items()}

        query = cls._search_must(query, tokens_must, category_names, label_names)
        query = cls._search_not(query, tokens_not, category_names, label_names)

        sub_query = query.with_entities(TransactionSplit.id_).scalar_subquery()
        query_modified = (
            query.session.query(LabelLink)
            .with_entities(LabelLink.t_split_id, LabelLink.label_id)
            .where(LabelLink.t_split_id.in_(sub_query))
        )
        split_labels: dict[int, set[int]] = defaultdict(set)
        for t_split_id, label_id in query_modified.yield_per(YIELD_PER):
            split_labels[t_split_id].add(label_id)

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

            full_text = f"{category_names[cat_id]} {text_fields or ''} " + " ".join(
                label_names[label_id] for label_id in split_labels[t_id]
            )

            # Clean a bit
            for s in string.punctuation:
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
        matches = sorted(matches, key=operator.itemgetter(1, 2), reverse=True)
        return [item[0] for item in matches]

    @classmethod
    def _search_must(
        cls,
        query: orm.Query[TransactionSplit],
        tokens_must: set[str],
        category_names: dict[int, str],
        label_names: dict[int, str],
    ) -> orm.Query[TransactionSplit]:
        # Add tokens_must as an OR for each category and text_fields
        for token in tokens_must:
            clauses_or: list[sqlalchemy.ColumnExpressionArgument] = []
            categories = {
                cat_id
                for cat_id, cat_name in category_names.items()
                if token in cat_name
            }
            if categories:
                clauses_or.append(TransactionSplit.category_id.in_(categories))
            labels = {
                label_id
                for label_id, label_name in label_names.items()
                if token in label_name
            }
            if labels:
                clauses_or.append(LabelLink.label_id.in_(labels))
            clauses_or.append(TransactionSplit.text_fields.ilike(f"%{token}%"))
            query = query.where(sqlalchemy.or_(*clauses_or))
        return query

    @classmethod
    def _search_not(
        cls,
        query: orm.Query[TransactionSplit],
        tokens_not: set[str],
        category_names: dict[int, str],
        label_names: dict[int, str],
    ) -> orm.Query[TransactionSplit]:
        # Add tokens_not as an NAND for each category and text_fields
        for token in tokens_not:
            categories = {
                cat_id
                for cat_id, cat_name in category_names.items()
                if token in cat_name
            }
            if categories:
                query = query.where(TransactionSplit.category_id.not_in(categories))
            labels = {
                label_id
                for label_id, label_name in label_names.items()
                if token in label_name
            }
            if labels:
                query = query.where(
                    LabelLink.label_id.not_in(labels) | LabelLink.label_id.is_(None),
                )
            query = query.where(TransactionSplit.text_fields.not_ilike(f"%{token}%"))
        return query


@event.listens_for(TransactionSplit, "before_insert")
def before_insert_transaction_split(
    _: orm.Mapper,
    __: sqlalchemy.Connection,
    target: TransactionSplit,
) -> None:
    """Handle event before insert of TransactionSplit.

    Args:
        mapper: Unused
        connection: Unused
        target: TransactionSplit being inserted

    """
    # If TransactionSplit has parent_tmp set, move it to real parent
    if hasattr(target, "parent_tmp"):
        target.parent = target.parent_tmp
        delattr(target, "parent_tmp")


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
        cleared: True when transaction has been imported from a bank source, False
            indicates transaction was manually created
        splits: List of TransactionSplits

    """

    __tablename__ = "transaction"
    __table_id__ = 0x00000000

    account_id: ORMInt = orm.mapped_column(ForeignKey("account.id_"))

    date_ord: ORMInt
    month_ord: ORMInt
    amount: ORMReal = orm.mapped_column(Decimal6)
    statement: ORMStr
    payee: ORMStrOpt
    cleared: ORMBool = orm.mapped_column(default=False)

    similar_txn_id: ORMIntOpt = orm.mapped_column(ForeignKey("transaction.id_"))

    splits: orm.Mapped[list[TransactionSplit]] = orm.relationship()

    __table_args__ = (
        *string_column_args("statement"),
        *string_column_args("payee"),
        Index("transaction_account_id", "account_id"),
        Index("transaction_date_ord", "date_ord"),
    )

    @orm.validates("statement", "payee")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validate string fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_strings(key, field)

    @orm.validates("amount")
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

    @date.setter
    def date(self, d: datetime.date) -> None:
        """Set date of Transaction."""
        self.date_ord = d.toordinal()
        self.month_ord = utils.start_of_month(d).toordinal()

    def find_similar(
        self,
        *,
        cache_ok: bool = True,
        set_property: bool = True,
    ) -> int | None:
        """Find the most similar Transaction.

        Args:
            cache_ok: If available, use Transaction.similar_txn_id
            set_property: If match found, set similar_txn_id

        Returns:
            Most similar Transaction.id_

        """
        s = obj_session(self)

        if cache_ok and self.similar_txn_id is not None:
            return self.similar_txn_id

        # Similar transaction must be within this range
        amount_min = min(
            self.amount * (1 - utils.MATCH_PERCENT),
            self.amount - utils.MATCH_ABSOLUTE,
        )
        amount_max = max(
            self.amount * (1 + utils.MATCH_PERCENT),
            self.amount + utils.MATCH_ABSOLUTE,
        )

        def set_match(matching_row: int | Row[tuple[int]]) -> int:
            id_ = matching_row if isinstance(matching_row, int) else matching_row[0]
            if set_property:
                self.similar_txn_id = id_
                s.flush()
            return id_

        # Convert txn.amount to the raw SQL value to make a raw query
        amount_raw = Transaction.amount.type.process_bind_param(self.amount, None)
        sort_closest_amount = sqlalchemy.text(f"abs({amount_raw} - amount)")

        cat_asset_linked = {
            t_cat_id
            for t_cat_id, in (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.asset_linked.is_(True))
                .all()
            )
        }

        # Check within Account first, exact matches
        # If this matches, great, no post filtering needed
        query = (
            s.query(Transaction.id_)
            .where(
                Transaction.account_id == self.account_id,
                Transaction.id_ != self.id_,
                Transaction.amount >= amount_min,
                Transaction.amount <= amount_max,
                Transaction.statement == self.statement,
            )
            .order_by(sort_closest_amount)
        )
        row = query.first()
        if row is not None:
            return set_match(row)

        # Maybe exact statement but different account
        query = (
            s.query(Transaction.id_)
            .where(
                Transaction.id_ != self.id_,
                Transaction.amount >= amount_min,
                Transaction.amount <= amount_max,
                Transaction.statement == self.statement,
            )
            .order_by(sort_closest_amount)
        )
        row = query.first()
        if row is not None:
            return set_match(row)

        # Maybe exact statement but different amount
        query = (
            s.query(Transaction.id_)
            .where(
                Transaction.id_ != self.id_,
                Transaction.statement == self.statement,
            )
            .order_by(sort_closest_amount)
        )
        row = query.first()
        if row is not None:
            return set_match(row)

        # No statements match, choose highest fuzzy matching statement
        query = (
            s.query(Transaction)
            .with_entities(
                Transaction.id_,
                Transaction.statement,
            )
            .where(
                Transaction.id_ != self.id_,
                Transaction.amount >= amount_min,
                Transaction.amount <= amount_max,
            )
            .order_by(sort_closest_amount)
        )
        statements: dict[int, str] = {
            t_id: re.sub(r"[0-9]+", "", statement).lower()
            for t_id, statement in query.yield_per(YIELD_PER)
        }
        if len(statements) == 0:
            return None
        # Don't match a Transaction if it has a Securities Traded split
        has_asset_linked = {
            id_
            for id_, in (
                s.query(TransactionSplit.parent_id)
                .where(
                    TransactionSplit.parent_id.in_(statements),
                    TransactionSplit.category_id.in_(cat_asset_linked),
                )
                .distinct()
            )
        }
        statements = {
            t_id: statement
            for t_id, statement in statements.items()
            if t_id not in has_asset_linked
        }
        if len(statements) == 0:
            return None
        extracted = process.extract(
            re.sub(r"[0-9]+", "", self.statement).lower(),
            statements,
            limit=None,
            score_cutoff=utils.SEARCH_THRESHOLD,
        )
        # There are transactions with similar amounts but not close statement
        # Return the closest in amount and account
        # Aka proceed with all matches
        matches = (
            dict.fromkeys(statements, 50)
            if len(extracted) == 0
            else {t_id: score for _, score, t_id in extracted}
        )

        # Add a bonuse points for closeness in price and same account
        query = (
            s.query(Transaction)
            .with_entities(
                Transaction.id_,
                Transaction.account_id,
                Transaction.amount,
            )
            .where(Transaction.id_.in_(matches))
        )
        matches_bonus: dict[int, float] = {}
        for t_id, acct_id, amount in query.yield_per(YIELD_PER):
            # 5% off will reduce score by 5%
            amount_diff_percent = abs(amount - self.amount) / self.amount
            # Extra 10 points for same account
            score = matches[t_id] * float(1 - amount_diff_percent) + (
                10 if acct_id == self.account_id else 0
            )
            matches_bonus[t_id] = score

        # Sort by best score and return best id
        best_id = min(matches_bonus.items(), key=lambda item: -item[1])[0]
        return set_match(best_id)
