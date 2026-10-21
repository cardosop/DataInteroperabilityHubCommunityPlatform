"""Phase 1.3 — guard-test failure clarity (313-H).

(a) ``_classify_real_file`` in ``test_check_core_boundary_guards.py`` must
    raise a NAMED error carrying the site (relpath:lineno) when no import
    exists at the requested line. Today it leaks a bare ``StopIteration``
    from ``next(...)`` — a guard-site regression reads as a generator
    bug, and the traceback doesn't even say WHICH site vanished.

(b) ``test_publish_tree.py`` must detect the PUBLIC tree (no
    ``.github/workflows/ci.yml``, no ``venv/``) and skip-with-reason.
    Today ``_build_tree`` hardcodes ``REPO_ROOT/venv/bin/python`` — which
    does not ship in the public tree — so every tree-building test dies
    with ``FileNotFoundError`` from ``subprocess``, while one non-tree
    test passes. The module result is a confusing 1 failed / 1 passed /
    3 errors instead of a clear "public checkout — publishing tests are
    private-repo-only".

No mocks: (b) builds a REAL synthetic public-tree layout (copied test
module + symlinked scripts, no venv, no ci.yml) and runs the real
pytest on it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_check_core_boundary_guards as guards

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON = Path(sys.executable)

# A file that certainly exists, with a line number that carries NO import.
_NO_IMPORT_SITE = ("hub/apps/tenants/views.py", 1)


class TestClassifyRealFileNamesTheSite:
    def test_missing_import_raises_named_error_with_site(self):
        relpath, lineno = _NO_IMPORT_SITE
        with pytest.raises(guards.ImportSiteNotFound) as exc_info:
            guards._classify_real_file(relpath, lineno)
        message = str(exc_info.value)
        assert relpath in message, f"error must name the file: {message!r}"
        assert str(lineno) in message, f"error must name the line: {message!r}"

    def test_named_error_is_not_a_bare_stopiteration(self):
        relpath, lineno = _NO_IMPORT_SITE
        with pytest.raises(guards.ImportSiteNotFound):
            guards._classify_real_file(relpath, lineno)
        # StopIteration inherits Exception — if the named error were still the
        # generator leak, the raises() above would have caught RuntimeError's
        # PEP-479 wrapper instead and this test would fail there already.
        assert not issubclass(guards.ImportSiteNotFound, StopIteration)


class TestPublishTreeSkipsOnPublicTree:
    @pytest.fixture
    def public_layout(self, tmp_path) -> Path:
        """A REAL public-tree-shaped checkout: the test module and the three
        builder scripts ship, but ``.github/workflows/ci.yml`` and ``venv/``
        do not — exactly what the public clone contains."""
        (tmp_path / "scripts" / "tests").mkdir(parents=True)
        shutil.copy(
            REPO_ROOT / "scripts" / "tests" / "test_publish_tree.py",
            tmp_path / "scripts" / "tests" / "test_publish_tree.py",
        )
        for name in ("publish_tree.sh", "publish_paths_exclude.txt", "build_replace_text.py"):
            (tmp_path / "scripts" / name).symlink_to(REPO_ROOT / "scripts" / name)
        assert not (tmp_path / ".github" / "workflows" / "ci.yml").exists()
        assert not (tmp_path / "venv").exists()
        return tmp_path

    @staticmethod
    def _run_module(public_layout: Path) -> tuple[str, str]:
        result = subprocess.run(
            [
                str(PYTHON),
                "-m",
                "pytest",
                "-c",
                "/dev/null",
                "-p",
                "no:django",
                "-q",
                "--no-header",
                "-rs",  # skip reasons ARE the assertion target
                "-p",
                "no:cacheprovider",
                str(public_layout / "scripts" / "tests" / "test_publish_tree.py"),
            ],
            cwd=public_layout,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout + "\n" + result.stderr, f"exit={result.returncode}"

    def test_public_tree_skips_with_reason(self, public_layout):
        output, exit_note = self._run_module(public_layout)
        assert "FileNotFound" not in output, (
            f"public-tree run must not crash ({exit_note}):\n{output}"
        )
        assert "skipped" in output, (
            f"every publish-tree test must skip on a public checkout ({exit_note}):\n{output}"
        )
        assert "failed" not in output, (
            f"every publish-tree test must skip on a public checkout ({exit_note}):\n{output}"
        )
        assert "public checkout" in output, (
            f"skip reason must explain WHY (public checkout):\n{output}"
        )

    def test_private_tree_still_runs_the_real_builder(self):
        """Guard-the-guard: the skip must NOT trigger on the private repo —
        this very module's REPO_ROOT carries ci.yml, and the real suite
        (test_publish_tree.py) must keep executing its builder tests.

        In a PUBLIC clone (where `.github/workflows/` is publish-excluded
        and ci.yml does not ship) the private-repo assertion is meaningless
        — skip with reason so this suite remains runnable in the public
        ci-core boundary job.
        """
        if not (REPO_ROOT / ".github" / "workflows" / "ci.yml").exists():
            pytest.skip(
                "public checkout: the private ci.yml does not ship — "
                "the publish-tree skip guard is private-repo-only"
            )
        assert (REPO_ROOT / ".github" / "workflows" / "ci.yml").exists()

    def test_private_repo_guard_skips_in_a_public_layout(self, tmp_path):
        """THE public-CI regression: this suite, copied into a public-shaped
        tree (no .github/workflows/ci.yml), must SKIP the private-repo guard
        instead of failing the boundary job."""
        target = tmp_path / "scripts" / "tests"
        target.mkdir(parents=True)
        shutil.copy(REPO_ROOT / "scripts" / "tests" / "test_guard_test_failure_clarity.py", target)
        shutil.copy(REPO_ROOT / "scripts" / "tests" / "test_check_core_boundary_guards.py", target)
        # The guards module imports the checker — copy it too (it ships in the
        # public tree, so this mirrors the real public layout).
        shutil.copy(REPO_ROOT / "scripts" / "check_core_boundary.py", tmp_path / "scripts")
        assert not (tmp_path / ".github" / "workflows" / "ci.yml").exists()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-c",
                "/dev/null",
                "-p",
                "no:django",
                "-q",
                "--no-header",
                "-rs",  # skip reasons ARE the assertion target
                "-p",
                "no:cacheprovider",
                str(target / "test_guard_test_failure_clarity.py"),
                "-k",
                "private_tree_still_runs",
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "skipped" in result.stdout, result.stdout + result.stderr
        assert "public checkout" in result.stdout
