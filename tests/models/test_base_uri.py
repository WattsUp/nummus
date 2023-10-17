from __future__ import annotations

from nummus.models import base_uri
from nummus.models.account import Account
from nummus.models.asset import Asset, AssetSplit, AssetValuation
from nummus.models.budget import Budget
from nummus.models.credentials import Credentials
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import TransactionCategory
from tests.base import TestBase
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nummus.models.base import Base


class TestBaseURI(TestBase):
    def test_symmetrical(self) -> None:
        uris = set()

        for i in range(100):
            uri = base_uri.id_to_uri(i)
            self.assertEqual(base_uri.URI_BYTES, len(uri))
            self.assertNotIn(uri, uris)
            uris.add(uri)

            i_decoded = base_uri.uri_to_id(uri)
            self.assertEqual(i, i_decoded)

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
