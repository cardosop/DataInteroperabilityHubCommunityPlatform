"""TDD suite for the traceability coverage gate's BEHAVIOR discounting
(Phase T.3 / W15).

The gate previously attributed a UC/journey ID to a file whenever the ID
appeared ANYWHERE in the file — including scaffold files whose only
UC-relevant test was ``test.skip(true, 'not yet implemented')``, and
Python tests whose marker sat on a skipped or assertion-free function.
That measured PROSE, not behavior: the scaffold duplicates counted as
coverage for 9 critical UCs while their real specs went unrecognized.

The discounting rules under test:

* TS specs: ``test.skip(...)`` / ``test.fixme(...)`` blocks are STRIPPED
  before substring matching — a skipped test's references do not count.
* Python files: ``@pytest.mark.uc/journey`` markers on a SKIPPED or
  ASSERTION-FREE test function do not count (assertion-freeness reuses
  T.1's AST predicate — one implementation, two callers).

No mocks: the REAL gate functions parse synthetic sources; the real-tree
test asserts the 9 scaffold duplicates are gone and their UCs are covered
by the real ``use-cases/`` specs.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from report_uc_journey_test_coverage import (
    build_coverage,
    find_references_in_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestSkippedTsDiscounting:
    def test_skipped_block_references_do_not_count(self, tmp_path):
        spec = tmp_path / "UC-FAKE-001.spec.ts"
        spec.write_text(
            "import { test, expect } from '@playwright/test';\n\n"
            "test.describe('scaffold', () => {\n"
            "  test('authenticated flow completes', async ({ page }) => {\n"
            "    // TODO: implement\n"
            "    test.skip(true, 'UC-FAKE-001 not yet implemented — scaffold ready');\n"
            "  });\n"
            "});\n",
            encoding="utf-8",
        )
        found = find_references_in_file(spec, ["UC-FAKE-001"])
        assert found == [], found

    def test_real_test_references_still_count(self, tmp_path):
        spec = tmp_path / "UC-REAL-001.spec.ts"
        spec.write_text(
            "import { test, expect } from '@playwright/test';\n\n"
            "test.describe('UC-REAL-001', () => {\n"
            "  test('page loads successfully', async ({ page }) => {\n"
            "    await page.goto('/');\n"
            "    await expect(page.locator('[data-testid=\"app-shell\"]')).toBeAttached();\n"
            "  });\n"
            "});\n",
            encoding="utf-8",
        )
        found = find_references_in_file(spec, ["UC-REAL-001"])
        assert found == ["UC-REAL-001"], found

    def test_multiline_skipped_block_is_stripped(self, tmp_path):
        spec = tmp_path / "UC-FAKE-002.spec.ts"
        spec.write_text(
            "test('x', async ({ page }) => {\n"
            "  test.skip(true, 'multi\\nline reason');\n"
            "});\n"
            "test('y', async ({ page }) => {\n"
            "  await expect(page).toHaveTitle('UC-FAKE-002');\n"
            "});\n",
            encoding="utf-8",
        )
        # The skip CALL itself is stripped; the real test still counts.
        found = find_references_in_file(spec, ["UC-FAKE-002"])
        assert found == ["UC-FAKE-002"], found

    def test_fixme_is_treated_like_skip(self, tmp_path):
        spec = tmp_path / "UC-FIX-001.spec.ts"
        spec.write_text(
            "test.fixme(true, 'UC-FIX-001 not implemented yet');\n",
            encoding="utf-8",
        )
        assert find_references_in_file(spec, ["UC-FIX-001"]) == []


class TestPythonMarkerDiscounting:
    def _build(self, tmp_path, source: str):
        py = tmp_path / "hub" / "apps" / "x" / "tests" / "test_uc.py"
        py.parent.mkdir(parents=True)
        py.write_text(source, encoding="utf-8")
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "USE_CASES.md").write_text("| UC-X-001 | title |\n")
        return py

    def test_marker_on_assertion_free_test_does_not_count(self, tmp_path):
        py = self._build(
            tmp_path,
            "import pytest\n\n\n@pytest.mark.uc('UC-X-001')\ndef test_stubbed():\n    x = 1\n",
        )
        files = [py]
        uc_to_files, _ = build_coverage(tmp_path, ["UC-X-001"], [], files)
        assert uc_to_files["UC-X-001"] == [], uc_to_files

    def test_marker_on_skipped_test_does_not_count(self, tmp_path):
        py = self._build(
            tmp_path,
            "import pytest\n\n\n"
            "@pytest.mark.uc('UC-X-001')\n"
            "@pytest.mark.skip(reason='blocked')\n"
            "def test_blocked():\n"
            "    assert 1 == 1\n",
        )
        uc_to_files, _ = build_coverage(tmp_path, ["UC-X-001"], [], [py])
        assert uc_to_files["UC-X-001"] == [], uc_to_files

    def test_marker_on_real_test_counts(self, tmp_path):
        py = self._build(
            tmp_path,
            "import pytest\n\n\n@pytest.mark.uc('UC-X-001')\ndef test_real():\n    assert 1 == 1\n",
        )
        uc_to_files, _ = build_coverage(tmp_path, ["UC-X-001"], [], [py])
        assert uc_to_files["UC-X-001"] != [], uc_to_files


class TestRealTreeScaffolds:
    SCAFFOLD_IDS = (
        "UC-AM-002",
        "UC-CM-003",
        "UC-CM-004",
        "UC-GOV-ADV-001",
        "UC-GOV-ADV-002",
        "UC-GOV-ADV-003",
        "UC-GOV-ADV-004",
        "UC-MKT-ADV-001",
        "UC-MKT-ADV-002",
    )

    def test_root_scaffold_duplicates_are_gone(self):
        for uc in self.SCAFFOLD_IDS:
            assert not (REPO_ROOT / "frontend" / "e2e" / f"{uc}.spec.ts").exists(), (
                f"{uc}.spec.ts scaffold duplicate still at the e2e root — the "
                "real spec under use-cases/ supersedes it"
            )

    def test_each_uc_is_covered_by_its_real_spec(self):
        for uc in self.SCAFFOLD_IDS:
            matches = list((REPO_ROOT / "frontend" / "e2e" / "use-cases").rglob(f"{uc}.spec.ts"))
            assert matches, f"{uc} has no real spec under use-cases/"
            found = find_references_in_file(matches[0], [uc])
            assert found == [uc], f"{uc}: real spec {matches[0]} does not reference the ID"
