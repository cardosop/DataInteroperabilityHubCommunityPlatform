#!/usr/bin/env python3
"""
check_push_protection.py — G12 secret-scanning push-protection control
(close-oss-release-conditions P0-9).

One tool for the push-protection ordering contract on BOTH remotes:

  origin:  push protection is enabled AFTER the P2 force-push lands
           (the pre-window guard proves it is OFF before the window
           opens — an enabled origin would block the rewritten push
           mid-flight);
  public:  push protection is enabled BEFORE the first re-sync — the
           publish pre-flight (scripts/publish_gates.sh,
           ``require_push_protection``) refuses to sync an unprotected
           public remote.

Commands:

  check --remote NAME | --repo OWNER/REPO --expect enabled|disabled
      exit 0 when the repo's ``secret_scanning_push_protection`` state
      matches the expectation, 1 on a state mismatch, 2 on a tooling or
      API failure.

  set   --remote NAME | --repo OWNER/REPO --state enabled|disabled
      PATCH the repo's security settings via the GitHub API; exit 0 on
      success, 2 on failure.

Fail-closed: a missing gh CLI, an unknown remote, or an API error is a
FAILURE (exit 2) — never "assume enabled".

The origin-side state is deliberately NOT pinned in the always-on
battery: until the P2 force-push lands it MUST stay OFF (G12), so any
standing "origin is enabled" assertion would violate the ordering.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_FAILURE = 2

# The three GitHub URL shapes git remotes actually take here:
# scp-style (git@github.com:o/r.git), https, and ssh://.
_GITHUB_RE = re.compile(
    r"^(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"([^/\s]+?)/([^/\s]+?)(?:\.git)?/?$"
)


def repo_slug(remote_url: str) -> str:
    """``owner/repo`` from a GitHub remote URL; ValueError otherwise."""
    match = _GITHUB_RE.match(remote_url.strip())
    if not match:
        raise ValueError(f"not a GitHub remote URL: {remote_url!r}")
    owner, name = match.groups()
    return f"{owner}/{name}"


def remote_url(repo_root: Path, name: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "remote", "get-url", name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"git remote '{name}' does not exist in {repo_root}")
    url = result.stdout.strip()
    if not url:
        raise ValueError(f"git remote '{name}' has no URL")
    return url


def _gh_api(gh_bin: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [gh_bin, "api", *args], capture_output=True, text=True, check=False
    )


def api_push_protection_state(gh_bin: str, slug: str) -> str:
    """``enabled`` / ``disabled`` / ``""`` (never configured) — the raw
    ``security_and_analysis.secret_scanning_push_protection.status``."""
    result = _gh_api(
        gh_bin,
        f"repos/{slug}",
        "--jq",
        ".security_and_analysis.secret_scanning_push_protection.status",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh api failed for {slug}: {result.stderr.strip()[:200]}"
        )
    return result.stdout.strip()


def api_set_push_protection(gh_bin: str, slug: str, state: str) -> None:
    result = _gh_api(
        gh_bin,
        "-X",
        "PATCH",
        f"repos/{slug}",
        "-f",
        f"security_and_analysis[secret_scanning_push_protection][status]={state}",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh api PATCH failed for {slug}: {result.stderr.strip()[:200]}"
        )


def state_satisfied(actual: str, expected: str) -> bool:
    """``--expect disabled`` is also satisfied by a never-configured
    repo (nothing is enabled, so the window is not blocked);
    ``--expect enabled`` requires the literal state."""
    if expected == "enabled":
        return actual == "enabled"
    return actual in ("disabled", "")


def _resolve_slug(args: argparse.Namespace) -> str:
    if args.repo:
        return str(args.repo)
    return repo_slug(remote_url(args.repo_root, args.remote))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_ROOT,
        help="checkout root for --remote resolution (default: this repo)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "set"):
        sub_parser = sub.add_parser(command)
        target = sub_parser.add_mutually_exclusive_group(required=True)
        target.add_argument(
            "--remote", help="git remote name (URL resolved via git)"
        )
        target.add_argument("--repo", help="explicit 'owner/repo' slug")
        if command == "check":
            sub_parser.add_argument(
                "--expect", choices=("enabled", "disabled"), required=True
            )
        else:
            sub_parser.add_argument(
                "--state", choices=("enabled", "disabled"), required=True
            )
    args = parser.parse_args(argv)

    gh_bin = shutil.which("gh")
    if not gh_bin:
        print(
            "ERROR: gh CLI not found — push-protection state cannot be "
            "verified (fail-closed: never assume enabled)",
            file=sys.stderr,
        )
        return EXIT_FAILURE

    try:
        slug = _resolve_slug(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_FAILURE

    actual = ""
    try:
        if args.command == "check":
            actual = api_push_protection_state(gh_bin, slug)
        else:
            api_set_push_protection(gh_bin, slug, args.state)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_FAILURE

    if args.command == "check":
        if state_satisfied(actual, args.expect):
            shown = actual or "not configured"
            print(
                f"OK: {slug} secret-scanning push protection is "
                f"{shown} (expected {args.expect})"
            )
            return EXIT_OK
        print(
            f"MISMATCH: {slug} secret-scanning push protection is "
            f"{actual or 'not configured'}, expected {args.expect}",
            file=sys.stderr,
        )
        return EXIT_MISMATCH
    print(f"OK: {slug} secret-scanning push protection set to {args.state}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
