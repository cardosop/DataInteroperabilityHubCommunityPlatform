"""GATE-55 (oss-release-remediation W12.1) pins — no mocks, no stubs.

The RED phase of W12.1: every pin below ran against the REAL repository
before the removal work landed and failed (tracked docs/docs/,
sdk/typescript/, test-results/, guard-failures/, placeholder metadata,
fictional SDK URLs, @meshant CODEOWNERS teams, scratch openspec dirs).

Pins exercise the REAL gate as a subprocess against:
  * the real repository (master GREEN pin),
  * a REAL publish_tree.sh build (the built public tree contains none of
    the artifacts),
  * planted-violation temp git repos (the gate BITES — a reintroduced
    artifact class, placeholder, or old-path reference flips it RED).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "check_shipped_tree_litter.py"
PUBLISH_TREE_SH = REPO_ROOT / "scripts" / "publish_tree.sh"

# The shipped metadata surfaces the placeholder checks read — copied into
# planted-violation repos so they exercise the real content checks.
METADATA_FILES = (
    "helm/Chart.yaml",
    "helm/community/Chart.yaml",
    "helm/community/values.yaml",
    "sdk/js/package.json",
    "sdk/python/pyproject.toml",
    "cli/setup.py",
    "package.json",
    ".github/CODEOWNERS",
)


def _run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _make_mini_repo(tmp_path: Path) -> Path:
    """A real git repo carrying the real metadata files (no mocks)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "pin@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "pin"], cwd=repo, check=True
    )
    for rel in METADATA_FILES:
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((REPO_ROOT / rel).read_text(encoding="utf-8"))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    return repo


class TestRealRepository:
    """The master GREEN pins — the real tree satisfies the whole contract."""

    def test_real_repo_is_clean(self):
        result = _run_gate()
        assert result.returncode == 0, result.stdout + result.stderr
        assert "shipped-tree litter check clean" in result.stdout

    def test_real_gitignore_carries_the_removal_guard(self):
        # Effective coverage, not literal patterns — GATE-55 uses
        # `git check-ignore` so any working pattern form counts. Directory
        # classes probe with a trailing slash (check-ignore treats a
        # slashless nonexistent path as a FILE).
        for guard in (
            "cli/build/",
            "storybook-static/",
            "sdk/typescript/",
            "mock_audit_results.json",
            "test-results/",
            "guard-failures/",
            "generated/",
            "=",
            "b12.txt",
        ):
            result = subprocess.run(
                ["git", "check-ignore", "-q", guard],
                cwd=REPO_ROOT,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 0, f"{guard!r} not gitignored"

    def test_real_codeowners_uses_the_repo_owner(self):
        owners = set()
        for line in (
            REPO_ROOT / ".github" / "CODEOWNERS"
        ).read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            owners |= {tok for tok in stripped.split() if tok.startswith("@")}
        assert owners == {"@cardosop"}, owners


class TestBuiltPublicTree:
    """The W12.1 evidence: the BUILT public tree contains none of the
    listed artifacts. Real publish_tree.sh build, real gate scan."""

    @pytest.fixture(scope="class")
    def built_tree(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("public") / "tree"
        replace_file = out.parent / "replace.txt"
        subprocess.run(
            [
                sys.executable,
                "scripts/build_replace_text.py",
                "--out",
                str(replace_file),
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        # The index tree legitimately lacks UNSTAGED PAID annotations —
        # the preview builder (build_public_tree_preview.sh) defers the
        # W7.2 scrub assertion for exactly this reason; this pin scans the
        # real built tree for W12.1 litter, so it takes the preview path.
        subprocess.run(
            [
                "bash",
                "-c",
                f'source "{PUBLISH_TREE_SH}" && '
                f"PUBLISH_SKIP_PAID_ASSERTION=1 "
                f'build_publish_tree "{out}" "{replace_file}"',
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return out

    def test_built_tree_builds(self, built_tree):
        files = sum(1 for p in built_tree.rglob("*") if p.is_file())
        assert files > 1000, "sanity: the public tree actually built"

    def test_built_tree_contains_no_artifacts(self, built_tree):
        result = _run_gate("--tree", str(built_tree))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "shipped-tree litter check clean" in result.stdout

    def test_built_tree_contains_no_tracked_litter(self, built_tree):
        for artifact in (
            "storybook-static",
            "cli/build",
            "docs/docs",
            "sdk/typescript",
            "test-results",
            "guard-failures",
            "mock_audit_results.json",
        ):
            assert not (built_tree / artifact).exists(), artifact
        assert not (built_tree / "=").exists()
        assert not list(built_tree.glob("b*.txt"))


class TestPlantedViolationsBite:
    """Drift pins — reintroducing any artifact class flips the gate RED."""

    def test_planted_tracked_artifact_bites(self, tmp_path):
        repo = _make_mini_repo(tmp_path)
        (repo / "test-results").mkdir()
        (repo / "test-results" / "skip-events.jsonl").write_text("{}\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "litter"], cwd=repo, check=True)
        result = _run_gate("--root", str(repo))
        assert result.returncode == 1
        assert "test-results/" in result.stdout

    def test_planted_root_litter_file_bites(self, tmp_path):
        repo = _make_mini_repo(tmp_path)
        (repo / "b12.txt").write_text("notes\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "litter"], cwd=repo, check=True)
        result = _run_gate("--root", str(repo))
        assert result.returncode == 1
        assert "root litter file 'b12.txt'" in result.stdout

    def test_planted_metadata_placeholder_bites(self, tmp_path):
        repo = _make_mini_repo(tmp_path)
        pkg = repo / "sdk" / "js" / "package.json"
        # Phase-independent plant: a regression re-introducing the
        # fictional repo host anywhere in a shipped metadata file flips
        # the gate RED (the pre-fix tree carried this host for real).
        pkg.write_text(
            pkg.read_text(encoding="utf-8")
            + '\n  "_planted": "https://github.com/datahub/interoperability-hub"\n'
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "placeholder"], cwd=repo, check=True
        )
        result = _run_gate("--root", str(repo))
        assert result.returncode == 1
        assert "fictional repo github.com/datahub/" in result.stdout

    def test_planted_your_org_chart_bites(self, tmp_path):
        repo = _make_mini_repo(tmp_path)
        chart = repo / "helm" / "Chart.yaml"
        chart.write_text(
            chart.read_text(encoding="utf-8") + "\nhome: https://github.com/your-org/x\n"
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "placeholder"], cwd=repo, check=True)
        result = _run_gate("--root", str(repo))
        assert result.returncode == 1
        assert "your-org" in result.stdout

    def test_planted_codeowners_team_bites(self, tmp_path):
        repo = _make_mini_repo(tmp_path)
        owners = repo / ".github" / "CODEOWNERS"
        owners.write_text(
            owners.read_text(encoding="utf-8")
            + "\nsdk/  @meshant/data-platform-eng @cardosop\n"
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "team"], cwd=repo, check=True)
        result = _run_gate("--root", str(repo))
        assert result.returncode == 1
        assert "@meshant/" in result.stdout

    def test_planted_old_path_reference_bites(self, tmp_path):
        repo = _make_mini_repo(tmp_path)
        archived = repo / "openspec" / "changes" / "archive" / "feat1"
        archived.mkdir(parents=True)
        (archived / "tasks.md").write_text("# archived\n")
        ref = repo / "scripts"
        ref.mkdir(exist_ok=True)
        (ref / "tool.py").write_text(
            'x = "openspec/changes/feat1/tasks.md"\n'
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "ref"], cwd=repo, check=True)
        result = _run_gate("--root", str(repo))
        assert result.returncode == 1
        assert "live references to old path openspec/changes/feat1/" in result.stdout

    def test_planted_unarchived_scratch_bites(self, tmp_path):
        repo = _make_mini_repo(tmp_path)
        old = repo / "openspec" / "changes" / "feat1"
        old.mkdir(parents=True)
        (old / "tasks.md").write_text("# scratch\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "scratch"], cwd=repo, check=True)
        result = _run_gate("--root", str(repo))
        assert result.returncode == 1
        assert "scratch openspec change 'feat1' still at its old path" in result.stdout

    def test_planted_gitignore_gap_bites(self, tmp_path):
        repo = _make_mini_repo(tmp_path)
        (repo / ".gitignore").write_text("node_modules/\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "gitignore"], cwd=repo, check=True)
        result = _run_gate("--root", str(repo))
        assert result.returncode == 1
        assert "'cli/build/' is not covered by .gitignore" in result.stdout
