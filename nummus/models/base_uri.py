"""Model Uniform Resource Identifier encoder/decoder."""
from __future__ import annotations

import random
import secrets

ID_BYTES = 4
ID_BITS = ID_BYTES * 8
URI_BYTES = ID_BYTES * 2  # HEX doubles

TABLE_BITS = 4

MASK_ID = 0xFFFFFFFF >> TABLE_BITS
MASK_TABLE = 0xFFFFFFFF ^ MASK_ID

_ORDER = "big"
_ROUNDS = 3

_KEYS = [int.from_bytes(secrets.token_bytes(ID_BYTES), _ORDER) for _ in range(_ROUNDS)]
_KEYS_REV = _KEYS[::-1]

SBOX = list(range(256))
random.shuffle(SBOX)

PBOX = list(range(ID_BITS))
random.shuffle(PBOX)


def _reverse_box(box: list[int]) -> list[int]:
    """Reverse a box.

    A box maps a location to a new location.
    0 => 1, 1 => 0, 2 => 2 would be the box [1, 0, 2]
    The reversed box is [0, 1, 2]

    Args:
        box: A shuffled range
    """
    # Validate box is a box
    n = len(box)
    if min(box) != 0:
        msg = f"Box's minimum should be zero: {box}"
        raise ValueError(msg)
    if max(box) != (n - 1):
        msg = f"Box's maximum should be n - 1: {box}"
        raise ValueError(msg)
    if sum(box) != (n * (n - 1) / 2):
        msg = f"Box's maximum should be n * (n - 1) / 2: {box}"
        raise ValueError(msg)
    box_rev = [0] * n
    for i, n in enumerate(box):
        box_rev[n] = i
    return box_rev


SBOX_REV = _reverse_box(SBOX)
PBOX_REV = _reverse_box(PBOX)


def _substitute(n: int, box: list[int]) -> int:
    """Substitute each byte in i with a different on based on box.

    Args:
        n: Input number
        box: Substitution box, shuffled range [0, 255]

    Returns:
        i with each byte shuffled
    """
    out = 0
    for _ in range(ID_BYTES):
        out = (out << 8) | box[n & 0xFF]
        n = n >> 8
    return out


def _permutate(n: int, box: list[int]) -> int:
    """Permutate each bit in i to a different location.

    Args:
        n: Input number
        box: Permutation box, shuffed range [0, ID_BITS - 1]

    Returns:
        i with each bit shuffled
    """
    n_bin = format(n, f"0{ID_BITS}b")

    o_bin = [n_bin[p] for p in box]

    return int("".join(o_bin), 2)


def _encode(pt: int) -> int:
    """Encode number using a SPN block cipher, reverses _decode.

    Args:
        pt: Plain text number to encode

    Returns:
        Cipher text number
    """
    n = pt
    for i in range(_ROUNDS):
        n = n ^ _KEYS[i]  # XOR with KEYS
        n = _substitute(n, SBOX)
        n = _permutate(n, PBOX)
    return n ^ _KEYS[-1]


def _decode(ct: int) -> int:
    """Decode number using a SPN block cipher, reverses _encode.

    Args:
        ct: Cipher text number to decode

    Returns:
        Plain text number
    """
    n = ct
    n = n ^ _KEYS[-1]
    for i in range(_ROUNDS):
        n = _permutate(n, PBOX_REV)
        n = _substitute(n, SBOX_REV)
        n = n ^ _KEYS_REV[i]
    return n


def id_to_uri(id_: int) -> str:
    """Transform an ID into a URI, reverses uri_to_id.

    Args:
        id_: ID to transform

    Returns:
        URI, hex encoded, 1:1 mapping
    """
    return _encode(id_).to_bytes(ID_BYTES, _ORDER).hex()


def uri_to_id(uri: str) -> int:
    """Transform a URI into an ID, reverses id_to_uri.

    Args:
        uri: URI to transform

    Returns:
        ID, 1:1 mapping

    Raises:
        TypeError if uri is not the correct length
    """
    if len(uri) != URI_BYTES:
        msg = f"URI is not {URI_BYTES} bytes long: {uri}"
        raise TypeError(msg)
    return _decode(int(uri, 16))
