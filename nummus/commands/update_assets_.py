"""Update asset valuations."""

from __future__ import annotations

from colorama import Fore

from nummus import portfolio


def update_assets(p: portfolio.Portfolio) -> int:
    """Update asset valuations using web sources.

    Args:
        p: Working Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    # Back up Portfolio
    _, tar_ver = p.backup()
    success = False

    try:
        updated = p.update_assets()
        success = True
    finally:
        # Restore backup if anything went really wrong
        # Coverage gets confused with finally blocks
        if not success:  # pragma: no cover
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(f"{Fore.RED}Abandoned update-assets, restored from backup")

    if len(updated) == 0:
        print(
            f"{Fore.YELLOW}No assets were updated, "
            "add a ticker to an Asset to download market data",
        )
        return -2

    updated = sorted(updated, key=lambda item: item[0].lower())  # sort by name
    name_len = max(len(item[0]) for item in updated)
    ticker_len = max(len(item[1]) for item in updated)
    failed = False
    for name, ticker, start, end, error in updated:
        if start is None:
            print(
                f"{Fore.RED}Asset {name:{name_len}} ({ticker:{ticker_len}}) "
                f"failed to update. Error: {error}",
            )
            failed = True
        else:
            print(
                f"{Fore.GREEN}Asset {name:{name_len}} ({ticker:{ticker_len}}) "
                f"updated from {start} to {end}",
            )
    return 1 if failed else 0
