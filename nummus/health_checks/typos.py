"""Checks for very similar fields and common typos."""

from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING

import spellchecker
from typing_extensions import override

from nummus.health_checks.base import Base
from nummus.models import (
    Account,
    Asset,
    AssetCategory,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from nummus import portfolio


class Typos(Base):
    """Checks for very similar fields and common typos."""

    _NAME = "Typos"
    _DESC = "Checks for very similar fields and common typos."
    _SEVERE = False

    _RE_WORDS = re.compile(r"[ ,/]")

    @override
    def test(self) -> None:
        spell = spellchecker.SpellChecker()
        # Known correct words
        known = {
            "401k",
            "etc.",
            "Inc.",
            "ETF",
            "ATM",
            "Uncategorized",
            "Rebalance",
        }
        known = {k.lower() for k in known}

        with self._p.get_session() as s:
            accounts = Account.map_name(s)

            # Create a dict of every word found with the first instance detected
            # Dictionary {word.lower(): (word, source, field)}
            words: dict[str, tuple[str, str, str]] = {}

            def add(s: str | None, source: str, field: str) -> None:
                if s is None:
                    return
                for token in self._RE_WORDS.split(s):
                    if not token:
                        continue
                    token_l = token.lower()
                    if token_l not in words:
                        words[token_l] = (token, source, field)

            query = s.query(Account).with_entities(
                Account.id_,
                Account.institution,
            )
            for acct_id, institution in query.yield_per(YIELD_PER):
                acct_id: int
                institution: str
                name = accounts[acct_id]
                source = f"Account {name}"
                add(name, source, "name")
                add(institution, source, "institution")

            query = (
                s.query(Asset)
                .with_entities(
                    Asset.name,
                    Asset.description,
                )
                .where(Asset.category != AssetCategory.INDEX)
            )
            for name, description in query.yield_per(YIELD_PER):
                name: str
                description: str
                source = f"Asset {name}"
                add(name, source, "name")
                add(description, source, "description")

            # TODO (WattsUp): Since payees are very unique they are almost all
            # misspelled. Instead of comparing to SpellChecker, compare to self looking
            # for payees within 2 distance from each other
            txn_fields = [
                TransactionSplit.payee,
                TransactionSplit.description,
                TransactionSplit.tag,
            ]
            for field in txn_fields:
                query = (
                    s.query(TransactionSplit)
                    .with_entities(
                        TransactionSplit.date_ord,
                        TransactionSplit.account_id,
                        field,
                    )
                    .group_by(field)
                )
                for date_ord, acct_id, value in query.yield_per(YIELD_PER):
                    date_ord: int
                    acct_id: int
                    value: str
                    date = datetime.date.fromordinal(date_ord)
                    source = f"{date} - {accounts[acct_id]}"
                    add(value, source, field.key)

            query = s.query(TransactionCategory.name)
            for (name,) in query.yield_per(YIELD_PER):
                name: str
                add(name, f"Txn category {name}", "name")

            words = {k: v for k, v in words.items() if k not in known}
            words = {k: v for k, v in words.items() if k in spell.unknown(words)}

            if len(words) != 0:
                source_len = 0
                field_len = 0

                for _, source, field in words.values():
                    source_len = max(source_len, len(source))
                    field_len = max(field_len, len(field))

                for uri, (word, source, field) in words.items():
                    # Getting a suggested correction is slow and error prone,
                    # Just say if a word is outside of the dictionary
                    msg = f"{source:{source_len}} {field:{field_len}}: {word}"
                    self._issues_raw[uri] = msg

        self._commit_issues()

    @override
    @classmethod
    def ignore(cls, p: portfolio.Portfolio, values: list[str] | set[str]) -> None:
        # Store the lower case version
        values = {v.lower() for v in values}
        return super().ignore(p, values)
