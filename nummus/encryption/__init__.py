"""Encryption providers."""

from __future__ import annotations

from nummus.encryption.base import EncryptionInterface, NoEncryption

try:
    from nummus.encryption.aes import EncryptionAES
except ImportError:
    print("Could not import nummus.encryption, encryption not available")
    print("Install libsqlcipher: apt install libsqlcipher-dev")
    print("Install encrypt extra: pip install nummus[encrypt]")
    Encryption = NoEncryption
    AVAILABLE = False
else:
    Encryption = EncryptionAES
    AVAILABLE = True

__all__ = [
    "AVAILABLE",
    "Encryption",
    "EncryptionInterface",
]
