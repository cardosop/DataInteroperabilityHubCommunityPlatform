#!/usr/bin/env python3
"""
P2-2 (close-oss-release-conditions) — the G4 origin-refs cleanup.

After the force-push, the server-side refs that still fork the tainted
lineage are removed: every OPEN pull request is closed (the rewritten
push invalidates them — their heads still reference the old SHAs), and
every ``dependabot/*`` branch is deleted (the stale dependabot
branches fork the tainted history). The pushed heads (main, prepro01,
staging, release/mvp-v1) are NEVER in the cleanup set — the
classification is a pure function and pinned as such.

Modes:

  plan (default) — enumerate via the REAL GitHub API and print the
      actions without mutating anything (exit 0 on a readable remote);
  --execute      — apply the plan (close PRs, delete the stale
      dependabot branches) via the REAL API; each mutation is printed
      as it lands; any API failure exits 2.

Fail-closed: a missing gh CLI or an API error is a failure, never
"assume clean". The window runner
(``scripts/run_history_rewrite_window.py``) gates the execute mode
behind the post-push sweep.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )


def cleanup_branches(branches: list[str]) -> list[str]:
    """The pure classification: stale dependabot branches only. The
    pushed heads and every other branch are never touched."""
    return sorted(b for b in branches if b.startswith("dependabot/"))


def _api_json(*args: str) -> list:
    """gh api + --jq + --paginate emits newline-delimited JSON objects
    (one per row, per page); a plain call emits one JSON array. Parse
    both shapes."""
    result = _gh("api", *args)
    if result.returncode != 0:
        raise RuntimeError(
            f"gh api failed: {result.stderr.strip()[:200]}"
        )
    try:
        loaded = json.loads(result.stdout or "[]")
        return loaded if isinstance(loaded, list) else [loaded]
    except json.JSONDecodeError:
        rows = []
        for raw in result.stdout.splitlines():
            row = raw.strip()
            if row:
                rows.append(json.loads(row))
        return rows


def open_pull_requests(slug: str) -> list[dict]:
    return _api_json(
        f"repos/{slug}/pulls?state=open",
        "--jq", ".[] | {number, title, headRefName: .head.ref, createdAt: .created_at}",
        "--paginate",
    )


def remote_branches(slug: str) -> list[str]:
    # --jq '.[].name' emits each name as a RAW string line (not JSON)
    result = _gh(
        "api", f"repos/{slug}/branches?per_page=100",
        "--jq", ".[].name", "--paginate",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh api failed: {result.stderr.strip()[:200]}"
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def plan(slug: str) -> tuple[list[dict], list[str]]:
    prs = open_pull_requests(slug)
    stale = cleanup_branches(remote_branches(slug))
    return prs, stale


def execute(slug: str, prs: list[dict], stale: list[str]) -> list[str]:
    actions: list[str] = []
    for pr in prs:
        result = _gh("pr", "close", str(pr["number"]), "--repo", slug)
        if result.returncode != 0:
            raise RuntimeError(f"gh pr close #{pr['number']} failed: {result.stderr.strip()[:200]}")
        actions.append(f"closed PR #{pr['number']} ({pr['headRefName']})")
    for branch in stale:
        result = _gh(
            "api", "-X", "DELETE",
            f"repos/{slug}/git/refs/heads/{branch}",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"branch delete failed for {branch}: {result.stderr.strip()[:200]}"
            )
        actions.append(f"deleted branch {branch}")
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="'owner/repo' slug")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    if not shutil.which("gh"):
        print("ERROR: gh CLI not found — the cleanup cannot be verified "
              "(fail-closed)", file=sys.stderr)
        return 2
    try:
        prs, stale = plan(args.repo)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"CLEANUP PLAN for {args.repo}:")
    print(f"  open PRs to close: {len(prs)}")
    for pr in prs:
        print(f"    PR #{pr['number']} '{pr['title'][:60]}' "
              f"(branch {pr['headRefName']}, opened {pr['createdAt'][:10]})")
    print(f"  stale dependabot branches to delete: {len(stale)}")
    for branch in stale:
        print(f"    {branch}")
    if not args.execute:
        print("PLAN ONLY — re-run with --execute (window-gated) to apply")
        return 0
    try:
        for action in execute(args.repo, prs, stale):
            print(f"EXECUTED: {action}")
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print("CLEANUP COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
