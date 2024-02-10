"""Clean and optimize a portfolio."""

from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore

if TYPE_CHECKING:
    from nummus import portfolio


def clean(p: portfolio.Portfolio) -> int:
    """Clean portfolio and delete unused files.

    Args:
        p: Working Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    size_before, size_after = p.clean()
    print(f"{Fore.GREEN}Portfolio cleaned")
    p_change = size_before - size_after
    print(
        f"{Fore.CYAN}Portfolio was optimized by "
        f"{p_change / 1000:,.1f}KB/{p_change / 1024:,.1f}KiB",
    )

    return 0
