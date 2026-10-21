#!/usr/bin/env python3
"""
P2-5 (close-oss-release-conditions, G3) — the public-repo replacement executor.

One-shot execution tool (NOT in the always-on battery). The public repo's
tainted history (measured 2026-10-20: 1,736 gitleaks findings across 4 deep
pre-resync commits — Playwright E2E traces carrying JWTs + API keys) can
never be removed by append-only publishes. Delete-and-recreate removes the
lineage, the PR refs (`refs/pull/*` survive force-pushes), the forking
branches, the legacy tags AND any dangling objects GitHub retains — the
root-cause close, chosen over force-push (0 stars / 0 forks / 0 watchers at
execution time, so no community state is lost).

  plan    --repo OWNER/REPO [--backup-dir DIR] [--taint-shas SHA,...]
          read-only: the live metadata (visibility, push-protection state,
          stars/forks/watchers, open PRs, settings to restore), the
          precondition verdicts, and — when a backup mirror is given — the
          TAINT classification of every ref (which refs fork the tainted
          lineage). Exit 1 when a precondition fails.

  execute --repo OWNER/REPO --backup-dir DIR --yes
          irreversibly: (1) re-verify the preconditions live, (2) run the
          BACKUP GUARD — the backup mirror must be fsck-clean and must
          cover every live ref at the same SHA (a torn backup refuses the
          delete), (3) delete the repo, (4) recreate it public with the
          original description/topics/homepage, (5) re-arm secret-scanning
          push protection BEFORE any sync (the G12 ordering — the P0-9
          publish pre-flight refuses an unprotected remote), (6) verify
          the recreated repo (public, push protection enabled, empty).

Exit codes: 0 ok · 1 plan/precondition violation · 2 tooling/API failure.

The rollback path is the backup mirror: recreate the repo and
`git push --mirror` the backup back into it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

PUBLIC_SLUG = "cardosop/DataInteroperabilityHubCommunityPlatform"

# The four commits measured (gitleaks, house config, 2026-10-20) to carry
# the public repo's tainted content — the deep pre-resync lineage.
DEFAULT_TAINT_SHAS = [
    "04231b9f21",
    "315762ae1f",
    "9a085e00d9",
    "ec348f7bbf",
]

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_FAILURE = 2


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )


def repo_metadata(slug: str) -> dict:
    """The live repo state via the real GitHub API. Raises RuntimeError
    on any API/tooling failure (fail-closed — never assume)."""
    result = _gh(
        "api",
        f"repos/{slug}",
        "--jq",
        "{visibility: .visibility, description: .description, homepage: .homepage, "
        "topics: .topics, has_wiki: .has_wiki, default_branch: .default_branch, "
        "stars: .stargazers_count, forks: .forks_count, watchers: .subscribers_count, "
        "ssh_url: .ssh_url, "
        "push_protection: .security_and_analysis.secret_scanning_push_protection.status}",
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh api repos/{slug} failed: {result.stderr.strip()[:200]}")
    return json.loads(result.stdout)


def open_pull_count(slug: str) -> int:
    result = _gh(
        "api", f"repos/{slug}/pulls?state=open&per_page=100", "--jq", "length"
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh api pulls failed: {result.stderr.strip()[:200]}")
    return int(result.stdout.strip() or "0")


def plan_state(metadata: dict) -> dict:
    """The state dict the preconditions + plan rendering consume (a copy
    — callers never mutate the API snapshot)."""
    return dict(metadata)


def precondition_problems(state: dict) -> list[str]:
    """The G12 ordering + scope preconditions: the public repo must be
    PUBLIC and push protection must be ENABLED before the replacement
    (the recreated repo is re-armed before the first sync)."""
    problems: list[str] = []
    if state.get("visibility") != "public":
        problems.append("visibility is not public — this tool only manages the public repo")
    if state.get("push_protection") != "enabled":
        problems.append(
            "secret-scanning push protection is not enabled (G12: enable it "
            "BEFORE the first re-sync)"
        )
    return problems


def classify_refs(backup_git_dir: str, taint_shas: list[str]) -> dict[str, bool]:
    """Which refs fork the tainted lineage. Pure git against the backup
    mirror: a ref is TAINTED when any taint SHA is its ancestor."""
    refs = subprocess.run(
        ["git", "--git-dir", backup_git_dir, "for-each-ref", "--format=%(refname)"],
        capture_output=True,
        text=True,
        check=False,
    )
    if refs.returncode != 0:
        raise RuntimeError(f"for-each-ref failed on {backup_git_dir}: {refs.stderr.strip()[:200]}")
    classification: dict[str, bool] = {}
    for ref in refs.stdout.splitlines():
        tainted = False
        for sha in taint_shas:
            probe = subprocess.run(
                ["git", "--git-dir", backup_git_dir, "merge-base", "--is-ancestor", sha, ref],
                capture_output=True,
                text=True,
                check=False,
            )
            if probe.returncode == 0:
                tainted = True
                break
        classification[ref] = tainted
    return classification


def verify_backup(backup_git_dir: str, live_refs: dict[str, str]) -> list[str]:
    """The backup guard: the mirror must be fsck-clean AND cover every
    live ref at the SAME sha. Returns the problems ([] = the guard
    passes); the delete refuses on any problem."""
    problems: list[str] = []
    fsck = subprocess.run(
        ["git", "--git-dir", backup_git_dir, "fsck", "--full"],
        capture_output=True,
        text=True,
        check=False,
    )
    if fsck.returncode != 0:
        problems.append(
            f"backup fsck is not clean: {fsck.stderr.strip()[:300] or fsck.stdout.strip()[:300]}"
        )
    for ref, sha in sorted(live_refs.items()):
        probe = subprocess.run(
            ["git", "--git-dir", backup_git_dir, "rev-parse", "--verify", f"{ref}^{{object}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0:
            problems.append(f"live ref {ref} is not covered by the backup")
            continue
        if probe.stdout.strip() != sha:
            problems.append(
                f"live ref {ref} moved since the backup (backup={probe.stdout.strip()[:12]} live={sha[:12]})"
            )
    return problems


def render_plan(state: dict) -> str:
    """The plan rendering — the human half of the --plan command."""
    lines = [
        f"repo: {state.get('slug', '?')}",
        f"visibility: {state.get('visibility', '?')} · default branch: {state.get('default_branch', '?')}",
        f"push protection: {state.get('push_protection', '?')}",
        f"stars: {state.get('stars', 0)} · forks: {state.get('forks', 0)} · watchers: {state.get('watchers', 0)}",
        f"{state.get('open_pulls', 0)} open pull requests (deleted with the repo)",
        "",
        "action: delete-and-recreate the repo, then re-arm push protection",
        "BEFORE the first publish_public.sh sync",
    ]
    if state.get("description"):
        lines.append(f"restore description: {state['description']!r}")
    if state.get("homepage"):
        lines.append(f"restore homepage: {state['homepage']!r}")
    if state.get("topics"):
        lines.append(f"restore topics: {', '.join(state['topics'])}")
    refs = state.get("refs") or {}
    if refs:
        lines.append("")
        lines.append(f"ref inventory ({len(refs)} refs — deleted wholesale):")
        for ref in sorted(refs):
            lines.append(f"  {ref}  {'TAINTED' if refs[ref] else 'clean'}")
    return "\n".join(lines) + "\n"


def _push_protection_tool(*args: str) -> subprocess.CompletedProcess[str]:
    """The P0-9 tool stays the single implementation of the G12
    push-protection control — invoked as a subprocess, never duplicated."""
    return subprocess.run(
        [
            sys.executable,
            str(_ROOT / "scripts" / "check_push_protection.py"),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def arm_push_protection(slug: str) -> None:
    result = _push_protection_tool("set", "--repo", slug, "--state", "enabled")
    if result.returncode != 0:
        raise RuntimeError(
            f"push-protection re-arm failed: {result.stderr.strip()[:200]}"
        )


def verify_recreated(slug: str) -> None:
    metadata = repo_metadata(slug)
    if metadata["visibility"] != "public":
        raise RuntimeError("recreated repo is not public")
    check = _push_protection_tool("check", "--repo", slug, "--expect", "enabled")
    if check.returncode != 0:
        raise RuntimeError(
            f"recreated repo lacks push protection: {check.stderr.strip()[:200]}"
        )
    branches = _gh("api", f"repos/{slug}/branches", "--jq", "length")
    if branches.returncode != 0 or branches.stdout.strip() not in ("0", ""):
        raise RuntimeError("recreated repo is not empty — refusing to sync over unknown content")


def cmd_plan(args: argparse.Namespace) -> int:
    metadata = repo_metadata(args.repo)
    state = dict(metadata)
    state["slug"] = args.repo
    state["open_pulls"] = open_pull_count(args.repo)
    if args.backup_dir:
        state["refs"] = classify_refs(args.backup_dir, args.taint_shas)
    problems = precondition_problems(state)
    print(render_plan(state))
    if problems:
        print("PRECONDITIONS FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return EXIT_VIOLATION
    print("preconditions: OK (public + push protection enabled)")
    return EXIT_OK


def _live_refs(ssh_url: str) -> dict[str, str] | None:
    ls_remote = subprocess.run(
        ["git", "ls-remote", ssh_url],
        capture_output=True,
        text=True,
        check=False,
    )
    if ls_remote.returncode != 0:
        print(f"refusing: cannot enumerate live refs ({ls_remote.stderr.strip()[:200]})")
        return None
    live_refs: dict[str, str] = {}
    for line in ls_remote.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        live_refs[ref] = sha
    return live_refs


def _delete_and_recreate(slug: str, metadata: dict) -> int:
    """The irreversible sequence — returns the first failure code or
    EXIT_OK. Separated from cmd_execute so the guard ladder stays
    reviewable in one screen."""
    deleted = _gh("repo", "delete", slug, "--yes")
    if deleted.returncode != 0:
        print(f"delete failed: {deleted.stderr.strip()[:300]}")
        return EXIT_FAILURE
    print(f"deleted {slug}")

    create_args = ["repo", "create", slug, "--public"]
    if metadata.get("description"):
        create_args += ["--description", metadata["description"]]
    created = _gh(*create_args)
    if created.returncode != 0:
        print(f"recreate failed: {created.stderr.strip()[:300]}")
        return EXIT_FAILURE
    print(f"recreated {slug} (public, empty)")

    edit_args = ["repo", "edit", slug]
    if metadata.get("homepage"):
        edit_args += ["--homepage", metadata["homepage"]]
    for topic in metadata.get("topics") or []:
        edit_args += ["--add-topic", topic]
    if len(edit_args) > 3:
        edited = _gh(*edit_args)
        if edited.returncode != 0:
            print(f"warning: settings restore failed: {edited.stderr.strip()[:200]}")
    else:
        print("no homepage/topics to restore")

    arm_push_protection(slug)
    print("push protection re-armed (G12: BEFORE the first sync)")
    verify_recreated(slug)
    print("recreated repo verified: public + push protection enabled + empty")
    return EXIT_OK


def cmd_execute(args: argparse.Namespace) -> int:
    if not args.yes:
        print("--execute is IRREVERSIBLE (repo deletion) — pass --yes to confirm")
        return EXIT_VIOLATION
    metadata = repo_metadata(args.repo)
    state = dict(metadata)
    state["slug"] = args.repo
    problems = precondition_problems(state)
    if problems:
        for problem in problems:
            print(f"refusing: {problem}")
        return EXIT_VIOLATION

    # Backup guard: every live ref must be covered at the same SHA.
    live_refs = _live_refs(metadata["ssh_url"])
    if live_refs is None:
        return EXIT_FAILURE
    guard_problems = verify_backup(args.backup_dir, live_refs)
    if guard_problems:
        print("refusing: the backup guard failed — the delete must not run on a torn backup:")
        for problem in guard_problems:
            print(f"  - {problem}")
        return EXIT_VIOLATION
    print(f"backup guard: OK ({len(live_refs)} live refs covered, fsck clean)")

    result = _delete_and_recreate(args.repo, metadata)
    if result != EXIT_OK:
        return result
    print("")
    print("NEXT: realign the local public checkout and run publish_public.sh:")
    print("  git -C <public-checkout> fetch --prune public")
    print("  (publish_public.sh bootstraps the ROOT lineage)")
    print("ROLLBACK: recreate the repo and `git push --mirror` the backup:")
    print(f"  git push --mirror {metadata['ssh_url']}  # from {args.backup_dir}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="enumerate the live state + planned actions (read-only)")
    plan.add_argument("--repo", default=PUBLIC_SLUG, help=f"owner/repo (default: {PUBLIC_SLUG})")
    plan.add_argument("--backup-dir", help="backup mirror for the taint classification")
    plan.add_argument(
        "--taint-shas",
        default=",".join(DEFAULT_TAINT_SHAS),
        help="comma-separated tainted commit SHAs (default: the measured P2-5 set)",
    )
    execute = sub.add_parser("execute", help="delete-and-recreate the repo (irreversible)")
    execute.add_argument("--repo", default=PUBLIC_SLUG, help=f"owner/repo (default: {PUBLIC_SLUG})")
    execute.add_argument("--backup-dir", required=True, help="the verified backup mirror")
    execute.add_argument("--yes", action="store_true", help="confirm the irreversible delete")
    args = parser.parse_args(argv)

    if args.command == "plan":
        args.taint_shas = [s for s in args.taint_shas.split(",") if s]
        return cmd_plan(args)
    return cmd_execute(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(EXIT_FAILURE)
