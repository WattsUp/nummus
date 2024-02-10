"""Summarize a portfolio and print."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import utils

if TYPE_CHECKING:
    from nummus import portfolio


def summarize(
    p: portfolio.Portfolio,
    *_,
    include_all: bool = False,
) -> int:
    """Print summary information and statistics on Portfolio.

    Args:
        p: Working Portfolio
        include_all: True will include all accounts and assets

    Returns:
        0 on success
        non-zero on failure
    """
    stats = p.summarize(include_all=include_all)

    def is_are(i: int) -> str:
        return "is" if i == 1 else "are"

    def plural(i: int) -> str:
        return "" if i == 1 else "s"

    size: int = stats["db_size"]
    print(f"Portfolio file size is {size/1000:,.1f}KB/{size/1024:,.1f}KiB")

    # Accounts
    table: list[list[str] | None] = [
        [
            "Name",
            "Institution.",
            "Category",
            ">Value/",
            ">Profit/",
            ">Age/",
        ],
        None,
    ]
    table.extend(
        [
            acct["name"],
            acct["institution"],
            acct["category"],
            utils.format_financial(acct["value"]),
            utils.format_financial(acct["profit"]),
            acct["age"],
        ]
        for acct in stats["accounts"]
    )
    table.append(None)
    table.append(
        [
            "Total",
            "",
            "",
            utils.format_financial(stats["net_worth"]),
            "",
            "",
        ],
    )
    n = stats["n_accounts"]
    n_table = len(stats["accounts"])
    print(
        f"There {is_are(n)} {n:,} account{plural(n)}, "
        f"{n_table:,} of which {is_are(n_table)} currently open",
    )
    utils.print_table(table)

    # Assets
    table = [
        [
            "Name",
            "Description.",
            "Class",
            "Ticker",
            ">Value/",
            ">Profit/",
        ],
        None,
    ]
    table.extend(
        [
            asset["name"],
            asset["description"] or "",
            asset["category"],
            asset["ticker"] or "",
            utils.format_financial(asset["value"]),
            utils.format_financial(asset["profit"]),
        ]
        for asset in stats["assets"]
    )
    table.append(None)
    table.append(
        [
            "Total",
            "",
            "",
            "",
            utils.format_financial(stats["total_asset_value"]),
            "",
        ],
    )
    n = stats["n_assets"]
    n_table = len(stats["assets"])
    print(
        f"There {is_are(n)} {n:,} asset{plural(n)}, "
        f"{n_table:,} of which {is_are(n_table)} currently held",
    )
    utils.print_table(table)

    n = stats["n_valuations"]
    print(f"There {is_are(n)} {n:,} asset valuation{plural(n)}")

    n = stats["n_transactions"]
    print(f"There {is_are(n)} {n:,} transaction{plural(n)}")
    return 0
