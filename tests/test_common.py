"""Test module nummus.common
"""

import io
from unittest import mock

from nummus import common

from tests.base import TestBase


class TestCommon(TestBase):
  """Test common methods
  """

  def test_camel_to_snake(self):
    s = "CamelCase"
    target = "camel_case"
    result = common.camel_to_snake(s)
    self.assertEqual(target, result)

    s = "Camel"
    target = "camel"
    result = common.camel_to_snake(s)
    self.assertEqual(target, result)

    s = "camel"
    target = "camel"
    result = common.camel_to_snake(s)
    self.assertEqual(target, result)

    s = "HTTPClass"
    target = "http_class"
    result = common.camel_to_snake(s)
    self.assertEqual(target, result)

    s = "HTTPClassXYZ"
    target = "http_class_xyz"
    result = common.camel_to_snake(s)
    self.assertEqual(target, result)

  def test_random_string(self):
    string1 = common.random_string(min_length=40, max_length=50)
    string2 = common.random_string(min_length=40, max_length=50)

    # Has a 2e-99 chance of failing (actually worse cause pseudo-random)
    self.assertNotEqual(string1, string2)

    self.assertGreaterEqual(len(string1), 40)
    self.assertLessEqual(len(string1), 50)
    self.assertGreaterEqual(len(string2), 40)
    self.assertLessEqual(len(string2), 50)

  def test_get_input(self):
    prompt = self.random_string()
    prompt_input = self.random_string(length=50)

    original_input = mock.builtins.input
    original_get_pass = common.getpass.getpass

    def mock_input(to_print):
      """Mock user input with echo
      """
      print(to_print + prompt_input)
      return prompt_input

    def mock_get_pass(to_print):
      """Mock user input without echo
      """
      print(to_print)
      return prompt_input

    def mock_input_interrupt(to_print):
      """Mock user input with echo
      """
      print(to_print + prompt_input)
      raise KeyboardInterrupt()

    def mock_get_pass_eof(to_print):
      """Mock user input without echo
      """
      print(to_print)
      raise EOFError()

    try:
      mock.builtins.input = mock_input
      common.getpass.getpass = mock_get_pass

      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        result = common.get_input(prompt=prompt, secure=False)

      self.assertEqual(prompt + prompt_input + "\n", fake_stdout.getvalue())
      self.assertEqual(result, prompt_input)

      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        result = common.get_input(prompt=prompt, secure=True, print_key=False)

      self.assertEqual(prompt + "\n", fake_stdout.getvalue())
      self.assertEqual(result, prompt_input)

      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        result = common.get_input(prompt=prompt, secure=True, print_key=True)

      self.assertEqual("\u26BF  " + prompt + "\n", fake_stdout.getvalue())
      self.assertEqual(result, prompt_input)

      mock.builtins.input = mock_input_interrupt
      common.getpass.getpass = mock_get_pass_eof

      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        result = common.get_input(prompt=prompt, secure=False)

      self.assertEqual(prompt + prompt_input + "\n", fake_stdout.getvalue())
      self.assertIsNone(result)

      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        result = common.get_input(prompt=prompt, secure=True, print_key=False)

      self.assertEqual(prompt + "\n", fake_stdout.getvalue())
      self.assertIsNone(result)

    finally:
      mock.builtins.input = original_input
      common.getpass.getpass = original_get_pass

  def test_confirm(self):
    prompt = self.random_string()
    prompt_input = self.random_string(length=50)

    original_input = mock.builtins.input

    try:
      mock.builtins.input = lambda _: None

      result = common.confirm(prompt=None, default=False)
      self.assertEqual(result, False)

      result = common.confirm(prompt=prompt, default=True)
      self.assertEqual(result, True)

      mock.builtins.input = lambda _: "Y"

      result = common.confirm(prompt=prompt)
      self.assertEqual(result, True)

      mock.builtins.input = lambda _: "N"

      result = common.confirm(prompt=prompt)
      self.assertEqual(result, False)

      queue = [prompt_input, "y"]

      def _mock_input(_):
        if len(queue) == 1:
          return queue[0]
        return queue.pop(0)

      mock.builtins.input = _mock_input

      with mock.patch("sys.stdout", new=io.StringIO()) as _:
        result = common.confirm(prompt=prompt)
      self.assertEqual(result, True)

    finally:
      mock.builtins.input = original_input

  def test_parse_financial(self):
    result = common.parse_financial(None)
    self.assertIsNone(result)

    result = common.parse_financial("")
    self.assertIsNone(result)

    result = common.parse_financial("Not a number")
    self.assertIsNone(result)

    s = "1000.1"
    result = common.parse_financial(s)
    self.assertEqualWithinError(result, 1000.1, 1e-6)

    s = "1,000.1"
    result = common.parse_financial(s)
    self.assertEqualWithinError(result, 1000.1, 1e-6)

    s = "$1000.1"
    result = common.parse_financial(s)
    self.assertEqualWithinError(result, 1000.1, 1e-6)

    s = "-$1,000.1"
    result = common.parse_financial(s)
    self.assertEqualWithinError(result, -1000.1, 1e-6)
