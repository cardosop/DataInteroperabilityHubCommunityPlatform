"""GATE-57 (oss-release-remediation W12.2) pins — no mocks, no stubs.

The RED phase of W12.2: every pin below ran against the REAL repository
before the triage landed and failed — the two ~200KB ``_services_legacy.py``
files sat in the tree, and the orphan finder reported "50" modules only
because ``orphans[:50]`` silently hid 75 more (the uncapped count is 125).

Pins exercise the REAL gate as a subprocess against:
  * the real repository (master GREEN pin),
  * planted-violation temp git repos (the gate BITES — a reintroduced
    legacy-class file, an untriaged orphan, a dead/reasonless/stale
    allowlist entry, or allowlist growth vs HEAD flips it RED),
  * finder-precision temp trees (relative imports and dotted-string
    wiring are NOT orphans — the root fix for the 125 false positives:
    the pre-fix finder ignored every ``from .x import`` relative import,
    which is how ``contracts/views.py``'s nine mixin imports and
    ``jobs/tasks.py``'s task imports became "orphans").
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "audit_dead_code.py"
BASELINE = REPO_ROOT / "scripts" / "dead_code_allowlist.json"

LEGACY_CLASS_NAMES = ("_services_legacy.py", "_legacy.py", "_deprecated.py")

# The two files W12.2 deletes — history preserves them, the gate pins
# their absence and a planted reintroduction flips it RED.
_DELETED_LEGACY_FILES = (
    "hub/apps/integrations/_services_legacy.py",
    "hub/apps/virtualization/_services_legacy.py",
)


def _run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _make_repo(
    tmp_path: Path,
    files: dict[str, str],
    baseline: dict[str, str] | None = None,
) -> Path:
    """A real git repo (no mocks) with ``hub/`` tree + committed baseline."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel, content in files.items():
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content)
    if baseline is not None:
        base = repo / "scripts" / "dead_code_allowlist.json"
        base.parent.mkdir(parents=True, exist_ok=True)
        base.write_text(json.dumps({"entries": baseline}, indent=2))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "pin@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "pin"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    return repo


class TestRealRepository:
    """The master GREEN pins — the real tree satisfies the whole contract."""

    def test_real_repo_has_no_legacy_class_files(self):
        for deleted in _DELETED_LEGACY_FILES:
            assert not (REPO_ROOT / deleted).exists(), (
                f"{deleted} still exists — W12.2 deletes it (git history "
                "preserves it); the gate treats the legacy class as "
                "zero-tolerance"
            )
        for pattern in LEGACY_CLASS_NAMES:
            for found in (REPO_ROOT / "hub").rglob(pattern):
                pytest.fail(
                    f"legacy-class file reintroduced: {found.relative_to(REPO_ROOT)}"
                )

    def test_real_repo_gate_passes(self):
        result = _run_gate("--check")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "dead-code gate clean" in result.stdout
        growth = _run_gate("--check-growth")
        assert growth.returncode == 0, growth.stdout + growth.stderr

    def test_real_repo_allowlist_entries_are_reasoned_and_live(self):
        payload = json.loads(BASELINE.read_text(encoding="utf-8"))
        entries = payload["entries"]
        # The W12.2 triage converged on ZERO allowlisted orphans (everything
        # was deleted or statically wired) — an empty allowlist is the ideal
        # state. When entries DO exist, every one must be reasoned and live.
        for path, reason in sorted(entries.items()):
            assert reason, f"{path}: allowlist entry reason is empty"
            assert not reason.strip().startswith("TODO"), (
                f"{path}: allowlist entry needs a reason citing its wiring "
                "site (GATE-57 contract)"
            )
            assert (
                REPO_ROOT / path
            ).is_file(), f"{path}: dead allowlist anchor — delete the entry"


class TestPlantedViolationsBite:
    """Drift pins — reintroducing any dead-code class flips the gate RED."""

    def test_planted_legacy_class_file_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/_services_legacy.py": "THING = 1\n"},
            baseline={},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        # The CLASS message, not just the filename — the falsifiability
        # harness blinds the legacy pattern and expects THIS pin to flip
        # RED (a legacy file slipping through as a mere orphan would be a
        # blinded gate).
        assert "legacy-class file" in result.stdout

    def test_planted_untriaged_orphan_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/untriaged.py": "THING = 1\n"},
            baseline={},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "untriaged.py" in result.stdout

    def test_planted_dead_allowlist_anchor_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/__init__.py": ""},
            baseline={"hub/apps/x/gone.py": "deleted without baseline update"},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "gone.py" in result.stdout

    def test_planted_reasonless_allowlist_entry_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/wired.py": "THING = 1\n"},
            baseline={"hub/apps/x/wired.py": "TODO: reason required"},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "wired.py" in result.stdout

    def test_planted_stale_allowlist_entry_bites(self, tmp_path):
        # A module that someone has since imported is no longer an orphan —
        # its allowlist entry must be removed (the shrink path).
        repo = _make_repo(
            tmp_path,
            {
                "hub/apps/x/used.py": "THING = 1\n",
                # urls.py is Django auto-discovered (never an orphan itself)
                "hub/apps/x/urls.py": "from .used import THING\n",
            },
            baseline={"hub/apps/x/used.py": "was wired by dotted string"},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "used.py" in result.stdout
        assert "no longer an orphan" in result.stdout

    def test_missing_allowlist_fails_closed(self, tmp_path):
        repo = _make_repo(tmp_path, {"hub/apps/x/__init__.py": ""})
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "allowlist" in result.stdout

    def test_allowlist_growth_bites_vs_head(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/live_a.py": "A = 1\n", "hub/apps/x/live_b.py": "B = 1\n"},
            baseline={"hub/apps/x/live_a.py": "wired by settings string"},
        )
        # Adding an entry grows the allowlist vs HEAD → RED.
        base = repo / "scripts" / "dead_code_allowlist.json"
        payload = json.loads(base.read_text(encoding="utf-8"))
        payload["entries"]["hub/apps/x/live_b.py"] = "wired by settings string"
        base.write_text(json.dumps(payload, indent=2))
        result = _run_gate("--root", str(repo), "--check-growth")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "live_b.py" in result.stdout
        # Removing an entry shrinks the allowlist vs HEAD → GREEN.
        payload["entries"] = {}
        base.write_text(json.dumps(payload, indent=2))
        result = _run_gate("--root", str(repo), "--check-growth")
        assert result.returncode == 0, result.stdout + result.stderr


class TestFinderPrecision:
    """Root-cause pins — the finder resolves relative imports and dotted
    string wiring, so live modules are never reported as orphans."""

    def _check_passes(self, tree: dict[str, str], tmp_path: Path) -> None:
        repo = tmp_path / "tree"
        repo.mkdir()
        for rel, content in tree.items():
            dst = repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content)
        base = repo / "scripts" / "dead_code_allowlist.json"
        base.parent.mkdir(parents=True, exist_ok=True)
        base.write_text(json.dumps({"entries": {}}))
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_relative_import_is_not_orphan(self, tmp_path):
        # urls.py (Django auto-discovered, never an orphan) → a.py →
        # b.py: the pre-fix finder ignored `from .b import` (level>0) and
        # reported b.py as orphaned.
        self._check_passes(
            {
                "hub/apps/pkg/urls.py": "from .a import A\n",
                "hub/apps/pkg/a.py": "from .b import B\nA = B\n",
                "hub/apps/pkg/b.py": "B = 1\n",
            },
            tmp_path,
        )

    def test_parent_relative_import_is_not_orphan(self, tmp_path):
        self._check_passes(
            {
                "hub/apps/pkg/urls.py": "from .sub.entry import E\n",
                "hub/apps/pkg/sub/entry.py": "from ..shared import S\nE = S\n",
                "hub/apps/pkg/shared.py": "S = 1\n",
            },
            tmp_path,
        )

    def test_dotted_string_wiring_is_not_orphan(self, tmp_path):
        # Middleware / URLconf modules are wired by dotted-path strings in
        # settings and `include(...)` — a real reference, not dead code.
        self._check_passes(
            {
                "hub/apps/pkg/urls.py": 'PATHS = ["hub.apps.pkg.wired.WiredThing"]\n',
                "hub/apps/pkg/wired.py": "class WiredThing:\n    pass\n",
            },
            tmp_path,
        )

    def test_package_level_import_is_not_orphan(self, tmp_path):
        # `from . import submod` (module=None, level=1).
        self._check_passes(
            {
                "hub/apps/pkg/urls.py": "from . import helper\n",
                "hub/apps/pkg/helper.py": "H = 1\n",
            },
            tmp_path,
        )

    def test_django_auto_discovered_files_are_not_orphans(self, tmp_path):
        self._check_passes(
            {
                "hub/apps/pkg/apps.py": "name = 'pkg'\n",
                "hub/apps/pkg/admin.py": "from django.contrib import admin\n",
                "hub/apps/pkg/signals.py": "SIGNAL = 1\n",
                "hub/apps/pkg/management/commands/doit.py": "def run():\n    pass\n",
            },
            tmp_path,
        )

    def test_unwired_views_stem_module_is_flagged(self, tmp_path):
        # The pre-fix finder skipped stems like `views` as "low-confidence"
        # — a blind spot that silently hid dead code. A views.py with NO
        # reference of any kind IS dead and must be flagged.
        repo = _make_repo(
            tmp_path,
            {"hub/apps/pkg/views.py": "class Unwired:\n    pass\n"},
            baseline={},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "views.py" in result.stdout

    def test_orphan_report_is_not_capped(self, tmp_path):
        # The pre-fix finder returned orphans[:50] — the "50 orphan
        # modules" in the W12.2 ticket was the cap, not the inventory.
        # The gate must report EVERY orphan.
        repo = _make_repo(
            tmp_path,
            {f"hub/apps/pkg/dead{i}.py": f"D{i} = {i}\n" for i in range(3)},
            baseline={},
        )
        result = _run_gate("--root", str(repo), "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        orphans = payload["orphaned_modules"]
        assert len(orphans) == 3, orphans
