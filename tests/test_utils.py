from __future__ import annotations

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
        self.assertEqual(target, result)

        s = "Camel"
        target = "camel"
        result = utils.camel_to_snake(s)
        self.assertEqual(target, result)

        s = "camel"
        target = "camel"
        result = utils.camel_to_snake(s)
        self.assertEqual(target, result)

        s = "HTTPClass"
        target = "http_class"
        result = utils.camel_to_snake(s)
        self.assertEqual(target, result)

        s = "HTTPClassXYZ"
        target = "http_class_xyz"
        result = utils.camel_to_snake(s)
        self.assertEqual(target, result)

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

            self.assertEqual(prompt + prompt_input + "\n", fake_stdout.getvalue())
            self.assertEqual(result, prompt_input)

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_input(prompt=prompt, secure=True, print_key=False)

            self.assertEqual(prompt + "\n", fake_stdout.getvalue())
            self.assertEqual(result, prompt_input)

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_input(prompt=prompt, secure=True, print_key=True)

            self.assertEqual("\u26BF  " + prompt + "\n", fake_stdout.getvalue())
            self.assertEqual(result, prompt_input)

            mock.builtins.input = mock_input_interrupt
            utils.getpass.getpass = mock_get_pass_eof

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_input(prompt=prompt, secure=False)

            self.assertEqual(prompt + prompt_input + "\n", fake_stdout.getvalue())
            self.assertIsNone(result)

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                result = utils.get_input(prompt=prompt, secure=True, print_key=False)

            self.assertEqual(prompt + "\n", fake_stdout.getvalue())
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
            self.assertEqual(result, False)

            result = utils.confirm(prompt=prompt, default=True)
            self.assertEqual(result, True)

            mock.builtins.input = lambda _: "Y"

            result = utils.confirm(prompt=prompt)
            self.assertEqual(result, True)

            mock.builtins.input = lambda _: "N"

            result = utils.confirm(prompt=prompt)
            self.assertEqual(result, False)

            queue = [prompt_input, "y"]

            def _mock_input(_) -> None:
                if len(queue) == 1:
                    return queue[0]
                return queue.pop(0)

            mock.builtins.input = _mock_input

            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                result = utils.confirm(prompt=prompt)
            self.assertEqual(result, True)

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
        self.assertEqual(Decimal("1000.1"), result)

        s = "1,000.1"
        result = utils.parse_real(s)
        self.assertEqual(Decimal("1000.1"), result)

        s = "$1000.1"
        result = utils.parse_real(s)
        self.assertEqual(Decimal("1000.1"), result)

        s = "-$1,000.1"
        result = utils.parse_real(s)
        self.assertEqual(Decimal("-1000.1"), result)

    def test_format_financial(self) -> None:
        x = Decimal("1000.1")
        result = utils.format_financial(x)
        self.assertEqual("$1,000.10", result)

        x = Decimal("-1000.1")
        result = utils.format_financial(x)
        self.assertEqual("-$1,000.10", result)

        x = Decimal("0")
        result = utils.format_financial(x)
        self.assertEqual("$0.00", result)

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
        self.assertEqual("0 days", result)

        labels = [self.random_string() for _ in range(4)]
        d = 2
        result = utils.format_days(d, labels=labels)
        self.assertEqual(f"2 {labels[0]}", result)

        d = 10
        result = utils.format_days(d)
        self.assertEqual("10 days", result)

        d = 11
        result = utils.format_days(d)
        self.assertEqual("2 wks", result)

        d = 8 * 7
        result = utils.format_days(d)
        self.assertEqual("8 wks", result)

        d = 8 * 7 + 1
        result = utils.format_days(d)
        self.assertEqual("2 mos", result)

        d = 18 * 365.25 / 12
        result = utils.format_days(d)
        self.assertEqual("18 mos", result)

        d = 18 * 365.25 / 12 + 1
        result = utils.format_days(d)
        self.assertEqual("2 yrs", result)

    def test_round_list(self) -> None:
        n = 9
        list_ = [1 / Decimal(n) for _ in range(n)]
        self.assertNotEqual(1, sum(list_))

        l_round = utils.round_list(list_)
        self.assertEqual(1, sum(l_round))
        self.assertNotEqual(list_[0], l_round[0])
        self.assertEqual(round(list_[0], 6), l_round[0])
