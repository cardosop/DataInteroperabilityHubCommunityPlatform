#!/usr/bin/env python3
"""
P2-2 (close-oss-release-conditions) — the maintenance-window RUNNER.

One-shot execution tool (NOT in the always-on battery): drives the
ordered P2-2 checklist with the machine-enforced G12 contract. The
step ORDER makes "enable push protection first" unrepresentable — the
enablement runs only after the force-push landed and the post-push
sweep is green:

  1. zero-live-pytest          scripts/check_no_live_tests.py exit 0
  2. rotation-gate             scripts/check_history_rotation_map.py
                               exit 0 (GATE-65 — the force-push gate:
                               PENDING rotations HALT Phase 2)
  3. inputs-ready              the P2-0 fragments file exists and
                               carries entries
  4. mirror-ready              --mirror is a git repository (the P2-1
                               rewritten mirror; this runner does NOT
                               build it)
  5. pre-window-push-protection  check_push_protection.py check
                               --expect disabled (an enabled origin
                               blocks the rewritten push mid-flight —
                               G12)
  6. force-push                git push --force <mirror> <remote>
                               refs/heads/* — requires
                               --confirm-force-push
  7. post-push-sweep           sweep_remote_fragments.py over the
                               remote (a reachable fragment HALTS the
                               window — the dangling-object
                               support-ticket path in the runbook)
  8. refs-cleanup              cleanup_origin_refs.py --execute
                               (open PRs + stale dependabot branches —
                               G4)
  9. actions-review            review_actions_artifacts.py plan
                               (the G4 Actions review; purge decisions
                               recorded from the output)
 10. enable-push-protection    check_push_protection.py set --state
                               enabled + check --expect enabled
                               (G12: origin AFTER, never during)

Every failed precondition HALTS the run before the next destructive
step and exits 1.  The GitHub-dependent steps (5, 8, 9, 10) are
REPORTED SKIPPED when --remote-url is not a GitHub URL (the fixture
shape); they run against the real API in the live window.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

WINDOW_STEPS: list[tuple[str, str]] = [
    ("zero-live-pytest", "the live-pytest guard (scripts/check_no_live_tests.py)"),
    ("rotation-gate", "GATE-65 (scripts/check_history_rotation_map.py) — the force-push gate"),
    ("inputs-ready", "the P2-0 fragments file exists and carries entries"),
    ("mirror-ready", "--mirror is a git repository (the P2-1 rewritten mirror)"),
    ("pre-window-push-protection", "origin push protection is DISABLED (G12 pre-window)"),
    ("force-push", "git push --force <mirror> <remote> refs/heads/*"),
    ("post-push-sweep", "sweep_remote_fragments.py — every fragment unreachable on the remote"),
    ("refs-cleanup", "cleanup_origin_refs.py --execute (open PRs + dependabot branches, G4)"),
    ("actions-review", "review_actions_artifacts.py plan (the G4 Actions review)"),
    ("enable-push-protection", "origin push protection ENABLED after the push + sweep (G12)"),
]

GITHUB_URL_MARKERS = ("github.com",)


def _is_github_url(url: str) -> bool:
    return any(marker in url for marker in GITHUB_URL_MARKERS)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, check=False
    )


class WindowHalt(Exception):
    """A precondition failure — the window stops at this step."""


def _halt(message: str) -> None:
    print(message)
    raise WindowHalt


def run_window(args: argparse.Namespace) -> int:
    """Drive the checklist; return 0 on completion, 1 on any HALT."""
    remote_url = args.remote_url
    if args.remote:
        resolved = subprocess.run(
            ["git", "-C", str(args.repo_root), "remote", "get-url", args.remote],
            capture_output=True,
            text=True,
            check=False,
        )
        if resolved.returncode != 0:
            _halt(f"HALTED at remote-resolution: git remote "
                  f"'{args.remote}' does not exist")
        remote_url = resolved.stdout.strip()
    github_remote = _is_github_url(remote_url)

    for name, description in WINDOW_STEPS:
        print(f"=== {name} — {description}")

        if name == "zero-live-pytest":
            if args.skip_guard:
                print("SKIPPED (--skip-guard — fixture/pin mode)")
                continue
            result = _run(str(args.guard_cmd))
            if result.returncode != 0:
                _halt(f"HALTED at zero-live-pytest: {result.stdout.strip()[:300]}")
            print("guard exit=0 — no live pytest/playwright runs")

        elif name == "rotation-gate":
            import os
            if not os.access(args.rotation_gate, os.X_OK):
                _halt(
                    f"HALTED at rotation-gate: {args.rotation_gate} is "
                    f"not executable — a gate that cannot run blocks the "
                    f"window (fail-closed)"
                )
            try:
                result = subprocess.run(
                    [str(args.rotation_gate)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError as exc:
                _halt(f"HALTED at rotation-gate: {exc}")
            if result.returncode != 0:
                _halt(
                    "HALTED at rotation-gate: GATE-65 reports PENDING "
                    "rotations — the force-push gate blocks Phase 2"
                )
            print("rotation gate green — every class dead-value evidenced")

        elif name == "inputs-ready":
            if not args.fragments.exists():
                _halt(f"HALTED at inputs-ready: fragments file missing: {args.fragments}")
            entries = [
                line.strip()
                for line in args.fragments.read_text().splitlines()
                if line.strip() and not line.startswith("#")
            ]
            if not entries:
                _halt("HALTED at inputs-ready: the fragments file carries no entries")
            print(f"fragments file ready ({len(entries)} entries)")

        elif name == "mirror-ready":
            check = subprocess.run(
                ["git", "-C", str(args.mirror), "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=False,
            )
            if check.returncode != 0:
                _halt(f"HALTED at mirror-ready: {args.mirror} is not a git repo "
                      f"(rebuild it in P2-1)")
            print(f"mirror ready: {args.mirror}")

        elif name == "pre-window-push-protection":
            if not github_remote:
                print("SKIPPED (non-GitHub remote — the live window runs it)")
                continue
            result = _run(
                str(_ROOT / "scripts/check_push_protection.py"),
                "check", "--remote", args.remote or "origin",
                "--expect", "disabled",
            )
            if result.returncode != 0:
                _halt(
                    "HALTED at pre-window-push-protection: origin push "
                    "protection is ENABLED — an enabled origin blocks the "
                    "rewritten push mid-flight (G12). STOP and resolve."
                )
            print("origin push protection disabled/not-configured — window may open")

        elif name == "force-push":
            if not args.confirm_force_push:
                _halt(
                    "HALTED at force-push: --confirm-force-push is required "
                    "for the destructive push (dry-run stops here)"
                )
            push = subprocess.run(
                ["git", "-C", str(args.mirror), "push", "--force",
                 remote_url, "refs/heads/*"],
                capture_output=True,
                text=True,
                check=False,
            )
            if push.returncode != 0:
                detail = push.stderr.strip().splitlines()
                tail = detail[-1] if detail else "no output"
                _halt(f"HALTED at force-push: {tail[:300]}")
            print("force-push landed")

        elif name == "post-push-sweep":
            result = _run(
                str(_ROOT / "scripts/sweep_remote_fragments.py"),
                "--fragments", str(args.fragments),
                "--remote-url", remote_url,
            )
            if result.returncode == 2:
                _halt(f"HALTED at post-push-sweep: {result.stdout.strip()[:300]}")
            if result.returncode == 1:
                _halt(
                    "HALTED at post-push-sweep: rotated fragments are still "
                    "reachable on the remote — open the dangling-object "
                    "support ticket (runbook) before enablement"
                )
            print(result.stdout.strip())

        elif name == "refs-cleanup":
            if not github_remote:
                print("SKIPPED (non-GitHub remote — the live window runs it)")
                continue
            result = _run(
                str(_ROOT / "scripts/cleanup_origin_refs.py"),
                "--repo", args.repo, "--execute",
            )
            if result.returncode != 0:
                _halt(f"HALTED at refs-cleanup: {result.stderr.strip()[:300]}")
            print("origin refs cleaned (open PRs closed, dependabot branches deleted)")

        elif name == "actions-review":
            if not github_remote:
                print("SKIPPED (non-GitHub remote — the live window runs it)")
                continue
            result = _run(
                str(_ROOT / "scripts/review_actions_artifacts.py"),
                "--repo", args.repo,
            )
            if result.returncode != 0:
                _halt(f"HALTED at actions-review: {result.stderr.strip()[:300]}")
            print("actions review recorded (purge decisions from the output)")

        elif name == "enable-push-protection":
            if not github_remote:
                print("SKIPPED (non-GitHub remote — the live window runs it)")
                continue
            result = _run(
                str(_ROOT / "scripts/check_push_protection.py"),
                "set", "--remote", args.remote or "origin", "--state", "enabled",
            )
            if result.returncode != 0:
                _halt(f"HALTED at enable-push-protection: {result.stderr.strip()[:300]}")
            result = _run(
                str(_ROOT / "scripts/check_push_protection.py"),
                "check", "--remote", args.remote or "origin", "--expect", "enabled",
            )
            if result.returncode != 0:
                _halt(f"HALTED at enable-push-protection verify: {result.stderr.strip()[:300]}")
            print("origin push protection ENABLED and verified (G12 post-push)")

    print("WINDOW COMPLETE — every step executed or reported skipped")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fragments", type=Path, required=True)
    parser.add_argument("--mirror", type=Path, required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--remote", help="git remote name (URL resolved via git)")
    target.add_argument("--remote-url", help="explicit URL (incl. file:// for fixtures)")
    parser.add_argument("--repo", default="cardosop/DataInteroperabilityHub")
    parser.add_argument("--repo-root", type=Path, default=_ROOT)
    parser.add_argument(
        "--rotation-gate",
        type=Path,
        default=_ROOT / "scripts/check_history_rotation_map.py",
    )
    parser.add_argument(
        "--guard-cmd",
        type=Path,
        default=_ROOT / "scripts/check_no_live_tests.py",
    )
    parser.add_argument("--skip-guard", action="store_true",
                        help="skip the zero-live-pytest guard (fixture/pin mode)")
    parser.add_argument("--confirm-force-push", action="store_true")
    args = parser.parse_args(argv)
    try:
        return run_window(args)
    except WindowHalt:
        return 1


if __name__ == "__main__":
    sys.exit(main())
