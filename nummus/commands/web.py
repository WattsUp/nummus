"""Run web server for GUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import web

if TYPE_CHECKING:
    from nummus import portfolio


# No unit test for wrapper command, too difficult to mock
def run_web(
    p: portfolio.Portfolio,
    host: str,
    port: int,
    *,
    debug: bool,
) -> int:  # pragma: no cover
    """Run web server serving the nummus Portfolio.

    Args:
        p: Working Portfolio
        host: IP to bind to
        port: Network port to bind to
        debug: True will run Flask in debug mode

    Returns:
        0 on success
        non-zero on failure
    """
    s = web.Server(p, host, port, debug=debug)
    s.run()
    return 0
