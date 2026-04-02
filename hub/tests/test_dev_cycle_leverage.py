"""
112.L — Dev-cycle leverage tests.

Proves:
1. L.1: PR template exists with evidence-linked closure checklist
2. L.2: Mypy ratchet strategy documented with owner + timeline
"""
import os

import pytest
from django.test import TestCase


pytestmark = pytest.mark.django_db(transaction=True)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _read(rel_path):
    path = os.path.join(_REPO_ROOT, rel_path)
    if not os.path.exists(path):
        pytest.skip(f"{rel_path} not found")
    with open(path) as f:
        return f.read()


def _exists(rel_path):
    return os.path.exists(os.path.join(_REPO_ROOT, rel_path))


class PRTemplateTest(TestCase):
    """L.1 — PR template enforces evidence-linked closure."""

    def test_pr_template_exists(self):
        self.assertTrue(
            _exists(".github/pull_request_template.md"),
            "PR template must exist at .github/pull_request_template.md",
        )

    def test_has_evidence_section(self):
        c = _read(".github/pull_request_template.md")
        self.assertIn("Evidence", c)

    def test_has_tests_pass_checkbox(self):
        c = _read(".github/pull_request_template.md")
        self.assertIn("Tests pass", c)

    def test_has_no_new_skips_checkbox(self):
        c = _read(".github/pull_request_template.md")
        self.assertIn("skip", c.lower())

    def test_has_security_checkbox(self):
        c = _read(".github/pull_request_template.md")
        self.assertIn("Security", c)
        self.assertIn("secret", c.lower())

    def test_has_checklist_section(self):
        c = _read(".github/pull_request_template.md")
        self.assertIn("Checklist", c)

    def test_references_skip_registry(self):
        c = _read(".github/pull_request_template.md")
        self.assertIn("SKIP_REGISTRY", c)


class MypyRatchetTest(TestCase):
    """L.2 — Mypy ratchet strategy documented."""

    def test_mypy_ratchet_doc_exists(self):
        self.assertTrue(
            _exists("docs/MYPY_RATCHET.md"),
        )

    def test_has_current_state(self):
        c = _read("docs/MYPY_RATCHET.md")
        self.assertIn("Current State", c)

    def test_has_owner_and_date(self):
        c = _read("docs/MYPY_RATCHET.md")
        self.assertIn("Owner", c)
        self.assertIn("Target date", c)

    def test_has_phased_strategy(self):
        c = _read("docs/MYPY_RATCHET.md")
        self.assertIn("Phase 1", c)
        self.assertIn("Phase 2", c)

    def test_mypy_in_ci(self):
        """CI must run mypy (even if non-blocking)."""
        c = _read(".github/workflows/ci.yml")
        self.assertIn("mypy", c)

    def test_mypy_config_exists(self):
        """pyproject.toml must have [tool.mypy] section."""
        c = _read("pyproject.toml")
        self.assertIn("[tool.mypy]", c)
