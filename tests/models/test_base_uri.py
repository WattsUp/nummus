from __future__ import annotations

import random

import numpy as np

from nummus import exceptions as exc
from nummus.models import _TABLES, base_uri
from nummus.models.account import Account
from nummus.models.asset import Asset, AssetSplit, AssetValuation
from nummus.models.budget import Budget
from nummus.models.credentials import Credentials
from nummus.models.imported_file import ImportedFile
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import TransactionCategory
from tests.base import TestBase


class TestBaseURI(TestBase):
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
        self.assertNotEqual(ct, pt)

        pt_decoded = "".join(ct[i] for i in box_rev)
        self.assertEqual(pt_decoded, pt)

    def test_symmetrical_unique(self) -> None:
        self.assertRaises(exc.InvalidURIError, base_uri.uri_to_id, "")

        uris = set()

        n = 10000
        for i in range(n):
            uri = base_uri.id_to_uri(i)
            self.assertEqual(len(uri), base_uri.URI_BYTES)
            self.assertNotIn(uri, uris)
            uris.add(uri)

            i_decoded = base_uri.uri_to_id(uri)
            self.assertEqual(i_decoded, i)

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
        self.assertEqual(sum(counts), total)

        std = np.std(counts) / total
        self.assertLessEqual(std, 0.05)

    def test_table_ids(self) -> None:
        # Make sure all models are covered
        tables = set(_TABLES)

        models = [
            Account,
            Asset,
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
            self.assertEqual(t_id & base_uri.MASK_TABLE, t_id)

            tables.remove(model.__table__)

        # Models without a URI not made for front end access
        models_none = [
            AssetSplit,
            AssetValuation,
            ImportedFile,
        ]
        for model in models_none:
            try:
                t_id = model.__table_id__
                self.assertIsNone(t_id)
            except AttributeError:
                # Not there works too
                pass
            tables.remove(model.__table__)

        self.assertEqual(len(tables), 0)

    def test_to_bytes(self) -> None:
        cipher = base_uri.Cipher.generate()
        b = cipher.to_bytes()
        self.assertIsInstance(b, bytes)

        pt = 0xDEADBEEF
        ct = cipher.encode(pt)
        self.assertNotEqual(ct, pt)
        pt_decoded = cipher.decode(ct)
        self.assertEqual(pt_decoded, pt)

        cipher_loaded = base_uri.Cipher.from_bytes(b)
        pt_decoded = cipher_loaded.decode(ct)
        self.assertEqual(pt_decoded, pt)

        self.assertRaises(TypeError, base_uri.Cipher.from_bytes, "")
        self.assertRaises(ValueError, base_uri.Cipher.from_bytes, b"")

        base_uri.load_cipher(b)
        ct_hex = ct.to_bytes(base_uri.ID_BYTES, base_uri._ORDER).hex()  # noqa: SLF001
        uri = base_uri.id_to_uri(pt)
        self.assertEqual(uri, ct_hex)
