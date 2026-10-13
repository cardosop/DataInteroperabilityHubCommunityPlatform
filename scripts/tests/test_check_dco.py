"""
0.4 — DCO check script tests (public repo contribution gate).

The public CI runs ``scripts/check_dco.sh`` on pull requests: every
commit in the PR range must carry a ``Signed-off-by:`` trailer, or the
PR fails. These tests build REAL temp git repositories (no mocks) and
run the real script against them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check_dco.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "config", "user.email", "tester@example.com")
    (repo / "file.txt").write_text("content\n")
    _git(repo, "add", "file.txt")
    return repo


def _commit(repo: Path, message: str) -> None:
    # --allow-empty: the fixtures commit messages without new file
    # changes (the DCO check reads commit metadata, not trees).
    _git(repo, "commit", "--allow-empty", "-m", message)


def _run_script(repo: Path, target: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), target],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_all_commits_signed_off_passes(tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: signed work\n\nSigned-off-by: Tester <tester@example.com>")
    result = _run_script(repo, "HEAD")
    assert result.returncode == 0, result.stderr


def test_unsigned_commit_fails_and_names_it(tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: unsigned work")
    result = _run_script(repo, "HEAD")
    assert result.returncode != 0
    assert "unsigned work" in result.stdout + result.stderr


def test_mixed_history_fails_on_the_unsigned_commit(tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: signed\n\nSigned-off-by: Tester <tester@example.com>")
    _commit(repo, "fix: later unsigned")
    result = _run_script(repo, "HEAD~1..HEAD")
    assert result.returncode != 0
    assert "later unsigned" in result.stdout + result.stderr


def test_empty_range_fails_loudly(tmp_path):
    repo = _init_repo(tmp_path)
    result = _run_script(repo, "")
    assert result.returncode != 0
