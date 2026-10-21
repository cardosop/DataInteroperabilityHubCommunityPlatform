"""
Contract tests for the P2-4 tag-publication machinery
(close-oss-release-conditions):

- ``scripts/check_tag_main_anchor.py`` — the P2-4 acceptance checker:
  the annotated ``v0.1.0`` release tag must PEEL to main's HEAD (the
  rewritten clean main — the anchor), the manifest + VERSION + the
  CHANGELOG's top release section must agree on the same version, and
  the remotes must carry NO legacy/tainted tags (origin: zero legacy
  tags; public: the legacy ``v2026.*`` + archive tags deleted). One-shot
  execution tool — the honest pre-window state is exit 1 (the tag
  anchors the tainted lineage until the P2-2 force-push lands).
- ``scripts/publish_release_tags.py`` — the one-shot executor:
  ``--plan`` enumerates the real remote tag state + the planned
  actions; ``--execute`` (gated on ``--expect-main <sha>`` — the
  rewritten main from the P2-2 record) re-creates the annotated tag at
  the verified clean main, deletes the legacy public tags via the REAL
  GitHub API, and pushes the tag to origin then public (real git).
- ``scripts/release_please_dry_run.sh`` — the G9 dry-run wrapper: the
  REAL release-please CLI (the 16.x line the workflow's action pins)
  with the isolated npm cache + the gh token via env. The live dry-run
  over the deep prepro01 history is RECORDED as API-blocked (the
  GraphQL PR-walk 500s/hangs past the pagination limits — the G9
  finding; the post-window retry targets the rewritten main), so the
  pin asserts the wrapper's contract, not the API's availability.

Fixtures are REAL: git repos with annotated/lightweight/misplaced
tags, a local bare remote for the push leg, the real gh CLI for the
live legs (W16-gated), and the real npx+release-please for the
wrapper — no mocks.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

ROOT = scripts_dir.parent
sys.path.insert(0, str(ROOT))

from envpolicy import skip_or_fail

ANCHOR = str(scripts_dir / "check_tag_main_anchor.py")
PUBLISHER = str(scripts_dir / "publish_release_tags.py")
DRY_RUN_WRAPPER = scripts_dir / "release_please_dry_run.sh"

spec = importlib.util.spec_from_file_location("check_tag_main_anchor", ANCHOR)
assert spec is not None, "check_tag_main_anchor.py must load (P2-4 ships it)"
assert spec.loader is not None
anchor_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(anchor_mod)

publisher_spec = importlib.util.spec_from_file_location("publish_release_tags", PUBLISHER)
assert publisher_spec is not None, "publish_release_tags.py must load (P2-4 ships it)"
assert publisher_spec.loader is not None
publisher_mod = importlib.util.module_from_spec(publisher_spec)
publisher_spec.loader.exec_module(publisher_mod)

GH = shutil.which("gh")
ORIGIN_SLUG = "cardosop/DataInteroperabilityHub"
PUBLIC_SLUG = "cardosop/DataInteroperabilityHubCommunityPlatform"

RELEASE_TAG = "v0.1.0"
LEGACY = ("v2026.10.14", "v2026.10.13", "v2026.08.14", "archive/main-pre-resync-2026-10-13")


def _require_gh() -> None:
    if not GH:
        skip_or_fail("gh CLI (the live tag legs run against the real API)")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, check=False, cwd=cwd
    )


def _fixture_repo(tmp_path: Path) -> Path:
    """A real repo with main + a VERSION file + a CHANGELOG, ready for
    tag fixtures."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "VERSION").write_text("0.1.0\n")
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 0.1.0 (2026-10-13)\n\n* initial\n")
    (repo / ".release-please-manifest.json").write_text('{\n  ".": "0.1.0"\n}\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "release: initial")
    return repo


def _tag(repo: Path, name: str, message: str | None = None) -> None:
    args = ["tag"]
    if message is not None:
        args += ["-a", name, "-m", message]
    else:
        args.append(name)
    _git(repo, *args)


# ── the anchor checker ──────────────────────────────────────────────────────


def test_anchor_checker_accepts_annotated_tag_at_main_head(tmp_path):
    repo = _fixture_repo(tmp_path)
    _tag(repo, RELEASE_TAG, "v0.1.0 — release")
    proc = _run([ANCHOR, "--repo", str(repo), "--tag", RELEASE_TAG, "--version", "0.1.0"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ANCHORED" in proc.stdout


def test_anchor_checker_rejects_lightweight_tag(tmp_path):
    repo = _fixture_repo(tmp_path)
    _tag(repo, RELEASE_TAG)  # lightweight — release-please needs the tag object
    proc = _run([ANCHOR, "--repo", str(repo), "--tag", RELEASE_TAG, "--version", "0.1.0"])
    assert proc.returncode == 1
    assert "annotated" in proc.stdout.lower()


def test_anchor_checker_rejects_tag_at_wrong_commit(tmp_path):
    repo = _fixture_repo(tmp_path)
    _tag(repo, RELEASE_TAG, "v0.1.0 — release")
    (repo / "VERSION").write_text("0.1.1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "chore: bump")
    proc = _run([ANCHOR, "--repo", str(repo), "--tag", RELEASE_TAG, "--version", "0.1.0"])
    assert proc.returncode == 1
    assert "main" in proc.stdout.lower()


def test_anchor_checker_rejects_manifest_mismatch(tmp_path):
    repo = _fixture_repo(tmp_path)
    _tag(repo, RELEASE_TAG, "v0.1.0 — release")
    (repo / ".release-please-manifest.json").write_text('{\n  ".": "9.9.9"\n}\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "chore: manifest drift")
    proc = _run([ANCHOR, "--repo", str(repo), "--tag", RELEASE_TAG, "--version", "0.1.0"])
    assert proc.returncode == 1
    assert "manifest" in proc.stdout.lower()


def test_anchor_checker_rejects_changelog_mismatch(tmp_path):
    repo = _fixture_repo(tmp_path)
    _tag(repo, RELEASE_TAG, "v0.1.0 — release")
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 9.9.9 (2026-10-13)\n\n* other\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "docs: changelog drift")
    proc = _run([ANCHOR, "--repo", str(repo), "--tag", RELEASE_TAG, "--version", "0.1.0"])
    assert proc.returncode == 1
    assert "changelog" in proc.stdout.lower()


def test_anchor_checker_flags_legacy_tags_on_a_remote(tmp_path):
    """A remote carrying legacy/archive tags fails the remote leg even
    when its release tag is correctly anchored."""
    repo = _fixture_repo(tmp_path)
    _tag(repo, RELEASE_TAG, "v0.1.0 — release")
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--bare", "-q", str(remote))
    _git(repo, "remote", "add", "r", str(remote))
    _git(repo, "push", "-q", "r", "HEAD:refs/heads/main")
    _git(repo, "push", "-q", "r", f"refs/tags/{RELEASE_TAG}")
    _tag(repo, "v2026.10.14", "legacy")
    _git(repo, "push", "-q", "r", "refs/tags/v2026.10.14")
    proc = _run(
        [
            ANCHOR, "--repo", str(repo), "--tag", RELEASE_TAG, "--version", "0.1.0",
            "--remote-url", str(remote),
        ]
    )
    assert proc.returncode == 1
    assert "legacy" in proc.stdout.lower()
    assert "v2026.10.14" in proc.stdout


def test_anchor_checker_remote_clean_when_only_release_tag(tmp_path):
    repo = _fixture_repo(tmp_path)
    _tag(repo, RELEASE_TAG, "v0.1.0 — release")
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--bare", "-q", str(remote))
    _git(repo, "remote", "add", "r", str(remote))
    _git(repo, "push", "-q", "r", "HEAD:refs/heads/main")
    _git(repo, "push", "-q", "r", f"refs/tags/{RELEASE_TAG}")
    proc = _run(
        [
            ANCHOR, "--repo", str(repo), "--tag", RELEASE_TAG, "--version", "0.1.0",
            "--remote-url", str(remote),
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── the publisher ───────────────────────────────────────────────────────────


def test_publisher_legacy_tag_classification():
    """The pure classification: the legacy/archive tags are deleted;
    the release tag is re-created, never deleted."""
    classify = publisher_mod.legacy_tags
    assert set(classify([RELEASE_TAG, *LEGACY, "v1.2.3"])) == set(LEGACY)


def test_publisher_execute_gated_on_expect_main(tmp_path):
    """The clean-main gate: --execute refuses when the local main HEAD
    differs from the expected rewritten SHA (the P2-2 anchor)."""
    repo = _fixture_repo(tmp_path)
    proc = _run(
        [
            PUBLISHER, "--repo-root", str(repo), "--remote-url", str(tmp_path / "remote.git"),
            "--execute", "--expect-main", "f" * 40,
        ]
    )
    assert proc.returncode == 1
    assert "expect-main" in proc.stdout


def test_publisher_creates_and_pushes_the_tag(tmp_path):
    """The real happy path against a local bare remote: the annotated
    tag is created at main HEAD and pushed (the gh-dependent legacy
    deletion is reported SKIPPED for a non-GitHub URL)."""
    repo = _fixture_repo(tmp_path)
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--bare", "-q", str(remote))
    _git(repo, "remote", "add", "r", str(remote))
    _git(repo, "push", "-q", "r", "HEAD:refs/heads/main")
    head = _git(repo, "rev-parse", "HEAD").strip()
    proc = _run(
        [
            PUBLISHER, "--repo-root", str(repo), "--remote-url", str(remote),
            "--execute", "--expect-main", head,
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SKIPPED" in proc.stdout  # gh-only legacy deletion
    # the tag exists locally, annotated, peeling to main HEAD
    assert _git(repo, "cat-file", "-t", RELEASE_TAG).strip() == "tag"
    assert _git(repo, "rev-list", "-n", "1", RELEASE_TAG).strip() == head
    # and on the remote
    remote_tags = _git(remote, "for-each-ref", "--format=%(refname:short)", "refs/tags")
    assert RELEASE_TAG in remote_tags


def test_publisher_reanchors_an_existing_wrong_tag(tmp_path):
    """Re-create semantics: an existing v0.1.0 pointing at an OLD
    commit is force-replaced at the verified clean main HEAD."""
    repo = _fixture_repo(tmp_path)
    _tag(repo, RELEASE_TAG, "old tainted release")  # at the initial commit
    _git(repo, "commit", "-qm", "chore: post-tag change", "--allow-empty")
    head = _git(repo, "rev-parse", "HEAD").strip()
    assert _git(repo, "rev-list", "-n", "1", RELEASE_TAG).strip() != head
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--bare", "-q", str(remote))
    _git(repo, "remote", "add", "r", str(remote))
    _git(repo, "push", "-q", "r", "HEAD:refs/heads/main")
    _git(repo, "push", "-q", "r", f"refs/tags/{RELEASE_TAG}")
    proc = _run(
        [
            PUBLISHER, "--repo-root", str(repo), "--remote-url", str(remote),
            "--execute", "--expect-main", head, "--force",
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _git(repo, "rev-list", "-n", "1", RELEASE_TAG).strip() == head


# ── the live leg + the dry-run wrapper ──────────────────────────────────────


def test_live_remote_tag_state_recorded():
    """LIVE leg: the honest pre-window tag state — the LOCAL v0.1.0 is
    anchored at the pre-rewrite main and the manifest/VERSION/CHANGELOG
    agree (the W9.1 state); origin carries ZERO tags (the W0.4
    baseline — the anchor leg fails naming the missing tag); the
    public remote carries the 4 legacy/archive tags (the remote leg
    fails naming them). All three flip green only after the P2-2
    force-push + the P2-4 publication."""
    _require_gh()
    proc = _run([ANCHOR, "--repo", str(ROOT), "--tag", RELEASE_TAG, "--version", "0.1.0"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = _run(
        [ANCHOR, "--repo", str(ROOT), "--tag", RELEASE_TAG, "--version", "0.1.0",
         "--remote", "origin"]
    )
    assert proc.returncode == 1
    assert f"does not carry tag {RELEASE_TAG}" in proc.stdout
    proc = _run(
        [ANCHOR, "--repo", str(ROOT), "--tag", RELEASE_TAG, "--version", "0.1.0",
         "--remote", "public"]
    )
    assert proc.returncode == 1
    assert "legacy/tainted tag" in proc.stdout
    # P2-5 (2026-10-21): the pre-replacement legacy tags died with the
    # deleted repo; the date-stamped publish tags (v2026.10.20/21) are
    # the current legacy-class refs the P2-4 publication will delete.
    assert "v2026.10.21" in proc.stdout
    assert "v2026.10.14" not in proc.stdout
    # cross-check: origin advertises no tags (real git over ssh)
    listed = subprocess.run(
        ["git", "ls-remote", "origin", "refs/tags/*"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert listed == "", "origin must carry zero tags pre-window"


def test_release_please_dry_run_wrapper_contract():
    """The G9 wrapper: the real 16.x CLI (the workflow's pinned major),
    an isolated npm cache, the gh token via env (never echoed), and the
    recorded API-block note for the deep-history walk."""
    text = DRY_RUN_WRAPPER.read_text()
    assert "release-please@16" in text
    assert "npm_config_cache" in text
    assert "gh auth token" in text
    assert "--dry-run" in text
    assert "target-branch" in text
    # the wrapper never PRINTS the token (the token flows via env +
    # the --token flag only)
    assert 'echo "$GITHUB_TOKEN"' not in text
    assert "printenv" not in text


def test_makefile_and_lint_list_wiring():
    makefile = (ROOT / "Makefile").read_text()
    assert "release-please-dry-run" in makefile
    lint = (ROOT / ".github/workflows/_reusable.lint.yml").read_text()
    assert "scripts/tests/test_p24_tag_publication.py" in lint
