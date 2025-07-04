from __future__ import annotations

import datetime
import io
import shutil
import textwrap
from decimal import Decimal
from unittest import mock

import numpy_financial as npf
from colorama import Fore

from nummus import exceptions as exc
from nummus import utils
from tests.base import TestBase


class TestUtils(TestBase):
    def test_camel_to_snake(self) -> None:
        s = "CamelCase"
        target = "camel_case"
        result = utils.camel_to_snake(s)
        self.assertEqual(result, target)

        s = "Camel"
        target = "camel"
        result = utils.camel_to_snake(s)
        self.assertEqual(result, target)

        s = "camel"
        target = "camel"
        result = utils.camel_to_snake(s)
        self.assertEqual(result, target)

        s = "HTTPClass"
        target = "http_class"
        result = utils.camel_to_snake(s)
        self.assertEqual(result, target)

        s = "HTTPClassXYZ"
        target = "http_class_xyz"
        result = utils.camel_to_snake(s)
        self.assertEqual(result, target)

    def test_get_input(self) -> None:
        prompt = self.random_string()
        prompt_input = self.random_string(length=50)

        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = utils.getpass.getpass

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

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            utils.getpass.getpass = mock_get_pass

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_input(prompt=prompt, secure=False)

            self.assertEqual(fake_stdout.getvalue(), prompt + prompt_input + "\n")
            self.assertEqual(prompt_input, result)

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_input(prompt=prompt, secure=True, print_key=False)

            self.assertEqual(fake_stdout.getvalue(), prompt + "\n")
            self.assertEqual(prompt_input, result)

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_input(prompt=prompt, secure=True, print_key=True)

            self.assertEqual(fake_stdout.getvalue(), "\u26bf  " + prompt + "\n")
            self.assertEqual(prompt_input, result)

            mock.builtins.input = mock_input_interrupt  # type: ignore[attr-defined]
            utils.getpass.getpass = mock_get_pass_eof

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_input(prompt=prompt, secure=False)

            self.assertEqual(fake_stdout.getvalue(), prompt + prompt_input + "\n")
            self.assertIsNone(result)

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_input(prompt=prompt, secure=True, print_key=False)

            self.assertEqual(fake_stdout.getvalue(), prompt + "\n")
            self.assertIsNone(result)

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            utils.getpass.getpass = original_get_pass

    def test_get_password(self) -> None:
        key = self.random_string()
        queue: list[str | None] = []

        def mock_input(to_print: str, *, secure: bool) -> str | None:
            self.assertTrue(secure)
            print(to_print)  # noqa: T201
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        original_get_input = utils.get_input
        try:
            utils.get_input = mock_input

            queue = [key, key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_password()

            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \nPlease confirm password: \n"
            self.assertEqual(fake_stdout, target)
            self.assertEqual(result, key)

            queue = [self.random_string(7), key, key + "typo", key, key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_password()

            fake_stdout = fake_stdout.getvalue()
            target = (
                "Please enter password: \n"
                f"{Fore.RED}Password must be at least 8 characters\n"
                "Please enter password: \n"
                "Please confirm password: \n"
                f"{Fore.RED}Passwords must match\n"
                "Please enter password: \n"
                "Please confirm password: \n"
            )
            self.assertEqual(fake_stdout, target)
            self.assertEqual(result, key)

            queue = [None]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_password()

            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \n"
            self.assertEqual(fake_stdout, target)
            self.assertIsNone(result)

            queue = [key, None]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_password()

            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \nPlease confirm password: \n"
            self.assertEqual(fake_stdout, target)
            self.assertIsNone(result)
        finally:
            utils.get_input = original_get_input

    def test_confirm(self) -> None:
        prompt = self.random_string()
        prompt_input = self.random_string(length=50)

        original_input = mock.builtins.input  # type: ignore[attr-defined]

        try:
            mock.builtins.input = lambda _: None  # type: ignore[attr-defined]

            result = utils.confirm(prompt=None, default=False)
            self.assertFalse(result, "Default is not False")

            result = utils.confirm(prompt=prompt, default=True)
            self.assertTrue(result, "Default is not True")

            mock.builtins.input = lambda _: "Y"  # type: ignore[attr-defined]

            result = utils.confirm(prompt=prompt)
            self.assertTrue(result, "Y is not True")

            mock.builtins.input = lambda _: "N"  # type: ignore[attr-defined]

            result = utils.confirm(prompt=prompt)
            self.assertFalse(result, "N is not False")

            queue = [prompt_input, "y"]

            def _mock_input(_) -> str | None:
                if len(queue) == 1:
                    return queue[0]
                return queue.pop(0)

            mock.builtins.input = _mock_input  # type: ignore[attr-defined]

            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                result = utils.confirm(prompt=prompt)
            self.assertTrue(result, "Y is not True")

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]

    def test_evaluate_real_statement(self) -> None:
        result = utils.evaluate_real_statement(None)
        self.assertIsNone(result)

        s = "(+21.3e-5*-.1234e5/81.7)*100"
        result = utils.evaluate_real_statement(s)
        target = Decimal("21.3e-5") * Decimal("-.1234e5") / Decimal("81.7") * 100
        self.assertEqual(result, round(target, 2))

        # Incomplete
        s = "(+21.3e-5*-.1234e5/81.7)*"
        result = utils.evaluate_real_statement(s)
        self.assertIsNone(result)

        # Unsupported operator
        s = "2>3"
        result = utils.evaluate_real_statement(s)
        self.assertIsNone(result)

        s = "__import__('os').system('rm -rf /')"
        result = utils.evaluate_real_statement(s)
        self.assertIsNone(result)

        s = "2+5j"
        result = utils.evaluate_real_statement(s)
        self.assertIsNone(result)

    def test_parse_real(self) -> None:
        result = utils.parse_real(None)
        self.assertIsNone(result)

        result = utils.parse_real("")
        self.assertIsNone(result)

        result = utils.parse_real("Not a number")
        self.assertIsNone(result)

        s = "1000.1"
        result = utils.parse_real(s)
        self.assertEqual(result, Decimal("1000.1"))

        s = "1000"
        result = utils.parse_real(s)
        self.assertEqual(result, Decimal(1000))

        s = "1,000.1"
        result = utils.parse_real(s)
        self.assertEqual(result, Decimal("1000.1"))

        s = "$1000.101"
        result = utils.parse_real(s)
        self.assertEqual(result, Decimal("1000.1"))

        s = "$1,000.101"
        result = utils.parse_real(s, precision=3)
        self.assertEqual(result, Decimal("1000.101"))

        s = "-$1,000.101"
        result = utils.parse_real(s)
        self.assertEqual(result, Decimal("-1000.1"))

        s = "-$1,000.101"
        result = utils.parse_real(s, precision=3)
        self.assertEqual(result, Decimal("-1000.101"))

    def test_format_financial(self) -> None:
        x = Decimal("1000.1")
        result = utils.format_financial(x)
        self.assertEqual(result, "$1,000.10")
        result = utils.format_financial(x, plus=True)
        self.assertEqual(result, "+$1,000.10")

        x = Decimal("-1000.1")
        result = utils.format_financial(x)
        self.assertEqual(result, "-$1,000.10")

        x = Decimal(0)
        result = utils.format_financial(x)
        self.assertEqual(result, "$0.00")

    def test_parse_bool(self) -> None:
        result = utils.parse_bool("")
        self.assertIsNone(result)

        result = utils.parse_bool("TRUE")
        self.assertTrue(result)

        result = utils.parse_bool("FALSE")
        self.assertFalse(result)

        result = utils.parse_bool("t")
        self.assertTrue(result)

        result = utils.parse_bool("f")
        self.assertFalse(result)

        result = utils.parse_bool("1")
        self.assertTrue(result)

        result = utils.parse_bool("0")
        self.assertFalse(result)

    def test_parse_date(self) -> None:
        result = utils.parse_date(None)
        self.assertIsNone(result)

        result = utils.parse_date("")
        self.assertIsNone(result)

        result = utils.parse_date("2024-01-01")
        target = datetime.date(2024, 1, 1)
        self.assertEqual(result, target)

    def test_format_days(self) -> None:
        d = 0
        result = utils.format_days(d)
        self.assertEqual(result, "0 days")

        labels = [self.random_string() for _ in range(4)]
        d = 2
        result = utils.format_days(d, labels=labels)
        self.assertEqual(result, f"2 {labels[0]}")

        d = 10
        result = utils.format_days(d)
        self.assertEqual(result, "10 days")

        d = 11
        result = utils.format_days(d)
        self.assertEqual(result, "2 weeks")

        d = 8 * 7
        result = utils.format_days(d)
        self.assertEqual(result, "8 weeks")

        d = 8 * 7 + 1
        result = utils.format_days(d)
        self.assertEqual(result, "2 months")

        d = int(18 * 365.25 / 12)
        result = utils.format_days(d)
        self.assertEqual(result, "18 months")

        d = int(18 * 365.25 / 12 + 1)
        result = utils.format_days(d)
        self.assertEqual(result, "2 years")

    def test_format_seconds(self) -> None:
        s = 0.0
        result = utils.format_seconds(s)
        self.assertEqual(result, "0.0 seconds")

        s = 60.0
        result = utils.format_seconds(s)
        self.assertEqual(result, "60.0 seconds")

        s = 90.1
        result = utils.format_seconds(s)
        self.assertEqual(result, "1.5 minutes")

        s = 5400.1
        result = utils.format_seconds(s)
        self.assertEqual(result, "1.5 hours")

        s = 86400.0
        result = utils.format_seconds(s)
        self.assertEqual(result, "24.0 hours")

        s = 86400 * 4.0
        result = utils.format_seconds(s)
        self.assertEqual(result, "96.0 hours")

        s = 86400 * 4.1
        result = utils.format_seconds(s)
        self.assertEqual(result, "4 days")

    def test_range_date(self) -> None:
        start = datetime.datetime.now().astimezone().date()
        end = start + datetime.timedelta(days=7)
        start_ord = start.toordinal()
        end_ord = end.toordinal()

        result = utils.range_date(start, end, include_end=True)
        self.assertEqual(len(result), 8)
        self.assertEqual(result[0], start)
        self.assertEqual(result[-1], end)

        result = utils.range_date(start_ord, end_ord, include_end=True)
        self.assertEqual(len(result), 8)
        self.assertEqual(result[0], start)
        self.assertEqual(result[-1], end)

        result = utils.range_date(start, end, include_end=False)
        self.assertEqual(len(result), 7)
        self.assertEqual(result[0], start)
        self.assertEqual(result[-1], end - datetime.timedelta(days=1))

        result = utils.range_date(start_ord, end_ord, include_end=False)
        self.assertEqual(len(result), 7)
        self.assertEqual(result[0], start)
        self.assertEqual(result[-1], end - datetime.timedelta(days=1))

    def test_date_add_months(self) -> None:
        start = datetime.date(2023, 1, 1)
        self.assertEqual(
            utils.date_add_months(start, 0),
            start,
        )
        self.assertEqual(
            utils.date_add_months(start, 1),
            datetime.date(2023, 2, 1),
        )
        self.assertEqual(
            utils.date_add_months(start, 12),
            datetime.date(2024, 1, 1),
        )
        self.assertEqual(
            utils.date_add_months(start, 11),
            datetime.date(2023, 12, 1),
        )
        self.assertEqual(
            utils.date_add_months(start, -1),
            datetime.date(2022, 12, 1),
        )
        self.assertEqual(
            utils.date_add_months(start, -12),
            datetime.date(2022, 1, 1),
        )
        self.assertEqual(
            utils.date_add_months(start, -11),
            datetime.date(2022, 2, 1),
        )

        start = datetime.date(2023, 6, 30)
        self.assertEqual(
            utils.date_add_months(start, 0),
            start,
        )
        self.assertEqual(
            utils.date_add_months(start, 1),
            datetime.date(2023, 7, 30),
        )
        self.assertEqual(
            utils.date_add_months(start, 12),
            datetime.date(2024, 6, 30),
        )
        self.assertEqual(
            utils.date_add_months(start, 23),
            datetime.date(2025, 5, 30),
        )
        self.assertEqual(
            utils.date_add_months(start, -4),
            datetime.date(2023, 2, 28),
        )

        start = datetime.date(2020, 1, 31)
        self.assertEqual(
            utils.date_add_months(start, 1),
            datetime.date(2020, 2, 29),
        )

    def test_period_months(self) -> None:
        start = datetime.date(2023, 1, 10)
        start_ord = start.toordinal()
        end = datetime.date(2023, 1, 28)
        end_ord = end.toordinal()
        target = {
            "2023-01": (start_ord, end_ord),
        }
        result = utils.period_months(start_ord, end_ord)
        self.assertEqual(result, target)

        end = datetime.date(2023, 2, 14)
        end_ord = end.toordinal()
        target = {
            "2023-01": (start_ord, datetime.date(2023, 1, 31).toordinal()),
            "2023-02": (datetime.date(2023, 2, 1).toordinal(), end_ord),
        }
        result = utils.period_months(start_ord, end_ord)
        self.assertEqual(result, target)

    def test_period_years(self) -> None:
        start = datetime.date(2023, 1, 10)
        start_ord = start.toordinal()
        end = datetime.date(2023, 1, 28)
        end_ord = end.toordinal()
        target = {
            "2023": (start_ord, end_ord),
        }
        result = utils.period_years(start_ord, end_ord)
        self.assertEqual(result, target)

        end = datetime.date(2023, 2, 14)
        end_ord = end.toordinal()
        target = {
            "2023": (start_ord, end_ord),
        }
        result = utils.period_years(start_ord, end_ord)
        self.assertEqual(result, target)

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
        result = utils.period_years(start_ord, end_ord)
        self.assertEqual(result, target)

    def test_downsample(self) -> None:
        start = datetime.date(2023, 1, 10)
        start_ord = start.toordinal()
        end = datetime.date(2023, 1, 28)
        end_ord = end.toordinal()
        n = end_ord - start_ord + 1

        values = [Decimal(i) for i in range(n)]

        labels, r_min, r_avg, r_max = utils.downsample(start_ord, end_ord, values)
        self.assertEqual(labels, ["2023-01"])
        self.assertEqual(r_min, [Decimal(0)])
        self.assertEqual(r_avg, [Decimal(n - 1) / 2])
        self.assertEqual(r_max, [Decimal(n - 1)])

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
        self.assertEqual(labels, ["2023-01", "2023-02"])
        self.assertEqual(r_min, [Decimal(1), Decimal(5)])
        self.assertEqual(r_avg, [Decimal(2), Decimal(6)])
        self.assertEqual(r_max, [Decimal(3), Decimal(7)])

    def test_round_list(self) -> None:
        n = 9
        list_ = [1 / Decimal(n) for _ in range(n)]
        self.assertNotEqual(sum(list_), 1)

        l_round = utils.round_list(list_)
        self.assertEqual(sum(l_round), 1)
        self.assertNotEqual(l_round[0], list_[0])
        self.assertEqual(l_round[0], round(list_[0], 6))

    def test_integrate(self) -> None:
        deltas: list[Decimal | None] = []
        result = utils.integrate(deltas)
        self.assertEqual(result, [])

        deltas = [Decimal(0)] * 5
        target = [Decimal(0)] * 5
        result = utils.integrate(deltas)
        self.assertEqual(result, target)

        deltas = [None] * 5
        target = [Decimal(0)] * 5
        result = utils.integrate(deltas)
        self.assertEqual(result, target)

        deltas[2] = Decimal(20)
        target[2] += Decimal(20)
        target[3] += Decimal(20)
        target[4] += Decimal(20)
        result = utils.integrate(deltas)
        self.assertEqual(result, target)

    def test_interpolate_step(self) -> None:
        n = 6
        values: list[tuple[int, Decimal]] = []

        target = [Decimal(0)] * n
        result = utils.interpolate_step(values, n)
        self.assertEqual(result, target)

        values.append((-3, Decimal(-1)))
        target = [Decimal(-1)] * n
        result = utils.interpolate_step(values, n)
        self.assertEqual(result, target)

        values.append((1, Decimal(1)))
        target = [Decimal(1)] * n
        target[0] = Decimal(-1)
        result = utils.interpolate_step(values, n)
        self.assertEqual(result, target)

        values.append((4, Decimal(3)))
        target[4] = Decimal(3)
        target[5] = Decimal(3)
        result = utils.interpolate_step(values, n)
        self.assertEqual(result, target)

    def test_interpolate_linear(self) -> None:
        n = 6
        values: list[tuple[int, Decimal]] = []

        target = [Decimal(0)] * n
        result = utils.interpolate_linear(values, n)
        self.assertEqual(result, target)

        values.append((-3, Decimal(-1)))
        target = [Decimal(-1)] * n
        result = utils.interpolate_linear(values, n)
        self.assertEqual(result, target)

        values.append((1, Decimal(1)))
        target = [
            Decimal("0.5"),
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal(1),
            Decimal(1),
        ]
        result = utils.interpolate_linear(values, n)
        self.assertEqual(result, target)

        values.append((4, Decimal(3)))
        target = [
            Decimal("0.5"),
            Decimal(1),
            Decimal(1) + Decimal(2) / Decimal(3),
            Decimal(1) + Decimal(2) / Decimal(3) * Decimal(2),
            Decimal(3),
            Decimal(3),  # Stay flat at the end
        ]
        result = utils.interpolate_linear(values, n)
        self.assertEqual(result, target)

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
        result = utils.interpolate_linear(values, n)
        self.assertEqual(result, target)

    def test_twrr(self) -> None:
        n = 5
        values = [Decimal(0)] * n
        profit = [Decimal(0)] * n
        target = [Decimal(0)] * n

        result = utils.twrr(values, profit)
        self.assertEqual(result, target)

        # Still no profit, no profit percent
        values = [
            Decimal(0),
            Decimal(10),
            Decimal(10),
            Decimal(10),
            Decimal(0),
        ]
        result = utils.twrr(values, profit)
        self.assertEqual(result, target)

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
        result = utils.twrr(values, profit)
        self.assertEqual(result, target)

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
        result = utils.twrr(values, profit)
        self.assertEqual(result, target)
        result = utils.twrr(values[1:], profit[1:])
        self.assertEqual(result, target[1:])

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
        result = utils.twrr(values, profit)
        self.assertEqual(result, target)

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
        result = utils.twrr(values, profit)
        self.assertEqual(result, target)

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
        result = utils.twrr(values, profit)
        self.assertEqual(result, target)

    def test_mwrr(self) -> None:
        n = 5
        values = [Decimal(0)] * n
        profit = [Decimal(0)] * n
        target = Decimal(0)

        result = utils.mwrr(values, profit)
        self.assertEqual(result, target)

        # Still no profit, no profit percent
        values = [
            Decimal(0),
            Decimal(10),
            Decimal(10),
            Decimal(10),
            Decimal(0),
        ]
        result = utils.mwrr(values, profit)
        self.assertEqual(result, target)

        values = [Decimal(101)]
        profit = [Decimal(1)]
        result = utils.mwrr(values, profit)
        target = round(Decimal((101 / 100) ** 365.25) - 1, 6)
        self.assertEqual(result, target)

        values = [Decimal(20)]
        profit = [Decimal(-100)]
        result = utils.mwrr(values, profit)
        target = Decimal(-1)
        self.assertEqual(result, target)

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
        result = utils.mwrr(values, profit)
        self.assertEqual(result, target)

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
        result = utils.mwrr(values, profit)
        self.assertEqual(result, target)

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
        result = utils.mwrr(values, profit)
        self.assertEqual(result, target)

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
        result = utils.mwrr(values, profit)
        self.assertEqual(result, target)

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
        result = utils.mwrr(values, profit)
        self.assertEqual(result, target)

    def test_pretty_table(self) -> None:
        table: list[list[str] | None] = []
        self.assertRaises(ValueError, utils.pretty_table, table)

        table = [None]
        self.assertRaises(ValueError, utils.pretty_table, table)

        original_terminal_size = shutil.get_terminal_size
        try:
            shutil.get_terminal_size = lambda: (80, 24)

            table = [
                ["H1", ">H2", "<H3", "^H4", "H5.", "H6/"],
            ]
            target = textwrap.dedent(
                """\
            ╭────┬────┬────┬────┬────┬────╮
            │ H1 │ H2 │ H3 │ H4 │ H5 │ H6 │
            ╰────┴────┴────┴────┴────┴────╯""",
            )
            result = "\n".join(utils.pretty_table(table))
            self.assertEqual(result, target)

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
            result = "\n".join(utils.pretty_table(table))
            self.assertEqual(result, target)

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
            result = "\n".join(utils.pretty_table(table))
            self.assertEqual(result, target)

            # Make terminal smaller, extra space goes first
            shutil.get_terminal_size = lambda: (70, 24)
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
            result = "\n".join(utils.pretty_table(table))
            self.assertEqual(result, target)

            # Make terminal smaller, truncate column goes next
            shutil.get_terminal_size = lambda: (60, 24)
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
            result = "\n".join(utils.pretty_table(table))
            self.assertEqual(result, target)

            # Make terminal smaller, other columns go next
            shutil.get_terminal_size = lambda: (50, 24)
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
            result = "\n".join(utils.pretty_table(table))
            self.assertEqual(result, target)

            # Make terminal tiny, other columns go next, never last
            shutil.get_terminal_size = lambda: (10, 24)
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
            result = "\n".join(utils.pretty_table(table))
            self.assertEqual(result, target)
        finally:
            shutil.get_terminal_size = original_terminal_size

    def test_dedupe(self) -> None:
        # Set without duplicates not changed
        items = {
            "Apple",
            "Banana",
            "Strawberry",
        }
        target = items
        result = utils.dedupe(items)
        self.assertEqual(result, target)

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
        result = utils.dedupe(items)
        self.assertEqual(result, target)

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
        result = utils.dedupe(items)
        self.assertEqual(result, target)

    def test_date_months_between(self) -> None:
        # Same date is zero
        start = datetime.date(2024, 11, 1)
        end = start
        result = utils.date_months_between(start, end)
        self.assertEqual(result, 0)

        # Same month is zero
        start = datetime.date(2024, 11, 1)
        end = datetime.date(2024, 11, 30)
        result = utils.date_months_between(start, end)
        self.assertEqual(result, 0)
        result = utils.date_months_between(end, start)
        self.assertEqual(result, 0)

        # Next month is one
        start = datetime.date(2024, 11, 1)
        end = datetime.date(2024, 12, 31)
        result = utils.date_months_between(start, end)
        self.assertEqual(result, 1)
        result = utils.date_months_between(end, start)
        self.assertEqual(result, -1)

        # 11 months is 11
        start = datetime.date(2023, 11, 1)
        end = datetime.date(2024, 10, 15)
        result = utils.date_months_between(start, end)
        self.assertEqual(result, 11)
        result = utils.date_months_between(end, start)
        self.assertEqual(result, -11)

        # 13 months is 13
        start = datetime.date(2024, 11, 1)
        end = datetime.date(2023, 10, 15)
        result = utils.date_months_between(start, end)
        self.assertEqual(result, -13)
        result = utils.date_months_between(end, start)
        self.assertEqual(result, 13)

    def test_weekdays_in_month(self) -> None:
        date = datetime.date(2024, 11, 1)
        weekday = date.weekday()  # Friday

        # weekday is Friday, there are 5 Fridays
        result = utils.weekdays_in_month(weekday, date)
        self.assertEqual(result, 5)

        # weekday is Saturday, there are 5 Saturday
        weekday = (weekday + 1) % 7
        result = utils.weekdays_in_month(weekday, date)
        self.assertEqual(result, 5)

        # weekday is Sunday, there are 4 Sundays
        weekday = (weekday + 1) % 7
        result = utils.weekdays_in_month(weekday, date)
        self.assertEqual(result, 4)

    def test_start_of_month(self) -> None:
        date = datetime.date(2024, 2, 20)

        result = utils.start_of_month(date)
        target = datetime.date(2024, 2, 1)
        self.assertEqual(result, target)

    def test_end_of_month(self) -> None:
        date = datetime.date(2024, 2, 20)

        result = utils.end_of_month(date)
        target = datetime.date(2024, 2, 29)
        self.assertEqual(result, target)

    def test_clamp(self) -> None:
        result = utils.clamp(Decimal("0.5"))
        target = Decimal("0.5")
        self.assertEqual(result, target)

        result = utils.clamp(Decimal("-0.5"))
        target = Decimal(0)
        self.assertEqual(result, target)

        result = utils.clamp(Decimal("1.5"))
        target = Decimal(1)
        self.assertEqual(result, target)

        result = utils.clamp(Decimal(150), c_max=Decimal(100))
        target = Decimal(100)
        self.assertEqual(result, target)

        result = utils.clamp(Decimal(-150), c_min=Decimal(-100))
        target = Decimal(-100)
        self.assertEqual(result, target)

    def test_strip_emojis(self) -> None:
        text = self.random_string()
        result = utils.strip_emojis(text)
        self.assertEqual(result, text)

        result = utils.strip_emojis(text + "😀")
        self.assertEqual(result, text)

    def test_classproperty(self) -> None:

        class Color:

            @utils.classproperty
            def name(cls) -> str:  # noqa: N805
                return "RED"

        self.assertEqual(Color.name, "RED")
        self.assertEqual(Color().name, "RED")

    def test_tokenize_search_str(self) -> None:
        s = "!{}"
        self.assertRaises(exc.EmptySearchError, utils.tokenize_search_str, s)

        s = '"query'
        r_must, r_can, r_not = utils.tokenize_search_str(s)
        self.assertEqual(r_must, set())
        self.assertEqual(r_can, {"query"})
        self.assertEqual(r_not, set())

        s = '+query "keep together" -ignore "    "'
        r_must, r_can, r_not = utils.tokenize_search_str(s)
        self.assertEqual(r_must, {"query"})
        self.assertEqual(r_can, {"keep together"})
        self.assertEqual(r_not, {"ignore"})

    def test_low_pass(self) -> None:
        data = [Decimal(1), Decimal(0), Decimal(0), Decimal(0)]
        target = data
        result = utils.low_pass(data, 1)
        self.assertEqual(result, target)

        target = [Decimal(1), Decimal("0.5"), Decimal("0.25"), Decimal("0.125")]
        result = utils.low_pass(data, 3)
        self.assertEqual(result, target)
