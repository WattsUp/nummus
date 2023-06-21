"""Test module nummus.encryption
"""

import base64

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
    self.assertNotEqual(secret, base64.b64decode(encrypted))
    decrypted = enc.decrypt(encrypted)
    self.assertEqual(secret, decrypted)

  def test_bad_key(self):

    key = self.random_string().encode()
    secret = self.random_string().encode()

    enc = encryption.Encryption(key)

    encrypted = enc.encrypt(secret)
    self.assertNotEqual(secret, encrypted)
    self.assertNotEqual(secret, base64.b64decode(encrypted))

    bad_key = key + self.random_string().encode()
    enc_bad = encryption.Encryption(bad_key)

    try:
      secret_bad = enc_bad.decrypt(encrypted)
      # Sometimes decrypting is valid but yields wrong secret
      self.assertNotEqual(secret, secret_bad)
    except ValueError:
      pass  # Expected mismatch of padding

  def test_salt(self):
    key = self.random_string().encode()
    secret = self.random_string().encode()

    enc = encryption.Encryption(key)

    salt = enc.gen_salt(set_salt=True)

    encrypted = enc.encrypt(secret)
    self.assertNotEqual(secret, encrypted)
    self.assertNotEqual(secret, base64.b64decode(encrypted))
    enc.set_salt(salt)
    decrypted = enc.decrypt(encrypted)
    self.assertEqual(secret, decrypted)

    salt = enc.gen_salt(set_salt=False)
    enc.set_salt(salt)
    encrypted = enc.encrypt(secret)
    self.assertNotEqual(secret, encrypted)
    self.assertNotEqual(secret, base64.b64decode(encrypted))
    enc.set_salt(salt)
    decrypted = enc.decrypt(encrypted)
    self.assertEqual(secret, decrypted)
