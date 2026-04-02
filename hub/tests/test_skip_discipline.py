"""
112.I — E2E skip program tests.

Proves:
1. I.1: Skip registry exists and is maintained
2. I.1: No bare skip markers without reasons
3. I.2: E2E conditional skips have descriptive reasons (not
        hiding infra issues behind generic skips)
4. I.2: Backend skips reference service/reason (not bare)
"""
import os
import re

import pytest
from django.test import TestCase


pytestmark = pytest.mark.django_db(transaction=True)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _read_file(rel_path):
    path = os.path.join(_REPO_ROOT, rel_path)
    if not os.path.exists(path):
        pytest.skip(f"{rel_path} not found")
    with open(path) as f:
        return f.read()


def _find_files(directory, extension):
    """Yield all files with given extension under directory."""
    base = os.path.join(_REPO_ROOT, directory)
    if not os.path.isdir(base):
        return
    for root, _, files in os.walk(base):
        for f in files:
            if f.endswith(extension):
                yield os.path.join(root, f)


class SkipRegistryTest(TestCase):
    """I.1 — Skip registry exists and is maintained."""

    def test_skip_registry_exists(self):
        """docs/SKIP_REGISTRY.md must exist."""
        path = os.path.join(_REPO_ROOT, "docs/SKIP_REGISTRY.md")
        self.assertTrue(
            os.path.exists(path),
            "docs/SKIP_REGISTRY.md must exist as the "
            "single source of truth for skipped tests",
        )

    def test_skip_registry_has_e2e_section(self):
        """Registry must document E2E skips."""
        content = _read_file("docs/SKIP_REGISTRY.md")
        self.assertIn("E2E Skips", content)

    def test_skip_registry_has_backend_section(self):
        """Registry must document backend skips."""
        content = _read_file("docs/SKIP_REGISTRY.md")
        self.assertIn("Backend Skips", content)

    def test_skip_registry_has_category_column(self):
        """Registry must categorise skips (INFRA/DEFERRED)."""
        content = _read_file("docs/SKIP_REGISTRY.md")
        self.assertIn("INFRA", content)
        self.assertIn("DEFERRED", content)

    def test_skip_registry_has_policy(self):
        """Registry must document the skip policy."""
        content = _read_file("docs/SKIP_REGISTRY.md")
        self.assertIn("Policy", content)


class E2ESkipDisciplineTest(TestCase):
    """I.1 + I.2 — E2E skips have reasons, no bare skips."""

    def test_no_bare_test_skip_in_e2e(self):
        """
        Every test.skip() in E2E specs must have a reason
        string — bare test.skip() without explanation is
        forbidden.
        """
        bare_skips = []
        for filepath in _find_files("frontend/e2e", ".spec.ts"):
            with open(filepath) as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    # Skip comments (// ...) — not actual code
                    if stripped.startswith("//") or stripped.startswith("/*"):
                        continue
                    # Match test.skip() with no args
                    if re.search(
                        r'test\.skip\(\s*\)\s*;',
                        stripped,
                    ):
                        rel = os.path.relpath(filepath, _REPO_ROOT)
                        bare_skips.append(f"{rel}:{i}")

        self.assertEqual(
            bare_skips, [],
            f"Found {len(bare_skips)} bare test.skip() "
            f"without reason: {bare_skips}",
        )

    def test_describe_skips_have_uc_reference(self):
        """
        Every test.describe.skip must reference a UC/JOURNEY
        ID or clear feature name in the surrounding context.
        """
        skipped_files = []
        for filepath in _find_files("frontend/e2e", ".spec.ts"):
            with open(filepath) as f:
                content = f.read()
            if "describe.skip" in content:
                rel = os.path.relpath(filepath, _REPO_ROOT)
                # Must have JOURNEY- or UC- or DEFERRED in file
                if not re.search(
                    r'JOURNEY-|UC-|DEFERRED|deferred|backlog',
                    content,
                    re.IGNORECASE,
                ):
                    skipped_files.append(rel)

        self.assertEqual(
            skipped_files, [],
            f"describe.skip without UC/JOURNEY reference: "
            f"{skipped_files}",
        )


class BackendSkipDisciplineTest(TestCase):
    """I.2 — Backend skips have descriptive reasons."""

    def test_no_bare_pytest_skip_in_hub(self):
        """
        Every pytest.skip() / skipTest() in hub/ must have
        a reason string.
        """
        bare_skips = []
        for filepath in _find_files("hub", ".py"):
            # Exclude conftest (uses skip for utility functions)
            # and this test file itself (contains search patterns)
            basename = os.path.basename(filepath)
            if basename in ("conftest.py", "test_skip_discipline.py"):
                continue
            with open(filepath) as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    # Match self.skipTest() or pytest.skip()
                    # with no string argument
                    if re.search(
                        r'(self\.skipTest|pytest\.skip)\(\s*\)',
                        stripped,
                    ):
                        rel = os.path.relpath(
                            filepath, _REPO_ROOT,
                        )
                        bare_skips.append(f"{rel}:{i}")

        self.assertEqual(
            bare_skips, [],
            f"Found {len(bare_skips)} bare skip() without "
            f"reason: {bare_skips}",
        )

    def test_no_infra_masked_as_xfail(self):
        """
        xfail must not be used to hide infrastructure
        issues — infra skips must use skipTest/pytest.skip
        with a service-level reason.
        """
        infra_xfails = []
        for filepath in _find_files("hub", ".py"):
            with open(filepath) as f:
                for i, line in enumerate(f, 1):
                    if "@pytest.mark.xfail" in line:
                        # Check if reason mentions infra
                        if re.search(
                            r'redis|postgres|docker|'
                            r'service.*unavailable|'
                            r'container|minio',
                            line, re.IGNORECASE,
                        ):
                            rel = os.path.relpath(
                                filepath, _REPO_ROOT,
                            )
                            infra_xfails.append(
                                f"{rel}:{i}",
                            )

        self.assertEqual(
            infra_xfails, [],
            f"Found xfail masking infra issues (should use "
            f"skipTest instead): {infra_xfails}",
        )
