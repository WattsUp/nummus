"""Transaction Category model for storing a type of Transaction."""

from __future__ import annotations

from sqlalchemy import orm
from typing_extensions import override

from nummus import custom_types as t
from nummus.models.base import Base, BaseEnum


class TransactionCategoryGroup(BaseEnum):
    """Types of Transaction Categories."""

    INCOME = 1
    EXPENSE = 2
    OTHER = 3


class TransactionCategory(Base):
    """Categories of Transactions.

    Attributes:
        id: TransactionCategory unique identifier
        uri: TransactionCategory unique identifier
        name: Name of category
        group: Type of category
        locked: True will prevent any changes being made
    """

    __table_id__ = 0x70000000

    name: t.ORMStr = orm.mapped_column(unique=True)
    group: orm.Mapped[TransactionCategoryGroup]
    locked: t.ORMBool
    is_profit_loss: t.ORMBool

    @orm.validates("name")
    @override
    def validate_strings(self, key: str, field: str | None) -> str | None:
        return super().validate_strings(key, field)

    @staticmethod
    def add_default(s: orm.Session) -> dict[str, TransactionCategory]:
        """Create default transaction categories.

        Args:
            s: SQL session to use

        Returns:
            Dictionary {name: category}
        """
        d: dict[str, TransactionCategory] = {}
        groups = {
            TransactionCategoryGroup.INCOME: {
                "Consulting": (False, False),
                "Deposits": (False, False),
                "Dividends Received": (False, False),
                "Interest": (False, True),
                "Investment Income": (False, False),
                "Other Income": (False, False),
                "Paychecks/Salary": (False, False),
                "Refunds & Reimbursements": (False, False),
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
                "Cable/Satellite": (False, False),
                "Charitable Giving": (False, False),
                "Checks": (False, False),
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
                "Investment Fees": (False, True),
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
                "Retirement Contributions": (True, False),
                "Savings": (True, False),
                "Securities Traded": (True, False),
                "Transfers": (True, False),
                "Uncategorized": (True, False),
                "Fraud": (False, False),
                "Loans": (False, False),
            },
        }

        for group, categories in groups.items():
            for name, item in categories.items():
                locked, is_profit_loss = item
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
