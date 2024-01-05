from __future__ import annotations

import datetime
import io
from decimal import Decimal
from unittest import mock

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
            print(to_print + prompt_input)
            return prompt_input

        def mock_get_pass(to_print: str) -> str | None:
            print(to_print)
            return prompt_input

        def mock_input_interrupt(to_print: str) -> None:
            print(to_print + prompt_input)
            raise KeyboardInterrupt

        def mock_get_pass_eof(to_print: str) -> None:
            print(to_print)
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

    def test_parse_financial(self) -> None:
        result = utils.parse_real(None)
        self.assertIsNone(result)

        result = utils.parse_real("")
        self.assertIsNone(result)

        result = utils.parse_real("Not a number")
        self.assertIsNone(result)

        s = "1000.1"
        result = utils.parse_real(s)
        self.assertEqual(result, Decimal("1000.1"))

        s = "1,000.1"
        result = utils.parse_real(s)
        self.assertEqual(result, Decimal("1000.1"))

        s = "$1000.1"
        result = utils.parse_real(s)
        self.assertEqual(result, Decimal("1000.1"))

        s = "-$1,000.1"
        result = utils.parse_real(s)
        self.assertEqual(result, Decimal("-1000.1"))

    def test_format_financial(self) -> None:
        x = Decimal("1000.1")
        result = utils.format_financial(x)
        self.assertEqual(result, "$1,000.10")

        x = Decimal("-1000.1")
        result = utils.format_financial(x)
        self.assertEqual(result, "-$1,000.10")

        x = Decimal("0")
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

        self.assertRaises(TypeError, utils.parse_bool, None)

        self.assertRaises(TypeError, utils.parse_bool, False)  # noqa: FBT003

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
        self.assertEqual(result, "2 wks")

        d = 8 * 7
        result = utils.format_days(d)
        self.assertEqual(result, "8 wks")

        d = 8 * 7 + 1
        result = utils.format_days(d)
        self.assertEqual(result, "2 mos")

        d = int(18 * 365.25 / 12)
        result = utils.format_days(d)
        self.assertEqual(result, "18 mos")

        d = int(18 * 365.25 / 12 + 1)
        result = utils.format_days(d)
        self.assertEqual(result, "2 yrs")

    def test_format_seconds(self) -> None:
        s = 0.0
        result = utils.format_seconds(s)
        self.assertEqual(result, "0.0 s")

        s = 60.0
        result = utils.format_seconds(s)
        self.assertEqual(result, "60.0 s")

        s = 90.1
        result = utils.format_seconds(s)
        self.assertEqual(result, "1.5 min")

        s = 5400.1
        result = utils.format_seconds(s)
        self.assertEqual(result, "1.5 hrs")

        s = 86400.0
        result = utils.format_seconds(s)
        self.assertEqual(result, "24.0 hrs")

        s = 86400 * 4.0
        result = utils.format_seconds(s)
        self.assertEqual(result, "96.0 hrs")

        s = 86400 * 4.1
        result = utils.format_seconds(s)
        self.assertEqual(result, "4 days")

    def test_range_date(self) -> None:
        start = datetime.date.today()
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
