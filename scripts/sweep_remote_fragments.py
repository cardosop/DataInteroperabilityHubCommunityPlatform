#!/usr/bin/env python3
"""
P2-2 (close-oss-release-conditions) — the post-push fragment sweep.

After the rewritten heads are force-pushed, prove on the REMOTE that
every rotated-secret fragment is unreachable: a fresh ``git clone
--mirror`` of the remote (the same fresh-clone evidence the W0.4
verifier demands), then ``git log --all -S <fragment>`` per entry of
the fragments file (the P2-0 reconstruction output —
``scripts/reconstruct_rewrite_inputs.py build``). Fragments are named
by INDEX only — the values are never printed.

Exit codes:

  0 — the remote is clean on every fragment;
  1 — at least one fragment is still reachable (the stop-the-line
      signal: the window HALTS and the dangling-object support-ticket
      path in docs/runbooks/history-rewrite-maintenance-window.md
      applies);
  2 — the sweep could not run (missing fragments file, unreachable
      remote, clone failure) — fail-closed, never "assume clean".
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def load_fragments(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def sweep(remote_url: str, fragments_file: Path, git_bin: str = "git") -> tuple[int, list[str]]:
    """(exit_code, problems) — problems name fragment indices only."""
    if not fragments_file.exists():
        return 2, [f"fragments file missing: {fragments_file}"]
    fragments = load_fragments(fragments_file)
    if not fragments:
        return 2, ["the fragments file carries no entries — a vacuous sweep is no sweep"]
    if not shutil.which(git_bin):
        return 2, [f"git binary not found: {git_bin}"]

    with tempfile.TemporaryDirectory(prefix="p22-sweep.") as tmp:
        mirror = Path(tmp) / "remote.git"
        clone = subprocess.run(
            [git_bin, "clone", "--mirror", "-q", remote_url, str(mirror)],
            capture_output=True,
            text=True,
            check=False,
        )
        if clone.returncode != 0:
            detail = clone.stderr.strip().splitlines()
            tail = detail[-1] if detail else "no output"
            return 2, [f"remote clone failed: {tail[:200]}"]
        problems: list[str] = []
        for index, fragment in enumerate(fragments):
            result = _git(mirror, "log", "--all", "--oneline", "-S", fragment)
            if result.stdout.strip():
                problems.append(
                    f"fragment #{index} reachable in "
                    f"{len(result.stdout.splitlines())} commit(s)"
                )
        return (1 if problems else 0), problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fragments", type=Path, required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--remote", help="git remote name (URL resolved via git)")
    target.add_argument("--remote-url", help="explicit URL (incl. file:// for fixtures)")
    parser.add_argument("--repo-root", type=Path, default=_ROOT)
    args = parser.parse_args(argv)

    if args.remote:
        url_result = subprocess.run(
            ["git", "-C", str(args.repo_root), "remote", "get-url", args.remote],
            capture_output=True,
            text=True,
            check=False,
        )
        if url_result.returncode != 0:
            print(f"FAIL: git remote '{args.remote}' does not exist", file=sys.stderr)
            return 2
        remote_url = url_result.stdout.strip()
    else:
        remote_url = args.remote_url

    code, problems = sweep(remote_url, args.fragments)
    if code == 2:
        for problem in problems:
            print(f"FAIL: {problem}")
        print("SWEEP FAILED: the remote could not be swept — fail-closed")
        return 2
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(
            "SWEEP FAILED: rotated fragments are still reachable on the "
            "remote — HALT the window (see the dangling-object "
            "support-ticket path in the runbook)"
        )
        return 1
    print(
        f"SWEEP: clean — every fragment unreachable on the remote "
        f"({len(load_fragments(args.fragments))} fragments, by index)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
