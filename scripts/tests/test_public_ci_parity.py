"""Public-CI parity test — the root-cause close for the unshipped-file class.

The GAP-A wiring twice assumed suites were "self-contained" for the public
boundary job, and each time a referenced file turned out not to ship
(ci.yml, and the clarity suite's import chain). This suite makes the
assumption TESTED instead of assumed: it builds the PUBLIC file subset the
way ``publish_tree.sh`` would — ``git ls-files`` filtered through the real
exclusion semantics (exact entries, dir prefixes, ``!`` negations), scoped
to the paths the public boundary suites touch, PLUS the publish overlay
applied the way ``publish_tree.sh`` applies it — and then RUNS those
suites against the subset. A suite referencing anything that does not
ship publicly fails HERE, in the private repo, before it can fail the
public ci-core job.

Phase P.8 D1 extension: the shipped workflow files must PARSE as YAML with
duplicate-key detection (PyYAML's default loader silently keeps the last
value for a duplicated key — which is how ``ci-core.yml`` shipped a dead
``test-core:`` job and the OSS artifact lost its CI). Verifying that a
workflow file exists in the published tree is not evidence that it can
run.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXCLUDE_FILE = REPO_ROOT / "scripts" / "publish_paths_exclude.txt"
PUBLIC_OVERLAY_DIR = REPO_ROOT / "scripts" / "publish_public_overlay"

# The paths the four public boundary suites (+ their import chain) touch.
# "monitoring/" feeds the P.8 core-safety suite (the excluded-by-default
# monitoring tree ships only the negated files, exactly like a publish).
PUBLIC_SUITE_SUBSET_PATTERNS = (
    "scripts/",
    "docker-compose.test.yml",
    "docker-compose.test.core.yml",
    "docker-compose.core.yml",
    "monitoring/",
    "hub/apps/manifest.py",
    "hub/apps/tenants/",
    "hub/settings.py",
)

PUBLIC_SUITE_FILES = (
    "scripts/tests/test_check_core_boundary_allowlist_ratchet.py",
    "scripts/tests/test_check_core_boundary_precommit.py",
    "scripts/tests/test_guard_test_failure_clarity.py",
    "scripts/tests/test_compose_overlay_parity.py",
    "scripts/tests/test_monitoring_core_safety.py",
)


def _exclusion_predicate(exclude_file: Path):
    entries = [
        line.strip()
        for line in exclude_file.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    plain = [e for e in entries if not e.startswith("!")]
    negations = [e[1:] for e in entries if e.startswith("!")]

    def excluded(path: str) -> bool:
        hit = any(
            path == e
            or (e.endswith("/") and path.startswith(e))
            or path.startswith(e.rstrip("/") + "/")
            for e in plain
        )
        if not hit:
            return False
        return not any(path == e or path.startswith(e) for e in negations)

    return excluded


def build_public_subset(repo: Path, exclude_file: Path, out_dir: Path) -> Path:
    """Materialize the public file subset the boundary suites depend on."""
    # Tracked files PLUS untracked-but-not-gitignored ones: the parity test
    # must cover what the NEXT COMMIT would ship (the suites are new files,
    # untracked until committed — ``git ls-files`` alone would miss them).
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    listing = tracked + untracked
    excluded = _exclusion_predicate(exclude_file)
    # One tuple call: exact pattern or pattern-prefix (dir semantics).
    subset_prefixes = tuple(p.rstrip("/") + "/" for p in PUBLIC_SUITE_SUBSET_PATTERNS)
    subset_exact = tuple(p for p in PUBLIC_SUITE_SUBSET_PATTERNS if not p.endswith("/"))
    kept = 0
    for rel in listing:
        if not (rel in subset_exact or rel.startswith(subset_prefixes)):
            continue
        if excluded(rel):
            continue
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / rel, target)
        kept += 1
    assert kept > 0, "public subset is empty — subset patterns must match files"
    # publish_tree.sh copies the publish overlay ONTO the tree after the
    # subset extraction (the overlay SOURCE dir is itself excluded) — the
    # parity tree must mirror that, or the shipped workflows never land
    # where the public clone will have them. In a public clone the overlay
    # source is gone (already applied at publish time), so the shipped
    # .github/ at the repo root IS the overlay result.
    overlay_source = repo / "scripts" / "publish_public_overlay"
    if overlay_source.is_dir():
        shutil.copytree(overlay_source, out_dir, dirs_exist_ok=True)
    elif (repo / ".github").is_dir():
        shutil.copytree(repo / ".github", out_dir / ".github")
    return out_dir


@pytest.fixture(scope="module")
def public_tree(tmp_path_factory) -> Path:
    return build_public_subset(REPO_ROOT, EXCLUDE_FILE, tmp_path_factory.mktemp("public-subset"))


def _run_suites(
    tree: Path, files: tuple[str, ...] = PUBLIC_SUITE_FILES
) -> subprocess.CompletedProcess:
    return subprocess.run(
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
            "-p",
            "no:cacheprovider",
            *(str(tree / rel) for rel in files),
        ],
        capture_output=True,
        text=True,
        cwd=tree,
        check=False,
    )


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """SafeLoader that REJECTS duplicate mapping keys.

    PyYAML silently keeps the LAST value for a duplicated key — which is
    exactly how the published ``ci-core.yml`` shipped a dead ``test-core:``
    job (an empty key followed by the real definition) and the OSS artifact
    lost its CI. GitHub's workflow parser rejects such documents, so a
    parity check that parses with plain ``yaml.safe_load`` would pass a
    workflow that GitHub refuses to run. This loader closes that class:
    any duplicate key raises, naming the key and its first definition line.
    """

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"duplicate key {key!r} (first defined at line {node.start_mark.line + 1})",
                    node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def parse_shipped_workflows(tree: Path) -> dict[Path, dict]:
    """Parse every workflow file the public clone will carry.

    Raises (names file + duplicated key) on any workflow that GitHub's
    strict parser would reject. Returns {relative_path: document}.
    """
    wf_dir = tree / ".github" / "workflows"
    assert wf_dir.is_dir(), (
        ".github/workflows missing from the public subset — the publish "
        "overlay was not applied (build_public_subset must mirror "
        "publish_tree.sh's overlay step)"
    )
    parsed: dict[Path, dict] = {}
    for wf in sorted(wf_dir.glob("*.yml")):
        parsed[wf.relative_to(tree)] = yaml.load(wf.read_text(), Loader=DuplicateKeySafeLoader)
    assert parsed, ".github/workflows is empty — no shipped workflows to validate"
    return parsed


class TestPublicSubset:
    def test_all_public_suites_pass_against_the_public_subset(self, public_tree):
        """The suites CI runs in the public boundary job MUST pass on a
        tree shaped exactly like the public clone (no ci.yml, no venv, only
        non-excluded files)."""
        assert not (public_tree / ".github" / "workflows" / "ci.yml").exists()
        assert not (public_tree / "venv").exists()
        result = _run_suites(public_tree)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_public_subset_contains_no_paid_apps(self, public_tree):
        paid = ("marketplace", "semantic", "billing", "baas", "rate_limiting", "ai", "ml")
        shipped_paid = [
            rel for rel in (f"hub/apps/{name}" for name in paid) if (public_tree / rel).exists()
        ]
        assert shipped_paid == [], f"paid app dirs in the public subset: {shipped_paid}"

    def test_red_drill_excluded_dependency_fails_loudly(self, tmp_path):
        """The class this suite exists for: exclude a LOAD-BEARING file the
        suites read directly and the parity run must FAIL naming it — not
        pass silently. (publish_tree.sh is deliberately NOT the victim: the
        clarity fixture only symlinks it, and the publish-tree tests skip
        before the symlink is ever dereferenced in a public layout.)"""
        drill_excludes = tmp_path / "drill_excludes.txt"
        drill_excludes.write_text(EXCLUDE_FILE.read_text() + "\ndocker-compose.test.yml\n")
        tree = build_public_subset(REPO_ROOT, drill_excludes, tmp_path / "tree")
        assert not (tree / "docker-compose.test.yml").exists()
        result = _run_suites(tree)
        assert result.returncode != 0, "a missing dependency must fail the parity run"
        assert "docker-compose.test.yml" in result.stdout + result.stderr


# The job keys the public ci-core.yml MUST declare, as distinct top-level
# jobs under `jobs:` (spec: "Structural expectations are asserted, not
# assumed" — a job accidentally nested inside another must fail the test).
EXPECTED_CI_CORE_JOBS = (
    "dco",
    "boundary-and-secrets",
    "lint-typecheck",
    "test-core",
    "core-boot-smoke",
    "docker-images",
    "docs",
    "codeql",
)


class TestShippedWorkflowYAML:
    """Phase P.8 D1 — the published workflow files must PARSE, with
    duplicate-key detection, before they can ship. Verifying that the file
    EXISTS in the published tree is not evidence that it can run: the OSS
    artifact shipped a ci-core.yml whose duplicate ``test-core:`` key made
    GitHub reject the whole workflow, and the old parity check never
    parsed a single line of it."""

    def test_shipped_workflows_parse_without_duplicate_keys(self, public_tree):
        parse_shipped_workflows(public_tree)

    def test_ci_core_declares_expected_jobs_as_distinct_mappings(self, public_tree):
        doc = parse_shipped_workflows(public_tree)[Path(".github/workflows/ci-core.yml")]
        jobs = doc.get("jobs")
        assert isinstance(jobs, dict), "ci-core.yml must declare a jobs mapping"
        for name in EXPECTED_CI_CORE_JOBS:
            assert name in jobs, f"ci-core.yml is missing the {name!r} job"
            job = jobs[name]
            assert isinstance(job, dict), (
                f"job {name!r} has no definition — an empty or nested key would silently shadow it"
            )
            assert job, (
                f"job {name!r} has no definition — an empty or nested key would silently shadow it"
            )
            assert job.get("runs-on"), (
                f"job {name!r} declares no runs-on — nested under the wrong "
                "mapping or never meant to run"
            )

    def test_duplicate_key_detection_bites_on_any_document(self):
        """The loader itself must be falsifiable: a minimal duplicate-key
        document raises, naming the key."""
        with pytest.raises(yaml.YAMLError, match="duplicate key 'test-core'"):
            yaml.load(
                "jobs:\n  test-core:\n  core-boot-smoke:\n    runs-on: x\n"
                "  test-core:\n    runs-on: y\n",
                Loader=DuplicateKeySafeLoader,
            )

    def test_red_drill_duplicate_job_key_fails_the_shipped_parse(self, tmp_path):
        """The class this test exists for: a duplicate job key in the
        SHIPPED workflow must fail the parity parse naming the key — the
        exact bug that shipped a dead public CI (an empty ``test-core:``
        followed by the real definition)."""
        tree = build_public_subset(REPO_ROOT, EXCLUDE_FILE, tmp_path / "tree")
        wf = tree / ".github" / "workflows" / "ci-core.yml"
        wf.write_text(wf.read_text() + "  test-core: {}\n")
        with pytest.raises(yaml.YAMLError, match="test-core"):
            parse_shipped_workflows(tree)
