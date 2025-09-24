from __future__ import annotations

import random
from typing import TYPE_CHECKING

import numpy as np
import pytest

from nummus import exceptions as exc
from nummus.models import _MODELS, base_uri
from nummus.models.account import Account
from nummus.models.asset import Asset, AssetSector, AssetSplit, AssetValuation
from nummus.models.base_uri import Cipher
from nummus.models.budget import BudgetAssignment, BudgetGroup, Target
from nummus.models.config import Config
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.imported_file import ImportedFile
from nummus.models.label import Label, LabelLink
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import TransactionCategory

if TYPE_CHECKING:
    from nummus.models.base import Base

MODELS_URI = [
    Account,
    Asset,
    AssetValuation,
    BudgetGroup,
    HealthCheckIssue,
    Label,
    Target,
    Transaction,
    TransactionCategory,
    TransactionSplit,
]
# Models without a URI not made for front end access
MODELS_NONE = [
    AssetSector,
    AssetSplit,
    BudgetAssignment,
    Config,
    ImportedFile,
    LabelLink,
]


@pytest.fixture
def cipher() -> Cipher:
    """Generate a random cipher.

    Returns:
        Cipher

    """
    return Cipher.generate()


@pytest.mark.parametrize(
    ("box", "target"),
    [
        ([1, 3], r"Box's minimum should be zero"),
        ([0, 1, 3], r"Box's maximum should be n - 1"),
        ([0, 1, 1, 3], r"Box's sum should be n \* \(n - 1\) / 2"),
    ],
)
def test_reverse_box_invalid(box: list[int], target: str) -> None:
    with pytest.raises(ValueError, match=target):
        Cipher._reverse_box(box)


def test_reverse_box_valid(rand_str: str) -> None:
    box = list(range(len(rand_str)))
    random.shuffle(box)
    box_rev = Cipher._reverse_box(box)
    assert sorted(box) == sorted(box_rev)

    pt = rand_str
    ct = "".join(pt[i] for i in box)
    assert pt != ct

    pt_decoded = "".join(ct[i] for i in box_rev)
    assert pt_decoded == pt


def test_empty_uri() -> None:
    with pytest.raises(exc.InvalidURIError):
        base_uri.uri_to_id("")


def test_symmetrical_unique() -> None:
    uris = set()

    n = 10000
    for i in range(n):
        uri = base_uri.id_to_uri(i)
        assert len(uri) == base_uri.URI_BYTES
        assert uri not in uris
        uris.add(uri)

        i_decoded = base_uri.uri_to_id(uri)
        assert i_decoded == i


def test_distribution() -> None:
    # Aim for an even distribution of bits
    nibbles = {f"{i:x}": 0 for i in range(16)}

    n = 10000
    for i in range(n):
        uri = base_uri.id_to_uri(i)
        for nibble in uri:
            nibbles[nibble] += 1

    counts = list(nibbles.values())
    total = n * 8
    assert sum(counts) == total

    std = float(np.std(counts) / total)
    assert std < 0.05


def test_table_ids_all_covered() -> None:
    models = set(_MODELS)

    for model in MODELS_URI:
        models.remove(model)
    for model in MODELS_NONE:
        models.remove(model)

    assert len(models) == 0


@pytest.mark.parametrize("m", MODELS_URI)
def test_table_ids(m: type[Base]) -> None:
    t_id: int | None = m.__table_id__
    assert t_id is not None
    assert t_id & base_uri.MASK_TABLE == t_id


@pytest.mark.parametrize("m", MODELS_NONE)
def test_table_ids_none(m: type[Base]) -> None:
    t_id = m.__table_id__
    assert t_id is None
    with pytest.raises(exc.NoURIError):
        m.id_to_uri(0)


def test_table_ids_no_duplicates() -> None:
    table_ids: set[int] = set()

    for m in MODELS_URI:
        t_id: int = m.__table_id__
        assert t_id not in table_ids
        table_ids.add(t_id)


def test_to_bytes(cipher: Cipher) -> None:
    assert isinstance(cipher.to_bytes(), bytes)


def test_generate(cipher: Cipher) -> None:
    pt = 0xDEADBEEF
    ct = cipher.encode(pt)
    assert ct != pt
    pt_decoded = cipher.decode(ct)
    assert pt_decoded == pt


def test_from_bytes(cipher: Cipher) -> None:
    pt = 0xDEADBEEF
    ct = cipher.encode(pt)

    b = cipher.to_bytes()
    cipher_loaded = Cipher.from_bytes(b)
    pt_decoded = cipher_loaded.decode(ct)
    assert pt_decoded == pt


def test_from_bytes_empty() -> None:
    with pytest.raises(ValueError, match="Buf is 0B long"):
        Cipher.from_bytes(b"")


def test_load_cipher(cipher: Cipher) -> None:
    pt = 0xDEADBEEF
    ct = cipher.encode(pt)

    base_uri.load_cipher(cipher.to_bytes())
    ct_hex = ct.to_bytes(base_uri.ID_BYTES, base_uri._ORDER).hex()
    uri = base_uri.id_to_uri(pt)
    assert uri == ct_hex


def test_uri_to_id_short() -> None:
    uri = "A" * (base_uri.URI_BYTES - 1)
    with pytest.raises(exc.InvalidURIError):
        base_uri.uri_to_id(uri)


def test_uri_to_id_not_hex() -> None:
    uri = "Z" * base_uri.URI_BYTES
    with pytest.raises(exc.InvalidURIError):
        base_uri.uri_to_id(uri)


def test_uri_to_id() -> None:
    id_ = 0
    uri = base_uri.id_to_uri(id_)
    result = base_uri.uri_to_id(uri)
    assert result == id_
