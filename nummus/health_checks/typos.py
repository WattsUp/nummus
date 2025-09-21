"""Checks for very similar fields and common typos."""

from __future__ import annotations

import datetime
import re
import string
from collections import defaultdict
from typing import override, TYPE_CHECKING

import spellchecker
from sqlalchemy import func, orm

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import (
    Account,
    Asset,
    AssetCategory,
    Label,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

_LIMIT_FREQUENCY = 10


class Typos(Base):
    """Checks for very similar fields and common typos."""

    _DESC = "Checks for very similar fields and common typos."
    _SEVERE = False

    _RE_WORDS = re.compile(rf"[ {re.escape(string.punctuation)}]")

    def __init__(
        self,
        *,
        no_ignores: bool = False,
        no_description_typos: bool = False,
    ) -> None:
        """Initialize Base health check.

        Args:
            p: Portfolio to test
            no_ignores: True will print issues that have been ignored
            no_description_typos: True will not check descriptions or memos for typos

        """
        super().__init__(no_ignores=no_ignores)
        self._no_description_typos = no_description_typos

        # Create a dict of every word found with the first instance detected
        # Dictionary {word.lower(): (word, source, field)}
        self._words: dict[str, tuple[str, str, str]] = {}
        self._frequency: dict[str, int] = defaultdict(int)
        self._proper_nouns: set[str] = set()

    @override
    def test(self, s: orm.Session) -> None:
        spell = spellchecker.SpellChecker()

        accounts = Account.map_name(s)
        assets = Asset.map_name(s)
        issues: dict[str, tuple[str, str, str]] = {}
        self._proper_nouns.update(accounts.values())
        self._proper_nouns.update(assets.values())

        issues.update(self._test_accounts(s, accounts))
        issues.update(self._test_labels(s))
        issues.update(self._test_transaction_nouns(s, accounts))

        # Escape words and sort to replace longest words first
        # So long words aren't partially replaced if they contain a short word
        proper_nouns_re = [
            re.escape(word)
            for word in sorted(self._proper_nouns, key=len, reverse=True)
        ]
        # Remove proper nouns indicated by word boundary or space at end
        re_cleaner = re.compile(rf"\b(?:{'|'.join(proper_nouns_re)})(?:\b|(?= |$))")

        issues.update(self._test_transaction_texts(s, accounts, re_cleaner, spell))
        issues.update(self._test_assets(s, assets, re_cleaner, spell))

        source_len = 0
        field_len = 0
        if len(issues) != 0:
            for _, source, field in issues.values():
                source_len = max(source_len, len(source))
                field_len = max(field_len, len(field))

        # Getting a suggested correction is slow and error prone,
        # Just say if a word is outside of the dictionary
        self._commit_issues(
            s,
            {
                uri: f"{source:{source_len}} {field:{field_len}}: {word}"
                for uri, (word, source, field) in issues.items()
            },
        )

        if self._no_description_typos:
            # Do commit and find issues as normal but hide the ones for description
            # If remove before, any ignores for descriptions are removed as well
            self._issues = {
                uri: issue
                for uri, issue in self._issues.items()
                if "description" not in issue and "memo" not in issue
            }

    def _add(self, s: str, source: str, field: str, count: int) -> None:
        if not s:
            return
        try:
            float(s)
        except ValueError:
            pass
        else:
            # Skip numbers
            return
        if s not in self._words:
            self._words[s] = (s, source, field)
        self._frequency[s] += count

    def _create_issues(self) -> dict[str, tuple[str, str, str]]:
        words_dedupe = utils.dedupe(self._words.keys())
        issues: dict[str, tuple[str, str, str]] = {
            word: item
            for word, item in self._words.items()
            if word not in words_dedupe and self._frequency[word] < _LIMIT_FREQUENCY
        }
        self._words.clear()
        self._frequency.clear()
        return issues

    def _test_accounts(
        self,
        s: orm.Session,
        accounts: dict[int, str],
    ) -> dict[str, tuple[str, str, str]]:
        query = s.query(Account).with_entities(
            Account.id_,
            Account.institution,
        )
        for acct_id, institution in query.yield_per(YIELD_PER):
            acct_id: int
            institution: str
            name = accounts[acct_id]
            source = f"Account {name}"
            self._add(institution, source, "institution", 1)
            self._proper_nouns.add(institution)
        return self._create_issues()

    def _test_labels(
        self,
        s: orm.Session,
    ) -> dict[str, tuple[str, str, str]]:
        query = s.query(Label.name)
        for (name,) in query.yield_per(YIELD_PER):
            name: str
            source = f"Label {name}"
            self._add(name, source, "name", 1)
            self._proper_nouns.add(name)
        return self._create_issues()

    def _test_transaction_nouns(
        self,
        s: orm.Session,
        accounts: dict[int, str],
    ) -> dict[str, tuple[str, str, str]]:
        issues: dict[str, tuple[str, str, str]] = {}
        txn_fields = [
            TransactionSplit.payee,
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
                .where(field.is_not(None))
                .group_by(field)
            )
            for date_ord, acct_id, value, count in query.yield_per(YIELD_PER):
                date_ord: int
                acct_id: int
                value: str
                date = datetime.date.fromordinal(date_ord)
                source = f"{date} - {accounts[acct_id]}"
                self._add(value, source, field.key, count)
                self._proper_nouns.add(value)
            issues.update(self._create_issues())
        return issues

    def _test_transaction_texts(
        self,
        s: orm.Session,
        accounts: dict[int, str],
        re_cleaner: re.Pattern,
        spell: spellchecker.SpellChecker,
    ) -> dict[str, tuple[str, str, str]]:
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.date_ord,
                TransactionSplit.account_id,
                TransactionSplit.memo,
                func.count(),
            )
            .group_by(TransactionSplit.memo)
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
                self._add(word, source, "memo", count)

        issues = {
            k: v
            for k, v in self._words.items()
            if k not in spell.word_frequency.dictionary
        }
        self._words.clear()
        return issues

    def _test_assets(
        self,
        s: orm.Session,
        assets: dict[int, str],
        re_cleaner: re.Pattern,
        spell: spellchecker.SpellChecker,
    ) -> dict[str, tuple[str, str, str]]:
        query = (
            s.query(Asset)
            .with_entities(
                Asset.id_,
                Asset.description,
            )
            .where(
                Asset.category != AssetCategory.INDEX,
                Asset.description.is_not(None),
            )
        )
        for a_id, value in query.yield_per(YIELD_PER):
            a_id: int
            value: str
            source = f"Asset {assets[a_id]}"
            cleaned = re_cleaner.sub("", value).lower()
            for word in self._RE_WORDS.split(cleaned):
                self._add(word, source, "description", 1)

        issues = {
            k: v
            for k, v in self._words.items()
            if k not in spell.word_frequency.dictionary
        }
        self._words.clear()
        return issues
