"""Pre-commit boundary gate — task 1.6 (313-H).

The hook runs ``scripts/check_core_boundary.py`` scoped to the STAGED files
so a paid-import leak in the commit fails at ``git commit`` time instead of
CI time. Two moving parts, both tested with real git repos (no mocks):

1. ``check_core_boundary.py --paths <f1> <f2>`` — scans only the given
   files (plus ``hub/settings.py`` string literals, which cannot be scoped
   out: MIDDLEWARE/ROUTERS entries bypass the import scanner by design).
2. ``scripts/check_core_boundary_precommit.sh`` — the pre-commit entry
   point: forwards the staged filenames pre-commit passes on argv.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SCRIPT = Path(__file__).resolve().parent.parent / "check_core_boundary.py"
HOOK = Path(__file__).resolve().parent.parent / "check_core_boundary_precommit.sh"

MANIFEST_SRC = """
_PAID_MODULES = frozenset(
    {
        "hub.apps.semantic",
        "hub.apps.marketplace",
    }
)
ALL_HUB_APPS = (
    "hub.apps.core",
)
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(repo),
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "hub" / "apps" / "core").mkdir(parents=True)
    (tmp_path / "hub" / "apps" / "manifest.py").write_text(MANIFEST_SRC)
    (tmp_path / "hub" / "apps" / "core" / "__init__.py").write_text("")
    (tmp_path / "hub" / "settings.py").write_text("# placeholder settings\n")
    (tmp_path / "scripts").mkdir()
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _run(paths: list[str], root: Path) -> subprocess.CompletedProcess:
    """Run the checker exactly as the pre-commit hook would, scoped to paths."""
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--allowlist",
            str(root / "scripts" / "allowlist.txt"),
            "--paths",
            *paths,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _run_hook(root: Path, *paths: str) -> subprocess.CompletedProcess:
    """Invoke the real pre-commit entry point with the staged paths.

    ``CORE_BOUNDARY_REPO_ROOT``/``CORE_BOUNDARY_ALLOWLIST`` point the hook at
    the temp repo — the hook's own hermetic-test seams (production runs use
    the script location's repo and allowlist).
    """
    return subprocess.run(
        [
            "bash",
            str(HOOK),
            *paths,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(root),
            "CORE_BOUNDARY_REPO_ROOT": str(root),
            "CORE_BOUNDARY_ALLOWLIST": str(root / "scripts" / "allowlist.txt"),
        },
    )


class TestPathsScopedScan:
    def test_staged_leak_fails(self, tmp_path):
        """A paid import in a staged core file must fail the gate."""
        root = _make_repo(tmp_path)
        (root / "hub" / "apps" / "core" / "leak.py").write_text(
            "from hub.apps.marketplace.models import Listing\n"
        )
        _git(root, "add", "hub/apps/core/leak.py")
        result = _run(["hub/apps/core/leak.py"], root)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "leak.py" in result.stdout

    def test_unstaged_leak_in_unlisted_path_is_not_scanned(self, tmp_path):
        """Scope is the point: a leak OUTSIDE --paths must not block the commit."""
        root = _make_repo(tmp_path)
        (root / "hub" / "apps" / "core" / "leak.py").write_text(
            "from hub.apps.marketplace.models import Listing\n"
        )
        (root / "hub" / "apps" / "core" / "clean.py").write_text("x = 1\n")
        _git(root, "add", "hub/apps/core/clean.py")
        result = _run(["hub/apps/core/clean.py"], root)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_allowlisted_and_guarded_leak_passes(self, tmp_path):
        """An allowlisted entry whose import is GUARDED (the 313.H.1 contract
        every allowlisted production site must meet) does not block the commit."""
        root = _make_repo(tmp_path)
        (root / "scripts" / "allowlist.txt").write_text(
            "hub/apps/core/leak.py:2:audited transition\n"
        )
        (root / "hub" / "apps" / "core" / "leak.py").write_text(
            "try:\n"
            "    from hub.apps.marketplace.models import Listing\n"
            "except (RuntimeError, ModuleNotFoundError):\n"
            "    Listing = None  # noqa: F841\n"
        )
        _git(root, "add", "hub/apps/core/leak.py", "scripts/allowlist.txt")
        result = _run(["hub/apps/core/leak.py"], root)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_allowlisted_but_unguarded_leak_fails_guards(self, tmp_path):
        """The hook runs BOTH gates: an allowlisted-but-UNGUARDED staged site
        must fail the commit with the guard message naming the site."""
        root = _make_repo(tmp_path)
        (root / "scripts" / "allowlist.txt").write_text(
            "hub/apps/core/leak.py:1:audited transition\n"
        )
        (root / "hub" / "apps" / "core" / "leak.py").write_text(
            "from hub.apps.marketplace.models import Listing\n"
        )
        _git(root, "add", "hub/apps/core/leak.py", "scripts/allowlist.txt")
        result = _run_hook(root, "hub/apps/core/leak.py")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "GUARD-313.H" in result.stdout + result.stderr
        assert "leak.py" in result.stdout + result.stderr

    def test_clean_staged_file_passes(self, tmp_path):
        root = _make_repo(tmp_path)
        (root / "hub" / "apps" / "core" / "clean.py").write_text("x = 1\n")
        _git(root, "add", "hub/apps/core/clean.py")
        result = _run(["hub/apps/core/clean.py"], root)
        assert result.returncode == 0, result.stdout + result.stderr


class TestPreCommitEntryPoint:
    def test_hook_forwards_staged_paths_to_the_checker(self, tmp_path):
        """The hook must invoke the checker with the paths pre-commit passes."""
        root = _make_repo(tmp_path)
        (root / "hub" / "apps" / "core" / "leak.py").write_text(
            "from hub.apps.marketplace.models import Listing\n"
        )
        _git(root, "add", "hub/apps/core/leak.py")
        result = _run_hook(root, "hub/apps/core/leak.py")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "leak.py" in result.stdout

    def test_hook_passes_on_clean_staged_paths(self, tmp_path):
        root = _make_repo(tmp_path)
        (root / "hub" / "apps" / "core" / "clean.py").write_text("x = 1\n")
        _git(root, "add", "hub/apps/core/clean.py")
        result = _run_hook(root, "hub/apps/core/clean.py")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_hook_runs_in_seconds_on_a_single_file(self, tmp_path):
        """The gate is on the commit hot path — scope keeps it fast."""
        import time

        root = _make_repo(tmp_path)
        (root / "hub" / "apps" / "core" / "clean.py").write_text("x = 1\n")
        start = time.monotonic()
        result = _run_hook(root, "hub/apps/core/clean.py")
        elapsed = time.monotonic() - start
        assert result.returncode == 0
        assert elapsed < 5, f"hook took {elapsed:.1f}s — the gate must be commit-fast"
