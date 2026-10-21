"""Contract tests for the P2-5 public-history REPLACEMENT + re-sync machinery
(close-oss-release-conditions, G3/G13):

- ``scripts/publish_sync.sh`` — the sync mechanics extracted from
  ``publish_public.sh`` (``sync_to_public STAGING TAG PRIVATE_SHA``):
  the bootstrap case (remote has no mirror ref) MUST commit the first
  sync commit as a ROOT lineage — a stale local ``mirror/public-core``
  forks the replaced (tainted) lineage and appending onto it would
  re-publish that history (G3: append-only publishes can never remove
  it). The sync commit MUST contain EXACTLY the built tree — checkout
  litter swept in by ``git add -A`` was the P-1 drift root cause. The
  remote ``main`` MUST land on the same commit (the default branch was
  never synced). Divergence and dirty-checkout states refuse fail-closed.
- ``scripts/replace_public_repo.py`` — the one-shot executor:
  ``--plan`` enumerates the live repo state + the taint classification
  of every ref (which refs fork the tainted lineage) from the backup
  mirror; ``--execute`` (``--yes`` required) verifies the backup guard
  (fsck clean + every live ref covered at the same SHA), delete-and-
  recreates the repo, restores the metadata, and re-arms secret-scanning
  push protection BEFORE any sync (the G12 ordering; the P0-9 publish
  pre-flight refuses an unprotected remote).
- ``scripts/check_public_resync_diff.py`` — the G13 acceptance checker:
  every file in the OLD public tree must be present in the NEW built
  tree or classified in the drift allowlist (path + reason); every
  overlay file must be present in the new tree (public-only files are
  never silently dropped).

Fixtures are REAL: git repos with a tainted commit + forking branches,
local bare remotes for the push legs, real tree fixtures for the diff
checker, and the real gh CLI for the live legs (W16-gated) — no mocks.
The sync mechanics run through the REAL sourced script in a subprocess;
``PUBLISH_SYNC_SKIP_VERIFY=1`` skips only the gitleaks/GATE-29/compose
post-commit re-scan inside the fixture checkout — those gates are
pinned independently in ``test_publish_gates.py`` (the pre-flight runs
them on the real tree at every real publish).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

ROOT = scripts_dir.parent
sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from types import ModuleType

from envpolicy import skip_or_fail

SYNC_SH = scripts_dir / "publish_sync.sh"
REPLACE = scripts_dir / "replace_public_repo.py"
RESYNC_DIFF = scripts_dir / "check_public_resync_diff.py"

PUBLIC_SLUG = "cardosop/DataInteroperabilityHubCommunityPlatform"


def _git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=check
    )


def _make_tainted_backup(tmp_path: Path) -> Path:
    """A bare repo mirroring the public 'before' shape: a TAINTED root
    commit (a committed .env.test with a fake credential value), later
    commits, a branch forking the taint, and a tag."""
    work = tmp_path / "origin-work"
    work.mkdir()
    _git("init", "-q", "-b", "main", cwd=work)
    _git("config", "user.email", "p25@example.com", cwd=work)
    _git("config", "user.name", "p25", cwd=work)
    (work / ".env.test").write_text("AWS_SECRET_ACCESS_KEY=fake-tainted-value\n")
    _git("add", ".", cwd=work)
    _git("commit", "-q", "-m", "tainted: committed env with credentials", cwd=work)
    _git("checkout", "-q", "-b", "community/core-fix", cwd=work)
    (work / "fix.txt").write_text("fix\n")
    _git("add", ".", cwd=work)
    _git("commit", "-q", "-m", "community fix", cwd=work)
    _git("checkout", "-q", "main", cwd=work)
    (work / "normal.txt").write_text("normal\n")
    _git("add", ".", cwd=work)
    _git("commit", "-q", "-m", "normal work", cwd=work)
    _git("tag", "v2026.08.14", cwd=work)
    # the public repo's mirror branch (forks the taint, like the live one)
    _git("branch", "mirror/public-core", cwd=work)
    # a genuinely CLEAN ref: an orphan branch with no taint ancestor
    _git("checkout", "-q", "--orphan", "clean-branch", cwd=work)
    (work / "clean.txt").write_text("clean\n")
    _git("add", ".", cwd=work)
    _git("commit", "-q", "-m", "clean lineage", cwd=work)
    _git("checkout", "-q", "main", cwd=work)
    backup = tmp_path / "backup.git"
    _git("clone", "-q", "--mirror", str(work), str(backup), cwd=tmp_path)
    # the tainted SHA is what the caller classifies against
    return backup


def _tainted_sha(backup: Path) -> str:
    return _git("rev-list", "--max-parents=0", "HEAD", cwd=backup).stdout.strip()


def _run_sync(
    checkout: Path,
    staging: Path,
    remote: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PUBLIC_REMOTE": remote,
        "PUBLISH_SYNC_SKIP_VERIFY": "1",
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [
            "bash",
            "-c",
            f'source "{SYNC_SH}" && sync_to_public "{staging}" "v2026.10.20" "feedbeef"',
        ],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _make_staging_tree(tmp_path: Path, files: dict[str, str], name: str = "staging") -> Path:
    staging = tmp_path / name
    for rel, content in files.items():
        target = staging / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return staging


# ---------------------------------------------------------------------------
# publish_sync.sh — the sync mechanics (G3 root fixes)
# ---------------------------------------------------------------------------


class TestSyncBootstrapRootLineage:
    """The class this task exists for: the FIRST sync onto a replaced
    (empty) remote must commit a ROOT lineage — never fork the stale
    local mirror branch, which carries the tainted history."""

    def _make_checkout(self, tmp_path: Path, tainted_backup: Path) -> tuple[Path, Path]:
        checkout = tmp_path / "public-checkout"
        _git("clone", "-q", str(tainted_backup), str(checkout), cwd=tmp_path)
        # the stale local branch forks the TAINTED lineage (the pre-replacement
        # state of the real public checkout)
        _git("branch", "mirror/public-core", cwd=checkout)
        _git("checkout", "-q", "mirror/public-core", cwd=checkout)
        (checkout / "litter.txt").write_text("untracked checkout litter\n")
        remote = tmp_path / "public-remote.git"  # the REPLACED repo: empty
        _git("init", "-q", "--bare", str(remote), cwd=tmp_path)
        _git("remote", "add", "public", str(remote), cwd=checkout)
        return checkout, remote

    def test_bootstrap_commits_a_root_never_forking_the_taint(self, tmp_path):
        backup = _make_tainted_backup(tmp_path)
        tainted = _tainted_sha(backup)
        checkout, remote = self._make_checkout(tmp_path, backup)
        staging = _make_staging_tree(tmp_path, {"README.md": "fresh\n", "src/app.py": "x\n"})
        result = _run_sync(checkout, staging, "public")
        assert result.returncode == 0, result.stderr
        head = _git("rev-parse", "refs/heads/mirror/public-core", cwd=remote).stdout.strip()
        parents = _git("rev-list", "--parents", "-n", "1", head, cwd=remote).stdout.split()
        assert len(parents) == 1, f"the first sync commit must be a ROOT commit, got parents {parents[1:]}"
        # the tainted commit is NOT reachable from the new lineage
        taint_check = _git(
            "merge-base", "--is-ancestor", tainted, head, cwd=remote, check=False
        )
        assert taint_check.returncode != 0, "the tainted commit must not enter the new lineage"
        # the stale local branch is REPLACED by the new orphan lineage
        assert _git("rev-parse", "mirror/public-core", cwd=checkout).stdout.strip() == head
        # main lands on the SAME commit (the default branch sync)
        assert _git("rev-parse", "refs/heads/main", cwd=remote).stdout.strip() == head
        # the movable date tag lands on it too
        assert _git("rev-parse", "refs/tags/v2026.10.20^{}", cwd=remote).stdout.strip() == head

    def test_sync_commit_contains_exactly_the_built_tree(self, tmp_path):
        backup = _make_tainted_backup(tmp_path)
        checkout, remote = self._make_checkout(tmp_path, backup)
        # a TRACKED file from the old lineage + untracked litter must both vanish
        _git("checkout", "-q", "main", cwd=checkout)
        (checkout / "stale-tracked.txt").write_text("stale\n")
        _git("add", "stale-tracked.txt", cwd=checkout)
        _git("commit", "-q", "-m", "stale", cwd=checkout)
        _git("checkout", "-q", "mirror/public-core", cwd=checkout)
        staging = _make_staging_tree(
            tmp_path,
            {
                "README.md": "fresh\n",
                "src/app.py": "print(1)\n",
                ".env.example": "EXAMPLE=1\n",
                # a glob-magic path: the exact-tree staging must ship it
                # LITERALLY (the P2-5 NUL-pathspec discipline), never
                # glob-interpreted away
                "odd[file].txt": "literal\n",
            },
        )
        result = _run_sync(checkout, staging, "public")
        assert result.returncode == 0, result.stderr
        head = _git("rev-parse", "refs/heads/mirror/public-core", cwd=remote).stdout.strip()
        shipped = _git("ls-tree", "-r", "--name-only", head, cwd=remote).stdout.splitlines()
        assert sorted(shipped) == [".env.example", "README.md", "odd[file].txt", "src/app.py"], shipped
        assert _git("show", f"{head}:src/app.py", cwd=remote).stdout == "print(1)\n"
        assert _git("show", f"{head}:odd[file].txt", cwd=remote).stdout == "literal\n"

    def test_sync_from_a_fresh_empty_checkout(self, tmp_path):
        """The clean-room path: a freshly `git init`-ed checkout (no
        HEAD, no branches) must bootstrap the root lineage — the dirty
        guard must tolerate the no-HEAD state instead of refusing it."""
        checkout = tmp_path / "fresh-checkout"
        checkout.mkdir()
        _git("init", "-q", cwd=checkout)
        remote = tmp_path / "public-remote.git"
        _git("init", "-q", "--bare", str(remote), cwd=tmp_path)
        _git("remote", "add", "public", str(remote), cwd=checkout)
        staging = _make_staging_tree(tmp_path, {"README.md": "fresh\n", "a/b.txt": "b\n"})
        result = _run_sync(checkout, staging, "public")
        assert result.returncode == 0, result.stderr
        head = _git("rev-parse", "refs/heads/mirror/public-core", cwd=remote).stdout.strip()
        parents = _git("rev-list", "--parents", "-n", "1", head, cwd=remote).stdout.split()
        assert len(parents) == 1, "the fresh-checkout sync must be a ROOT commit"
        shipped = sorted(_git("ls-tree", "-r", "--name-only", head, cwd=remote).stdout.splitlines())
        assert shipped == ["README.md", "a/b.txt"], shipped

    def test_sync_uses_the_deterministic_index_discipline(self):
        """The real first sync unioned the stale tree into the commit
        because `git rm --cached` silently failed mid-bootstrap — the
        post-commit exactness gate caught it (no push). The mechanism
        must be the deterministic forms: `git read-tree --empty` (no
        HEAD/stat dependencies), ONE literal `--pathspec-from-file`
        add, ONE `git diff --no-index` content gate."""
        text = (scripts_dir / "publish_sync.sh").read_text()
        assert "git read-tree --empty" in text
        assert "--pathspec-from-file" in text
        assert "--pathspec-file-nul" in text
        assert "git diff --no-index" in text
        assert "git rm -r -q --cached" not in text, "the fragile index clear must be gone"

    def test_second_sync_appends_and_fast_forwards_main(self, tmp_path):
        backup = _make_tainted_backup(tmp_path)
        checkout, remote = self._make_checkout(tmp_path, backup)
        first = _make_staging_tree(tmp_path, {"README.md": "one\n"}, name="first")
        assert _run_sync(checkout, first, "public").returncode == 0
        root = _git("rev-parse", "refs/heads/mirror/public-core", cwd=remote).stdout.strip()
        second = _make_staging_tree(tmp_path, {"README.md": "two\n", "b.txt": "b\n"}, name="second")
        assert _run_sync(checkout, second, "public").returncode == 0
        head = _git("rev-parse", "refs/heads/mirror/public-core", cwd=remote).stdout.strip()
        assert head != root
        assert _git("rev-parse", f"{head}^", cwd=remote).stdout.strip() == root, "sync commits must chain"
        assert _git("rev-parse", "refs/heads/main", cwd=remote).stdout.strip() == head
        assert _git("rev-parse", "refs/tags/v2026.10.20^{}", cwd=remote).stdout.strip() == head

    def test_diverged_remote_refuses_with_a_realign_recipe(self, tmp_path):
        backup = _make_tainted_backup(tmp_path)
        checkout, remote = self._make_checkout(tmp_path, backup)
        staging = _make_staging_tree(tmp_path, {"README.md": "one\n"})
        assert _run_sync(checkout, staging, "public").returncode == 0
        # diverge the remote: another clone force-pushes a different commit
        other = tmp_path / "other"
        _git("clone", "-q", str(remote), str(other), cwd=tmp_path)
        _git("config", "user.email", "other@example.com", cwd=other)
        _git("config", "user.name", "other", cwd=other)
        (other / "rogue.txt").write_text("rogue\n")
        _git("add", ".", cwd=other)
        _git("commit", "-q", "-m", "rogue", cwd=other)
        _git("push", "-q", "-f", "origin", "HEAD:mirror/public-core", cwd=other)
        # the local branch is now BEHIND a diverged remote — refuse
        result = _run_sync(checkout, staging, "public")
        assert result.returncode != 0, "a diverged remote mirror must refuse the sync"
        assert "diverged" in (result.stdout + result.stderr).lower()
        assert "realign" in (result.stdout + result.stderr).lower()

    def test_dirty_checkout_refuses(self, tmp_path):
        backup = _make_tainted_backup(tmp_path)
        checkout, _remote = self._make_checkout(tmp_path, backup)
        staging = _make_staging_tree(tmp_path, {"README.md": "one\n"})
        (checkout / "normal.txt").write_text("modified\n")  # tracked modification
        result = _run_sync(checkout, staging, "public")
        assert result.returncode != 0, "a dirty public checkout must refuse the sync"
        assert "uncommitted" in (result.stdout + result.stderr).lower()

    def test_missing_remote_refuses(self, tmp_path):
        backup = _make_tainted_backup(tmp_path)
        checkout, _remote = self._make_checkout(tmp_path, backup)
        staging = _make_staging_tree(tmp_path, {"README.md": "one\n"})
        result = _run_sync(checkout, staging, "nonexistent-remote")
        assert result.returncode != 0
        assert "remote" in (result.stdout + result.stderr).lower()


# ---------------------------------------------------------------------------
# replace_public_repo.py — plan / backup guard / taint classification
# ---------------------------------------------------------------------------

import importlib.util


def _load_replace() -> ModuleType:
    spec = importlib.util.spec_from_file_location("replace_public_repo", REPLACE)
    assert spec is not None, "replace_public_repo.py must load (P2-5 ships it)"
    assert spec.loader is not None, "replace_public_repo.py must load (P2-5 ships it)"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTaintClassification:
    def test_classify_refs_finds_exactly_the_forking_refs(self, tmp_path):
        mod = _load_replace()
        backup = _make_tainted_backup(tmp_path)
        tainted = _tainted_sha(backup)
        classification = mod.classify_refs(str(backup), [tainted])
        tainted_refs = sorted(r for r, t in classification.items() if t)
        # main, mirror/public-core, community/core-fix AND the tag all fork
        # the tainted root (the tag sits on main's lineage);
        # the orphan clean-branch must NOT be classified
        assert "refs/heads/main" in tainted_refs
        assert "refs/heads/mirror/public-core" in tainted_refs
        assert "refs/heads/community/core-fix" in tainted_refs
        assert "refs/tags/v2026.08.14" in tainted_refs
        assert "refs/heads/clean-branch" not in tainted_refs

    def test_clean_backup_classifies_nothing(self, tmp_path):
        mod = _load_replace()
        work = tmp_path / "clean"
        work.mkdir()
        _git("init", "-q", "-b", "main", cwd=work)
        _git("config", "user.email", "c@example.com", cwd=work)
        _git("config", "user.name", "c", cwd=work)
        (work / "f.txt").write_text("fine\n")
        _git("add", ".", cwd=work)
        _git("commit", "-q", "-m", "fine", cwd=work)
        backup = tmp_path / "clean.git"
        _git("clone", "-q", "--mirror", str(work), str(backup), cwd=tmp_path)
        classification = mod.classify_refs(str(backup), ["0" * 40])
        assert classification
        assert not any(classification.values())


class TestBackupGuard:
    def test_complete_backup_passes(self, tmp_path):
        mod = _load_replace()
        backup = _make_tainted_backup(tmp_path)
        live_refs = {}
        for ref in ["refs/heads/main", "refs/heads/community/core-fix", "refs/tags/v2026.08.14"]:
            live_refs[ref] = _git("rev-parse", ref, cwd=backup).stdout.strip()
        problems = mod.verify_backup(str(backup), live_refs)
        assert problems == []

    def test_backup_missing_a_live_ref_fails(self, tmp_path):
        mod = _load_replace()
        backup = _make_tainted_backup(tmp_path)
        live_refs = {"refs/heads/main": _git("rev-parse", "refs/heads/main", cwd=backup).stdout.strip()}
        # a live ref that only exists server-side (e.g. a PR ref) must fail
        live_refs["refs/pull/1/head"] = "0" * 40
        problems = mod.verify_backup(str(backup), live_refs)
        assert any("refs/pull/1/head" in p for p in problems)

    def test_backup_with_stale_sha_fails(self, tmp_path):
        mod = _load_replace()
        backup = _make_tainted_backup(tmp_path)
        live_refs = {"refs/heads/main": "0" * 40}
        problems = mod.verify_backup(str(backup), live_refs)
        assert any("refs/heads/main" in p for p in problems)

    def test_corrupt_backup_fails(self, tmp_path):
        mod = _load_replace()
        backup = _make_tainted_backup(tmp_path)
        # corrupt the backup: a ref file pointing at a missing object
        # (written directly — update-ref refuses to create dangling refs)
        (backup / "refs" / "heads" / "broken").write_text("1" * 40 + "\n")
        live_refs = {"refs/heads/main": _git("rev-parse", "refs/heads/main", cwd=backup).stdout.strip()}
        problems = mod.verify_backup(str(backup), live_refs)
        assert problems, "a corrupt backup (dangling ref) must fail the guard"


class TestReplacePlanRendering:
    def test_plan_renders_the_actions_and_preconditions(self, tmp_path):
        mod = _load_replace()
        state = {
            "slug": "owner/repo",
            "visibility": "public",
            "stars": 0,
            "forks": 0,
            "watchers": 0,
            "open_pulls": 14,
            "push_protection": "enabled",
            "default_branch": "main",
            "description": "desc",
            "refs": {
                "refs/heads/main": True,
                "refs/heads/community/core-fix": True,
                "refs/tags/v2026.08.14": False,
            },
        }
        text = mod.render_plan(state)
        assert "owner/repo" in text
        assert "delete-and-recreate" in text.lower()
        assert "push protection: enabled" in text.lower()
        assert "14 open pull requests" in text
        assert "refs/heads/community/core-fix" in text
        assert "TAINTED" in text
        tag_line = text.split("refs/tags/v2026.08.14")[1].splitlines()[0]
        assert "TAINTED" not in tag_line

    def test_plan_requires_push_protection_enabled(self):
        mod = _load_replace()
        problems = mod.precondition_problems(
            {"visibility": "public", "push_protection": "disabled"}
        )
        assert any("push protection" in p for p in problems)
        problems = mod.precondition_problems(
            {"visibility": "private", "push_protection": "enabled"}
        )
        assert any("visibility" in p for p in problems)
        assert mod.precondition_problems(
            {"visibility": "public", "push_protection": "enabled"}
        ) == []

    def test_plan_cli_accepts_repo_after_the_subcommand(self):
        """The Makefile form is `plan --repo OWNER/REPO` — the --repo flag
        must live on the SUBPARSER (main-parser flags require the
        pre-subcommand position)."""
        result = subprocess.run(
            [
                "python",
                str(REPLACE),
                "plan",
                "--repo",
                "owner/nonexistent-repo-xyz",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        # exit 2 = tooling/API failure (repo not found), NOT a usage error
        # (exit 2 from argparse would print "unrecognized arguments")
        assert result.returncode == 2, result.stderr
        assert "unrecognized arguments" not in result.stderr


# ---------------------------------------------------------------------------
# check_public_resync_diff.py — the G13 acceptance checker
# ---------------------------------------------------------------------------


def _load_diff_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_public_resync_diff", RESYNC_DIFF)
    assert spec is not None, "check_public_resync_diff.py must load (P2-5 ships it)"
    assert spec.loader is not None, "check_public_resync_diff.py must load (P2-5 ships it)"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestResyncDiff:
    def test_kept_and_drift_files_classify(self, tmp_path):
        mod = _load_diff_checker()
        old = _make_staging_tree(
            tmp_path / "old",
            {
                "README.md": "public readme\n",
                "LICENSE": "apache\n",
                "AGENTS.md": "stale community file\n",
                "archive/old-thing.txt": "x\n",
            },
        )
        new = _make_staging_tree(tmp_path / "new", {"README.md": "fresh\n", "LICENSE": "apache\n"})
        drift_file = tmp_path / "drift.txt"
        drift_file.write_text(
            "AGENTS.md\tcheckout litter swept in by add -A (root-fixed)\n"
            "archive/\tpre-resync archive kept only in the backup mirror\n"
        )
        report = mod.diff_trees(old, new, drift_file)
        assert report["unclassified"] == [], report["unclassified"]
        assert "README.md" in report["kept"]
        assert "LICENSE" in report["kept"]
        assert set(report["removed"]) == {"AGENTS.md", "archive/old-thing.txt"}

    def test_unclassified_public_only_file_fails(self, tmp_path):
        mod = _load_diff_checker()
        old = _make_staging_tree(tmp_path / "old", {"SECURITY.md": "policy\n"})
        new = _make_staging_tree(tmp_path / "new", {"README.md": "r\n"})
        drift_file = tmp_path / "drift.txt"
        drift_file.write_text("")
        report = mod.diff_trees(old, new, drift_file)
        assert "SECURITY.md" in report["unclassified"], "a dropped public-only file must be named"

    def test_overlay_files_must_be_preserved(self, tmp_path):
        mod = _load_diff_checker()
        overlay = tmp_path / "overlay"
        overlay.mkdir(parents=True)
        (overlay / "LICENSE").write_text("apache\n")
        (overlay / ".github").mkdir()
        (overlay / ".github" / "workflows").mkdir()
        (overlay / ".github" / "workflows" / "ci-core.yml").write_text("on: [push]\n")
        new = _make_staging_tree(tmp_path / "new", {"README.md": "r\n", "LICENSE": "apache\n"})
        missing = mod.overlay_missing_files(new, overlay)
        assert missing == [".github/workflows/ci-core.yml"], missing

    def test_cli_exit_codes(self, tmp_path):
        old = _make_staging_tree(tmp_path / "old", {"README.md": "old\n", "LICENSE": "x\n"})
        new = _make_staging_tree(tmp_path / "new", {"README.md": "new\n", "LICENSE": "x\n"})
        drift_file = tmp_path / "drift.txt"
        drift_file.write_text("")
        empty_overlay = tmp_path / "overlay"
        empty_overlay.mkdir()
        ok = subprocess.run(
            [
                "python",
                str(RESYNC_DIFF),
                str(old),
                str(new),
                "--drift-file",
                str(drift_file),
                "--overlay-dir",
                str(empty_overlay),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert ok.returncode == 0, ok.stderr
        # a nonexistent NEW tree is a tooling failure (exit 2)
        bad = subprocess.run(
            [
                "python",
                str(RESYNC_DIFF),
                str(old),
                str(tmp_path / "new2"),
                "--drift-file",
                str(drift_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert bad.returncode == 2


class TestWiring:
    def test_makefile_and_lint_list_wiring(self):
        makefile = (ROOT / "Makefile").read_text()
        assert "public-replace-plan" in makefile
        assert "public-replace-execute" in makefile
        assert "public-resync-diff" in makefile
        lint = (ROOT / ".github/workflows/_reusable.lint.yml").read_text()
        assert "scripts/tests/test_p25_public_replacement.py" in lint

    def test_publish_public_sources_the_sync_script(self):
        text = (ROOT / "scripts" / "publish_public.sh").read_text()
        assert "publish_sync.sh" in text
        assert "sync_to_public" in text


class TestLiveLegs:
    """The real gh legs — W16-gated: local runs hit the real API, CI
    raises (never a silent skip)."""

    def test_live_plan_preconditions_hold(self):
        if shutil.which("gh") is None:
            skip_or_fail("gh CLI (the live plan leg runs against the real API)")
        mod = _load_replace()
        metadata = mod.repo_metadata(PUBLIC_SLUG)
        assert metadata["visibility"] == "public"
        # the G12 ordering: push protection must be enabled BEFORE the
        # first re-sync (the replacement re-arms it AFTER recreation;
        # the publish pre-flight machine-enforces it).
        assert metadata["push_protection"] == "enabled"
        state = mod.plan_state(metadata)
        assert mod.precondition_problems(state) == []
