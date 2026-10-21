#!/usr/bin/env python3
"""
P2-4 (close-oss-release-conditions) — the tag-publication executor.

One-shot execution tool (NOT in the always-on battery). Runs AFTER the
P2-2 force-push:

  --plan     (default) — enumerate the real remote tag state and print
             the planned actions without mutating anything;
  --execute  — gated on ``--expect-main <sha>`` (the rewritten main
             commit from the P2-2 record): the LOCAL main HEAD must
             equal it (the clean-main gate — a wrong anchor refuses),
             then:
               1. (re-)create the annotated ``v0.1.0`` at main HEAD
                  (``--force`` replaces a pre-existing tainted tag —
                  ``git tag -fa``);
               2. delete every legacy/tainted tag (the ``v2026.*`` +
                  archive classes) on the remotes via the REAL GitHub
                  API (SKIPPED for non-GitHub remote URLs — the
                  fixture shape);
               3. push the release tag to the remotes in order (real
                  git push).

The classification is a pinned pure function: the release tag is
re-created, never deleted.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

RELEASE_TAG = "v0.1.0"
TAG_MESSAGE = "v0.1.0 — first public (OSS) release"
ORIGIN_SLUG = "cardosop/DataInteroperabilityHub"
PUBLIC_SLUG = "cardosop/DataInteroperabilityHubCommunityPlatform"


def legacy_tags(tag_names: list[str]) -> list[str]:
    """The legacy/tainted classes: the date-stamped release tags
    (``v20YY.MM.DD`` — the W9.1-era convention) and the archive
    prefix. A future SEMVER release tag (``v<semver>``, the
    release-please shape) is never in the deletion set."""
    legacy = []
    for name in tag_names:
        if name == RELEASE_TAG:
            continue
        if name.startswith("archive/"):
            legacy.append(name)
            continue
        if re.match(r"^v20\d\d\.\d\d\.\d\d$", name):
            legacy.append(name)
    return sorted(legacy)


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )


def remote_tags_via_api(slug: str) -> list[str]:
    result = _gh(
        "api", f"repos/{slug}/tags?per_page=100",
        "--jq", ".[].name", "--paginate",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh api failed for {slug}: {result.stderr.strip()[:200]}"
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def remote_tags_via_git(remote_url: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-remote", remote_url, "refs/tags/*"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ls-remote failed for {remote_url}: {result.stderr.strip()[:200]}"
        )
    return [
        line.split()[1].removeprefix("refs/tags/")
        for line in result.stdout.splitlines()
    ]


def plan(remote_url: str, github_slug: str | None) -> None:
    print(f"TAG PUBLICATION PLAN ({remote_url}):")
    try:
        names = remote_tags_via_git(remote_url)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    legacy = legacy_tags(names)
    print(f"  remote tags now: {sorted(names) or '(none)'}")
    print(f"  1. (re-)create annotated {RELEASE_TAG} at local main HEAD")
    print(f"     message: {TAG_MESSAGE!r}")
    if github_slug:
        print(f"  2. delete legacy/tainted tags on {github_slug}: {legacy}")
    else:
        print(f"  2. legacy-tag deletion SKIPPED (non-GitHub URL; "
              f"{len(legacy)} legacy tag(s) on the remote)")
    print(f"  3. push {RELEASE_TAG} to the remote")
    print("PLAN ONLY — re-run with --execute (gated on --expect-main)")


def execute(
    repo_root: Path,
    remote_url: str,
    github_slug: str | None,
    expect_main: str,
    force: bool,
) -> None:
    head = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    if head != expect_main:
        print(
            f"HALTED: local main HEAD is {head[:12]}, "
            f"--expect-main is {expect_main[:12]} — the tag must anchor "
            f"the verified rewritten main (the P2-2 record's SHA)"
        )
        raise SystemExit(1)
    tag_args = ["tag", "-a", RELEASE_TAG, "-m", TAG_MESSAGE]
    if force:
        tag_args = ["tag", "-fa", RELEASE_TAG, "-m", TAG_MESSAGE]
    created = subprocess.run(
        ["git", "-C", str(repo_root), *tag_args],
        capture_output=True, text=True, check=False,
    )
    if created.returncode != 0:
        print(f"HALTED: tag creation failed: {created.stderr.strip()[:200]}")
        raise SystemExit(1)
    print(f"tag {RELEASE_TAG} (re-)created at {head[:12]}")

    if github_slug:
        if not shutil.which("gh"):
            print("HALTED: gh CLI not found — the legacy-tag deletion "
                  "cannot run (fail-closed)")
            raise SystemExit(2)
        try:
            legacy = legacy_tags(remote_tags_via_api(github_slug))
        except RuntimeError as exc:
            print(f"HALTED: {exc}")
            raise SystemExit(2) from exc
        for name in legacy:
            deleted = _gh(
                "api", "-X", "DELETE",
                f"repos/{github_slug}/git/refs/tags/{name}",
            )
            if deleted.returncode != 0:
                print(f"HALTED: tag delete failed for {name}: "
                      f"{deleted.stderr.strip()[:200]}")
                raise SystemExit(2)
            print(f"deleted legacy tag {name} on {github_slug}")
    else:
        print("legacy-tag deletion SKIPPED (non-GitHub remote URL)")

    # --force: a re-anchored tag (moved from the tainted commit to the
    # clean main) is REJECTED by the remote without it — and forcing a
    # fresh tag is harmless. This is the re-anchor semantics itself.
    pushed = subprocess.run(
        ["git", "-C", str(repo_root), "push", "--force", remote_url,
         f"refs/tags/{RELEASE_TAG}"],
        capture_output=True, text=True, check=False,
    )
    if pushed.returncode != 0:
        print(f"HALTED: tag push failed: {pushed.stderr.strip()[:200]}")
        raise SystemExit(1)
    print(f"pushed {RELEASE_TAG} to {remote_url}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_ROOT)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--remote", help="git remote name")
    target.add_argument("--remote-url", help="explicit URL (incl. file:// for fixtures)")
    parser.add_argument("--slug", default=None, help="owner/repo for the gh API leg")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expect-main", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    remote_url = args.remote_url
    github_slug = args.slug
    if args.remote:
        resolved = subprocess.run(
            ["git", "-C", str(args.repo_root), "remote", "get-url", args.remote],
            capture_output=True, text=True, check=False,
        )
        if resolved.returncode != 0:
            print(f"ERROR: git remote '{args.remote}' does not exist")
            return 2
        remote_url = resolved.stdout.strip()
        if "github.com" in remote_url and github_slug is None:
            github_slug = (
                ORIGIN_SLUG if args.remote == "origin" else PUBLIC_SLUG
            )
    if not args.execute:
        plan(remote_url, github_slug)
        return 0
    if not args.expect_main:
        print("HALTED: --execute requires --expect-main <sha> (the "
              "rewritten main from the P2-2 record)")
        return 1
    try:
        execute(
            args.repo_root, remote_url, github_slug,
            args.expect_main, args.force,
        )
    except SystemExit as exc:
        return exc.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
