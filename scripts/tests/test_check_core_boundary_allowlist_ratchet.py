"""GATE-29 allowlist ratchet — NET accounting (Phase 313-H task 1.2).

The allowlist (`scripts/core_boundary_allowlist.txt`) keys entries as
``relpath:lineno:reason``. Because ``lineno`` is part of the key, ANY edit
that shifts lines in an allowlisted file rewrites its keys — a pure
mechanical churn that the original ratchet ("fail if the working set has
any key not in HEAD") reported as *growth*. Phase 0.1 hit exactly that:
12 keys churned on a commit that added no boundary violations at all.

What the ratchet must distinguish
---------------------------------
* **churn** — an allowlisted site moved to a different line (or several
  moved inside one file). The file still has the same number of audited
  violations. MUST PASS.
* **growth** — a NEW audited violation appeared. MUST FAIL, that is the
  whole point of the ratchet.
* **shrink** — entries removed. MUST PASS; the ratchet only tightens.

Why per-file counting rather than global ``len(added) > len(removed)``
----------------------------------------------------------------------
Global additions-minus-removals (the accounting the guard-growth check
uses today) nets a *brand-new violation in file B* against an *unrelated
removal in file A* and passes. That is a laundering hole: delete one
audited line anywhere, introduce one new boundary violation anywhere.
``test_cross_file_swap_is_growth`` pins that hole shut — it is the test
that fails under global accounting and passes under per-file accounting.

No mocks: real ``git`` repositories under ``tmp_path``, the real CLI
entry point invoked as a subprocess, the real allowlist parser.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_core_boundary import (
    allowlist_ratchet_report,
    parse_allowlist_entries,
)

SCRIPT = Path(__file__).resolve().parent.parent / "check_core_boundary.py"

MANIFEST_SRC = """
_PAID_MODULES = frozenset(
    {
        "hub.apps.semantic",
        "hub.apps.marketplace",
    }
)
ALL_HUB_APPS = (
    "hub.apps.core",
    "hub.apps.tenants",
)
"""

REASON = "Phase 313.2 long-tail inversion (lazy import → hook/registry/event-bus)"


# ---------------------------------------------------------------------------
# Unit layer — the pure report, no git, no filesystem
# ---------------------------------------------------------------------------
def _report(head_lines, work_lines):
    return allowlist_ratchet_report("\n".join(head_lines), "\n".join(work_lines))


class TestRatchetReport:
    def test_identical_sets_are_clean(self):
        lines = [f"a.py:10:{REASON}", f"b.py:20:{REASON}"]
        assert _report(lines, lines).ok

    def test_line_shift_in_one_file_is_churn_not_growth(self):
        """THE regression from Phase 0.1: same file, same count, new line."""
        report = _report([f"a.py:10:{REASON}"], [f"a.py:47:{REASON}"])
        assert report.ok, report.grown
        assert report.grown == {}

    def test_many_line_shifts_in_one_file_are_churn(self):
        """Real shape: `tests/e2e/test_user_journeys_comprehensive.py` holds 18."""
        head = [f"big.py:{n}:{REASON}" for n in range(10, 28)]
        work = [f"big.py:{n + 5}:{REASON}" for n in range(10, 28)]
        report = _report(head, work)
        assert report.ok
        assert report.moved == ["big.py"]

    def test_extra_entry_in_existing_file_is_growth(self):
        report = _report([f"a.py:10:{REASON}"], [f"a.py:10:{REASON}", f"a.py:99:{REASON}"])
        assert not report.ok
        assert report.grown == {"a.py": 1}

    def test_entry_in_brand_new_file_is_growth(self):
        report = _report([f"a.py:10:{REASON}"], [f"a.py:10:{REASON}", f"new.py:1:{REASON}"])
        assert not report.ok
        assert report.grown == {"new.py": 1}

    def test_removal_only_is_clean(self):
        report = _report([f"a.py:10:{REASON}", f"b.py:20:{REASON}"], [f"a.py:10:{REASON}"])
        assert report.ok
        assert report.shrunk == {"b.py": 1}

    def test_cross_file_swap_is_growth(self):
        """The laundering hole global additions-minus-removals leaves open.

        One removal in `a.py`, one BRAND-NEW violation in `b.py`. Global
        accounting sees 1 added / 1 removed and passes. Per-file accounting
        sees `b.py` gain a violation and fails — which is correct: nothing
        about deleting an audited entry in `a.py` justifies a new one in
        `b.py`.
        """
        report = _report([f"a.py:10:{REASON}"], [f"b.py:10:{REASON}"])
        assert not report.ok, "a new violation in b.py must not be offset by a removal in a.py"
        assert report.grown == {"b.py": 1}
        assert report.shrunk == {"a.py": 1}

    def test_churn_and_growth_together_reports_only_growth(self):
        head = [f"a.py:10:{REASON}", f"b.py:20:{REASON}"]
        work = [f"a.py:33:{REASON}", f"b.py:20:{REASON}", f"b.py:88:{REASON}"]
        report = _report(head, work)
        assert not report.ok
        assert report.grown == {"b.py": 1}
        assert "a.py" in report.moved

    def test_shrink_in_one_file_does_not_offset_growth_in_the_same_file(self):
        """Net-zero WITHIN a file is still churn only if the count matches."""
        head = [f"a.py:10:{REASON}", f"a.py:20:{REASON}"]
        work = [f"a.py:10:{REASON}", f"a.py:20:{REASON}", f"a.py:30:{REASON}"]
        assert _report(head, work).grown == {"a.py": 1}

    def test_reason_text_is_not_part_of_identity(self):
        """417 entries use `→` and 48 use `->` for the same reason — reason
        text cannot be an identity component without inventing churn."""
        head = ["a.py:10:Phase 313.2 long-tail inversion (lazy import -> hook)"]
        work = ["a.py:10:Phase 313.2 long-tail inversion (lazy import → hook)"]
        assert _report(head, work).ok


class TestAllowlistParsing:
    def test_comments_and_blanks_are_ignored(self):
        entries = parse_allowlist_entries("# header\n\n  \na.py:1:why\n# trailing\n")
        assert [(e.relpath, e.lineno) for e in entries] == [("a.py", 1)]

    def test_reason_may_contain_colons(self):
        (entry,) = parse_allowlist_entries("a.py:7:Phase 313.2: lazy import -> hook")
        assert entry.relpath == "a.py"
        assert entry.lineno == 7
        assert entry.reason == "Phase 313.2: lazy import -> hook"

    def test_windows_style_path_is_kept_verbatim(self):
        (entry,) = parse_allowlist_entries("hub/apps/core/x.py:12:why")
        assert entry.relpath == "hub/apps/core/x.py"

    def test_malformed_line_is_rejected_loudly(self):
        """A silently-dropped malformed entry would weaken the ratchet."""
        with pytest.raises(ValueError, match="malformed"):
            parse_allowlist_entries("this-has-no-line-number\n")

    def test_non_integer_lineno_is_rejected_loudly(self):
        with pytest.raises(ValueError, match="malformed"):
            parse_allowlist_entries("a.py:notanumber:why\n")

    def test_duplicate_entries_are_counted_once(self):
        """The file is a set of audited sites; a dup must not inflate counts."""
        entries = parse_allowlist_entries(f"a.py:10:{REASON}\na.py:10:{REASON}\n")
        assert len(entries) == 1


# ---------------------------------------------------------------------------
# Integration layer — real git repo, real CLI, real scanner
# ---------------------------------------------------------------------------
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


def _make_repo(tmp_path: Path, core_source: str, allowlist_lines: list[str]) -> Path:
    """A real git repo: manifest + one core module + a committed allowlist."""
    (tmp_path / "hub" / "apps" / "core").mkdir(parents=True)
    (tmp_path / "hub" / "apps" / "manifest.py").write_text(MANIFEST_SRC)
    (tmp_path / "hub" / "apps" / "core" / "__init__.py").write_text("")
    (tmp_path / "hub" / "apps" / "core" / "mod.py").write_text(core_source)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "allowlist.txt").write_text("\n".join(allowlist_lines) + "\n")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _run_ratchet(root: Path) -> subprocess.CompletedProcess:
    """Invoke the real CLI from an unrelated cwd.

    Running from elsewhere is deliberate: the checker must resolve `git show
    HEAD:` against `--root`, not against the caller's working directory.
    """
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--allowlist",
            str(root / "scripts" / "allowlist.txt"),
            "--check-allowlist-growth",
        ],
        cwd=SCRIPT.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def _set_allowlist(root: Path, lines: list[str]) -> None:
    (root / "scripts" / "allowlist.txt").write_text("\n".join(lines) + "\n")


class TestRatchetCli:
    def test_line_shift_churn_passes(self, tmp_path):
        """A blank line pushes the import down; the allowlist is regenerated."""
        root = _make_repo(
            tmp_path,
            "from hub.apps.semantic.models import Thing\n",
            [f"hub/apps/core/mod.py:1:{REASON}"],
        )
        # The import moves 1 -> 3, and the allowlist follows it.
        (root / "hub" / "apps" / "core" / "mod.py").write_text(
            "\n\nfrom hub.apps.semantic.models import Thing\n"
        )
        _set_allowlist(root, [f"hub/apps/core/mod.py:3:{REASON}"])
        result = _run_ratchet(root)
        assert result.returncode == 0, f"churn must not fail:\n{result.stdout}{result.stderr}"

    def test_genuine_growth_fails(self, tmp_path):
        root = _make_repo(
            tmp_path,
            "from hub.apps.semantic.models import Thing\n",
            [f"hub/apps/core/mod.py:1:{REASON}"],
        )
        # A SECOND paid import appears, and is allowlisted.
        (root / "hub" / "apps" / "core" / "mod.py").write_text(
            "from hub.apps.semantic.models import Thing\n"
            "from hub.apps.marketplace.models import Listing\n"
        )
        _set_allowlist(
            root,
            [f"hub/apps/core/mod.py:1:{REASON}", f"hub/apps/core/mod.py:2:{REASON}"],
        )
        result = _run_ratchet(root)
        assert result.returncode == 1
        assert "ratchet" in result.stdout.lower()

    def test_removal_passes(self, tmp_path):
        root = _make_repo(
            tmp_path,
            "from hub.apps.semantic.models import Thing\n",
            [f"hub/apps/core/mod.py:1:{REASON}", f"hub/apps/core/gone.py:9:{REASON}"],
        )
        _set_allowlist(root, [f"hub/apps/core/mod.py:1:{REASON}"])
        result = _run_ratchet(root)
        assert result.returncode == 0, result.stdout

    def test_git_lookup_is_rooted_at_root_not_cwd(self, tmp_path):
        """`git show HEAD:<allowlist>` must read the repo under --root.

        Resolved against the caller's cwd it silently reads THIS repo's
        allowlist (or nothing), and the ratchet compares against the wrong
        baseline — passing or failing for reasons unrelated to the tree
        under test.
        """
        root = _make_repo(
            tmp_path,
            "from hub.apps.semantic.models import Thing\n",
            [f"hub/apps/core/mod.py:1:{REASON}"],
        )
        (root / "hub" / "apps" / "core" / "mod.py").write_text(
            "from hub.apps.semantic.models import Thing\n"
            "from hub.apps.marketplace.models import Listing\n"
        )
        _set_allowlist(
            root,
            [f"hub/apps/core/mod.py:1:{REASON}", f"hub/apps/core/mod.py:2:{REASON}"],
        )
        result = _run_ratchet(root)
        # Growth in the TARGET repo must be detected even though cwd is elsewhere.
        assert result.returncode == 1, (
            "growth went undetected — the HEAD lookup did not use --root:\n"
            f"{result.stdout}{result.stderr}"
        )
        assert "hub/apps/core/mod.py" in result.stdout
