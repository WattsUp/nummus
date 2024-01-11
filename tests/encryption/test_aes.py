from __future__ import annotations

import base64
import hashlib

from nummus import exceptions as exc
from tests.base import TestBase

try:
    from nummus.encryption.aes import EncryptionAES as Encryption
except ImportError:
    NO_ENCRYPTION = True
    from nummus.encryption.base import NoEncryption as Encryption
else:
    NO_ENCRYPTION = False


class TestEncryption(TestBase):
    def setUp(self, *_, clean: bool = True) -> None:
        super().setUp(clean=clean)
        if NO_ENCRYPTION:
            self.skipTest("Encryption is not installed")

    def test_encrypt_decrypt(self) -> None:
        key = self.random_string()
        secret = self.random_string()

        enc, enc_config = Encryption.create(key)

        encrypted = enc.encrypt(secret)
        self.assertNotEqual(encrypted, secret)
        self.assertNotEqual(base64.b64decode(encrypted), secret)
        decrypted = enc.decrypt_s(encrypted)
        self.assertEqual(decrypted, secret)

        # Make sure key actually got hashed
        self.assertNotEqual(key, enc.hashed_key)
        self.assertNotEqual(hashlib.sha256(key.encode()).digest(), enc.hashed_key)
        self.assertNotIn(key.encode(), enc.hashed_key)
        self.assertNotIn(key.encode(), enc_config)

        # Load from enc_config
        enc_loaded = Encryption(key, enc_config)
        decrypted = enc_loaded.decrypt_s(encrypted)
        self.assertEqual(decrypted, secret)

        bad_key = key + self.random_string()
        enc_bad = Encryption(bad_key, enc_config)

        try:
            secret_bad = enc_bad.decrypt_s(encrypted)
            # Sometimes decrypting is valid but yields wrong secret
            self.assertNotEqual(secret_bad, secret)
        except ValueError:
            pass  # Expected mismatch of padding

        enc_config = b"a:bc"
        self.assertRaises(
            exc.UnknownEncryptionVersionError,
            Encryption,
            key,
            enc_config,
        )
