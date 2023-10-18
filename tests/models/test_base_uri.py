from __future__ import annotations

import random
from typing import TYPE_CHECKING

import numpy as np

from nummus.models import base_uri
from nummus.models.account import Account
from nummus.models.asset import Asset, AssetSplit, AssetValuation
from nummus.models.budget import Budget
from nummus.models.credentials import Credentials
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import TransactionCategory
from tests.base import TestBase

if TYPE_CHECKING:
    from nummus.models.base import Base


class TestBaseURI(TestBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        base_uri._CIPHER = base_uri.Cipher.generate()  # noqa: SLF001

    def test_reverse_box(self) -> None:
        box = [1, 3]
        self.assertRaises(ValueError, base_uri.Cipher._reverse_box, box)  # noqa: SLF001

        box = [0, 1, 3]
        self.assertRaises(ValueError, base_uri.Cipher._reverse_box, box)  # noqa: SLF001

        box = [0, 1, 1, 3]
        self.assertRaises(ValueError, base_uri.Cipher._reverse_box, box)  # noqa: SLF001

        box = list(range(10))
        random.shuffle(box)
        box_rev = base_uri.Cipher._reverse_box(box)  # noqa: SLF001
        self.assertEqual(sorted(box), sorted(box_rev))

        pt = self.random_string(10)
        ct = "".join(pt[i] for i in box)
        self.assertNotEqual(pt, ct)

        pt_decoded = "".join(ct[i] for i in box_rev)
        self.assertEqual(pt, pt_decoded)

    def test_symmetrical_unique(self) -> None:
        self.assertRaises(TypeError, base_uri.uri_to_id, "")

        uris = set()

        n = 10000
        for i in range(n):
            uri = base_uri.id_to_uri(i)
            self.assertEqual(base_uri.URI_BYTES, len(uri))
            self.assertNotIn(uri, uris)
            uris.add(uri)

            i_decoded = base_uri.uri_to_id(uri)
            self.assertEqual(i, i_decoded)

    def test_distribution(self) -> None:
        # Aim for an even distribution of bits
        nibbles = {f"{i:x}": 0 for i in range(16)}

        n = 10000
        for i in range(n):
            uri = base_uri.id_to_uri(i)
            for nibble in uri:
                nibbles[nibble] += 1

        counts = list(nibbles.values())
        total = n * 8
        self.assertEqual(total, sum(counts))

        std = np.std(counts) / total
        self.assertLessEqual(std, 0.02)

    def test_table_ids(self) -> None:
        models: list[type[Base]] = [
            Account,
            Asset,
            AssetSplit,
            AssetValuation,
            Budget,
            Credentials,
            Transaction,
            TransactionCategory,
            TransactionSplit,
        ]
        table_ids = set()
        for model in models:
            t_id = model.__table_id__
            self.assertNotIn(t_id, table_ids)
            table_ids.add(t_id)
            self.assertEqual(t_id, t_id & base_uri.MASK_TABLE)

    def test_to_bytes(self) -> None:
        cipher = base_uri.Cipher.generate()
        b = cipher.to_bytes()
        self.assertIsInstance(b, bytes)

        pt = 0xDEADBEEF
        ct = cipher.encode(pt)
        self.assertNotEqual(pt, ct)
        pt_decoded = cipher.decode(ct)
        self.assertEqual(pt, pt_decoded)

        cipher_loaded = base_uri.Cipher.from_bytes(b)
        pt_decoded = cipher_loaded.decode(ct)
        self.assertEqual(pt, pt_decoded)

        self.assertRaises(TypeError, base_uri.Cipher.from_bytes, "")
        self.assertRaises(ValueError, base_uri.Cipher.from_bytes, b"")

        base_uri.load_cipher(b)
        ct_hex = ct.to_bytes(base_uri.ID_BYTES, base_uri._ORDER).hex()  # noqa: SLF001
        uri = base_uri.id_to_uri(pt)
        self.assertEqual(ct_hex, uri)
