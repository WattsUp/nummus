"""Checks for very similar fields and common typos."""

from __future__ import annotations

import datetime
import re
import string
from collections import defaultdict
from typing import TYPE_CHECKING

import spellchecker
from sqlalchemy import func
from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, Asset, AssetCategory, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from nummus import portfolio

_LIMIT_FREQUENCY = 10


class Typos(Base):
    """Checks for very similar fields and common typos."""

    _DESC = "Checks for very similar fields and common typos."
    _SEVERE = False

    _RE_WORDS = re.compile(r"[ .,/()\[\]\-#:&!+?%'\";]")

    def __init__(
        self,
        p: portfolio.Portfolio,
        *,
        no_ignores: bool = False,
        no_description_typos: bool = False,
    ) -> None:
        """Initialize Base health check.

        Args:
            p: Portfolio to test
            no_ignores: True will print issues that have been ignored
            no_description_typos: True will not check descriptions for typos
        """
        super().__init__(p, no_ignores=no_ignores)
        self._no_description_typos = no_description_typos

    @override
    def test(self) -> None:
        spell = spellchecker.SpellChecker()

        with self._p.begin_session() as s:
            accounts = Account.map_name(s)
            assets = Asset.map_name(s)
            issues: dict[str, tuple[str, str, str]] = {}

            # Create a dict of every word found with the first instance detected
            # Dictionary {word.lower(): (word, source, field)}
            words: dict[str, tuple[str, str, str]] = {}
            frequency: dict[str, int] = defaultdict(int)
            proper_nouns: set[str] = {*accounts.values(), *assets.values()}

            def add(s: str, source: str, field: str, count: int) -> None:
                if not s:
                    return
                try:
                    float(s)
                except ValueError:
                    pass
                else:
                    # Skip numbers
                    return
                if s in string.punctuation:
                    return
                if s not in words:
                    words[s] = (s, source, field)
                frequency[s] += count

            def check_duplicates() -> None:
                words_dedupe = utils.dedupe(words.keys())
                issues.update(
                    {
                        word: item
                        for word, item in words.items()
                        if word not in words_dedupe
                        and frequency[word] < _LIMIT_FREQUENCY
                    },
                )
                words.clear()
                frequency.clear()

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
                proper_nouns.add(institution)
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
                        func.count(),
                    )
                    .group_by(field)
                )
                for date_ord, acct_id, value, count in query.yield_per(YIELD_PER):
                    date_ord: int
                    acct_id: int
                    value: str | None
                    if value is None:
                        continue
                    date = datetime.date.fromordinal(date_ord)
                    source = f"{date} - {accounts[acct_id]}"
                    add(value, source, field.key, count)
                    proper_nouns.add(value)
                check_duplicates()

            # Escape words and sort to replace longest words first
            # So long words aren't partially replaced if they contain a short word
            proper_nouns_re = [
                re.escape(word)
                for word in sorted(proper_nouns, key=lambda x: len(x), reverse=True)
            ]
            # Remove proper nouns indicated by word boundary or space at end
            re_cleaner = re.compile(rf"\b(?:{'|'.join(proper_nouns_re)})(?:\b|(?= |$))")

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.date_ord,
                    TransactionSplit.account_id,
                    TransactionSplit.description,
                    func.count(),
                )
                .group_by(TransactionSplit.description)
            )
            for date_ord, acct_id, value, count in query.yield_per(YIELD_PER):
                date_ord: int
                acct_id: int
                value: str | None
                if value is None:
                    continue
                date = datetime.date.fromordinal(date_ord)
                source = f"{date} - {accounts[acct_id]}"
                cleaned = re_cleaner.sub("", value).lower()
                for word in self._RE_WORDS.split(cleaned):
                    add(word, source, "description", count)

            query = (
                s.query(Asset)
                .with_entities(
                    Asset.id_,
                    Asset.description,
                )
                .where(Asset.category != AssetCategory.INDEX)
            )
            for a_id, value in query.yield_per(YIELD_PER):
                a_id: int
                value: str | None
                if value is None:
                    continue
                source = f"Asset {assets[a_id]}"
                cleaned = re_cleaner.sub("", value).lower()
                for word in self._RE_WORDS.split(cleaned):
                    add(word, source, "description", 1)

            words = {
                k: v
                for k, v in words.items()
                if k not in spell.word_frequency.dictionary
            }
            issues.update(words)

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

        if self._no_description_typos:
            # Do commit and find issues as normal but hide the ones for description
            # If remove before, any ignores for descriptions are removed as well
            self._issues = {
                uri: issue
                for uri, issue in self._issues.items()
                if "description:" not in issue
            }
