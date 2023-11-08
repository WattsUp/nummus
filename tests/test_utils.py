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

        original_input = mock.builtins.input
        original_get_pass = utils.getpass.getpass

        def mock_input(to_print: str) -> None:
            print(to_print + prompt_input)
            return prompt_input

        def mock_get_pass(to_print: str) -> None:
            print(to_print)
            return prompt_input

        def mock_input_interrupt(to_print: str) -> None:
            print(to_print + prompt_input)
            raise KeyboardInterrupt

        def mock_get_pass_eof(to_print: str) -> None:
            print(to_print)
            raise EOFError

        try:
            mock.builtins.input = mock_input
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

            self.assertEqual(fake_stdout.getvalue(), "\u26BF  " + prompt + "\n")
            self.assertEqual(prompt_input, result)

            mock.builtins.input = mock_input_interrupt
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
            mock.builtins.input = original_input
            utils.getpass.getpass = original_get_pass

    def test_confirm(self) -> None:
        prompt = self.random_string()
        prompt_input = self.random_string(length=50)

        original_input = mock.builtins.input

        try:
            mock.builtins.input = lambda _: None

            result = utils.confirm(prompt=None, default=False)
            self.assertFalse(result, "Default is not False")

            result = utils.confirm(prompt=prompt, default=True)
            self.assertTrue(result, "Default is not True")

            mock.builtins.input = lambda _: "Y"

            result = utils.confirm(prompt=prompt)
            self.assertTrue(result, "Y is not True")

            mock.builtins.input = lambda _: "N"

            result = utils.confirm(prompt=prompt)
            self.assertFalse(result, "N is not False")

            queue = [prompt_input, "y"]

            def _mock_input(_) -> None:
                if len(queue) == 1:
                    return queue[0]
                return queue.pop(0)

            mock.builtins.input = _mock_input

            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                result = utils.confirm(prompt=prompt)
            self.assertTrue(result, "Y is not True")

        finally:
            mock.builtins.input = original_input

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

        d = 18 * 365.25 / 12
        result = utils.format_days(d)
        self.assertEqual(result, "18 mos")

        d = 18 * 365.25 / 12 + 1
        result = utils.format_days(d)
        self.assertEqual(result, "2 yrs")

    def test_range_date(self) -> None:
        start = datetime.date.today()
        end = start + datetime.timedelta(days=7)

        result = utils.range_date(start, end, include_end=True)
        self.assertEqual(len(result), 8)
        self.assertEqual(result[0], start)
        self.assertEqual(result[-1], end)

        result = utils.range_date(start, end, include_end=False)
        self.assertEqual(len(result), 7)
        self.assertEqual(result[0], start)
        self.assertEqual(result[-1], end - datetime.timedelta(days=1))

    def test_round_list(self) -> None:
        n = 9
        list_ = [1 / Decimal(n) for _ in range(n)]
        self.assertNotEqual(sum(list_), 1)

        l_round = utils.round_list(list_)
        self.assertEqual(sum(l_round), 1)
        self.assertNotEqual(l_round[0], list_[0])
        self.assertEqual(l_round[0], round(list_[0], 6))
