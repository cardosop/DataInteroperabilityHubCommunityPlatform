#!/usr/bin/env python3
"""GATE-55 (oss-release-remediation W12.1) — shipped-tree litter gate.

W12.1: the public tree must be clean. This gate pins the shipped-tree
contract at four levels:

  1. TRACKED tree (`git ls-files`) — the committed litter is gone:
     `storybook-static/`, `cli/build/`, the `docs/docs/` duplication,
     `sdk/typescript/` (D3 physical deletion), `test-results/`,
     `guard-failures/`, `mock_audit_results.json`, and root-level `=`
     / `b*.txt` files.
  2. WORKING tree — the same artifacts are gone from disk, and every
     scratch openspec change moved to `openspec/changes/archive/<name>/`
     (archive-not-delete), with no live reference to the old paths from
     non-openspec files.
  3. METADATA — no placeholder org/team metadata in the shipped
     surfaces (helm Chart.yaml, community values, SDK/CLI package
     metadata, root package.json, CODEOWNERS owners).
  4. `--tree DIR` — a BUILT public tree contains none of the artifacts
     (used by the pins over a real publish_tree.sh build).

Seams: `--root DIR` overrides the repository root (planted-violation
pins run against temp git repos); `--tree DIR` scans a built tree.

Exit 0 clean; 1 violations; 2 usage error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# The W12.1 artifact classes — none may exist in the tracked tree, the
# working tree, or a built public tree.
TRACKED_ARTIFACT_PREFIXES = (
    "storybook-static/",
    "cli/build/",
    "docs/docs/",
    "sdk/typescript/",
    "test-results/",
    "guard-failures/",
)

ROOT_LITTER_NAME = "="
ROOT_LITTER_PATTERN = re.compile(r"^b.*\.txt$")

# Scratch openspec changes archived by W12.1 (archive-not-delete). Each
# must be ABSENT from openspec/changes/<name>/ and PRESENT under
# openspec/changes/archive/<name>/ — and no runtime-surface file may
# still reference the old path. Prose references in docs/ are historical
# narrative (doc-claim veracity is W12.8's scope); code, CI, tests, and
# manifests are import risk (W12.1 "archive-not-delete where import
# risk exists") and must follow the move.
ARCHIVED_CHANGES = (
    "arch-improvements-01",
    "backendready",
    "close-test-coverage-gaps",
    "feat1",
    "frontdev1",
    "fullcontract",
    "gapfix1",
    "odps1",
    "perfect1",
    "security-quality-review-01",
    "sonnetgapfix",
    "test2",
    "testreview1",
    "testsfix1",
    "useronboardfix",
    "workflows1",
)

# Runtime surfaces whose references to an old openspec path BREAK at
# runtime (code reads, CI jobs, test fixtures, consumed manifests).
# Excluded: docs/ prose, openspec/ itself, archive/ records, and
# READMEs/status notes under source trees.
RUNTIME_REFERENCE_DIRS = (
    ".github/",
    "scripts/",
    "tests/",
    "hub/",
    "frontend/src/",
    "frontend/e2e/",
    "cli/",
    "sdk/",
    "helm/",
)
RUNTIME_REFERENCE_FILES = {
    "Makefile",
    "Makefile.core",
    "pyproject.toml",
    "package.json",
    ".gitignore",
}

# Shipped surfaces that carry package/repo metadata — placeholder org
# hosts, fictional repos, and example.com emails must never appear in
# them (RFC-2606 example.com use in TEST fixtures is legitimate and out
# of this gate's scope by design).
PUBLIC_REPO = (
    "https://github.com/cardosop/DataInteroperabilityHubCommunityPlatform"
)
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

# Artifact-class paths that an effective .gitignore pattern must cover
# (checked via `git check-ignore` — pattern-form agnostic). Directory
# classes carry a trailing slash: check-ignore treats a slashless
# nonexistent path as a FILE, so directory-only patterns (trailing `/`)
# would never match. The preview public-tree builder ships
# untracked-but-unignored files, so the removed classes must be unable
# to silently re-enter the tree.
GITIGNORE_GUARD_PATHS = (
    "cli/build/",
    "storybook-static/",
    "sdk/typescript/",
    "mock_audit_results.json",
    "test-results/",
    "guard-failures/",
    "generated/",
    "=",
    "b12.txt",
)


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, capture_output=True, text=True, cwd=cwd, check=False
    ).stdout


def _tracked_paths(root: Path) -> list[str]:
    """`git ls-files` output; empty when the root is not a git repo."""
    return [
        line
        for line in _run(["git", "ls-files"], cwd=root).splitlines()
        if line
    ]


def _violations(root: Path) -> list[str]:
    """Collect every W12.1 contract violation at `root` (real repo)."""
    problems: list[str] = []
    tracked = _tracked_paths(root)

    # 1. Tracked tree — no committed artifact may remain.
    for prefix in TRACKED_ARTIFACT_PREFIXES:
        hits = [p for p in tracked if p.startswith(prefix)]
        if hits:
            problems.append(
                f"tracked artifact prefix {prefix!r} has {len(hits)} files "
                f"(e.g. {hits[0]})"
            )
    for rel_path in tracked:
        if "/" not in rel_path and (
            rel_path == ROOT_LITTER_NAME
            or ROOT_LITTER_PATTERN.fullmatch(rel_path)
        ):
            problems.append(f"tracked root litter file {rel_path!r}")

    mock_hits = [
        p for p in tracked if Path(p).name == "mock_audit_results.json"
    ]
    if mock_hits:
        problems.append(
            f"tracked mock_audit_results.json at {mock_hits[0]!r}"
        )

    # 2. Working tree — artifacts gone from disk, scratch changes moved.
    for prefix in TRACKED_ARTIFACT_PREFIXES:
        artifact = root / prefix.rstrip("/")
        if artifact.exists():
            problems.append(
                f"artifact exists on disk: {artifact.relative_to(root)}/"
            )
    if (root / ROOT_LITTER_NAME).exists():
        problems.append("root litter file '=' exists on disk")
    for litter in sorted(root.glob("b*.txt")):
        problems.append(f"root litter file {litter.name!r} exists on disk")

    changes_dir = root / "openspec" / "changes"
    for name in ARCHIVED_CHANGES:
        old = changes_dir / name
        archived = changes_dir / "archive" / name
        if old.exists():
            problems.append(
                f"scratch openspec change {name!r} still at its old path"
            )
        if not archived.is_dir():
            problems.append(
                f"archived openspec change {name!r} missing under "
                "openspec/changes/archive/"
            )
        if archived.is_dir() and not any(
            p.startswith(f"openspec/changes/archive/{name}/") for p in tracked
        ):
            problems.append(
                f"openspec/changes/archive/{name}/ exists but is not tracked"
            )
        # Live references to the old path break at runtime — only files
        # OUTSIDE openspec/ on runtime surfaces are checked (openspec
        # prose may narrate the archival itself; docs prose is W12.8's
        # scope). `git grep` runs against HEAD so the check is
        # index-stable and costs one subprocess per archived name.
        # `git grep` without a tree-ish searches the WORKING tree of
        # tracked files — the gate is a local pre-commit check too, so
        # uncommitted fixes must count (CI runs post-checkout where
        # working tree == HEAD).
        refs = _run(
            ["git", "grep", "-l", f"openspec/changes/{name}", "--"],
            cwd=root,
        ).splitlines()
        live = sorted(
            {
                p
                for p in refs
                if not p.startswith("openspec/")
                and not p.endswith(".md")
                and (
                    p.startswith(RUNTIME_REFERENCE_DIRS)
                    or p in RUNTIME_REFERENCE_FILES
                )
            }
        )
        if live:
            problems.append(
                f"live references to old path openspec/changes/{name}/ "
                f"in {live}"
            )

    # 3. .gitignore coverage — removed classes cannot silently return.
    if (root / ".gitignore").exists():
        for guard in GITIGNORE_GUARD_PATHS:
            result = subprocess.run(
                ["git", "check-ignore", "-q", guard],
                cwd=root,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                problems.append(f"{guard!r} is not covered by .gitignore")

    # 4. Placeholder metadata in the shipped surfaces.
    for rel in METADATA_FILES:
        path = root / rel
        if not path.exists():
            problems.append(f"metadata file missing: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if "your-org" in lowered:
            problems.append(f"placeholder 'your-org' in {rel}")
        if "github.com/datahub/" in lowered:
            problems.append(f"fictional repo github.com/datahub/ in {rel}")
        if "github.com/example/" in lowered:
            problems.append(f"fictional repo github.com/example/ in {rel}")
        if "@example.com" in lowered:
            problems.append(f"placeholder @example.com email in {rel}")

    helm_chart = root / "helm" / "Chart.yaml"
    if helm_chart.exists():
        helm_text = helm_chart.read_text(encoding="utf-8")
        if f"home: {PUBLIC_REPO}" not in helm_text:
            problems.append("helm/Chart.yaml home is not the public repo URL")

    root_pkg = root / "package.json"
    if root_pkg.exists():
        pkg_text = root_pkg.read_text(encoding="utf-8")
        if '"license": "UNLICENSED"' in pkg_text:
            problems.append('root package.json license is "UNLICENSED"')
        if '"url": "."' in pkg_text:
            problems.append('root package.json repository.url is "."')

    codeowners = root / ".github" / "CODEOWNERS"
    if codeowners.exists():
        codeowners_text = codeowners.read_text(encoding="utf-8")
        for line in codeowners_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            owners = [tok for tok in stripped.split() if tok.startswith("@")]
            bad = [o for o in owners if o != "@cardosop"]
            if bad:
                hint = " (unresolvable @meshant/ team)" if any(
                    o.startswith("@meshant/") for o in bad
                ) else ""
                problems.append(
                    f"CODEOWNERS owner {bad} is not the repo owner @cardosop"
                    f"{hint}: {stripped!r}"
                )
        # Only RULES count — comments may narrate the W12.1 deletion.
        for line in codeowners_text.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            if "sdk/typescript/" in line:
                problems.append(
                    "CODEOWNERS still carries a rule for deleted "
                    "sdk/typescript/"
                )

    return problems


def _tree_violations(tree: Path) -> list[str]:
    """Scan a BUILT public tree for the W12.1 artifact classes."""
    problems: list[str] = []
    for prefix in TRACKED_ARTIFACT_PREFIXES:
        path = tree / prefix.rstrip("/")
        if path.exists():
            problems.append(f"built tree contains {prefix}")
    if (tree / ROOT_LITTER_NAME).exists():
        problems.append("built tree contains root file '='")
    for path in sorted(tree.glob("b*.txt")):
        problems.append(f"built tree contains root litter {path.name!r}")
    if (tree / "mock_audit_results.json").exists():
        problems.append("built tree contains mock_audit_results.json")
    for name in ARCHIVED_CHANGES:
        if (tree / "openspec" / "changes" / name).exists():
            problems.append(f"built tree contains openspec/changes/{name}/")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GATE-55 — shipped-tree litter check (W12.1)"
    )
    parser.add_argument(
        "--root", default=str(_REPO_ROOT), help="repo root override"
    )
    parser.add_argument("--tree", help="scan a BUILT public tree at DIR")
    args = parser.parse_args(argv)

    if args.tree:
        problems = _tree_violations(Path(args.tree))
        subject = f"built tree {args.tree}"
    else:
        root = Path(args.root).resolve()
        problems = _violations(root)
        subject = f"repo root {root}"

    if problems:
        print(f"shipped-tree litter check FAILED ({subject}):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"shipped-tree litter check clean ({subject})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
