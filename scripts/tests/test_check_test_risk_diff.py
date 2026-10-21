"""TDD suite for the PR-level test-risk signal (Phase T.6 / W18).

``scripts/check_test_risk_diff.py`` turns the three test-debt growth
classes into a routed PR signal (non-blocking — a signal, not a gate):
  * ADDED skip sites (pytest.mark.skip / pytest.skip( / test.skip /
    test.fixme / describe.skip / unittest.skip / it.skip),
  * REMOVED assertion lines (assert / self.assert* / expect( ),
  * INTRODUCED broad excepts (except Exception / bare except:),
in TEST files only (test_*.py, *_test.py, conftest.py, tests/**,
*.spec.ts, *.test.ts(x)).

Each finding is routed to the owning team resolved from CODEOWNERS
(last-order-wins longest-prefix match).

No mocks: real diff text analyzed by the real analyzer; a real temp git
repository exercises the end-to-end git-diff path; the owner resolver
runs against the committed .github/CODEOWNERS.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_test_risk_diff as risk  # type: ignore[import-not-found]  # runtime sys.path injection, scripts/ is not a package

DIFF_HEADER = "diff --git a/tests/test_x.py b/tests/test_x.py\n"
HUNK_HEADER = "--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1,4 +1,5 @@\n"


def diff(*hunks: str) -> str:
    return "".join(hunks)


class TestDiffAnalysis:
    def test_added_skip_is_flagged(self):
        d = diff(
            DIFF_HEADER,
            HUNK_HEADER,
            " def test_x():\n",
            "+    pytest.skip('service down')\n",
            "     assert True\n",
        )
        findings = risk.analyze_diff(d)
        assert len(findings) == 1
        assert findings[0].kind == "added-skip"
        assert findings[0].file == "tests/test_x.py"

    def test_added_mark_skip_decorator_is_flagged(self):
        d = diff(
            DIFF_HEADER,
            HUNK_HEADER,
            "+@pytest.mark.skip(reason='flaky')\n",
            " def test_x():\n",
            "     assert True\n",
        )
        findings = risk.analyze_diff(d)
        assert [f.kind for f in findings] == ["added-skip"]

    def test_added_ts_skip_is_flagged(self):
        d = diff(
            "diff --git a/frontend/e2e/x.spec.ts b/frontend/e2e/x.spec.ts\n",
            "--- a/frontend/e2e/x.spec.ts\n+++ b/frontend/e2e/x.spec.ts\n@@ -1,2 +1,3 @@\n",
            "+test.skip(true, 'not implemented');\n",
            " test('real', () => {});\n",
        )
        findings = risk.analyze_diff(d)
        assert [f.kind for f in findings] == ["added-skip"]

    def test_removed_assertion_is_flagged(self):
        d = diff(
            DIFF_HEADER,
            HUNK_HEADER,
            "-    assert result == 42\n",
            "     return result\n",
        )
        findings = risk.analyze_diff(d)
        assert [f.kind for f in findings] == ["removed-assertion"]

    def test_removed_expect_is_flagged(self):
        d = diff(
            "diff --git a/frontend/e2e/x.spec.ts b/frontend/e2e/x.spec.ts\n",
            "--- a/frontend/e2e/x.spec.ts\n+++ b/frontend/e2e/x.spec.ts\n@@ -1,2 +1,2 @@\n",
            "-  expect(page).toHaveURL(/dashboard/);\n",
            "   await page.goto('/dashboard');\n",
        )
        findings = risk.analyze_diff(d)
        assert [f.kind for f in findings] == ["removed-assertion"]

    def test_added_except_exception_is_flagged(self):
        d = diff(
            DIFF_HEADER,
            HUNK_HEADER,
            "+    except Exception:\n",
            "         pass\n",
        )
        findings = risk.analyze_diff(d)
        assert [f.kind for f in findings] == ["broad-except"]

    def test_bare_except_is_flagged(self):
        d = diff(
            DIFF_HEADER,
            HUNK_HEADER,
            "+    except:\n",
        )
        findings = risk.analyze_diff(d)
        assert [f.kind for f in findings] == ["broad-except"]

    def test_non_test_files_ignored(self):
        d = diff(
            "diff --git a/hub/apps/assets/views.py b/hub/apps/assets/views.py\n",
            "--- a/hub/apps/assets/views.py\n+++ b/hub/apps/assets/views.py\n@@ -1,2 +1,3 @@\n",
            "+    except Exception:\n",
        )
        assert risk.analyze_diff(d) == []

    def test_unchanged_context_lines_ignored(self):
        d = diff(
            DIFF_HEADER,
            HUNK_HEADER,
            "     except Exception:\n",  # context line, not an addition
            "     assert True\n",
        )
        assert risk.analyze_diff(d) == []

    def test_clean_diff_has_no_findings(self):
        d = diff(
            DIFF_HEADER,
            HUNK_HEADER,
            "+    assert result == 42\n",
        )
        assert risk.analyze_diff(d) == []


class TestOwnerResolution:
    def test_owner_resolution_from_real_codeowners(self):
        codeowners = REPO_ROOT / ".github" / "CODEOWNERS"
        team = risk.resolve_owner("sdk/python/tests/security/test_api_key_scope.py", codeowners)
        assert "@meshant/dev-tooling-eng" in team

    def test_owner_resolution_last_order_wins(self, tmp_path):
        co = tmp_path / "CODEOWNERS"
        co.write_text("sdk/ @team-a\nsdk/python/ @team-b\n", encoding="utf-8")
        assert risk.resolve_owner("sdk/python/tests/x.py", co) == ["@team-b"]

    def test_unknown_path_owner_is_none(self, tmp_path):
        co = tmp_path / "CODEOWNERS"
        co.write_text("sdk/python/ @team-a\n", encoding="utf-8")
        assert risk.resolve_owner("hub/apps/assets/x.py", co) == []


class TestEndToEndGitRepo:
    def test_git_diff_path_flags_added_skip(self, tmp_path):
        """Real git repository: commit a test file, add a skip, and the
        script must report it with exit 0 (a signal, not a gate)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
        (repo / "tests").mkdir()
        (repo / "tests" / "test_x.py").write_text(
            "def test_x():\n    assert True\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        (repo / "tests" / "test_x.py").write_text(
            "import pytest\n\ndef test_x():\n    pytest.skip('temp')\n    assert True\n",
            encoding="utf-8",
        )
        out = risk.report_for_range(str(repo / "CODEOWNERS"), base="HEAD", head=None, cwd=str(repo))
        assert "added-skip" in out
        assert "test_x.py" in out
