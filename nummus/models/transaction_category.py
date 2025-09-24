"""Transaction Category model for storing a type of Transaction."""

from __future__ import annotations

from typing import NamedTuple, override

from sqlalchemy import CheckConstraint, ForeignKey, orm, UniqueConstraint

from nummus import exceptions as exc
from nummus.models.base import (
    Base,
    BaseEnum,
    ORMBool,
    ORMIntOpt,
    ORMStr,
    SQLEnum,
    string_column_args,
)
from nummus.models.utils import query_to_dict


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
        emoji_name: Name with optional emojis
        group: Type of category
        locked: True will prevent any changes being made, okay to change emoji
        is_profit_loss: True will include category in profit loss calculations
        essential_spending: True indicates category is included in an emergency budget
        asset_linked: True expects transactions to be linked to an Asset
        budget_group: Name of group in budget category is a part of
        budget_position: Position on budget page where category is located

    """

    __tablename__ = "transaction_category"
    __table_id__ = 0x00000000

    name: ORMStr = orm.mapped_column(unique=True)
    emoji_name: ORMStr
    group: orm.Mapped[TransactionCategoryGroup] = orm.mapped_column(
        SQLEnum(TransactionCategoryGroup),
    )
    locked: ORMBool
    is_profit_loss: ORMBool
    asset_linked: ORMBool
    essential_spending: ORMBool

    budget_group_id: ORMIntOpt = orm.mapped_column(ForeignKey("budget_group.id_"))
    budget_position: ORMIntOpt

    __table_args__ = (
        *string_column_args("name", lower_check=True),
        *string_column_args("emoji_name"),
        CheckConstraint(
            "not essential_spending OR `group` != "
            f"{TransactionCategoryGroup.INCOME.value}",
            name="INCOME cannot be essential spending",
        ),
        CheckConstraint(
            "(budget_group_id IS NOT NULL) == (budget_position IS NOT NULL)",
            name="group and position same null state",
        ),
        UniqueConstraint("budget_group_id", "budget_position"),
    )

    @override
    def __setattr__(self, name: str, value: object) -> None:
        if name == "name":
            msg = "Call TransactionSplit.emoji_name = x. Do not set name directly"
            raise exc.ParentAttributeError(msg)
        if name == "emoji_name" and isinstance(value, str):
            super().__setattr__("name", self.clean_emoji_name(value))
        super().__setattr__(name, value)

    @orm.validates("name", "emoji_name")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validate string fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_strings(key, field)

    @orm.validates("essential_spending")
    def validate_essential_spending(self, _: str, field: object) -> bool:
        """Validate income groups are not marked essential_spending.

        Args:
            field: Updated value

        Returns:
            field

        Raises:
            InvalidORMValueError: If field is essential_spending
            TypeError: If field is not bool

        """
        if not isinstance(field, bool):
            msg = f"field is not of type bool: {type(field)}"
            raise TypeError(msg)
        if field and self.group in {
            TransactionCategoryGroup.INCOME,
            TransactionCategoryGroup.OTHER,
        }:
            msg = f"{self.group.name.capitalize()} cannot be essential spending"
            raise exc.InvalidORMValueError(msg)
        return field

    @staticmethod
    def add_default(s: orm.Session) -> dict[str, TransactionCategory]:
        """Create default transaction categories.

        Args:
            s: SQL session to use

        Returns:
            Dictionary {name: category}

        """
        d: dict[str, TransactionCategory] = {}

        class Spec(NamedTuple):
            locked: bool = False
            is_profit_loss: bool = False
            asset_linked: bool = False
            essential_spending: bool = False

        groups: dict[TransactionCategoryGroup, dict[str, Spec]] = {
            TransactionCategoryGroup.INCOME: {
                "Consulting": Spec(),
                "Deposits": Spec(),
                "Dividends Received": Spec(
                    locked=True,
                    is_profit_loss=True,
                    asset_linked=True,
                ),
                "Interest": Spec(locked=True, is_profit_loss=True),
                "Investment Income": Spec(),
                "Other Income": Spec(),
                "Paychecks/Salary": Spec(),
                "Refunds & Reimbursements": Spec(),
                "Retirement Contributions": Spec(locked=True),
                "Retirement Income": Spec(),
                "Rewards Redemption": Spec(is_profit_loss=True),
                "Sales": Spec(),
                "Services": Spec(),
            },
            TransactionCategoryGroup.EXPENSE: {
                "Advertising": Spec(),
                "Advisory Fee": Spec(),
                "ATM/Cash": Spec(),
                "Automotive": Spec(),
                "Business Miscellaneous": Spec(),
                "Charitable Giving": Spec(),
                "Child/Dependent": Spec(),
                "Clothing/Shoes": Spec(),
                "Dues & Subscriptions": Spec(),
                "Education": Spec(),
                "Electronics": Spec(),
                "Entertainment": Spec(),
                "Gasoline/Fuel": Spec(),
                "General Merchandise": Spec(),
                "Gifts": Spec(),
                "Groceries": Spec(),
                "Healthcare/Medical": Spec(),
                "Hobbies": Spec(),
                "Home Improvement": Spec(),
                "Home Maintenance": Spec(),
                "Insurance": Spec(),
                "Investment Fees": Spec(
                    locked=True,
                    is_profit_loss=True,
                    asset_linked=True,
                ),
                "Mortgages": Spec(),
                "Office Maintenance": Spec(),
                "Office Supplies": Spec(),
                "Other Bills": Spec(),
                "Other Expenses": Spec(),
                "Personal Care": Spec(),
                "Pets/Pet Care": Spec(),
                "Postage & Shipping": Spec(),
                "Printing": Spec(),
                "Rent": Spec(),
                "Restaurants": Spec(),
                "Service Charge/Fees": Spec(),
                "Taxes": Spec(),
                "Telephone": Spec(),
                "Travel": Spec(),
                "Utilities": Spec(),
                "Wages Paid": Spec(),
            },
            TransactionCategoryGroup.TRANSFER: {
                "Credit Card Payments": Spec(locked=True),
                "Expense Reimbursement": Spec(),
                "Emergency Fund": Spec(locked=True),
                "General Rebalance": Spec(),
                "Portfolio Management": Spec(),
                "Savings": Spec(locked=True),
                "Transfers": Spec(locked=True),
                "Fraud": Spec(),
            },
            TransactionCategoryGroup.OTHER: {
                "Securities Traded": Spec(
                    locked=True,
                    is_profit_loss=True,
                    asset_linked=True,
                ),
                "Uncategorized": Spec(locked=True),
            },
        }

        for group, categories in groups.items():
            for name, spec in categories.items():
                cat = TransactionCategory(
                    emoji_name=name,
                    group=group,
                    locked=spec.locked,
                    is_profit_loss=spec.is_profit_loss,
                    asset_linked=spec.asset_linked,
                    essential_spending=spec.essential_spending,
                )
                s.add(cat)
                d[cat.name] = cat
        return d

    @override
    @classmethod
    def map_name(
        cls,
        s: orm.Session,
        *,
        no_asset_linked: bool = False,
    ) -> dict[int, str]:
        """Get mapping between id and names.

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
        return query_to_dict(query)

    @classmethod
    def map_name_emoji(
        cls,
        s: orm.Session,
        *,
        no_asset_linked: bool = False,
    ) -> dict[int, str]:
        """Get mapping between id and names with emojis.

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
                TransactionCategory.emoji_name,
            )
            .order_by(TransactionCategory.name)
        )
        if no_asset_linked:
            query = query.where(TransactionCategory.asset_linked.is_(False))
        return query_to_dict(query)

    @classmethod
    def _get_protected_id(cls, s: orm.Session, name: str) -> tuple[int, str]:
        """Get the ID and URI of a protected category.

        Args:
            s: SQL session to use
            name: Name of protected category to fetch

        Returns:
            tuple(id_, URI)

        Raises:
            ProtectedObjectNotFoundError: If not found

        """
        try:
            id_ = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == name)
                .one()[0]
            )
        except exc.NoResultFound as e:
            msg = f"Category {name} not found"
            raise exc.ProtectedObjectNotFoundError(msg) from e
        return id_, cls.id_to_uri(id_)

    @classmethod
    def uncategorized(cls, s: orm.Session) -> tuple[int, str]:
        """Get the ID and URI of the uncategorized category.

        Args:
            s: SQL session to use

        Returns:
            tuple(id_, URI)

        Raises:
            ProtectedObjectNotFound if not found

        """
        return cls._get_protected_id(s, "uncategorized")

    @classmethod
    def emergency_fund(cls, s: orm.Session) -> tuple[int, str]:
        """Get the ID and URI of the emergency fund category.

        Args:
            s: SQL session to use

        Returns:
            tuple(id_, URI)

        Raises:
            ProtectedObjectNotFound if not found

        """
        return cls._get_protected_id(s, "emergency fund")

    @classmethod
    def securities_traded(cls, s: orm.Session) -> tuple[int, str]:
        """Get the ID and URI of the securities traded category.

        Args:
            s: SQL session to use

        Returns:
            tuple(id_, URI)

        Raises:
            ProtectedObjectNotFound if not found

        """
        return cls._get_protected_id(s, "securities traded")
