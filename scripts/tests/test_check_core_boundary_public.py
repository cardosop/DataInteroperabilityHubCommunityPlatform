"""W7.1 (oss-release-remediation R2-M1) — GATE-29 PUBLIC-mode pins.

In the public tree the paid apps are physically ABSENT, so every
allowlisted NON-TEST paid reference in a public-shipping core file
must be GUARDED (try-covered / branch-guarded / annotated) or the
import crashes at module load.  ``check_core_boundary.py --public``
enforces the plain gate PLUS the guard gate (the DECIDED blocking
option with the synced allowlist):

  * an UNGUARDED allowlisted non-test import is a violation even
    though private mode would pass it (the public tree would crash);
  * a GUARDED import passes only when allowlisted (the allowlist is
    the audited-transition record in both trees);
  * TEST modules are exempt from the guard half — the shipped root
    conftest's collection gate ignores unguarded paid-importing test
    modules in core mode (the sanctioned protection);
  * non-shipping files (publish-excluded) are out of scope — the
    public tree does not contain them.

No mocks: the pins build REAL temp trees (minimal manifest + core
sources) and run the REAL checker's main() via subprocess, then also
assert the classification helper directly.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
CHECKER = SCRIPTS / "check_core_boundary.py"
sys.path.insert(0, str(SCRIPTS))


MANIFEST = """
_PAID_MODULES = ["hub.apps.semantic", "hub.apps.marketplace", "hub.apps.billing"]
"""


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "hub" / "apps").mkdir(parents=True)
    (tmp_path / "hub" / "apps" / "manifest.py").write_text(MANIFEST)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "publish_paths_exclude.txt").write_text(
        "hub/apps/semantic/\nhub/apps/marketplace/\nhub/apps/billing/\n"
        "private_tooling/\n"
    )
    return tmp_path


def _core_file(tmp_path: Path, rel: str, source: str) -> None:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source).strip() + "\n")


def _allowlist(tmp_path: Path, entries: list[str]) -> Path:
    allow = tmp_path / "scripts" / "core_boundary_allowlist.txt"
    allow.write_text("\n".join(entries) + "\n")
    return allow


def _run_public(tmp_path: Path, allowlist: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(CHECKER), "--root", str(tmp_path), "--public"]
    if allowlist is not None:
        cmd += ["--allowlist", str(allowlist)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


UNGUARDED = """
from hub.apps.semantic.models import Thing

def use_it():
    return Thing
"""

GUARDED_TRY = """
def get_thing():
    try:
        from hub.apps.semantic.models import Thing
    except (RuntimeError, ModuleNotFoundError):
        Thing = None
    return Thing
"""

GUARDED_BRANCH = """
from django.conf import settings

if not settings.HUB_CORE_ONLY:
    from hub.apps.semantic.models import Thing
else:
    Thing = None
"""


class TestPublicModeBlocking:
    def test_flag_exists_and_fails_on_unguarded_allowlisted_site(self, tmp_path):
        """Private mode would pass an allowlisted site; public mode must
        fail it when unguarded — the public tree would crash on import."""
        root = _tree(tmp_path)
        _core_file(root, "hub/apps/assets/views.py", UNGUARDED)
        allow = _allowlist(root, ["hub/apps/assets/views.py:1:audited"])
        result = _run_public(root, allow)
        assert result.returncode != 0, result.stdout
        assert "unguarded" in result.stdout.lower()

    def test_guarded_try_site_passes_when_allowlisted(self, tmp_path):
        root = _tree(tmp_path)
        _core_file(root, "hub/apps/assets/views.py", GUARDED_TRY)
        allow = _allowlist(root, ["hub/apps/assets/views.py:3:audited W7.1"])
        result = _run_public(root, allow)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_guarded_branch_site_passes_when_allowlisted(self, tmp_path):
        root = _tree(tmp_path)
        _core_file(root, "hub/apps/assets/views.py", GUARDED_BRANCH)
        allow = _allowlist(root, ["hub/apps/assets/views.py:4:audited W7.1"])
        result = _run_public(root, allow)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_guarded_but_not_allowlisted_is_still_a_violation(self, tmp_path):
        """The allowlist travels to the public tree — a guarded site must
        be audited in BOTH trees (the synced-allowlist decision)."""
        root = _tree(tmp_path)
        _core_file(root, "hub/apps/assets/views.py", GUARDED_TRY)
        result = _run_public(root)
        assert result.returncode != 0, result.stdout
        assert "boundary violation" in result.stdout

    def test_publish_excluded_files_are_out_of_scope(self, tmp_path):
        """Private-only tooling never ships; its imports (guarded or not)
        are not governed by the public gate."""
        root = _tree(tmp_path)
        _core_file(
            root,
            "private_tooling/paid_scratch.py",
            UNGUARDED,
        )
        # A guarded core site keeps the tree otherwise clean.
        _core_file(root, "hub/apps/assets/views.py", GUARDED_TRY)
        allow = _allowlist(root, ["hub/apps/assets/views.py:3:audited"])
        result = _run_public(root, allow)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_allowlist_entries_for_absent_files_do_not_break_public_mode(self, tmp_path):
        """The synced allowlist still carries entries for paid-only files
        (they ship in the private tree); public mode ignores them."""
        root = _tree(tmp_path)
        _core_file(root, "hub/apps/assets/views.py", GUARDED_TRY)
        allow = _allowlist(
            root,
            [
                "hub/apps/assets/views.py:3:audited W7.1",
                "hub/apps/semantic/views.py:10:paid file — absent in public tree",
            ],
        )
        result = _run_public(root, allow)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_test_modules_are_exempt_in_public_mode(self, tmp_path):
        """Test modules stay exempt from the guard half of the public
        gate — the shipped root conftest's collection gate ignores
        paid-importing test modules in core mode (the sanctioned
        protection, same as the private core CI)."""
        root = _tree(tmp_path)
        _core_file(root, "hub/apps/assets/tests/test_thing.py", UNGUARDED)
        allow = _allowlist(root, ["hub/apps/assets/tests/test_thing.py:1:audited"])
        result = _run_public(root, allow)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_test_modules_are_exempt_in_plain_mode(self, tmp_path):
        """P2-3 root cause: the PLAIN gate flagged test modules while the
        guard half (and the root conftest's collection gate) exempt them
        by design — and the allowlist ratchet blocks allowlisting NEW
        test files, making every new paid-importing test module
        unfixable. The plain gate must apply the same exemption: the
        conftest collection gate is the sanctioned protection."""
        root = _tree(tmp_path)
        _core_file(root, "hub/apps/assets/tests/test_thing.py", UNGUARDED)
        plain = [sys.executable, str(CHECKER), "--root", str(tmp_path)]
        result = subprocess.run(plain, capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        # conftest.py stays in scope — a paid import there crashes
        # collection for every module under it.
        _core_file(root, "hub/apps/assets/tests/conftest.py", UNGUARDED)
        result = subprocess.run(plain, capture_output=True, text=True, check=False)
        assert result.returncode != 0

    def test_unguarded_non_test_site_fails_even_when_allowlisted(self, tmp_path):
        """The blocking invariant: an allowlisted NON-test site that is
        not guarded crashes the public tree at module load — the gate
        must fail it (private mode would pass it)."""
        root = _tree(tmp_path)
        _core_file(root, "hub/apps/assets/views.py", UNGUARDED)
        allow = _allowlist(root, ["hub/apps/assets/views.py:1:audited"])
        result = _run_public(root, allow)
        assert result.returncode != 0, result.stdout
        assert "unguarded" in result.stdout.lower()


class TestPublicClassificationHelper:
    """The public gate reuses the existing classifier — pin the exact
    classification contract it leans on."""

    def test_try_pair_classifies_covering(self):
        import ast

        from check_core_boundary import classify_import_guard

        tree = ast.parse(GUARDED_TRY)
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom))
        assert classify_import_guard(tree, node, GUARDED_TRY.splitlines()) == "try-covered-BROKEN"
