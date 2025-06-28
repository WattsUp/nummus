"""Encryption providers."""

from __future__ import annotations

import logging

from nummus.encryption.base import EncryptionInterface, NoEncryption

try:
    from nummus.encryption.aes import EncryptionAES
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import nummus.encryption, encryption not available")
    logger.warning("Install libsqlcipher: apt install libsqlcipher-dev")
    logger.warning("Install encrypt extra: pip install nummus[encrypt]")
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
