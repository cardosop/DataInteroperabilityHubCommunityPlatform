#!/usr/bin/env python3
"""
P2-4 (close-oss-release-conditions) — the tag↔main anchor checker.

The P2-4 acceptance contract, one-shot execution tool (NOT in the
always-on battery — the pre-window state is legitimately RED until
the P2-2 force-push lands):

- the annotated release tag (``v0.1.0``) exists locally and PEELS to
  main's HEAD (the rewritten clean main — the anchor; a lightweight
  tag is a violation: release-please needs the tag object);
- the release-please manifest (``.release-please-manifest.json``),
  the ``VERSION`` file and the top release section of
  ``CHANGELOG.md`` all agree on the same version (the G9
  desync contract — a manually re-created tag must not drift the
  release history);
- the remotes carry NO legacy/tainted tags: ``--remote-url`` /
  ``--remote NAME`` adds the remote leg — the release tag must peel
  to the SAME commit as the local main HEAD, and every other tag on
  the remote is a legacy/tainted-tag violation (the ``v2026.*`` +
  archive classes).

Exit 0 anchored + clean / 1 contract violations (each named) /
2 cannot verify (fail-closed).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

RELEASE_TAG_DEFAULT = "v0.1.0"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _peel(repo: Path, ref: str) -> str:
    """The commit a ref points at (peels annotated tags)."""
    result = _git(repo, "rev-list", "-n", "1", ref)
    return result.stdout.strip()


def local_anchor_problems(repo: Path, tag: str, version: str) -> list[str]:
    """The local contract: annotated tag at main HEAD + the
    manifest/VERSION/CHANGELOG agreement."""
    problems: list[str] = []
    if _git(repo, "rev-parse", "--git-dir").returncode != 0:
        return [f"{repo} is not a git repo"]
    kind = _git(repo, "cat-file", "-t", tag).stdout.strip()
    if kind != "tag":
        problems.append(
            f"tag {tag} is {kind or 'missing'}, not an annotated tag "
            f"(release-please needs the tag object)"
        )
        return problems
    tag_commit = _peel(repo, tag)
    main_head = _peel(repo, "main")
    if tag_commit != main_head:
        problems.append(
            f"tag {tag} peels to {tag_commit[:12]}, main HEAD is "
            f"{main_head[:12]} — not anchored to the clean main"
        )
    manifest = repo / ".release-please-manifest.json"
    if not manifest.exists():
        problems.append("release-please manifest missing")
    else:
        try:
            data = json.loads(manifest.read_text())
        except (OSError, json.JSONDecodeError):
            data = {}
        if data.get(".") != version:
            problems.append(
                f"manifest '.' is {data.get('.')!r}, expected {version!r}"
            )
    version_file = repo / "VERSION"
    if not version_file.exists() or version_file.read_text().strip() != version:
        problems.append(
            f"VERSION file is "
            f"{version_file.read_text().strip()!r}, expected {version!r}"
        )
    changelog = repo / "CHANGELOG.md"
    if not changelog.exists():
        problems.append("CHANGELOG.md missing")
    else:
        text = changelog.read_text()
        # the release-please bracket form ("## [0.1.0] - date") and the
        # bare form ("## 0.1.0 (...)") are both valid sections
        match = re.search(r"^##\s+\[?(\d+\.\d+\.\d+)\]?", text, re.M)
        top = match.group(1) if match else None
        if top != version:
            problems.append(
                f"CHANGELOG top release section is {top!r}, "
                f"expected {version!r}"
            )
    return problems


def legacy_tag(tag_name: str, release_tag: str) -> bool:
    """Every tag other than the release tag is a legacy/tainted tag
    for the tag-publication contract."""
    return tag_name != release_tag


def remote_problems(repo: Path, remote_url: str, tag: str) -> list[str]:
    """The remote leg: the release tag peels to the local main HEAD
    and NO other tag exists on the remote."""
    problems: list[str] = []
    listed = subprocess.run(
        ["git", "ls-remote", remote_url, "refs/tags/*"],
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode != 0:
        return [f"ls-remote failed for {remote_url}: {listed.stderr.strip()[:200]}"]
    tags: dict[str, str] = {}
    for line in listed.stdout.splitlines():
        sha, ref = line.split()
        name = ref.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            continue
        tags[name] = sha
    if tag not in tags:
        problems.append(f"remote {remote_url} does not carry tag {tag}")
    else:
        peeled = subprocess.run(
            ["git", "ls-remote", remote_url, f"refs/tags/{tag}^{{}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        remote_commit = peeled.stdout.split()[0] if peeled.stdout.strip() else ""
        main_head = _peel(repo, "main")
        if remote_commit != main_head:
            problems.append(
                f"remote tag {tag} peels to {remote_commit[:12]}, "
                f"local main HEAD is {main_head[:12]}"
            )
    for name in sorted(tags):
        if legacy_tag(name, tag):
            problems.append(f"legacy/tainted tag still on the remote: {name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=_ROOT)
    parser.add_argument("--tag", default=RELEASE_TAG_DEFAULT)
    parser.add_argument("--version", default="0.1.0")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--remote", help="git remote name (URL resolved via git)")
    target.add_argument("--remote-url", help="explicit URL (incl. file:// for fixtures)")
    args = parser.parse_args(argv)

    problems = local_anchor_problems(args.repo, args.tag, args.version)
    if args.remote or args.remote_url:
        remote_url = args.remote_url
        if args.remote:
            resolved = subprocess.run(
                ["git", "-C", str(args.repo), "remote", "get-url", args.remote],
                capture_output=True,
                text=True,
                check=False,
            )
            if resolved.returncode != 0:
                print(f"FAIL: git remote '{args.remote}' does not exist")
                return 2
            remote_url = resolved.stdout.strip()
        problems.extend(remote_problems(args.repo, remote_url, args.tag))
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"ANCHOR CHECK FAILED: {len(problems)} problem(s)")
        return 1
    print(
        f"ANCHORED: tag {args.tag} peels to main HEAD "
        f"({_peel(args.repo, args.tag)[:12]}) — manifest/VERSION/CHANGELOG "
        f"agree on {args.version}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
