"""
Contract tests for scripts/verify_history_rewrite.py (oss-release-remediation
W0.4).

The verifier proves, on a FRESH CLONE of the rewritten repository, that:

- every excluded path is unreachable from every ref
  (`git log --all -- <path>` empty);
- the dropped tag prefixes have no refs left;
- every secret fragment from the rotation list is unreachable
  (`git log --all -S <fragment>` empty — fragments are never printed);
- `git fsck` reports no errors.

The fixtures are REAL git repositories, rewritten with the REAL
git-filter-repo binary — the pins prove the verifier catches an
UNREWRITTEN repo and accepts a REWRITTEN one (end-to-end, no mocks).
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "verify_history_rewrite.py"
spec = importlib.util.spec_from_file_location("verify_history_rewrite", script_path)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

ROOT = scripts_dir.parent
FILTER_REPO = shutil.which("git-filter-repo") or str(ROOT / "venv/bin/git-filter-repo")

PLANTED = "FIXTURESECRET7f3d2a1b9c4e8f6a5d3b7c9e1f2a4b6d"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _init_repo(tmp_path: Path, seed_secret: bool = True) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "keep.txt").write_text("keep me\n")
    (repo / "secrets.env").write_text(f"TOKEN={PLANTED}\n")
    (repo / "leaky.md").write_text("doc with a secret\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "initial with secret")
    _git(repo, "tag", "backup-staging-20251207_test")
    _git(repo, "tag", "release-v1")
    if not seed_secret:
        _git(repo, "rm", "-q", "secrets.env", "leaky.md")
        _git(repo, "commit", "-qm", "drop the secret files")
    return repo


def _rewrite(repo: Path, exclude: Path) -> Path:
    """The real rewrite: a bare mirror copy, filter-repo, drop the tags."""
    mirror = repo.parent / "mirror.git"
    subprocess.run(
        ["git", "clone", "--mirror", "-q", str(repo), str(mirror)], check=True
    )
    subprocess.run(
        [
            FILTER_REPO,
            "--force",
            "--invert-paths",
            "--paths-from-file",
            str(exclude),
        ],
        cwd=mirror,
        check=True,
        capture_output=True,
    )
    # Drop the archived staging-restore tags after the rewrite (the
    # refname-callback None-return is rejected by this filter-repo build).
    for tag in subprocess.run(
        ["git", "-C", str(mirror), "tag", "-l", "backup-staging-*"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines():
        subprocess.run(
            ["git", "-C", str(mirror), "update-ref", "-d", f"refs/tags/{tag}"],
            check=True,
            capture_output=True,
        )
    fresh = repo.parent / "fresh-clone"
    subprocess.run(
        ["git", "clone", "-q", "--mirror", str(mirror), str(fresh)], check=True
    )
    return fresh


@pytest.fixture
def fixture_repo(tmp_path):
    repo = _init_repo(tmp_path)
    exclude = tmp_path / "exclude.txt"
    exclude.write_text("secrets.env\nleaky.md\n")
    return repo, exclude


def _fragments(tmp_path, present=True):
    f = tmp_path / "fragments.txt"
    f.write_text((PLANTED if present else "NONEXISTENTFRAGMENT1234567890\n") + "\n")
    return f


def test_unrewritten_repo_fails(fixture_repo, tmp_path):
    repo, exclude = fixture_repo
    tags = tmp_path / "tags.txt"
    tags.write_text("backup-staging-\n")
    problems = verify.check(repo, exclude, _fragments(tmp_path), tags)
    assert any("secrets.env" in p for p in problems)
    assert any("leaky.md" in p for p in problems)
    assert any("backup-staging" in p for p in problems)
    assert any("fragment" in p for p in problems)


def test_rewritten_repo_passes(fixture_repo, tmp_path):
    repo, exclude = fixture_repo
    fresh = _rewrite(repo, exclude)
    problems = verify.check(fresh, exclude, _fragments(tmp_path))
    assert problems == []


def test_surviving_tag_prefix_fails(fixture_repo, tmp_path):
    # release-v1 must survive the rewrite; a planted non-dropped prefix
    # must be reported when asked for.
    repo, exclude = fixture_repo
    fresh = _rewrite(repo, exclude)
    tags = tmp_path / "tags.txt"
    tags.write_text("backup-staging-\nrelease-\n")
    problems = verify.check(fresh, exclude, _fragments(tmp_path), tags)
    assert any("release-" in p for p in problems)


def test_present_fragment_fails(fixture_repo, tmp_path):
    repo, exclude = fixture_repo
    problems = verify.check(repo, exclude, _fragments(tmp_path))
    assert any("fragment" in p for p in problems)


def test_missing_fragments_file_fails(fixture_repo, tmp_path):
    repo, exclude = fixture_repo
    problems = verify.check(repo, exclude, tmp_path / "nope.txt")
    assert any("fragments" in p for p in problems)


def test_missing_paths_file_fails(fixture_repo, tmp_path):
    repo, _exclude = fixture_repo
    problems = verify.check(repo, tmp_path / "nope.txt", _fragments(tmp_path))
    assert any("paths" in p for p in problems)


def test_missing_repo_fails(tmp_path):
    problems = verify.check(
        tmp_path / "no-repo", tmp_path / "e.txt", _fragments(tmp_path)
    )
    assert any("not a git repo" in p for p in problems)


def test_default_paths_file_exists():
    assert (ROOT / "scripts/history_rewrite_paths.txt").exists()


def test_directory_prefix_entry_excludes_subtree(tmp_path):
    """A trailing-slash entry covers everything below it; a bare entry
    is an exact file name (so `.env` must not swallow `.env.example`)."""
    repo = _init_repo(tmp_path)
    (repo / "subdir").mkdir()
    (repo / "subdir" / "nested.txt").write_text("nested\n")
    (repo / ".env.example").write_text("template\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "add subtree and template")
    exclude = tmp_path / "exclude2.txt"
    exclude.write_text("subdir/\n.env\n")
    fresh = _rewrite(repo, exclude)
    paths = verify._all_object_paths(fresh)
    assert not any(p.startswith("subdir/") for p in paths)
    assert ".env.example" in paths, "the template must survive an exact `.env` entry"


class TestMainContract:
    def test_problems_exit_1(self, fixture_repo, tmp_path, monkeypatch):
        repo, exclude = fixture_repo
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "verify_history_rewrite.py",
                "--repo",
                str(repo),
                "--paths",
                str(exclude),
                "--fragments",
                str(_fragments(tmp_path)),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, fixture_repo, tmp_path, monkeypatch):
        repo, exclude = fixture_repo
        fresh = _rewrite(repo, exclude)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "verify_history_rewrite.py",
                "--repo",
                str(fresh),
                "--paths",
                str(exclude),
                "--fragments",
                str(_fragments(tmp_path)),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 0
