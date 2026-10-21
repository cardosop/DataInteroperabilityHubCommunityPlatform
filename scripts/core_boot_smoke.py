#!/usr/bin/env python3
"""Core boot + management-command smoke (313-H task 1.7) — the H.2.5 recipe,
automated for the public CI's ``core-boot-smoke`` job.

Why: the public repo has no paid layer. An unguarded paid import anywhere
in the boot path — a management command, a settings branch, a signal
handler — survives the source-scanning import-direction gates and only
explodes at RUNTIME in a contributor's checkout (or worse, on the first
production boot after a public merge). This gate runs, with
``HUB_CORE_ONLY=1``:

  1. ``manage.py check``            — Django system checks + app ``ready()``
  2. ``manage.py help``             — imports EVERY installed management
                                      command (Django imports commands to
                                      list them), the single widest
                                      import-time sweep available
  3. ``<sampled command> --help``   — argparse builds for a deterministic
                                      sample (so ``add_arguments``-time
                                      imports are exercised too)

Any nonzero exit, stderr traceback, or timeout fails the job with the
failing step named. No database is required: ``check``/``help``/``--help``
never connect.

Override hooks (tests + local debugging):
  SMOKE_SAMPLE_COMMANDS — comma-separated command names to sample
                          (default: a fixed core-app sample).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Fixed sample across core apps — deterministic in CI, representative of
# commands that do nontrivial import-time work. The env override exists
# for tests and ad-hoc debugging.
DEFAULT_SAMPLE_COMMANDS = (
    "check_services",
    "seed_demo_data",
    "validate_config",
    # process_event_outbox was retired with the event_outbox table (core
    # 0005 DeleteModel — U.7 rehearsal). Its DB-backed outbox was superseded
    # by the Event store + write-behind buffer; replay_events covers
    # reprocessing. process_dlq is the surviving periodic-queue command.
    "process_dlq",
    "expire_impersonation_sessions",
)

STEP_TIMEOUT_SECONDS = 120


def _run_step(repo: Path, manage: str, argv: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("HUB_CORE_ONLY", "1")
    return subprocess.run(
        [sys.executable, str(repo / manage), *argv],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT_SECONDS,
        env=env,
        check=False,  # exit codes ARE the smoke signal — captured, never raised
    )


def _sample_commands() -> list[str]:
    override = os.environ.get("SMOKE_SAMPLE_COMMANDS", "").strip()
    if override:
        return [name.strip() for name in override.split(",") if name.strip()]
    return list(DEFAULT_SAMPLE_COMMANDS)


def run_smoke(repo: Path, manage: str) -> int:
    """Run the boot smoke; return the process exit code (0 = pass)."""
    failures: list[str] = []

    check = _run_step(repo, manage, ["check"])
    print(f"[core-boot-smoke] manage.py check      -> exit {check.returncode}")
    if check.returncode != 0:
        failures.append("check")
        print(check.stdout[-2000:])
        print(check.stderr[-2000:])

    help_run = _run_step(repo, manage, ["help"])
    print(f"[core-boot-smoke] manage.py help       -> exit {help_run.returncode}")
    if help_run.returncode != 0:
        failures.append("help")
        print(help_run.stdout[-2000:])
        print(help_run.stderr[-2000:])

    for command in _sample_commands():
        step = _run_step(repo, manage, [command, "--help"])
        print(f"[core-boot-smoke] {command} --help    -> exit {step.returncode}")
        if step.returncode != 0 or "Traceback" in step.stderr:
            failures.append(command)
            print(step.stdout[-2000:])
            print(step.stderr[-2000:])

    if failures:
        print(f"[core-boot-smoke] FAILED steps: {', '.join(failures)}")
        return 1
    print(
        "[core-boot-smoke] all boot checks passed "
        f"(check, help, {len(_sample_commands())} sampled commands)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Core boot + command smoke")
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repo root containing manage.py (default: script's parent repo)",
    )
    parser.add_argument(
        "--manage",
        default="hub/manage.py",
        help="manage.py path relative to --repo",
    )
    args = parser.parse_args(argv)
    try:
        return run_smoke(args.repo, args.manage)
    except subprocess.TimeoutExpired:
        print(f"[core-boot-smoke] FAILED: a step exceeded {STEP_TIMEOUT_SECONDS}s")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
