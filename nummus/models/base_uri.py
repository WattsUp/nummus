"""Model Uniform Resource Identifier encoder/decoder."""
from __future__ import annotations

import base64
import secrets

ID_BYTES = 4
ID_BITS = ID_BYTES * 8
URI_BYTES = 6

TABLE_BITS = 4

MASK_ID = 0xFFFFFFFF >> TABLE_BITS
MASK_TABLE = 0xFFFFFFFF ^ MASK_ID

_ORDER = "big"
_ROUNDS = 3

_KEYS = [int.from_bytes(secrets.token_bytes(ID_BYTES), _ORDER) for _ in range(_ROUNDS)]
_KEYS_REV = _KEYS[::-1]


def id_to_uri(id_: int) -> str:
    """Transform an id into a URI, reverses uri_to_id.

    Args:
        id_: ID to transform

    Returns:
        URI safe base 64 uri, 1:1 mapping
    """
    b = id_.to_bytes(ID_BYTES, _ORDER)
    return base64.urlsafe_b64encode(b)[:URI_BYTES].decode()


def uri_to_id(uri: str) -> int:
    """Transform a URI into an id, reverses id_to_uri.

    Args:
        uri: URI to transform

    Returns:
        id, 1:1 mapping

    Raises:
        TypeError if uri is not the correct length
    """
    if len(uri) != URI_BYTES:
        msg = f"URI is not {URI_BYTES} bytes long: {uri}"
        raise TypeError(msg)
    b = base64.urlsafe_b64decode(uri + "==")
    return int.from_bytes(b, _ORDER)
