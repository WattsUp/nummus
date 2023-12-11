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
                "Consulting": False,
                "Deposits": False,
                "Dividends Received": False,
                "Interest": False,
                "Investment Income": False,
                "Other Income": False,
                "Paychecks/Salary": False,
                "Refunds & Reimbursements": False,
                "Retirement Income": False,
                "Rewards": False,
                "Sales": False,
                "Services": False,
            },
            TransactionCategoryGroup.EXPENSE: {
                "Advertising": False,
                "Advisory Fee": False,
                "ATM/Cash": False,
                "Automotive": False,
                "Business Miscellaneous": False,
                "Cable/Satellite": False,
                "Charitable Giving": False,
                "Checks": False,
                "Child/Dependent": False,
                "Clothing/Shoes": False,
                "Dues & Subscriptions": False,
                "Education": False,
                "Electronics": False,
                "Entertainment": False,
                "Gasoline/Fuel": False,
                "General Merchandise": False,
                "Gifts": False,
                "Groceries": False,
                "Healthcare/Medical": False,
                "Hobbies": False,
                "Home Improvement": False,
                "Home Maintenance": False,
                "Insurance": False,
                "Loans": False,
                "Mortgages": False,
                "Office Maintenance": False,
                "Office Supplies": False,
                "Other Bills": False,
                "Other Expenses": False,
                "Personal Care": False,
                "Pets/Pet Care": False,
                "Postage & Shipping": False,
                "Printing": False,
                "Rent": False,
                "Restaurants": False,
                "Service Charge/Fees": False,
                "Taxes": False,
                "Telephone": False,
                "Travel": False,
                "Utilities": False,
                "Wages Paid": False,
            },
            TransactionCategoryGroup.OTHER: {
                "Credit Card Payments": True,
                "Expense Reimbursement": False,
                "General Rebalance": False,
                "Portfolio Management": False,
                "Retirement Contributions": True,
                "Savings": True,
                "Securities Traded": True,
                "Transfers": True,
                "Uncategorized": True,
                "Fraud": False,
            },
        }

        for group, categories in groups.items():
            for name, locked in categories.items():
                cat = TransactionCategory(name=name, group=group, locked=locked)
                s.add(cat)
                d[name] = cat
        s.commit()
        return d
