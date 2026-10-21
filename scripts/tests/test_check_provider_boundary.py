"""GATE-54 TDD suite (openspec oss-release-remediation W4.6 / G1) — pins for
the control-plane provider-boundary import checker.

No mocks: real fixture trees under ``tmp_path`` drive the REAL CLI
(``check_provider_boundary.py`` via subprocess — the GATE-29 convention),
real git repositories drive the ratchet pins, and the REAL repository
tree is pinned for the live-state contract: the checker MUST be GREEN on
the real tree (the W4.6 evidence — "checker green") and MUST flip RED
when a planted violation is added (the planted-violation pin).

Contract under test (one decision per pin):
- an import of ``hub.apps.databricks_admin`` from a non-test file outside
  the estate app is a VIOLATION (exit 1) unless allowlisted;
- ``if TYPE_CHECKING:`` imports are exempt — proven NON-VACUOUS by the
  same import outside the guard flipping the gate;
- test files (a ``tests``/``test`` path component or a ``test_*``/
  ``*_test`` basename) are out of the blocking scope — ``--include-tests``
  reports them advisory (exit unchanged);
- the estate app's own files may import their own modules;
- allowlist anchors are exact ``relpath:lineno`` triples — a drifted
  anchor or a dead anchor FAILS LOUDLY;
- the ratchet (``--check-allowlist-growth``) uses per-file accounting:
  line churn passes, a NEW entry in any file is growth and fails.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check_provider_boundary.py"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VIOLATING_SRC = '''"""A provider-agnostic module that reaches into the estate."""


def run(tenant_id):
    from hub.apps.databricks_admin.models import DatabricksWorkspace

    return DatabricksWorkspace.objects.filter(tenant_id=tenant_id)
'''

TYPECHECKING_SRC = '''"""Type-only estate reference — no runtime coupling."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hub.apps.databricks_admin.client import DatabricksApiClient


def stage(client: "DatabricksApiClient") -> None:
    return None
'''

ALLOWLISTED_SRC = '''"""The sanctioned connector seam (task 1.7)."""
from hub.apps.databricks_admin.client import DatabricksApiClient, DatabricksApiError


def request_path(client: DatabricksApiClient):
    return client.request("GET", "uc.catalogs.list")
'''


def _write(root: Path, relpath: str, content: str) -> None:
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--root",
        str(root),
        "--allowlist",
        str(root / "allowlist.txt"),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    root.mkdir()
    (root / "hub" / "apps").mkdir(parents=True)
    (root / "allowlist.txt").write_text("# empty\n")
    return root


class TestViolationDetection:
    def test_planted_violation_flips_red(self, tmp_path):
        root = _fixture_root(tmp_path)
        _write(root, "hub/data_movement/pipeline.py", VIOLATING_SRC)

        proc = _run(root)
        assert proc.returncode == 1, proc.stdout
        assert "hub/data_movement/pipeline.py:5" in proc.stdout
        assert "GATE-54 FAILED" in proc.stdout

    def test_clean_tree_is_green(self, tmp_path):
        root = _fixture_root(tmp_path)
        _write(root, "hub/data_movement/pipeline.py", "def run(): pass\n")

        proc = _run(root)
        assert proc.returncode == 0, proc.stdout
        assert "GATE-54 PASSED" in proc.stdout

    def test_import_forms_all_detected(self, tmp_path):
        """``from``, ``import``, module-level, and function-level nesting."""
        root = _fixture_root(tmp_path)
        _write(
            root,
            "hub/data_movement/forms.py",
            (
                "import hub.apps.databricks_admin.client\n"
                "from hub.apps.databricks_admin import models\n"
                "\n"
                "def f():\n"
                "    from hub.apps.databricks_admin.token_cache import M2MTokenCache\n"
            ),
        )
        proc = _run(root)
        assert proc.returncode == 1, proc.stdout
        assert proc.stdout.count("VIOLATION") == 3, proc.stdout


class TestTypeCheckingExemption:
    def test_typechecking_guard_is_exempt(self, tmp_path):
        root = _fixture_root(tmp_path)
        _write(root, "hub/data_movement/staging.py", TYPECHECKING_SRC)

        proc = _run(root)
        assert proc.returncode == 0, proc.stdout

    def test_exemption_is_non_vacuous(self, tmp_path):
        """The SAME import outside the guard flips the gate — the exemption
        is the guard, not a blanket pardon for the file."""
        root = _fixture_root(tmp_path)
        _write(root, "hub/data_movement/staging.py", TYPECHECKING_SRC)
        _write(
            root,
            "hub/data_movement/runtime.py",
            "from hub.apps.databricks_admin.client import DatabricksApiClient\n",
        )
        proc = _run(root)
        assert proc.returncode == 1, proc.stdout
        assert "hub/data_movement/runtime.py:1" in proc.stdout


class TestAllowlist:
    def test_allowlisted_seam_passes(self, tmp_path):
        root = _fixture_root(tmp_path)
        _write(
            root,
            "hub/apps/integrations/connectors/databricks_connector.py",
            ALLOWLISTED_SRC,
        )
        _write(
            root,
            "allowlist.txt",
            "hub/apps/integrations/connectors/databricks_connector.py:2:"
            "sanctioned seam (task 1.7) — delegation-mode client consumer\n",
        )
        proc = _run(root)
        assert proc.returncode == 0, proc.stdout

    def test_drifted_anchor_fails_loudly(self, tmp_path):
        """A line shift without re-anchoring is a violation (the W0.4b
        lesson — 541 silent violations rotted while anchors drifted)."""
        root = _fixture_root(tmp_path)
        _write(
            root,
            "hub/apps/integrations/connectors/databricks_connector.py",
            ALLOWLISTED_SRC,
        )
        _write(
            root,
            "allowlist.txt",
            "hub/apps/integrations/connectors/databricks_connector.py:99:"
            "sanctioned seam (task 1.7) — delegation-mode client consumer\n",
        )
        proc = _run(root)
        assert proc.returncode == 1, proc.stdout
        assert ":2" in proc.stdout  # the real site is reported
        assert "DEAD ANCHOR" in proc.stdout  # the drifted anchor is reported

    def test_dead_anchor_alone_fails(self, tmp_path):
        """An allowlist entry matching no import is drift — never silent."""
        root = _fixture_root(tmp_path)
        _write(root, "hub/data_movement/pipeline.py", "def run(): pass\n")
        _write(
            root,
            "allowlist.txt",
            "hub/apps/gone/removed.py:7:audited site that no longer exists\n",
        )
        proc = _run(root)
        assert proc.returncode == 1, proc.stdout
        assert "DEAD ANCHOR hub/apps/gone/removed.py:7" in proc.stdout

    def test_malformed_allowlist_entry_raises(self, tmp_path):
        root = _fixture_root(tmp_path)
        _write(root, "allowlist.txt", "no_lineno_here\n")
        proc = _run(root)
        assert proc.returncode != 0
        assert "malformed allowlist entry" in proc.stderr


class TestScope:
    def test_test_file_import_is_out_of_blocking_scope(self, tmp_path):
        root = _fixture_root(tmp_path)
        _write(root, "hub/apps/warehouses/tests/test_real_api.py", VIOLATING_SRC)
        _write(root, "tests/integration/databricks_e2e/test_x.py", VIOLATING_SRC)
        _write(root, "scripts/tests/test_tooling.py", VIOLATING_SRC)

        proc = _run(root)
        assert proc.returncode == 0, proc.stdout
        assert "VIOLATION" not in proc.stdout

    def test_include_tests_reports_advisory_only(self, tmp_path):
        root = _fixture_root(tmp_path)
        _write(root, "hub/apps/warehouses/tests/test_real_api.py", VIOLATING_SRC)

        proc = _run(root, "--include-tests")
        assert proc.returncode == 0, proc.stdout
        assert (
            "ADVISORY (test file) hub/apps/warehouses/tests/test_real_api.py:5"
            in proc.stdout
        )

    def test_estate_app_self_imports_are_fine(self, tmp_path):
        root = _fixture_root(tmp_path)
        _write(root, "hub/apps/databricks_admin/services.py", VIOLATING_SRC)
        _write(
            root,
            "hub/apps/databricks_admin/views.py",
            "from hub.apps.databricks_admin.client import DatabricksApiClient\n",
        )
        proc = _run(root)
        assert proc.returncode == 0, proc.stdout


class TestRealTree:
    def test_real_tree_is_green(self):
        """The live-state contract (the W4.6 evidence): the REAL repository
        tree passes the checker with the REAL allowlist."""
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout

    def test_real_tree_planted_violation_flips_red(self, tmp_path):
        """The planted-violation evidence against the REAL tree: copy the
        tree is unnecessary — a temporary violation file under the repo is
        created, scanned, and removed (a `hub/` subdir the checker scans)."""
        planted = REPO_ROOT / "hub" / "data_movement" / "_g54_planted.py"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text(VIOLATING_SRC)
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert proc.returncode == 1, proc.stdout
            assert "_g54_planted.py:5" in proc.stdout
        finally:
            planted.unlink()


class TestRatchet:
    def _report(self, head_lines: list[str], work_lines: list[str]):
        from check_provider_boundary import allowlist_ratchet_report

        return allowlist_ratchet_report("\n".join(head_lines), "\n".join(work_lines))

    def test_identical_sets_are_clean(self):
        lines = ["a.py:10:reason", "b.py:20:reason"]
        assert self._report(lines, lines).ok

    def test_line_shift_is_churn_not_growth(self):
        report = self._report(["a.py:10:reason"], ["a.py:47:reason"])
        assert report.ok, report.grown

    def test_new_entry_in_any_file_is_growth(self):
        report = self._report(["a.py:10:reason"], ["a.py:10:reason", "b.py:3:reason"])
        assert not report.ok
        assert "b.py" in report.grown

    def test_removal_passes(self):
        report = self._report(["a.py:10:reason", "b.py:20:reason"], ["a.py:10:reason"])
        assert report.ok, report.grown

    def _git_repo(self, tmp_path: Path, allowlist_text: str) -> Path:
        """A real git repo with a committed allowlist and two planted
        import sites at the anchored lines (the plain check must stay clean
        so the ratchet outcome is the ONLY exit driver)."""
        import subprocess as sp

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "allowlist.txt").write_text(allowlist_text)
        # The planted sites land the import on the anchored line exactly
        # (10 comment lines before it for a.py; 2 for b.py).
        _write(
            repo,
            "hub/data_movement/a.py",
            "\n".join(["# pad"] * 9)
            + "\nfrom hub.apps.databricks_admin.models import UCTable\n",
        )
        _write(
            repo,
            "hub/data_movement/b.py",
            "# pad\n# pad\nfrom hub.apps.databricks_admin.models import UCTable\n",
        )
        sp.run(["git", "-C", str(repo), "init", "-q"], check=True)
        sp.run(["git", "-C", str(repo), "config", "user.email", "g@t"], check=True)
        sp.run(["git", "-C", str(repo), "config", "user.name", "g"], check=True)
        sp.run(["git", "-C", str(repo), "add", "."], check=True)
        sp.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
        return repo

    def _run_ratchet(self, repo: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(repo),
                "--allowlist",
                str(repo / "allowlist.txt"),
                "--check-allowlist-growth",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_cli_growth_fails_against_git_head(self, tmp_path):
        """Real git repository: the committed baseline is one entry; adding
        a second entry to the working allowlist fails the ratchet."""
        repo = self._git_repo(
            tmp_path,
            "hub/data_movement/a.py:10:reason\n",
        )
        (repo / "allowlist.txt").write_text(
            "hub/data_movement/a.py:10:reason\nhub/data_movement/b.py:3:reason\n"
        )
        proc = self._run_ratchet(repo)
        assert proc.returncode == 1, proc.stdout
        assert "GROWTH" in proc.stdout
        assert "hub/data_movement/b.py" in proc.stdout

    def test_cli_shrink_passes_against_git_head(self, tmp_path):
        repo = self._git_repo(
            tmp_path,
            "hub/data_movement/a.py:10:reason\nhub/data_movement/b.py:3:reason\n",
        )
        # A true shrink: the b.py site AND its anchor both disappear.
        (repo / "hub/data_movement/b.py").unlink()
        (repo / "allowlist.txt").write_text("hub/data_movement/a.py:10:reason\n")
        proc = self._run_ratchet(repo)
        assert proc.returncode == 0, proc.stdout

    def test_cli_churn_passes_against_git_head(self, tmp_path):
        """A line shift re-anchored in the SAME file (count unchanged) is
        churn, not growth — the GATE-29 net-accounting contract."""
        repo = self._git_repo(
            tmp_path,
            "hub/data_movement/a.py:10:reason\n",
        )
        (repo / "allowlist.txt").write_text("hub/data_movement/a.py:11:reason\n")
        proc = self._run_ratchet(repo)
        # The :11 anchor is dead (the import sits on line 10) — the dead-
        # anchor check fires; the RATCHET itself must not report growth.
        assert "GROWTH" not in proc.stdout
