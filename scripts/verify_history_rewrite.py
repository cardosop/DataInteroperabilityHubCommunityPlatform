#!/usr/bin/env python3
"""
W0.4 (oss-release-remediation) — history-rewrite verifier.

Runs on a FRESH CLONE of the rewritten repository and proves the rewrite
worked:

- every LITERAL entry in the exclusion list matches no object reachable
  from any ref (the installed filter-repo build matches entries
  literally — exact file names, or directory prefixes that exclude
  everything below; the check applies the same semantics against every
  blob/tree path in ``git rev-list --all --objects``);
- every tag prefix in the tags list has no refs left;
- every secret fragment in the fragments file is unreachable
  (`git log --all -S <fragment>` must be empty — fragments are referred
  to by index only, NEVER printed);
- `git fsck` reports no errors.

The fragments file carries the rotated/leaked secret values (or their
prefixes) and lives OUTSIDE the repository — the verifier never writes
or prints its contents.

Exit 0 when the repository is clean on every check; 1 otherwise, each
problem named (without values).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
PATHS_DEFAULT = _ROOT / "scripts/history_rewrite_paths.txt"
TAGS_DEFAULT = _ROOT / "scripts/history_rewrite_tags.txt"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _all_object_paths(repo: Path) -> list[str]:
    """Every blob/tree path reachable from any ref, from one rev-list."""
    out = _git(repo, "rev-list", "--all", "--objects")
    return [line.split(" ", 1)[1] for line in out.stdout.splitlines() if " " in line]


def _reachable(repo: Path, log_args: list[str]) -> bool:
    """True when any commit across all refs matches the log arguments."""
    result = _git(repo, "log", "--all", "--oneline", *log_args)
    return bool(result.stdout.strip())


def check(
    repo: Path,
    paths_file: Path,
    fragments_file: Path,
    tags_file: Path = TAGS_DEFAULT,
) -> list[str]:
    problems: list[str] = []
    if _git(repo, "rev-parse", "--git-dir").returncode != 0:
        return [f"{repo} is not a git repo"]
    if not paths_file.exists():
        return [f"excluded-paths file missing: {paths_file}"]
    if not fragments_file.exists():
        return [f"secret-fragments file missing: {fragments_file}"]

    entries: list[str] = []
    for line in paths_file.read_text().splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        entries.append(entry)
    if entries:
        object_paths = _all_object_paths(repo)
        for entry in entries:
            # Literal semantics matching filter-repo exactly: a trailing
            # slash entry covers everything below it; a bare entry is an
            # exact file name (so `.env` must not swallow `.env.example`).
            if entry.endswith("/"):
                matched = any(path.startswith(entry) for path in object_paths)
            else:
                matched = any(path == entry for path in object_paths)
            if matched:
                problems.append(f"excluded path still reachable from a ref: {entry}")

    if tags_file.exists():
        for line in tags_file.read_text().splitlines():
            prefix = line.strip()
            if not prefix or prefix.startswith("#"):
                continue
            tags = _git(repo, "tag", "-l", f"{prefix}*")
            if tags.stdout.strip():
                problems.append(
                    f"dropped tag prefix still has refs: {prefix} "
                    f"({len(tags.stdout.splitlines())} tags)"
                )

    fragments = [
        line.strip()
        for line in fragments_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for index, fragment in enumerate(fragments):
        if _reachable(repo, ["-S", fragment]):
            problems.append(f"secret fragment #{index} still reachable from a ref")

    fsck = _git(repo, "fsck", "--full")
    bad_lines = [
        line
        for line in fsck.stdout.splitlines() + fsck.stderr.splitlines()
        if "error" in line.lower() or "missing" in line.lower()
    ]
    if fsck.returncode != 0 or bad_lines:
        problems.append(f"git fsck reported {len(bad_lines) or 'a nonzero'} error(s)")

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--paths", type=Path, default=PATHS_DEFAULT)
    parser.add_argument("--fragments", type=Path, required=True)
    parser.add_argument("--tags", type=Path, default=TAGS_DEFAULT)
    args = parser.parse_args()
    problems = check(args.repo, args.paths, args.fragments, args.tags)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"VERIFY-REWRITE FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"VERIFY-REWRITE PASSED: {args.repo} is clean on every check")
    sys.exit(0)


if __name__ == "__main__":
    main()
