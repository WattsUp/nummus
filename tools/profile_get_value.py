"""Run viztracer profiler on a web call."""
from __future__ import annotations

import argparse
import datetime
import sys
import time
from pathlib import Path

import colorama
import sqlalchemy
import viztracer
from colorama import Fore

from nummus import commands
from nummus import custom_types as t
from nummus.models import Account, Asset, AssetValuation, TransactionSplit

colorama.init(autoreset=True)


def main(command_line: t.Strings | None = None) -> int:
    """Main program entry.

    Args:
        command_line: command line arguments, None for sys.argv

    Return:
        0 on success
        non-zero on failure
    """
    desc = "Run viztracer profiler on a web call, only supports GET"
    home = Path("~").expanduser()
    default_path = str(home.joinpath(".nummus", "portfolio.db"))
    parser = argparse.ArgumentParser(prog="nummus", description=desc)
    parser.add_argument(
        "--portfolio",
        "-p",
        metavar="PATH",
        default=default_path,
        help="specify portfolio.db location",
        type=Path,
    )
    parser.add_argument(
        "--pass-file",
        metavar="PATH",
        help="specify password file location, omit will prompt when necessary",
        type=Path,
    )
    parser.add_argument(
        "--output-file",
        "-o",
        metavar="PATH",
        default="result.json",
        help="output file path. End with .json or .html or .gz",
        type=Path,
    )

    args = parser.parse_args(args=command_line)

    path_db: Path = args.portfolio
    path_password: Path = args.pass_file
    output_file: Path = args.output_file

    p = commands.unlock(path_db=path_db, path_password=path_password)
    if p is None:
        return 1

    with p.get_session() as s:
        # Get start date
        query = s.query(TransactionSplit)
        query = query.where(TransactionSplit.asset_id.is_(None))
        query = query.with_entities(sqlalchemy.func.min(TransactionSplit.date_ord))
        start_ord = query.scalar()
        start = (
            datetime.date.fromordinal(start_ord)
            if start_ord
            else datetime.date(1970, 1, 1)
        )
        end = datetime.date.today()
        start_ord = start.toordinal()
        end_ord = end.toordinal()

        # All accounts
        Account.get_value_all(s, start_ord, end_ord)  # Cache stuff

        with viztracer.VizTracer(output_file=str(output_file)) as _:
            t_start = time.perf_counter()
            Account.get_value_all(s, start_ord, end_ord)
            t_duration = time.perf_counter() - t_start
        print(f"All accounts {t_duration*1000:6.1f}ms (with profiler)")

        # Don't attach profiler
        t_start = time.perf_counter()
        Account.get_value_all(s, start_ord, end_ord)
        t_duration = time.perf_counter() - t_start
        print(f"All accounts {t_duration*1000:6.1f}ms (sans profiler)")

        durations: list[t.DictAny] = []

        accounts = s.query(Account).all()
        for acct in accounts:
            acct.get_value(start_ord, end_ord)  # Cache stuff

            query = s.query(TransactionSplit)
            query = query.where(TransactionSplit.account_id == acct.id_)
            n = query.count()

            t_start = time.perf_counter()
            acct.get_value(start_ord, end_ord)
            t_duration_single = time.perf_counter() - t_start

            Account.get_value_all(s, start_ord, end_ord, ids=[acct.id_])  # Cache stuff

            t_start = time.perf_counter()
            Account.get_value_all(s, start_ord, end_ord, ids=[acct.id_])
            t_duration_all = time.perf_counter() - t_start

            durations.append(
                {
                    "uri": acct.uri,
                    "name": acct.name,
                    "n": n,
                    "single": t_duration_single,
                    "all": t_duration_all,
                },
            )

        durations = sorted(durations, key=lambda item: -item["single"])
        print(f"{Fore.CYAN}Individual account get_value")
        for item in durations:
            print(
                f"{item['uri']} {item['name']:25} "
                f"{item['single']*1000:6.1f}ms "
                f"{item['all']*1000:6.1f}ms "
                f"{item['n']:4} transactions",
            )

        durations: list[t.DictAny] = []

        accounts = s.query(Account).all()
        for acct in accounts:
            acct.get_cash_flow(start_ord, end_ord)  # Cache stuff

            query = s.query(TransactionSplit)
            query = query.where(TransactionSplit.account_id == acct.id_)
            n = query.count()

            t_start = time.perf_counter()
            acct.get_cash_flow(start_ord, end_ord)
            t_duration_single = time.perf_counter() - t_start

            Account.get_cash_flow_all(
                s,
                start_ord,
                end_ord,
                ids=[acct.id_],
            )  # Cache stuff

            t_start = time.perf_counter()
            Account.get_cash_flow_all(s, start_ord, end_ord, ids=[acct.id_])
            t_duration_all = time.perf_counter() - t_start

            durations.append(
                {
                    "uri": acct.uri,
                    "name": acct.name,
                    "n": n,
                    "single": t_duration_single,
                    "all": t_duration_all,
                },
            )

        durations = sorted(durations, key=lambda item: -item["single"])
        print(f"{Fore.CYAN}Individual account get_cash_flow")
        for item in durations:
            print(
                f"{item['uri']} {item['name']:25} "
                f"{item['single']*1000:6.1f}ms "
                f"{item['all']*1000:6.1f}ms "
                f"{item['n']:4} transactions",
            )

        durations: list[t.DictAny] = []

        assets = s.query(Asset).all()
        for asset in assets:
            asset.get_value(start_ord, end_ord)  # Cache stuff

            query = s.query(AssetValuation)
            query = query.where(AssetValuation.asset_id == asset.id_)
            n = query.count()

            t_start = time.perf_counter()
            asset.get_value(start_ord, end_ord)
            t_duration_single = time.perf_counter() - t_start

            Asset.get_value_all(s, start_ord, end_ord, ids=[asset.id_])  # Cache stuff

            t_start = time.perf_counter()
            Asset.get_value_all(s, start_ord, end_ord, ids=[asset.id_])
            t_duration_all = time.perf_counter() - t_start

            durations.append(
                {
                    "uri": asset.uri,
                    "name": asset.name,
                    "n": n,
                    "single": t_duration_single,
                    "all": t_duration_all,
                },
            )

        durations = sorted(durations, key=lambda item: -item["single"])
        print(f"{Fore.CYAN}Individual asset get_value")
        for item in durations:
            print(
                f"{item['uri']} {item['name']:25} "
                f"{item['single']*1000:6.1f}ms "
                f"{item['all']*1000:6.1f}ms "
                f"{item['n']:4} valuations",
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
