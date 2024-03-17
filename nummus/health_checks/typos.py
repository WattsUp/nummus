"""Checks for very similar fields and common typos."""

from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING

import sqlalchemy
from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, Asset, AssetCategory, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from nummus import portfolio

# If a non-unique word has a bunch of instances, it is probably not spelled wrong
_LIMIT_FREQUENCY = 10


class Typos(Base):
    """Checks for very similar fields and common typos."""

    _NAME = "Typos"
    _DESC = "Checks for very similar fields and common typos."
    _SEVERE = False

    _RE_WORDS = re.compile(r"[ ,/]")

    @override
    def test(self) -> None:
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
            issues: dict[str, tuple[str, str, str]] = {}

            # Create a dict of every word found with the first instance detected
            # Dictionary {word.lower(): (word, source, field)}
            words: dict[str, tuple[str, str, str]] = {}
            frequency: dict[str, int] = {}
            proper_nouns: set[str] = set()

            def add(s: str | None, source: str, field: str, count: int) -> None:
                if s is None:
                    return
                if s not in words:
                    words[s] = (s, source, field)
                    frequency[s] = 0
                frequency[s] += count

            def check_duplicates() -> None:
                words_dedupe = utils.dedupe(words.keys())
                for word, item in words.items():
                    if word in words_dedupe:
                        proper_nouns.add(word)
                    elif frequency[word] < _LIMIT_FREQUENCY:
                        issues[word] = item
                words.clear()
                frequency.clear()

            for name in accounts.values():
                source = f"Account {name}"
                add(name, source, "name", 1)
            check_duplicates()

            query = s.query(Account).with_entities(
                Account.id_,
                Account.institution,
            )
            for acct_id, institution in query.yield_per(YIELD_PER):
                acct_id: int
                institution: str
                name = accounts[acct_id]
                source = f"Account {name}"
                add(institution, source, "institution", 1)
            check_duplicates()

            query = s.query(Asset.name).where(Asset.category != AssetCategory.INDEX)
            for (name,) in query.yield_per(YIELD_PER):
                name: str
                source = f"Asset {name}"
                add(name, source, "name", 1)
            check_duplicates()

            txn_fields = [
                TransactionSplit.payee,
                TransactionSplit.tag,
            ]
            for field in txn_fields:
                query = (
                    s.query(TransactionSplit)
                    .with_entities(
                        TransactionSplit.date_ord,
                        TransactionSplit.account_id,
                        field,
                        sqlalchemy.func.count(),
                    )
                    .group_by(field)
                )
                for date_ord, acct_id, value, count in query.yield_per(YIELD_PER):
                    date_ord: int
                    acct_id: int
                    value: str
                    date = datetime.date.fromordinal(date_ord)
                    source = f"{date} - {accounts[acct_id]}"
                    add(value, source, field.key, count)
                check_duplicates()

            # TODO (WattsUp): Add check spelling of descriptions

            if len(issues) != 0:
                source_len = 0
                field_len = 0

                for _, source, field in issues.values():
                    source_len = max(source_len, len(source))
                    field_len = max(field_len, len(field))

                for uri, (word, source, field) in issues.items():
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
