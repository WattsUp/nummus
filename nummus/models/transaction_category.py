"""Transaction Category model for storing a type of Transaction
"""

from __future__ import annotations

from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models.base import Base, BaseEnum

ORMTxnCat = orm.Mapped["TransactionCategory"]
ORMTxnCatOpt = orm.Mapped[t.Optional["TransactionCategory"]]
ORMTxnCatType = orm.Mapped["TransactionCategoryType"]


class TransactionCategoryType(BaseEnum):
  """Types of Transaction Categories
  """
  INCOME = 1
  EXPENSE = 2
  OTHER = 3


class TransactionCategory(Base):
  """Categories of Transactions

  Attributes:
    id: TransactionCategory unique identifier
    uuid: TransactionCategory unique identifier
    name: Name of category
    type_: Type of category
    custom: True if category is user made
  """
  name: t.ORMStr
  type_: ORMTxnCatType
  custom: t.ORMBool

  @staticmethod
  def add_default(s: orm.Session) -> t.Dict[str, TransactionCategory]:
    """Create default transaction categories

    Args:
      s: SQL session to use

    Returns:
      Dictionary {name: category}
    """
    d: t.Dict[str, TransactionCategory] = {}
    income = [
        "Consulting", "Deposits", "Dividends Received",
        "Dividends Received (tax-advantaged)", "Interest", "Investment Income",
        "Other Income", "Paychecks/Salary", "Refunds & Reimbursements",
        "Retirement Income", "Rewards", "Sales", "Services"
    ]
    expense = [
        "Advertising", "Advisory Fee", "ATM/Cash", "Automotive",
        "Business Miscellaneous", "Cable/Satellite", "Charitable Giving",
        "Checks", "Child/Dependent", "Clothing/Shoes", "Dues & Subscriptions",
        "Education", "Electronics", "Entertainment", "Gasoline/Fuel",
        "General Merchandise", "Gifts", "Groceries", "Healthcare/Medical",
        "Hobbies", "Home Improvement", "Home Maintenance", "Insurance", "Loans",
        "Mortgages", "Office Maintenance", "Office Supplies", "Other Bills",
        "Other Expenses", "Personal Care", "Pets/Pet Care",
        "Postage & Shipping", "Printing", "Rent", "Restaurants",
        "Service Charge/Fees", "Taxes", "Telephone", "Travel", "Utilities",
        "Wages Paid"
    ]
    other = [
        "Credit Card Payments", "Expense Reimbursement", "General Rebalance",
        "Portfolio Management", "Retirement Contributions", "Savings",
        "Securities Traded", "Transfers", "Uncategorized", "Fraud"
    ]
    for name in income:
      cat = TransactionCategory(name=name,
                                type_=TransactionCategoryType.INCOME,
                                custom=False)
      s.add(cat)
      d[name] = cat
    for name in expense:
      cat = TransactionCategory(name=name,
                                type_=TransactionCategoryType.EXPENSE,
                                custom=False)
      s.add(cat)
      d[name] = cat
    for name in other:
      cat = TransactionCategory(name=name,
                                type_=TransactionCategoryType.OTHER,
                                custom=False)
      s.add(cat)
      d[name] = cat
    s.commit()
    return d
