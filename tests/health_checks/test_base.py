from __future__ import annotations

import secrets

from typing_extensions import override

from nummus import portfolio
from nummus.health_checks.base import Base
from nummus.models import HealthCheckIssue
from tests.base import TestBase


class TestCheckBase(TestBase):
    def test_init_properties(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        name = self.random_string()
        desc = self.random_string()

        class MockCheck(Base):
            _NAME = name
            _DESC = desc
            _SEVERE = True

            @override
            def test(self) -> None:
                self._issues_raw = {}

        c = MockCheck(p)
        self.assertEqual(c.name, name)
        self.assertEqual(c.description, desc)
        self.assertFalse(c.any_issues, "Check has an issue")
        self.assertTrue(c.is_severe, "Check is not severe")

        d = {"0": self.random_string()}
        c._issues = d  # noqa: SLF001
        self.assertTrue(c.any_issues, "Check has no issues")
        self.assertEqual(c.issues, d)

    def test_ignore(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        name = self.random_string()
        desc = self.random_string()

        class MockCheck(Base):
            _NAME = name
            _DESC = desc
            _SEVERE = True

            @override
            def test(self) -> None:
                self._issues_raw = {}

        uri_0 = self.random_string()
        uri_1 = self.random_string()
        MockCheck.ignore(p, {uri_0})
        with p.get_session() as s:
            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, name)
            self.assertEqual(i.value, uri_0)
            self.assertTrue(i.ignore, "Issue is not ignored")

        MockCheck.ignore(p, [uri_0, uri_1])
        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 2)

            i = s.query(HealthCheckIssue).where(HealthCheckIssue.value == uri_1).one()
            self.assertEqual(i.check, name)
            self.assertEqual(i.value, uri_1)
            self.assertTrue(i.ignore, "Issue is not ignored")

        MockCheck.ignore(p, [])
        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 2)

            c = s.query(HealthCheckIssue).where(HealthCheckIssue.value == uri_1).one()
            self.assertEqual(c.check, name)
            self.assertEqual(c.value, uri_1)
            self.assertTrue(c.ignore, "Issue is not ignored")

    def test_test_and_commit_issues(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        name = self.random_string()
        desc = self.random_string()

        d = {
            "0": self.random_string(),
            "1": self.random_string(),
        }

        class MockCheck(Base):
            _NAME = name
            _DESC = desc
            _SEVERE = True

            @override
            def test(self) -> None:
                self._issues_raw = dict(d)
                self._commit_issues()

        c = MockCheck(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 2)

            i = s.query(HealthCheckIssue).where(HealthCheckIssue.value == "0").one()
            self.assertFalse(i.ignore, "Issue is ignored")
            uri_0 = i.uri

            i = s.query(HealthCheckIssue).where(HealthCheckIssue.value == "1").one()
            self.assertFalse(i.ignore, "Issue is ignored")
            uri_1 = i.uri

        result = c.issues
        target = {
            uri_0: d["0"],
            uri_1: d["1"],
        }
        self.assertEqual(result, target)

        MockCheck.ignore(p, {"1"})

        c = MockCheck(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 2)

            i = s.query(HealthCheckIssue).where(HealthCheckIssue.value == "0").one()
            self.assertFalse(i.ignore, "Issue is ignored")
            uri_0 = i.uri

            i = s.query(HealthCheckIssue).where(HealthCheckIssue.value == "1").one()
            self.assertTrue(i.ignore, "Issue is not ignored")
            uri_1 = i.uri

        result = c.issues
        target = {
            uri_0: d["0"],
        }
        self.assertEqual(result, target)

        c = MockCheck(p, no_ignores=True)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 2)

            i = s.query(HealthCheckIssue).where(HealthCheckIssue.value == "0").one()
            self.assertFalse(i.ignore, "Issue is ignored")
            uri_0 = i.uri

            i = s.query(HealthCheckIssue).where(HealthCheckIssue.value == "1").one()
            self.assertTrue(i.ignore, "Issue is not ignored")
            uri_1 = i.uri

        result = c.issues
        target = {
            uri_0: d["0"],
            uri_1: d["1"],
        }
        self.assertEqual(result, target)

        # Solved this issue
        d.pop("1")
        c = MockCheck(p, no_ignores=True)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).where(HealthCheckIssue.value == "0").one()
            self.assertFalse(i.ignore, "Issue is ignored")
            uri_0 = i.uri

        result = c.issues
        target = {
            uri_0: d["0"],
        }
        self.assertEqual(result, target)
