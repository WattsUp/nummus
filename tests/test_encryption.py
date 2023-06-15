"""Test module nummus.encryption
"""

try:
  from nummus import encryption  # pylint: disable=import-outside-toplevel
except ImportError:
  # Helpful information printed in nummus.portfolio
  encryption = None

from tests import base


class TestEncryption(base.TestBase):
  """Test Encryption
  """

  def setUp(self):
    super().setUp()
    if encryption is None:
      self.skipTest("Encryption is not installed")

  def test_good_key(self):
    key = self.random_string().encode()
    secret = self.random_string().encode()

    enc = encryption.Encryption(key)

    encrypted = enc.encrypt(secret)
    self.assertNotEqual(secret, encrypted)
    decrypted = enc.decrypt(encrypted)
    self.assertEqual(secret, decrypted)

  def test_bad_key(self):

    key = self.random_string().encode()
    secret = self.random_string().encode()

    enc = encryption.Encryption(key)

    encrypted = enc.encrypt(secret)
    self.assertNotEqual(secret, encrypted)

    bad_key = key + self.random_string().encode()
    enc_bad = encryption.Encryption(bad_key)

    self.assertRaises(ValueError, enc_bad.decrypt, encrypted)

  def test_salt(self):
    key = self.random_string().encode()
    secret = self.random_string().encode()

    enc = encryption.Encryption(key)

    salt = enc.gen_salt(set_salt=True)

    encrypted = enc.encrypt(secret)
    self.assertNotEqual(secret, encrypted)
    enc.set_salt(salt)
    decrypted = enc.decrypt(encrypted)
    self.assertEqual(secret, decrypted)

    salt = enc.gen_salt(set_salt=False)
    enc.set_salt(salt)
    encrypted = enc.encrypt(secret)
    self.assertNotEqual(secret, encrypted)
    enc.set_salt(salt)
    decrypted = enc.decrypt(encrypted)
    self.assertEqual(secret, decrypted)
