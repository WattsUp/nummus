"""Encryption provider."""

from __future__ import annotations

import base64
import secrets
from typing import TYPE_CHECKING

import Crypto
import Crypto.Random
from Crypto.Cipher import AES
from Crypto.Hash import SHA256

if TYPE_CHECKING:
    from Crypto.Cipher._mode_cbc import CbcMode


class Encryption:
    """Encryption provider.

    Uses AES encryption for encryption and decryption

    Attributes:
        key: encryption key
        salted_key: encryption key with salt
    """

    def __init__(self, key: bytes | str) -> None:
        """Initialize Encryption.

        Args:
            key: encryption key
        """
        self.key = key.encode() if isinstance(key, str) else bytes(key)
        self.salted_key = None

    def _digest_key(self) -> bytes:
        """Get digest key.

        Hashes the key (with optional salt) to get a fixed length key

        Returns:
            bytes hashed key
        """
        key = self.key
        if self.salted_key:
            key = self.salted_key
        return SHA256.new(key).digest()

    def _get_aes(self, iv: bytes) -> CbcMode:
        """Get AES cipher from digest key and initialization vector.

        Args:
            iv: Initialization vector

        Returns:
            AES cipher object
        """
        return AES.new(self._digest_key(), AES.MODE_CBC, iv)

    def gen_salt(self, *, set_salt: bool = True) -> bytes:
        """Generate salt to be added to key.

        Args:
            set_salt: True will set_salt after generation

        Returns:
            bytes Generated salt
        """
        salt = secrets.token_bytes()

        if set_salt:
            self.set_salt(salt)

        return salt

    def set_salt(self, salt: bytes | None = None) -> None:
        """Set salt to be added to key.

        Args:
            salt: Salt to add
        """
        if salt:
            self.salted_key = salt + self.key
        else:
            self.salted_key = None

    def encrypt(self, secret: bytes | str) -> str:
        """Encrypt a secret using the key.

        Args:
            secret: Object to encrypt

        Returns:
            base64 encoded encrypted object
        """
        secret_b = secret.encode() if isinstance(secret, str) else bytes(secret)

        # Generate a random initialization vector
        iv = Crypto.Random.new().read(AES.block_size)
        aes = self._get_aes(iv)

        # Add padding the secret to fit in whole blocks
        # Always adds at least 1 byte of padding
        padding = AES.block_size - len(secret_b) % AES.block_size
        secret_b += bytes([padding]) * padding

        # Prepend initialization vector to encrypted secret
        data = iv + aes.encrypt(secret_b)

        # Reset salt if present
        self.set_salt()

        return base64.b64encode(data).decode()

    def decrypt(self, enc_secret: str) -> bytes:
        """Decrypt an encoded secret using the key.

        Args:
            enc_secret: base64 encoded encrypted object

        Returns:
            bytes decoded object
        """
        # Un-stringify bytes
        enc_secret_b = base64.b64decode(enc_secret)

        # Get the AES cipher from the included initialization vector
        iv = enc_secret_b[: AES.block_size]
        aes = self._get_aes(iv)

        # Decrypt secret and get length of padding
        data = aes.decrypt(enc_secret_b[AES.block_size :])
        padding = data[-1]

        # Validate padding is unchanged
        if data[-padding:] != bytes([padding]) * padding:  # pragma: no cover
            # Cannot guarantee this gets covered by a bad key test
            # Some bad keys decrypt with valid padding but the decoded secret is wrong
            msg = "Invalid padding"
            raise ValueError(msg)

        # Reset salt if present
        self.set_salt()

        return data[:-padding]

    def decrypt_s(self, enc_secret: str) -> str:
        """Decrypt an encoded secret using the key.

        Args:
            enc_secret: base64 encoded encrypted string

        Returns:
            decoded string
        """
        return self.decrypt(enc_secret).decode()
