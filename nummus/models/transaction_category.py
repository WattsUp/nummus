"""Transaction Category model for storing a type of Transaction."""

from __future__ import annotations

import emoji as emoji_mod
import sqlalchemy
from sqlalchemy import orm

from nummus import exceptions as exc
from nummus import utils
from nummus.models.base import Base, BaseEnum, ORMBool, ORMIntOpt, ORMStr, ORMStrOpt


class TransactionCategoryGroup(BaseEnum):
    """Types of Transaction Categories."""

    INCOME = 1
    EXPENSE = 2
    OTHER = 3  # Change to TRANSFER


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
        budget_group: Name of group in budget category is a part of
        budget_position: Position on budget page where category is located
    """

    __table_id__ = 0x70000000

    name: ORMStr = orm.mapped_column(unique=True)
    emoji: ORMStrOpt
    group: orm.Mapped[TransactionCategoryGroup]
    locked: ORMBool
    is_profit_loss: ORMBool

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
        # Dictionary {group: {name: (locked, is_profit_loss)}}
        groups = {
            TransactionCategoryGroup.INCOME: {
                "Consulting": (False, False),
                "Deposits": (False, False),
                "Dividends Received": (True, True),
                "Interest": (True, True),
                "Investment Income": (False, False),
                "Other Income": (False, False),
                "Paychecks/Salary": (False, False),
                "Refunds & Reimbursements": (False, False),
                "Retirement Contributions": (True, False),
                "Retirement Income": (False, False),
                "Rewards Redemption": (False, True),
                "Sales": (False, False),
                "Services": (False, False),
            },
            TransactionCategoryGroup.EXPENSE: {
                "Advertising": (False, False),
                "Advisory Fee": (False, False),
                "ATM/Cash": (False, False),
                "Automotive": (False, False),
                "Business Miscellaneous": (False, False),
                "Charitable Giving": (False, False),
                "Child/Dependent": (False, False),
                "Clothing/Shoes": (False, False),
                "Dues & Subscriptions": (False, False),
                "Education": (False, False),
                "Electronics": (False, False),
                "Entertainment": (False, False),
                "Gasoline/Fuel": (False, False),
                "General Merchandise": (False, False),
                "Gifts": (False, False),
                "Groceries": (False, False),
                "Healthcare/Medical": (False, False),
                "Hobbies": (False, False),
                "Home Improvement": (False, False),
                "Home Maintenance": (False, False),
                "Insurance": (False, False),
                "Investment Fees": (True, True),
                "Mortgages": (False, False),
                "Office Maintenance": (False, False),
                "Office Supplies": (False, False),
                "Other Bills": (False, False),
                "Other Expenses": (False, False),
                "Personal Care": (False, False),
                "Pets/Pet Care": (False, False),
                "Postage & Shipping": (False, False),
                "Printing": (False, False),
                "Rent": (False, False),
                "Restaurants": (False, False),
                "Service Charge/Fees": (False, False),
                "Taxes": (False, False),
                "Telephone": (False, False),
                "Travel": (False, False),
                "Utilities": (False, False),
                "Wages Paid": (False, False),
            },
            TransactionCategoryGroup.OTHER: {
                "Credit Card Payments": (True, False),
                "Expense Reimbursement": (False, False),
                "General Rebalance": (False, False),
                "Portfolio Management": (False, False),
                "Savings": (True, False),
                "Securities Traded": (True, True),
                "Transfers": (True, False),
                "Uncategorized": (True, False),
                "Fraud": (False, False),
            },
        }

        for group, categories in groups.items():
            for name, (locked, is_profit_loss) in categories.items():
                cat = TransactionCategory(
                    name=name,
                    group=group,
                    locked=locked,
                    is_profit_loss=is_profit_loss,
                )
                s.add(cat)
                d[name] = cat
        s.commit()
        return d

    @classmethod
    def map_name_emoji(
        cls,
        s: orm.Session,
        *,
        no_securities_traded: bool = True,
    ) -> dict[int, str]:
        """Mapping between id and names with emojis.

        Args:
            s: SQL session to use
            no_securities_traded: True will not include "Securities Traded"

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
        if no_securities_traded:
            query = query.where(TransactionCategory.name != "Securities Traded")
        return {
            t_cat_id: (f"{emoji} {name}" if emoji else name)
            for t_cat_id, name, emoji in query.all()
        }
