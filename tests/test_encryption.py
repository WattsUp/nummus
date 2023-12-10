from __future__ import annotations

import base64

from nummus import encryption_fb
from tests.base import TestBase

try:
    from nummus import encryption
except ImportError:
    # Helpful information printed in nummus.portfolio
    from nummus import encryption_fb as encryption


class TestEncryption(TestBase):
    def setUp(self, *_, clean: bool = True) -> None:
        super().setUp(clean=clean)
        if encryption is None:
            self.assertIsNotNone(encryption_fb.Encryption)
            self.skipTest("Encryption is not installed")

    def test_good_key(self) -> None:
        key = self.random_string()
        secret = self.random_string()

        enc = encryption.Encryption(key)

        encrypted = enc.encrypt(secret)
        self.assertNotEqual(encrypted, secret)
        self.assertNotEqual(base64.b64decode(encrypted), secret)
        decrypted = enc.decrypt_s(encrypted)
        self.assertEqual(decrypted, secret)

    def test_bad_key(self) -> None:
        key = self.random_string()
        secret = self.random_string()

        enc = encryption.Encryption(key)

        encrypted = enc.encrypt(secret)
        self.assertNotEqual(encrypted, secret)
        self.assertNotEqual(base64.b64decode(encrypted), secret)

        bad_key = key + self.random_string()
        enc_bad = encryption.Encryption(bad_key)

        try:
            secret_bad = enc_bad.decrypt_s(encrypted)
            # Sometimes decrypting is valid but yields wrong secret
            self.assertNotEqual(secret_bad, secret)
        except ValueError:
            pass  # Expected mismatch of padding

    def test_salt(self) -> None:
        key = self.random_string()
        secret = self.random_string()

        enc = encryption.Encryption(key)

        salt = enc.gen_salt(set_salt=True)

        encrypted = enc.encrypt(secret)
        self.assertNotEqual(encrypted, secret)
        self.assertNotEqual(base64.b64decode(encrypted), secret)
        enc.set_salt(salt)
        decrypted = enc.decrypt_s(encrypted)
        self.assertEqual(decrypted, secret)

        salt = enc.gen_salt(set_salt=False)
        enc.set_salt(salt)
        encrypted = enc.encrypt(secret)
        self.assertNotEqual(encrypted, secret)
        self.assertNotEqual(base64.b64decode(encrypted), secret)
        enc.set_salt(salt)
        decrypted = enc.decrypt_s(encrypted)
        self.assertEqual(decrypted, secret)
