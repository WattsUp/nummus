"""Transaction Category model for storing a type of Transaction."""

from __future__ import annotations

import emoji as emoji_mod
import sqlalchemy
from sqlalchemy import orm
from typing_extensions import override

from nummus import exceptions as exc
from nummus import utils
from nummus.models.base import Base, BaseEnum, ORMBool, ORMIntOpt, ORMStr, ORMStrOpt


class TransactionCategoryGroup(BaseEnum):
    """Types of Transaction Categories."""

    INCOME = 1
    EXPENSE = 2
    TRANSFER = 3
    OTHER = 4


class TransactionCategory(Base):
    """Categories of Transactions.

    Attributes:
        id: TransactionCategory unique identifier
        uri: TransactionCategory unique identifier
        name: Name of category
        emoji: Emoji(s) to prepend to name
        group: Type of category
        locked: True will prevent any changes being made, okay to change emoji
        is_profit_loss: True will include category in profit loss calculations
        asset_linked: True expects transactions to be linked to an Asset
        budget_group: Name of group in budget category is a part of
        budget_position: Position on budget page where category is located
    """

    __table_id__ = 0x70000000

    name: ORMStr = orm.mapped_column(unique=True)
    emoji: ORMStrOpt
    group: orm.Mapped[TransactionCategoryGroup]
    locked: ORMBool
    is_profit_loss: ORMBool
    asset_linked: ORMBool
    essential: ORMBool

    budget_group: ORMStrOpt
    budget_position: ORMIntOpt

    __table_args__ = (
        sqlalchemy.CheckConstraint(
            "(budget_group IS NOT NULL) == (budget_position IS NOT NULL)",
            name="group and position same null state",
        ),
    )

    @orm.validates("name")
    def validate_name(self, _: str, field: str | None) -> str | None:
        """Validates name is long enough and doesn't contains emojis.

        Args:
            field: Updated value

        Returns:
            field

        Raises:
            InvalidORMValueError if field is too short
        """
        if field is None or field in ["", "[blank]"]:
            return None
        if emoji_mod.emoji_count(field) > 0:
            msg = "Transaction category name must not have emojis"
            raise exc.InvalidORMValueError(msg)
        if len(field) < utils.MIN_STR_LEN:
            msg = (
                "Transaction category name must be at least "
                f"{utils.MIN_STR_LEN} characters long"
            )
            raise exc.InvalidORMValueError(msg)
        return field

    @orm.validates("emoji")
    def validate_emoji(self, _: str, field: str | None) -> str | None:
        """Validate emoji contains exactly one emoji.

        Args:
            field: Updated value

        Returns:
            field

        Raises:
            InvalidORMValueError if field is not a single emoji
        """
        if field is None or field in ["", "[blank]"]:
            return None
        if not emoji_mod.purely_emoji(field):
            msg = "Transaction category emoji must only be emojis"
            raise exc.InvalidORMValueError(msg)
        return field

    @orm.validates("essential")
    def validate_essential(self, _: str, field: bool | None) -> bool | None:
        """Validates income groups are not marked essential.

        Args:
            field: Updated value

        Returns:
            field

        Raises:
            InvalidORMValueError if field is essential
        """
        if (
            self.group
            in (TransactionCategoryGroup.INCOME, TransactionCategoryGroup.OTHER)
            and field
        ):
            msg = f"{self.group.name.capitalize()} cannot be essential"
            raise exc.InvalidORMValueError(msg)
        return field

    @property
    def emoji_name(self) -> str:
        """Name of category with emoji."""
        return f"{self.emoji} {self.name}" if self.emoji else self.name

    @staticmethod
    def add_default(s: orm.Session) -> dict[str, TransactionCategory]:
        """Create default transaction categories.

        Args:
            s: SQL session to use

        Returns:
            Dictionary {name: category}
        """
        d: dict[str, TransactionCategory] = {}
        # Dictionary {group: {name: (locked, is_profit_loss, asset_linked)}}
        # TODO (WattsUp): Add emojis and update default categories
        groups = {
            TransactionCategoryGroup.INCOME: {
                "Consulting": (False, False, False),
                "Deposits": (False, False, False),
                "Dividends Received": (True, True, True),
                "Interest": (True, True, False),
                "Investment Income": (False, False, False),
                "Other Income": (False, False, False),
                "Paychecks/Salary": (False, False, False),
                "Refunds & Reimbursements": (False, False, False),
                "Retirement Contributions": (True, False, False),
                "Retirement Income": (False, False, False),
                "Rewards Redemption": (False, True, False),
                "Sales": (False, False, False),
                "Services": (False, False, False),
            },
            TransactionCategoryGroup.EXPENSE: {
                "Advertising": (False, False, False),
                "Advisory Fee": (False, False, False),
                "ATM/Cash": (False, False, False),
                "Automotive": (False, False, False),
                "Business Miscellaneous": (False, False, False),
                "Charitable Giving": (False, False, False),
                "Child/Dependent": (False, False, False),
                "Clothing/Shoes": (False, False, False),
                "Dues & Subscriptions": (False, False, False),
                "Education": (False, False, False),
                "Electronics": (False, False, False),
                "Entertainment": (False, False, False),
                "Gasoline/Fuel": (False, False, False),
                "General Merchandise": (False, False, False),
                "Gifts": (False, False, False),
                "Groceries": (False, False, False),
                "Healthcare/Medical": (False, False, False),
                "Hobbies": (False, False, False),
                "Home Improvement": (False, False, False),
                "Home Maintenance": (False, False, False),
                "Insurance": (False, False, False),
                "Investment Fees": (True, True, True),
                "Mortgages": (False, False, False),
                "Office Maintenance": (False, False, False),
                "Office Supplies": (False, False, False),
                "Other Bills": (False, False, False),
                "Other Expenses": (False, False, False),
                "Personal Care": (False, False, False),
                "Pets/Pet Care": (False, False, False),
                "Postage & Shipping": (False, False, False),
                "Printing": (False, False, False),
                "Rent": (False, False, False),
                "Restaurants": (False, False, False),
                "Service Charge/Fees": (False, False, False),
                "Taxes": (False, False, False),
                "Telephone": (False, False, False),
                "Travel": (False, False, False),
                "Utilities": (False, False, False),
                "Wages Paid": (False, False, False),
            },
            TransactionCategoryGroup.TRANSFER: {
                "Credit Card Payments": (True, False, False),
                "Expense Reimbursement": (False, False, False),
                "General Rebalance": (False, False, False),
                "Portfolio Management": (False, False, False),
                "Savings": (True, False, False),
                "Transfers": (True, False, False),
                "Fraud": (False, False, False),
            },
            TransactionCategoryGroup.OTHER: {
                "Securities Traded": (True, True, True),
                "Uncategorized": (True, False, False),
            },
        }

        for group, categories in groups.items():
            for name, (locked, is_profit_loss, asset_linked) in categories.items():
                cat = TransactionCategory(
                    name=name,
                    group=group,
                    locked=locked,
                    is_profit_loss=is_profit_loss,
                    asset_linked=asset_linked,
                )
                s.add(cat)
                d[name] = cat
        s.commit()
        return d

    @override
    @classmethod
    def map_name(
        cls,
        s: orm.Session,
        *,
        no_asset_linked: bool = False,
    ) -> dict[int, str]:
        """Mapping between id and names.

        Args:
            s: SQL session to use
            no_asset_linked: True will not include asset_linked categories

        Returns:
            Dictionary {id: name}

        Raises:
            KeyError if model does not have name property
        """
        query = (
            s.query(TransactionCategory)
            .with_entities(
                TransactionCategory.id_,
                TransactionCategory.name,
            )
            .order_by(TransactionCategory.name)
        )
        if no_asset_linked:
            query = query.where(TransactionCategory.asset_linked.is_(False))
        return dict(query.all())  # type: ignore[attr-defined]

    @classmethod
    def map_name_emoji(
        cls,
        s: orm.Session,
        *,
        no_asset_linked: bool = False,
    ) -> dict[int, str]:
        """Mapping between id and names with emojis.

        Args:
            s: SQL session to use
            no_asset_linked: True will not include asset_linked categories

        Returns:
            Dictionary {id: name with emoji}

        Raises:
            KeyError if model does not have name property
        """
        query = (
            s.query(TransactionCategory)
            .with_entities(
                TransactionCategory.id_,
                TransactionCategory.name,
                TransactionCategory.emoji,
            )
            .order_by(TransactionCategory.name)
        )
        if no_asset_linked:
            query = query.where(TransactionCategory.asset_linked.is_(False))
        return {
            t_cat_id: (f"{emoji} {name}" if emoji else name)
            for t_cat_id, name, emoji in query.all()
        }
