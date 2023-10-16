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

    def __init__(self, key: bytes) -> None:
        """Initialize Encryption.

        Args:
            key: encryption key
        """
        self.key = key
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

    def encrypt(self, secret: bytes) -> bytes:
        """Encrypt a secret using the key.

        Args:
            secret: Object to encrypt

        Returns:
            bytes encrypted object
        """
        # Generate a random initialization vector
        iv = Crypto.Random.new().read(AES.block_size)
        aes = self._get_aes(iv)

        # Add padding the secret to fit in whole blocks
        # Always adds at least 1 byte of padding
        padding = AES.block_size - len(secret) % AES.block_size
        secret += bytes([padding]) * padding

        # Prepend initialization vector to encrypted secret
        data = iv + aes.encrypt(secret)

        # Reset salt if present
        self.set_salt()

        # Stringify bytes with base64
        return base64.b64encode(data)

    def decrypt(self, enc_secret: bytes) -> bytes:
        """Decrypt an encoded secret using the key.

        Args:
            enc_secret: Encoded secret

        Returns:
            bytes decoded secret
        """
        # Un-stringify bytes
        enc_secret = base64.b64decode(enc_secret)

        # Get the AES cipher from the included initialization vector
        iv = enc_secret[: AES.block_size]
        aes = self._get_aes(iv)

        # Decrypt secret and get length of padding
        data = aes.decrypt(enc_secret[AES.block_size :])
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
