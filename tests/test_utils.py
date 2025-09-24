from __future__ import annotations

import ast
import datetime
import textwrap
from decimal import Decimal
from typing import TYPE_CHECKING

import numpy_financial as npf
import pytest

from nummus import exceptions as exc
from nummus import utils
from tests import conftest

if TYPE_CHECKING:
    from tests.conftest import RandomStringGenerator


@pytest.mark.parametrize(
    ("s", "c"),
    [
        ("CamelCase", "camel_case"),
        ("Camel", "camel"),
        ("camel", "camel"),
        ("HTTPClass", "http_class"),
        ("HTTPClassXYZ", "http_class_xyz"),
    ],
)
def test_camel_to_snake(s: str, c: str) -> None:
    assert utils.camel_to_snake(s) == c


def test_get_input_insecure(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    rand_str_generator: RandomStringGenerator,
) -> None:
    prompt = rand_str_generator()
    prompt_input = rand_str_generator()

    def mock_input(to_print: str) -> str | None:
        print(to_print + prompt_input)
        return prompt_input

    monkeypatch.setattr("builtins.input", mock_input)
    assert utils.get_input(prompt=prompt, secure=False) == prompt_input
    assert capsys.readouterr().out == prompt + prompt_input + "\n"


def test_get_input_insecure_abort(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    rand_str_generator: RandomStringGenerator,
) -> None:
    prompt = rand_str_generator()
    prompt_input = rand_str_generator()

    def mock_input(to_print: str) -> str | None:
        print(to_print + prompt_input)
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", mock_input)
    assert utils.get_input(prompt=prompt, secure=False) is None
    assert capsys.readouterr().out == prompt + prompt_input + "\n"


def test_get_input_secure(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    rand_str_generator: RandomStringGenerator,
) -> None:
    prompt = rand_str_generator()
    prompt_input = rand_str_generator()

    def mock_get_pass(to_print: str) -> str | None:
        print(to_print)
        return prompt_input

    monkeypatch.setattr("getpass.getpass", mock_get_pass)
    assert utils.get_input(prompt=prompt, secure=True, print_key=False) == prompt_input
    assert capsys.readouterr().out == prompt + "\n"


def test_get_input_secure_abort(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    rand_str: str,
) -> None:
    def mock_get_pass(to_print: str) -> str | None:
        print(to_print)
        raise EOFError

    monkeypatch.setattr("getpass.getpass", mock_get_pass)
    assert utils.get_input(prompt=rand_str, secure=True, print_key=False) is None
    assert capsys.readouterr().out == rand_str + "\n"


def test_get_input_secure_with_icon(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    rand_str_generator: RandomStringGenerator,
) -> None:
    prompt = rand_str_generator()
    prompt_input = rand_str_generator()

    def mock_get_pass(to_print: str) -> str | None:
        print(to_print)
        return prompt_input

    monkeypatch.setattr("getpass.getpass", mock_get_pass)
    assert utils.get_input(prompt=prompt, secure=True, print_key=True) == prompt_input
    assert capsys.readouterr().out == "\u26bf  " + prompt + "\n"


@pytest.mark.parametrize(
    ("queue", "target"),
    [
        (["password", "password"], "password"),
        (["short", "password", "typo", "password", "password"], "password"),
        ([None], None),
        (["password", None], None),
    ],
)
def test_get_password(
    monkeypatch: pytest.MonkeyPatch,
    queue: list[str | None],
    target: str,
) -> None:

    def mock_input(to_print: str, *, secure: bool) -> str | None:
        assert secure
        print(to_print)
        return queue.pop(0)

    monkeypatch.setattr(utils, "get_input", mock_input)

    assert utils.get_password() == target


@pytest.mark.parametrize(
    ("queue", "default", "target"),
    [
        ([None], False, False),
        ([None], True, True),
        (["Y"], False, True),
        (["N"], False, False),
        (["bad", "y"], False, True),
    ],
)
def test_confirm(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    rand_str: str,
    queue: list[str | None],
    default: bool,
    target: bool | None,
) -> None:
    retries = len(queue) > 1

    def mock_input(to_print: str) -> str | None:
        print(to_print)
        if len(queue) == 1:
            return queue[0]
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", mock_input)
    assert utils.confirm(prompt=rand_str, default=default) == target

    out = capsys.readouterr().out
    assert rand_str in out
    if default:
        assert "[Y/n]" in out
    else:
        assert "[y/N]" in out

    assert ("Please enter y or n" in out) == retries


@pytest.mark.parametrize(
    ("s", "target"),
    [
        (None, None),
        ("(+21.3e-5*-.1234e5/81.7)*100", Decimal("-3.22")),
        ("-1*2", Decimal(-2)),
        ("1*2", Decimal(2)),
        ("-1*-2", Decimal(2)),
        ("-1*(-2)", Decimal(2)),
        ("2>3", None),
        ("2+5j", None),
        ("(+21.3e-5*-.1234e5/81.7)*", None),
        ("__import__('os').system('rm -rf /')", None),
    ],
)
def test_evaluate_real_statement(s: str | None, target: Decimal | None) -> None:
    assert utils.evaluate_real_statement(s) == target


def test_eval_node_unknown() -> None:
    with pytest.raises(exc.EvaluationError):
        utils._eval_node(ast.expr())


@pytest.mark.parametrize(
    ("s", "precision", "target"),
    [
        (None, 2, None),
        ("", 2, None),
        ("Not a number", 2, None),
        ("1000.1", 2, Decimal("1000.1")),
        ("1000", 2, Decimal(1000)),
        ("$1,000.101", 2, Decimal("1000.1")),
        ("$1,000.101", 3, Decimal("1000.101")),
        ("-$1,000.101", 2, Decimal("-1000.1")),
        ("-$1,000.101", 3, Decimal("-1000.101")),
    ],
)
def test_parse_real(s: str | None, precision: int, target: Decimal | None) -> None:
    assert utils.parse_real(s, precision=precision) == target


@pytest.mark.parametrize(
    ("x", "plus", "target"),
    [
        (Decimal("1000.1"), False, "$1,000.10"),
        (Decimal("1000.1"), True, "+$1,000.10"),
        (Decimal("-1000.1"), False, "-$1,000.10"),
        (Decimal(), False, "$0.00"),
    ],
)
def test_format_financial(x: Decimal, plus: bool, target: str) -> None:
    assert utils.format_financial(x, plus=plus) == target


@pytest.mark.parametrize(
    ("s", "target"),
    [
        ("", None),
        ("TRUE", True),
        ("FALSE", False),
        ("t", True),
        ("f", False),
        ("1", True),
        ("0", False),
    ],
)
def test_parse_bool(s: str, target: bool | None) -> None:
    assert utils.parse_bool(s) == target


@pytest.mark.parametrize(
    ("s", "target"),
    [
        ("", None),
        ("2024-01-01", datetime.date(2024, 1, 1)),
    ],
)
def test_parse_date(s: str, target: datetime.date | None) -> None:
    assert utils.parse_date(s) == target


@pytest.mark.parametrize(
    ("d", "target"),
    [
        (0, "0 days"),
        (10, "10 days"),
        (11, "2 weeks"),
        (8 * 7, "8 weeks"),
        (8 * 7 + 1, "2 months"),
        (int(18 * 365.25 / 12), "18 months"),
        (int(18 * 365.25 / 12 + 1), "2 years"),
    ],
)
def test_format_days(d: int, target: str) -> None:
    assert utils.format_days(d) == target


def test_format_days_custom_labels(rand_str_generator: RandomStringGenerator) -> None:
    labels = [rand_str_generator() for _ in range(4)]
    assert utils.format_days(2, labels=labels) == f"2 {labels[0]}"


@pytest.mark.parametrize(
    ("s", "target"),
    [
        (0, "0.0 seconds"),
        (60, "60.0 seconds"),
        (90.1, "1.5 minutes"),
        (5400.1, "1.5 hours"),
        (86400, "24.0 hours"),
        (86400 * 4, "96.0 hours"),
        (86400 * 4.1, "4 days"),
    ],
)
def test_format_seconds(s: float, target: str) -> None:
    assert utils.format_seconds(s) == target


@pytest.mark.parametrize(
    ("include_end", "n"),
    [
        (True, 8),
        (False, 7),
    ],
)
def test_range_date(today: datetime.date, include_end: bool, n: int) -> None:
    end = today + datetime.timedelta(days=7)

    result = utils.range_date(today, end, include_end=include_end)
    assert len(result) == n
    assert result[0] == today
    if include_end:
        assert result[-1] == end
    else:
        assert result[-1] == end - datetime.timedelta(days=1)


@pytest.mark.parametrize(
    ("include_end", "n"),
    [
        (True, 8),
        (False, 7),
    ],
)
def test_range_date_ordinal_input(
    today: datetime.date,
    include_end: bool,
    n: int,
) -> None:
    end = today + datetime.timedelta(days=7)

    result = utils.range_date(
        today.toordinal(),
        end.toordinal(),
        include_end=include_end,
    )
    assert len(result) == n
    assert result[0] == today
    if include_end:
        assert result[-1] == end
    else:
        assert result[-1] == end - datetime.timedelta(days=1)


@pytest.mark.parametrize(
    ("start", "n", "target"),
    [
        (datetime.date(2023, 1, 1), 0, datetime.date(2023, 1, 1)),
        (datetime.date(2023, 1, 1), 1, datetime.date(2023, 2, 1)),
        (datetime.date(2023, 1, 1), 12, datetime.date(2024, 1, 1)),
        (datetime.date(2023, 1, 1), 11, datetime.date(2023, 12, 1)),
        (datetime.date(2023, 1, 1), -1, datetime.date(2022, 12, 1)),
        (datetime.date(2023, 1, 1), -12, datetime.date(2022, 1, 1)),
        (datetime.date(2023, 1, 1), -11, datetime.date(2022, 2, 1)),
        (datetime.date(2023, 6, 30), 0, datetime.date(2023, 6, 30)),
        (datetime.date(2023, 6, 30), 1, datetime.date(2023, 7, 30)),
        (datetime.date(2023, 6, 30), 12, datetime.date(2024, 6, 30)),
        (datetime.date(2023, 6, 30), 23, datetime.date(2025, 5, 30)),
        (datetime.date(2023, 6, 30), -4, datetime.date(2023, 2, 28)),
        (datetime.date(2020, 1, 31), 1, datetime.date(2020, 2, 29)),
    ],
    ids=conftest.id_func,
)
def test_date_add_months(start: datetime.date, n: int, target: datetime.date) -> None:
    assert utils.date_add_months(start, n) == target


def test_period_months_single() -> None:
    start = datetime.date(2023, 1, 10)
    start_ord = start.toordinal()
    end = datetime.date(2023, 1, 28)
    end_ord = end.toordinal()
    target = {
        "2023-01": (start_ord, end_ord),
    }
    assert utils.period_months(start_ord, end_ord) == target


def test_period_months_multiple() -> None:
    start = datetime.date(2023, 1, 10)
    start_ord = start.toordinal()
    end = datetime.date(2023, 2, 14)
    end_ord = end.toordinal()
    target = {
        "2023-01": (start_ord, datetime.date(2023, 1, 31).toordinal()),
        "2023-02": (datetime.date(2023, 2, 1).toordinal(), end_ord),
    }
    assert utils.period_months(start_ord, end_ord) == target


def test_period_years_single_month() -> None:
    start = datetime.date(2023, 1, 10)
    start_ord = start.toordinal()
    end = datetime.date(2023, 1, 28)
    end_ord = end.toordinal()
    target = {
        "2023": (start_ord, end_ord),
    }
    assert utils.period_years(start_ord, end_ord) == target


def test_period_years_two_months() -> None:
    start = datetime.date(2023, 1, 10)
    start_ord = start.toordinal()
    end = datetime.date(2023, 2, 14)
    end_ord = end.toordinal()
    target = {
        "2023": (start_ord, end_ord),
    }
    assert utils.period_years(start_ord, end_ord) == target


def test_period_years_two_years() -> None:
    start = datetime.date(2023, 1, 10)
    start_ord = start.toordinal()
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


def test_round_list() -> None:
    n = 9
    list_ = [1 / Decimal(n) for _ in range(n)]
    assert sum(list_) != 1

    l_round = utils.round_list(list_)
    assert sum(l_round) == 1
    assert l_round[0] != list_[0]
    assert l_round[0] == round(list_[0], 6)


@pytest.mark.parametrize(
    ("deltas", "target"),
    [
        pytest.param([], [], id="empty"),
        pytest.param([Decimal()] * 5, [Decimal()] * 5, id="zeros"),
        pytest.param([None] * 5, [Decimal()] * 5, id="nones"),
        pytest.param(
            [None, None, Decimal(20), None, None],
            [Decimal(), Decimal(), Decimal(20), Decimal(20), Decimal(20)],
            id="one sample",
        ),
        pytest.param(
            [Decimal(1), Decimal(3), Decimal(5)],
            [Decimal(1), Decimal(4), Decimal(9)],
            id="all samples",
        ),
    ],
)
def test_integrate(deltas: list[Decimal | None], target: list[Decimal]) -> None:
    assert utils.integrate(deltas) == target


@pytest.mark.parametrize(
    ("values", "target"),
    [
        pytest.param([], [Decimal()] * 5, id="empty"),
        pytest.param([(-3, Decimal(-1))], [Decimal(-1)] * 5, id="past"),
        pytest.param(
            [(-3, Decimal(-1)), (1, Decimal(1))],
            [Decimal(-1)] + [Decimal(1)] * 4,
            id="one in range",
        ),
        pytest.param(
            [(-3, Decimal(-1)), (1, Decimal(1)), (3, Decimal(3))],
            [Decimal(-1), Decimal(1), Decimal(1), Decimal(3), Decimal(3)],
            id="two in range",
        ),
    ],
)
def test_interpolate_step(
    values: list[tuple[int, Decimal]],
    target: list[Decimal],
) -> None:
    assert utils.interpolate_step(values, 5) == target


@pytest.mark.parametrize(
    ("values", "target"),
    [
        pytest.param([], [Decimal()] * 5, id="empty"),
        pytest.param([(-3, Decimal(-1))], [Decimal(-1)] * 5, id="past"),
        pytest.param(
            [(-3, Decimal(-1)), (1, Decimal(1))],
            [Decimal("0.5"), Decimal(1), Decimal(1), Decimal(1), Decimal(1)],
            id="one in range",
        ),
        pytest.param(
            [(-3, Decimal(-1)), (1, Decimal(1)), (3, Decimal(3))],
            [Decimal("0.5"), Decimal(1), Decimal(2), Decimal(3), Decimal(3)],
            id="two in range",
        ),
    ],
)
def test_interpolate_linear(
    values: list[tuple[int, Decimal]],
    target: list[Decimal],
) -> None:
    assert utils.interpolate_linear(values, 5) == target


@pytest.mark.parametrize(
    ("values", "profit", "target"),
    [
        pytest.param([Decimal()] * 5, [Decimal()] * 5, [Decimal()] * 5, id="empty"),
        pytest.param(
            [Decimal(), Decimal(10), Decimal(10), Decimal(10), Decimal()],
            [Decimal()] * 5,
            [Decimal()] * 5,
            id="no profit",
        ),
        pytest.param(
            [Decimal(), Decimal(11), Decimal(11), Decimal(11), Decimal()],
            [Decimal(), Decimal(1), Decimal(1), Decimal(1), Decimal(1)],
            [
                Decimal(),
                Decimal("0.1"),
                Decimal("0.1"),
                Decimal("0.1"),
                Decimal("0.1"),
            ],
            id="profit on buy day",
        ),
        pytest.param(
            [Decimal(), Decimal(11), Decimal(11), Decimal(11), Decimal()],
            [Decimal(), Decimal(1), Decimal(1), Decimal(1), Decimal(12)],
            [
                Decimal(),
                Decimal("0.1"),
                Decimal("0.1"),
                Decimal("0.1"),
                Decimal("1.2"),
            ],
            id="profit on buy and sell day",
        ),
        pytest.param(
            [Decimal(10), Decimal(21), Decimal(42), Decimal(42), Decimal()],
            [Decimal(), Decimal(1), Decimal(22), Decimal(22), Decimal(22)],
            [
                Decimal(),
                Decimal("0.1"),
                Decimal("1.2"),
                Decimal("1.2"),
                Decimal("1.2"),
            ],
            id="profit on buy and mid day",
        ),
        pytest.param(
            [
                # Buy 100 shares at $100
                Decimal(10000),
                # Buy 100 more at $500
                Decimal(100000),
                # Sell 100 at $50
                Decimal(5000),
                # Returns to $100
                Decimal(10000),
            ],
            [Decimal(), Decimal(40000), Decimal(-50000), Decimal(-45000)],
            [Decimal(), Decimal(4), Decimal("-0.5"), Decimal()],
            id="profit and loss",
        ),
    ],
)
def test_twrr(
    values: list[Decimal],
    profit: list[Decimal],
    target: list[Decimal],
) -> None:
    assert utils.twrr(values, profit) == target


@pytest.mark.parametrize(
    ("values", "profit", "target"),
    [
        pytest.param([Decimal()] * 5, [Decimal()] * 5, Decimal(), id="empty"),
        pytest.param(
            [Decimal(), Decimal(10), Decimal(10), Decimal(10), Decimal()],
            [Decimal()] * 5,
            Decimal(),
            id="no profit",
        ),
        pytest.param(
            [Decimal(101)],
            [Decimal(1)],
            round(Decimal((101 / 100) ** 365.25) - 1, 6),
            id="one day profit",
        ),
        pytest.param(
            [Decimal(20)],
            [Decimal(-100)],
            Decimal(-1),
            id="one day loss",
        ),
        pytest.param(
            [Decimal(), Decimal(101), Decimal(101), Decimal(101), Decimal()],
            [Decimal(), Decimal(1), Decimal(1), Decimal(1), Decimal(1)],
            [Decimal(), Decimal(-100), Decimal(), Decimal(), Decimal(101)],
            id="profit on buy",
        ),
        pytest.param(
            [Decimal(), Decimal(101), Decimal(101), Decimal(101), Decimal()],
            [Decimal(), Decimal(1), Decimal(1), Decimal(1), Decimal(2)],
            [Decimal(), Decimal(-100), Decimal(), Decimal(), Decimal(102)],
            id="profit on buy and sell day",
        ),
        pytest.param(
            [Decimal(100), Decimal(201), Decimal(202), Decimal(202), Decimal()],
            [Decimal(), Decimal(1), Decimal(2), Decimal(2), Decimal(2)],
            [Decimal(-100), Decimal(-100), Decimal(), Decimal(), Decimal(202)],
            id="profit on buy and mid day",
        ),
        pytest.param(
            [Decimal(100), Decimal(101), Decimal(102), Decimal(103), Decimal(104)],
            [Decimal(), Decimal(1), Decimal(2), Decimal(3), Decimal(4)],
            [Decimal(-100), Decimal(), Decimal(), Decimal(), Decimal(104)],
            id="profit on every day",
        ),
        pytest.param(
            [
                # Buy 100 shares at $100
                Decimal(10000),
                # Buy 100 more at $500
                Decimal(100000),
                # Sell 100 at $50
                Decimal(5000),
                # Returns to $100
                Decimal(10000),
            ],
            [Decimal(), Decimal(40000), Decimal(-50000), Decimal(-45000)],
            [Decimal(-10000), Decimal(-50000), Decimal(5000), Decimal(10000)],
            id="profit and loss",
        ),
        # 5x in one day!! is too high
        ([Decimal(1), Decimal(5)], [Decimal(0), Decimal(5)], None),
    ],
)
def test_mwrr(
    values: list[Decimal],
    profit: list[Decimal],
    target: Decimal | list[Decimal] | None,
) -> None:
    if isinstance(target, list):
        # target is cash_flows
        target = round(Decimal((npf.irr(target) + 1) ** 365.25) - 1, 6)
    assert utils.mwrr(values, profit) == target


def test_pretty_table_no_rows() -> None:
    with pytest.raises(ValueError, match="Table has no rows"):
        utils.pretty_table([])


def test_pretty_table_no_header() -> None:
    with pytest.raises(ValueError, match="First row cannot be None"):
        utils.pretty_table([None])


def test_pretty_table_only_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.get_terminal_size", lambda **_: (80, 24))
    table: list[list[str] | None] = [
        ["H1", ">H2", "<H3", "^H4", "H5.", "H6/"],
    ]
    target = textwrap.dedent(
        """\
    ╭────┬────┬────┬────┬────┬────╮
    │ H1 │ H2 │ H3 │ H4 │ H5 │ H6 │
    ╰────┴────┴────┴────┴────┴────╯""",
    )
    assert "\n".join(utils.pretty_table(table)) == target

    # Reset terminal width before verbose info is printed
    monkeypatch.undo()


def test_pretty_table_only_separator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.get_terminal_size", lambda **_: (80, 24))
    table: list[list[str] | None] = [
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

    # Reset terminal width before verbose info is printed
    monkeypatch.undo()


@pytest.fixture
def table() -> list[list[str] | None]:
    return [
        ["H1", ">H2", "<H3", "^H4", "H5.", "H6/"],
        None,
        ["Short"] * 6,
        None,
        ["Long word"] * 6,
    ]


def test_pretty_table_width_80(
    monkeypatch: pytest.MonkeyPatch,
    table: list[list[str] | None],
) -> None:
    monkeypatch.setattr("shutil.get_terminal_size", lambda **_: (80, 24))
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

    # Reset terminal width before verbose info is printed
    monkeypatch.undo()


def test_pretty_table_width_70(
    monkeypatch: pytest.MonkeyPatch,
    table: list[list[str] | None],
) -> None:
    # Make terminal smaller, extra space goes first
    monkeypatch.setattr("shutil.get_terminal_size", lambda **_: (70, 24))
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

    # Reset terminal width before verbose info is printed
    monkeypatch.undo()


def test_pretty_table_width_60(
    monkeypatch: pytest.MonkeyPatch,
    table: list[list[str] | None],
) -> None:
    # Make terminal smaller, truncate column goes next
    monkeypatch.setattr("shutil.get_terminal_size", lambda **_: (60, 24))
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

    # Reset terminal width before verbose info is printed
    monkeypatch.undo()


def test_pretty_table_width_50(
    monkeypatch: pytest.MonkeyPatch,
    table: list[list[str] | None],
) -> None:
    # Make terminal smaller, other columns go next
    monkeypatch.setattr("shutil.get_terminal_size", lambda **_: (50, 24))
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

    # Reset terminal width before verbose info is printed
    monkeypatch.undo()


def test_pretty_table_width_10(
    monkeypatch: pytest.MonkeyPatch,
    table: list[list[str] | None],
) -> None:
    # Make terminal tiny, other columns go next, never last
    monkeypatch.setattr("shutil.get_terminal_size", lambda **_: (10, 24))
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

    # Reset terminal width before verbose info is printed
    monkeypatch.undo()


@pytest.mark.parametrize(
    ("items", "target"),
    [
        pytest.param(
            {"Apple", "Banana", "Strawberry"},
            {"Apple", "Banana", "Strawberry"},
            id="no duplicates",
        ),
        pytest.param(
            {"Apple", "Banana", "Bananas", "Strawberry"},
            {"Apple", "Banana", "Strawberry"},
            id="one duplicate",
        ),
        pytest.param(
            {
                "Apple",
                "Banana",
                "Bananas",
                "Strawberry",
                "Mango",
                "Mengo",
                "A bunch of chocolate pies",
                "A bunch of chocolate cake",
                "A bunch of chocolate tart",
            },
            {"Apple", "Banana", "Strawberry", "Mango", "A bunch of chocolate cake"},
            id="typos",
        ),
    ],
)
def test_dedupe(items: set[str], target: set[str]) -> None:
    assert utils.dedupe(items) == target


@pytest.mark.parametrize(
    ("start", "end", "n"),
    [
        (datetime.date(2024, 11, 1), datetime.date(2024, 11, 1), 0),
        (datetime.date(2024, 11, 1), datetime.date(2024, 11, 30), 0),
        (datetime.date(2024, 11, 1), datetime.date(2024, 12, 31), 1),
        (datetime.date(2023, 11, 1), datetime.date(2024, 10, 15), 11),
        (datetime.date(2024, 11, 1), datetime.date(2023, 10, 15), -13),
    ],
)
def test_date_months_between(start: datetime.date, end: datetime.date, n: int) -> None:
    assert utils.date_months_between(start, end) == n
    assert utils.date_months_between(end, start) == -n


@pytest.mark.parametrize(
    ("weekday", "n"),
    [
        (0, 4),
        (1, 4),
        (2, 4),
        (3, 4),
        (4, 5),
        (5, 5),
        (6, 4),
    ],
)
def test_weekdays_in_month(weekday: int, n: int) -> None:
    date = datetime.date(2024, 11, 1)
    assert utils.weekdays_in_month(weekday, date) == n


def test_start_of_month() -> None:
    date = datetime.date(2024, 2, 20)
    assert utils.start_of_month(date) == datetime.date(2024, 2, 1)


def test_end_of_month() -> None:
    date = datetime.date(2024, 2, 20)
    assert utils.end_of_month(date) == datetime.date(2024, 2, 29)


@pytest.mark.parametrize(
    ("x", "target"),
    [
        (Decimal("0.5"), Decimal("0.5")),
        (Decimal("-0.5"), Decimal()),
        (Decimal("1.5"), Decimal(1)),
    ],
)
def test_clamp(x: Decimal, target: Decimal) -> None:
    assert utils.clamp(x) == target


def test_clamp_custom_max() -> None:
    assert utils.clamp(Decimal(150), c_max=Decimal(100)) == Decimal(100)


def test_clamp_custom_min() -> None:
    assert utils.clamp(Decimal(-150), c_min=Decimal(-100)) == Decimal(-100)


@pytest.mark.parametrize("suffix", ["", "😀"])
def test_strip_emojis(rand_str: str, suffix: str) -> None:
    assert utils.strip_emojis(rand_str + suffix) == rand_str


def test_tokenize_search_str_only_symbols() -> None:
    s = "!{}"
    with pytest.raises(exc.EmptySearchError):
        utils.tokenize_search_str(s)


def test_tokenize_search_str_unbalanced_quote() -> None:
    s = '"query'
    r_must, r_can, r_not = utils.tokenize_search_str(s)
    assert r_must == set()
    assert r_can == {"query"}
    assert r_not == set()


def test_tokenize_search_str_everything() -> None:
    s = '+query "keep together" -ignore "    "'
    r_must, r_can, r_not = utils.tokenize_search_str(s)
    assert r_must == {"query"}
    assert r_can == {"keep together"}
    assert r_not == {"ignore"}


def test_low_pass_n1() -> None:
    data = [Decimal(1), Decimal(), Decimal(), Decimal()]
    assert utils.low_pass(data, 1) == data


def test_low_pass_n3() -> None:
    data = [Decimal(1), Decimal(), Decimal(), Decimal()]
    target = [Decimal(1), Decimal("0.5"), Decimal("0.25"), Decimal("0.125")]
    assert utils.low_pass(data, 3) == target
