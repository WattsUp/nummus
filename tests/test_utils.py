from __future__ import annotations

import datetime
import textwrap
from decimal import Decimal
from typing import TYPE_CHECKING

import numpy_financial as npf
import pytest
from colorama import Fore

from nummus import exceptions as exc
from nummus import utils

if TYPE_CHECKING:
    from tests.conftest import RandomString


def test_camel_to_snake() -> None:
    s = "CamelCase"
    target = "camel_case"
    result = utils.camel_to_snake(s)
    assert result == target

    s = "Camel"
    target = "camel"
    result = utils.camel_to_snake(s)
    assert result == target

    s = "camel"
    target = "camel"
    result = utils.camel_to_snake(s)
    assert result == target

    s = "HTTPClass"
    target = "http_class"
    result = utils.camel_to_snake(s)
    assert result == target

    s = "HTTPClassXYZ"
    target = "http_class_xyz"
    result = utils.camel_to_snake(s)
    assert result == target


def test_get_input(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    rand_str: RandomString,
) -> None:
    prompt = rand_str()
    prompt_input = rand_str()

    def mock_input(to_print: str) -> str | None:
        print(to_print + prompt_input)  # noqa: T201
        return prompt_input

    def mock_get_pass(to_print: str) -> str | None:
        print(to_print)  # noqa: T201
        return prompt_input

    def mock_input_interrupt(to_print: str) -> None:
        print(to_print + prompt_input)  # noqa: T201
        raise KeyboardInterrupt

    def mock_get_pass_eof(to_print: str) -> None:
        print(to_print)  # noqa: T201
        raise EOFError

    monkeypatch.setattr("builtins.input", mock_input)
    assert utils.get_input(prompt=prompt, secure=False) == prompt_input
    assert capsys.readouterr().out == prompt + prompt_input + "\n"

    monkeypatch.setattr("getpass.getpass", mock_get_pass)
    assert utils.get_input(prompt=prompt, secure=True, print_key=False) == prompt_input
    assert capsys.readouterr().out == prompt + "\n"

    assert utils.get_input(prompt=prompt, secure=True, print_key=True) == prompt_input
    assert capsys.readouterr().out == "\u26bf  " + prompt + "\n"

    monkeypatch.setattr("builtins.input", mock_input_interrupt)
    assert utils.get_input(prompt=prompt, secure=False) is None
    assert capsys.readouterr().out == prompt + prompt_input + "\n"

    monkeypatch.setattr("getpass.getpass", mock_get_pass_eof)
    assert utils.get_input(prompt=prompt, secure=True, print_key=False) is None
    assert capsys.readouterr().out == prompt + "\n"


def test_get_password(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    rand_str: RandomString,
) -> None:
    key = rand_str()
    queue: list[str | None] = []

    def mock_input(to_print: str, *, secure: bool) -> str | None:
        assert secure
        print(to_print)  # noqa: T201
        if len(queue) == 1:
            return queue[0]
        return queue.pop(0)

    monkeypatch.setattr(utils, "get_input", mock_input)

    queue = [key, key]
    target = "Please enter password: \nPlease confirm password: \n"
    assert utils.get_password() == key
    assert capsys.readouterr().out == target

    queue = [rand_str(7), key, key + "typo", key, key]
    target = (
        "Please enter password: \n"
        f"{Fore.RED}Password must be at least 8 characters\n"
        "Please enter password: \n"
        "Please confirm password: \n"
        f"{Fore.RED}Passwords must match\n"
        "Please enter password: \n"
        "Please confirm password: \n"
    )
    assert utils.get_password() == key
    assert capsys.readouterr().out == target

    queue = [None]
    target = "Please enter password: \n"
    assert utils.get_password() is None
    assert capsys.readouterr().out == target

    queue = [key, None]
    target = "Please enter password: \nPlease confirm password: \n"
    assert utils.get_password() is None
    assert capsys.readouterr().out == target


def test_confirm(monkeypatch: pytest.MonkeyPatch, rand_str: RandomString) -> None:
    prompt = rand_str()
    prompt_input = rand_str(length=50)

    monkeypatch.setattr("builtins.input", lambda _: None)
    assert not utils.confirm(prompt=None, default=False)
    assert utils.confirm(prompt=prompt, default=True)

    monkeypatch.setattr("builtins.input", lambda _: "Y")
    assert utils.confirm(prompt=prompt)

    monkeypatch.setattr("builtins.input", lambda _: "N")
    assert not utils.confirm(prompt=prompt)

    queue = [prompt_input, "y"]

    def mock_input(_) -> str | None:
        if len(queue) == 1:
            return queue[0]
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", mock_input)
    assert utils.confirm(prompt=prompt)


def test_evaluate_real_statement() -> None:
    assert utils.evaluate_real_statement(None) is None

    s = "(+21.3e-5*-.1234e5/81.7)*100"
    target = Decimal("21.3e-5") * Decimal("-.1234e5") / Decimal("81.7") * 100
    assert utils.evaluate_real_statement(s) == round(target, 2)

    assert utils.evaluate_real_statement("2>3") is None
    assert utils.evaluate_real_statement("2+5j") is None

    s = "(+21.3e-5*-.1234e5/81.7)*"
    assert utils.evaluate_real_statement(s) is None
    s = "__import__('os').system('rm -rf /')"
    assert utils.evaluate_real_statement(s) is None


def test_parse_real() -> None:
    assert utils.parse_real(None) is None
    assert utils.parse_real("") is None
    assert utils.parse_real("Not a number") is None

    assert utils.parse_real("1000.1") == Decimal("1000.1")
    assert utils.parse_real("1000") == Decimal(1000)
    assert utils.parse_real("1,000.101") == Decimal("1000.1")
    assert utils.parse_real("$1,000.101") == Decimal("1000.1")
    assert utils.parse_real("$1,000.101", precision=3) == Decimal("1000.101")
    assert utils.parse_real("-$1,000.101") == Decimal("-1000.1")
    assert utils.parse_real("-$1,000.101", precision=3) == Decimal("-1000.101")


def test_format_financial() -> None:
    assert utils.format_financial(Decimal("1000.1")) == "$1,000.10"
    assert utils.format_financial(Decimal("1000.1"), plus=True) == "+$1,000.10"
    assert utils.format_financial(Decimal("-1000.1")) == "-$1,000.10"
    assert utils.format_financial(Decimal(0)) == "$0.00"


def test_parse_bool() -> None:
    assert utils.parse_bool("") is None
    assert utils.parse_bool("TRUE")
    assert not utils.parse_bool("FALSE")
    assert utils.parse_bool("t")
    assert not utils.parse_bool("f")
    assert utils.parse_bool("1")
    assert not utils.parse_bool("0")


def test_parse_date() -> None:
    assert utils.parse_date("") is None
    assert utils.parse_date("2024-01-01") == datetime.date(2024, 1, 1)


def test_format_days(rand_str: RandomString) -> None:
    assert utils.format_days(0) == "0 days"
    assert utils.format_days(10) == "10 days"
    assert utils.format_days(11) == "2 weeks"
    assert utils.format_days(8 * 7) == "8 weeks"
    assert utils.format_days(8 * 7 + 1) == "2 months"
    assert utils.format_days(int(18 * 365.25 // 12)) == "18 months"
    assert utils.format_days(int(18 * 365.25 // 12 + 1)) == "2 years"

    labels = [rand_str() for _ in range(4)]
    assert utils.format_days(2, labels=labels) == f"2 {labels[0]}"


def test_format_seconds() -> None:
    assert utils.format_seconds(0) == "0.0 seconds"
    assert utils.format_seconds(60) == "60.0 seconds"
    assert utils.format_seconds(90.1) == "1.5 minutes"
    assert utils.format_seconds(5400.1) == "1.5 hours"
    assert utils.format_seconds(86400) == "24.0 hours"
    assert utils.format_seconds(86400 * 4) == "96.0 hours"
    assert utils.format_seconds(86400 * 4.1) == "4 days"


def test_range_date() -> None:
    start = datetime.datetime.now().astimezone().date()
    end = start + datetime.timedelta(days=7)
    start_ord = start.toordinal()
    end_ord = end.toordinal()

    result = utils.range_date(start, end, include_end=True)
    assert len(result) == 8
    assert result[0] == start
    assert result[-1] == end

    result = utils.range_date(start_ord, end_ord, include_end=True)
    assert len(result) == 8
    assert result[0] == start
    assert result[-1] == end

    result = utils.range_date(start, end, include_end=False)
    assert len(result) == 7
    assert result[0] == start
    assert result[-1] == end - datetime.timedelta(days=1)

    result = utils.range_date(start_ord, end_ord, include_end=False)
    assert len(result) == 7
    assert result[0] == start
    assert result[-1] == end - datetime.timedelta(days=1)


def test_date_add_months() -> None:
    start = datetime.date(2023, 1, 1)
    assert utils.date_add_months(start, 0) == start
    assert utils.date_add_months(start, 1) == datetime.date(2023, 2, 1)
    assert utils.date_add_months(start, 12) == datetime.date(2024, 1, 1)
    assert utils.date_add_months(start, 11) == datetime.date(2023, 12, 1)
    assert utils.date_add_months(start, -1) == datetime.date(2022, 12, 1)
    assert utils.date_add_months(start, -12) == datetime.date(2022, 1, 1)
    assert utils.date_add_months(start, -11) == datetime.date(2022, 2, 1)

    start = datetime.date(2023, 6, 30)
    assert utils.date_add_months(start, 0) == start
    assert utils.date_add_months(start, 1) == datetime.date(2023, 7, 30)
    assert utils.date_add_months(start, 12) == datetime.date(2024, 6, 30)
    assert utils.date_add_months(start, 23) == datetime.date(2025, 5, 30)
    assert utils.date_add_months(start, -4) == datetime.date(2023, 2, 28)

    start = datetime.date(2020, 1, 31)
    assert utils.date_add_months(start, 1) == datetime.date(2020, 2, 29)


def test_period_months() -> None:
    start = datetime.date(2023, 1, 10)
    start_ord = start.toordinal()
    end = datetime.date(2023, 1, 28)
    end_ord = end.toordinal()
    target = {
        "2023-01": (start_ord, end_ord),
    }
    assert utils.period_months(start_ord, end_ord) == target

    end = datetime.date(2023, 2, 14)
    end_ord = end.toordinal()
    target = {
        "2023-01": (start_ord, datetime.date(2023, 1, 31).toordinal()),
        "2023-02": (datetime.date(2023, 2, 1).toordinal(), end_ord),
    }
    assert utils.period_months(start_ord, end_ord) == target


def test_period_years() -> None:
    start = datetime.date(2023, 1, 10)
    start_ord = start.toordinal()
    end = datetime.date(2023, 1, 28)
    end_ord = end.toordinal()
    target = {
        "2023": (start_ord, end_ord),
    }
    assert utils.period_years(start_ord, end_ord) == target

    end = datetime.date(2023, 2, 14)
    end_ord = end.toordinal()
    target = {
        "2023": (start_ord, end_ord),
    }
    assert utils.period_years(start_ord, end_ord) == target

    end = datetime.date(2025, 2, 14)
    end_ord = end.toordinal()
    target = {
        "2023": (start_ord, datetime.date(2023, 12, 31).toordinal()),
        "2024": (
            datetime.date(2024, 1, 1).toordinal(),
            datetime.date(2024, 12, 31).toordinal(),
        ),
        "2025": (datetime.date(2025, 1, 1).toordinal(), end_ord),
    }
    assert utils.period_years(start_ord, end_ord) == target


def test_downsample() -> None:
    start = datetime.date(2023, 1, 10)
    start_ord = start.toordinal()
    end = datetime.date(2023, 1, 28)
    end_ord = end.toordinal()
    n = end_ord - start_ord + 1

    values = [Decimal(i) for i in range(n)]

    labels, r_min, r_avg, r_max = utils.downsample(start_ord, end_ord, values)
    assert labels == ["2023-01"]
    assert r_min == [Decimal(0)]
    assert r_avg == [Decimal(n - 1) / 2]
    assert r_max == [Decimal(n - 1)]

    start = datetime.date(2023, 1, 30)
    start_ord = start.toordinal()
    end = datetime.date(2023, 2, 2)
    end_ord = end.toordinal()

    values = [
        Decimal(1),
        Decimal(3),
        Decimal(5),
        Decimal(7),
    ]

    labels, r_min, r_avg, r_max = utils.downsample(start_ord, end_ord, values)
    assert labels == ["2023-01", "2023-02"]
    assert r_min == [Decimal(1), Decimal(5)]
    assert r_avg == [Decimal(2), Decimal(6)]
    assert r_max == [Decimal(3), Decimal(7)]


def test_round_list() -> None:
    n = 9
    list_ = [1 / Decimal(n) for _ in range(n)]
    assert sum(list_) != 1

    l_round = utils.round_list(list_)
    assert sum(l_round) == 1
    assert l_round[0] != list_[0]
    assert l_round[0] == round(list_[0], 6)


def test_integrate() -> None:
    deltas: list[Decimal | None] = []
    assert utils.integrate(deltas) == []

    deltas = [Decimal(0)] * 5
    target = [Decimal(0)] * 5
    assert utils.integrate(deltas) == target

    deltas = [None] * 5
    target = [Decimal(0)] * 5
    assert utils.integrate(deltas) == target

    deltas[2] = Decimal(20)
    target[2] += Decimal(20)
    target[3] += Decimal(20)
    target[4] += Decimal(20)
    assert utils.integrate(deltas) == target


def test_interpolate_step() -> None:
    n = 6
    values: list[tuple[int, Decimal]] = []

    target = [Decimal(0)] * n
    assert utils.interpolate_step(values, n) == target

    values.append((-3, Decimal(-1)))
    target = [Decimal(-1)] * n
    assert utils.interpolate_step(values, n) == target

    values.append((1, Decimal(1)))
    target = [Decimal(1)] * n
    target[0] = Decimal(-1)
    assert utils.interpolate_step(values, n) == target

    values.append((4, Decimal(3)))
    target[4] = Decimal(3)
    target[5] = Decimal(3)
    assert utils.interpolate_step(values, n) == target


def test_interpolate_linear() -> None:
    n = 6
    values: list[tuple[int, Decimal]] = []

    target = [Decimal(0)] * n
    assert utils.interpolate_linear(values, n) == target

    values.append((-3, Decimal(-1)))
    target = [Decimal(-1)] * n
    assert utils.interpolate_linear(values, n) == target

    values.append((1, Decimal(1)))
    target = [
        Decimal("0.5"),
        Decimal(1),
        Decimal(1),
        Decimal(1),
        Decimal(1),
        Decimal(1),
    ]
    assert utils.interpolate_linear(values, n) == target

    values.append((4, Decimal(3)))
    target = [
        Decimal("0.5"),
        Decimal(1),
        Decimal(1) + Decimal(2) / Decimal(3),
        Decimal(1) + Decimal(2) / Decimal(3) * Decimal(2),
        Decimal(3),
        Decimal(3),  # Stay flat at the end
    ]
    assert utils.interpolate_linear(values, n) == target

    values = [
        (2, Decimal(1)),
        (4, Decimal(3)),
    ]
    target = [
        Decimal(0),
        Decimal(0),
        Decimal(1),
        Decimal(2),
        Decimal(3),
        Decimal(3),
    ]
    assert utils.interpolate_linear(values, n) == target


def test_twrr() -> None:
    n = 5
    values = [Decimal(0)] * n
    profit = [Decimal(0)] * n
    target = [Decimal(0)] * n
    assert utils.twrr(values, profit) == target

    # Still no profit, no profit percent
    values = [
        Decimal(0),
        Decimal(10),
        Decimal(10),
        Decimal(10),
        Decimal(0),
    ]
    target = [Decimal(0)] * n
    assert utils.twrr(values, profit) == target

    # Profit on buy day
    values = [
        Decimal(0),
        Decimal(11),
        Decimal(11),
        Decimal(11),
        Decimal(0),
    ]
    profit = [
        Decimal(0),
        Decimal(1),
        Decimal(1),
        Decimal(1),
        Decimal(1),
    ]
    target = [
        Decimal(0),
        Decimal("0.1"),
        Decimal("0.1"),
        Decimal("0.1"),
        Decimal("0.1"),
    ]
    assert utils.twrr(values, profit) == target

    # Profit on buy and sell day
    values = [
        Decimal(0),
        Decimal(11),
        Decimal(11),
        Decimal(11),
        Decimal(0),
    ]
    profit = [
        Decimal(0),
        Decimal(1),
        Decimal(1),
        Decimal(1),
        Decimal(12),
    ]
    target = [
        Decimal(0),
        Decimal("0.1"),
        Decimal("0.1"),
        Decimal("0.1"),
        Decimal("1.2"),
    ]
    assert utils.twrr(values, profit) == target
    assert utils.twrr(values[1:], profit[1:]) == target[1:]

    values = [
        Decimal(10),
        Decimal(21),
        Decimal(42),
        Decimal(42),
        Decimal(0),
    ]
    profit = [
        Decimal(0),
        Decimal(1),
        Decimal(22),
        Decimal(22),
        Decimal(22),
    ]
    target = [
        Decimal(0),
        Decimal("0.1"),
        Decimal("1.2"),
        Decimal("1.2"),
        Decimal("1.2"),
    ]
    assert utils.twrr(values, profit) == target

    values = [
        Decimal(10),
        Decimal(11),
        Decimal(12),
        Decimal(13),
        Decimal(14),
    ]
    profit = [
        Decimal(0),
        Decimal(1),
        Decimal(2),
        Decimal(3),
        Decimal(4),
    ]
    target = [
        Decimal(0),
        Decimal("0.1"),
        Decimal("0.2"),
        Decimal("0.3"),
        Decimal("0.4"),
    ]
    assert utils.twrr(values, profit) == target

    values = [
        # Buy 100 shares at $100
        Decimal(10000),
        # Buy 100 more at $500
        Decimal(100000),
        # Sell 100 at $50
        Decimal(5000),
        # Returns to $100
        Decimal(10000),
    ]
    profit = [
        Decimal(0),
        Decimal(40000),
        Decimal(-50000),
        Decimal(-45000),
    ]
    target = [
        Decimal(0),
        Decimal(4),
        Decimal("-0.5"),
        Decimal(0),
    ]
    assert utils.twrr(values, profit) == target


def test_mwrr() -> None:
    n = 5
    values = [Decimal(0)] * n
    profit = [Decimal(0)] * n

    assert utils.mwrr(values, profit) == Decimal(0)

    # Still no profit, no profit percent
    values = [
        Decimal(0),
        Decimal(10),
        Decimal(10),
        Decimal(10),
        Decimal(0),
    ]
    assert utils.mwrr(values, profit) == Decimal(0)

    values = [Decimal(101)]
    profit = [Decimal(1)]
    target = round(Decimal((101 / 100) ** 365.25) - 1, 6)
    assert utils.mwrr(values, profit) == target

    values = [Decimal(20)]
    profit = [Decimal(-100)]
    assert utils.mwrr(values, profit) == Decimal(-1)

    # Profit on buy day
    values = [
        Decimal(0),
        Decimal(101),
        Decimal(101),
        Decimal(101),
        Decimal(0),
    ]
    profit = [
        Decimal(0),
        Decimal(1),
        Decimal(1),
        Decimal(1),
        Decimal(1),
    ]
    cash_flows = [
        Decimal(0),
        Decimal(-100),
        Decimal(0),
        Decimal(0),
        Decimal(101),
    ]
    target = round(Decimal((npf.irr(cash_flows) + 1) ** 365.25) - 1, 6)
    assert utils.mwrr(values, profit) == target

    # Profit on buy and sell day
    values = [
        Decimal(0),
        Decimal(101),
        Decimal(101),
        Decimal(101),
        Decimal(0),
    ]
    profit = [
        Decimal(0),
        Decimal(1),
        Decimal(1),
        Decimal(1),
        Decimal(2),
    ]
    cash_flows = [
        Decimal(0),
        Decimal(-100),
        Decimal(0),
        Decimal(0),
        Decimal(102),
    ]
    target = round(Decimal((npf.irr(cash_flows) + 1) ** 365.25) - 1, 6)
    assert utils.mwrr(values, profit) == target

    values = [
        Decimal(100),
        Decimal(201),
        Decimal(202),
        Decimal(202),
        Decimal(0),
    ]
    profit = [
        Decimal(0),
        Decimal(1),
        Decimal(2),
        Decimal(2),
        Decimal(2),
    ]
    cash_flows = [
        Decimal(-100),
        Decimal(-100),
        Decimal(0),
        Decimal(0),
        Decimal(202),
    ]
    target = round(Decimal((npf.irr(cash_flows) + 1) ** 365.25) - 1, 6)
    assert utils.mwrr(values, profit) == target

    values = [
        Decimal(100),
        Decimal(101),
        Decimal(102),
        Decimal(103),
        Decimal(104),
    ]
    profit = [
        Decimal(0),
        Decimal(1),
        Decimal(2),
        Decimal(3),
        Decimal(4),
    ]
    cash_flows = [
        Decimal(-100),
        Decimal(0),
        Decimal(0),
        Decimal(0),
        Decimal(104),
    ]
    target = round(Decimal((npf.irr(cash_flows) + 1) ** 365.25) - 1, 6)
    assert utils.mwrr(values, profit) == target

    values = [
        # Buy 100 shares at $100
        Decimal(10000),
        # Buy 100 more at $500
        Decimal(100000),
        # Sell 100 at $50
        Decimal(5000),
        # Returns to $100
        Decimal(10000),
    ]
    profit = [
        Decimal(0),
        Decimal(40000),
        Decimal(-50000),
        Decimal(-45000),
    ]
    cash_flows = [
        Decimal(-10000),
        Decimal(-50000),
        Decimal(5000),
        Decimal(10000),
    ]
    target = round(Decimal((npf.irr(cash_flows) + 1) ** 365.25) - 1, 6)
    assert utils.mwrr(values, profit) == target


def test_pretty_table(monkeypatch: pytest.MonkeyPatch) -> None:
    table: list[list[str] | None] = []
    with pytest.raises(ValueError, match="Table has no rows"):
        utils.pretty_table(table)

    table = [None]
    with pytest.raises(ValueError, match="First row cannot be None"):
        utils.pretty_table(table)

    monkeypatch.setattr("shutil.get_terminal_size", lambda: (80, 24))
    table = [
        ["H1", ">H2", "<H3", "^H4", "H5.", "H6/"],
    ]
    target = textwrap.dedent(
        """\
    ╭────┬────┬────┬────┬────┬────╮
    │ H1 │ H2 │ H3 │ H4 │ H5 │ H6 │
    ╰────┴────┴────┴────┴────┴────╯""",
    )
    assert "\n".join(utils.pretty_table(table)) == target

    table = [
        ["H1", ">H2", "<H3", "^H4", "H5.", "H6/"],
        None,
    ]
    target = textwrap.dedent(
        """\
    ╭────┬────┬────┬────┬────┬────╮
    │ H1 │ H2 │ H3 │ H4 │ H5 │ H6 │
    ╞════╪════╪════╪════╪════╪════╡
    ╰────┴────┴────┴────┴────┴────╯""",
    )
    assert "\n".join(utils.pretty_table(table)) == target

    table = [
        ["H1", ">H2", "<H3", "^H4", "H5.", "H6/"],
        None,
        ["Short"] * 6,
        None,
        ["Long word"] * 6,
    ]
    target = textwrap.dedent(
        """\
    ╭───────────┬───────────┬───────────┬───────────┬───────────┬───────────╮
    │    H1     │    H2     │    H3     │    H4     │    H5     │    H6     │
    ╞═══════════╪═══════════╪═══════════╪═══════════╪═══════════╪═══════════╡
    │ Short     │     Short │ Short     │   Short   │ Short     │ Short     │
    ╞═══════════╪═══════════╪═══════════╪═══════════╪═══════════╪═══════════╡
    │ Long word │ Long word │ Long word │ Long word │ Long word │ Long word │
    ╰───────────┴───────────┴───────────┴───────────┴───────────┴───────────╯""",
    )
    assert "\n".join(utils.pretty_table(table)) == target

    # Make terminal smaller, extra space goes first
    monkeypatch.setattr("shutil.get_terminal_size", lambda: (70, 24))
    target = textwrap.dedent(
        """\
    ╭───────────┬───────────┬───────────┬───────────┬─────────┬─────────╮
    │    H1     │    H2     │    H3     │    H4     │   H5    │   H6    │
    ╞═══════════╪═══════════╪═══════════╪═══════════╪═════════╪═════════╡
    │ Short     │     Short │ Short     │   Short   │Short    │Short    │
    ╞═══════════╪═══════════╪═══════════╪═══════════╪═════════╪═════════╡
    │ Long word │ Long word │ Long word │ Long word │Long word│Long word│
    ╰───────────┴───────────┴───────────┴───────────┴─────────┴─────────╯""",
    )
    assert "\n".join(utils.pretty_table(table)) == target

    # Make terminal smaller, truncate column goes next
    monkeypatch.setattr("shutil.get_terminal_size", lambda: (60, 24))
    target = textwrap.dedent(
        """\
    ╭─────────┬─────────┬─────────┬─────────┬───────┬─────────╮
    │   H1    │   H2    │   H3    │   H4    │  H5   │   H6    │
    ╞═════════╪═════════╪═════════╪═════════╪═══════╪═════════╡
    │Short    │    Short│Short    │  Short  │Short  │Short    │
    ╞═════════╪═════════╪═════════╪═════════╪═══════╪═════════╡
    │Long word│Long word│Long word│Long word│Long w…│Long word│
    ╰─────────┴─────────┴─────────┴─────────┴───────┴─────────╯""",
    )
    assert "\n".join(utils.pretty_table(table)) == target

    # Make terminal smaller, other columns go next
    monkeypatch.setattr("shutil.get_terminal_size", lambda: (50, 24))
    target = textwrap.dedent(
        """\
    ╭───────┬───────┬───────┬────────┬────┬─────────╮
    │  H1   │  H2   │  H3   │   H4   │ H5 │   H6    │
    ╞═══════╪═══════╪═══════╪════════╪════╪═════════╡
    │Short  │  Short│Short  │ Short  │Sho…│Short    │
    ╞═══════╪═══════╪═══════╪════════╪════╪═════════╡
    │Long w…│Long w…│Long w…│Long wo…│Lon…│Long word│
    ╰───────┴───────┴───────┴────────┴────┴─────────╯""",
    )
    assert "\n".join(utils.pretty_table(table)) == target

    # Make terminal tiny, other columns go next, never last
    monkeypatch.setattr("shutil.get_terminal_size", lambda: (10, 24))
    target = textwrap.dedent(
        """\
    ╭────┬────┬────┬────┬────┬─────────╮
    │ H1 │ H2 │ H3 │ H4 │ H5 │   H6    │
    ╞════╪════╪════╪════╪════╪═════════╡
    │Sho…│Sho…│Sho…│Sho…│Sho…│Short    │
    ╞════╪════╪════╪════╪════╪═════════╡
    │Lon…│Lon…│Lon…│Lon…│Lon…│Long word│
    ╰────┴────┴────┴────┴────┴─────────╯""",
    )
    assert "\n".join(utils.pretty_table(table)) == target


def test_dedupe() -> None:
    # Set without duplicates not changed
    items = {
        "Apple",
        "Banana",
        "Strawberry",
    }
    assert utils.dedupe(items) == items

    items = {
        "Apple",
        "Banana",
        "Bananas",
        "Strawberry",
    }
    target = {
        "Apple",
        "Banana",
        "Strawberry",
    }
    assert utils.dedupe(items) == target

    items = {
        "Apple",
        "Banana",
        "Bananas",
        "Strawberry",
        "Mango",
        "Mengo",
        "A bunch of chocolate pies",
        "A bunch of chocolate cake",
        "A bunch of chocolate tart",
    }
    target = {
        "Apple",
        "Banana",
        "Strawberry",
        "Mango",
        "A bunch of chocolate cake",
    }
    assert utils.dedupe(items) == target


def test_date_months_between() -> None:
    # Same date is zero
    start = datetime.date(2024, 11, 1)
    end = start
    assert utils.date_months_between(start, end) == 0
    assert utils.date_months_between(end, start) == 0

    # Same month is zero
    start = datetime.date(2024, 11, 1)
    end = datetime.date(2024, 11, 30)
    assert utils.date_months_between(start, end) == 0
    assert utils.date_months_between(end, start) == 0

    # Next month is one
    start = datetime.date(2024, 11, 1)
    end = datetime.date(2024, 12, 31)
    assert utils.date_months_between(start, end) == 1
    assert utils.date_months_between(end, start) == -1

    # 11 months is 11
    start = datetime.date(2023, 11, 1)
    end = datetime.date(2024, 10, 15)
    assert utils.date_months_between(start, end) == 11
    assert utils.date_months_between(end, start) == -11

    # 13 months is 13
    start = datetime.date(2024, 11, 1)
    end = datetime.date(2023, 10, 15)
    assert utils.date_months_between(start, end) == -13
    assert utils.date_months_between(end, start) == 13


def test_weekdays_in_month() -> None:
    date = datetime.date(2024, 11, 1)

    # weekday is Friday, there are 5 Fridays
    weekday = date.weekday()  # Friday
    assert utils.weekdays_in_month(weekday, date) == 5

    # weekday is Saturday, there are 5 Saturday
    weekday = (weekday + 1) % 7
    assert utils.weekdays_in_month(weekday, date) == 5

    # weekday is Sunday, there are 4 Sundays
    weekday = (weekday + 1) % 7
    assert utils.weekdays_in_month(weekday, date) == 4


def test_start_of_month() -> None:
    date = datetime.date(2024, 2, 20)
    assert utils.start_of_month(date) == datetime.date(2024, 2, 1)


def test_end_of_month() -> None:
    date = datetime.date(2024, 2, 20)
    assert utils.end_of_month(date) == datetime.date(2024, 2, 29)


def test_clamp() -> None:
    assert utils.clamp(Decimal("0.5")) == Decimal("0.5")
    assert utils.clamp(Decimal("-0.5")) == Decimal(0)
    assert utils.clamp(Decimal("1.5")) == Decimal(1)

    assert utils.clamp(Decimal(150), c_max=Decimal(100)) == Decimal(100)
    assert utils.clamp(Decimal(-150), c_min=Decimal(-100)) == Decimal(-100)


def test_strip_emojis(rand_str: RandomString) -> None:
    text = rand_str()
    assert utils.strip_emojis(text) == text
    assert utils.strip_emojis(text + "😀") == text


def test_classproperty() -> None:

    class Color:

        @utils.classproperty
        def name(cls) -> str:  # noqa: N805
            return "RED"

    assert Color.name == "RED"
    assert Color().name == "RED"


def test_tokenize_search_str() -> None:
    s = "!{}"
    with pytest.raises(exc.EmptySearchError):
        utils.tokenize_search_str(s)

    s = '"query'
    r_must, r_can, r_not = utils.tokenize_search_str(s)
    assert r_must == set()
    assert r_can == {"query"}
    assert r_not == set()

    s = '+query "keep together" -ignore "    "'
    r_must, r_can, r_not = utils.tokenize_search_str(s)
    assert r_must == {"query"}
    assert r_can == {"keep together"}
    assert r_not == {"ignore"}


def test_low_pass() -> None:
    data = [Decimal(1), Decimal(0), Decimal(0), Decimal(0)]
    assert utils.low_pass(data, 1) == data

    target = [Decimal(1), Decimal("0.5"), Decimal("0.25"), Decimal("0.125")]
    assert utils.low_pass(data, 3) == target
