"""close-test-coverage-gaps task 0.4 — the gated LOCAL driver for the live
Databricks E2E sandbox run (the ``test-batch-13-8`` Makefile target).

Mirrors the nightly workflow (``databricks-e2e-nightly.yml``) ONE-FOR-ONE
so a local operator reproduces the CI run exactly:

1. **GATE**    — ``DATABRICKS_E2E=1`` + ``DATABRICKS_E2E_ACCOUNT_ID`` +
                 ``DATABRICKS_E2E_ACCOUNT_TOKEN``, else SKIPPED with the
                 reason (exit 0 — a gated-away run is a skip, not a
                 failure) and ZERO infrastructure calls;
2. **BUDGET**  — ``python -m scripts.databricks_e2e.budget``: the hard
                 ceiling pre-flight BEFORE any create call (fail-closed:
                 a missing ceiling resolves to zero and refuses);
3. **CREATE**  — ``python -m hub.apps.databricks_admin.e2e_tooling.sandbox create`` with
                 ``GITHUB_RUN_ID`` pinned to this run's id so the
                 convention name matches the audit envelope;
4. **SUITE**   — ``pytest tests/integration/databricks_e2e -q
                 --timeout=1800 --junitxml=...`` (the suite's W16 guard
                 governs missing workspace credentials: local skip, CI
                 raise — never a silent pass);
5. **DESTROY** — ALWAYS (the idempotent ``meshant_e2e_*`` sweep — a
                 refused budget still sweeps leftovers, per sandbox.py's
                 backstop contract);
6. **AUDIT**   — ALWAYS (best-effort by construction; never masks the
                 run's exit code).

Exit code: the FIRST failing step's (budget → create → suite → destroy,
in order); 0 on success; 0 on gate-skip. The audit step never changes the
exit code. Every child runs with the repo root on ``PYTHONPATH`` so the
sequence works from any cwd, and child output is replayed to this
process's streams so one log tells the whole story.

The env keys the gate reads are the same secrets the nightly's GitHub
environment injects — nothing new for the operator to learn.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

GATE_ENV = "DATABRICKS_E2E"
ACCOUNT_ID_ENV = "DATABRICKS_E2E_ACCOUNT_ID"
ACCOUNT_TOKEN_ENV = "DATABRICKS_E2E_ACCOUNT_TOKEN"
RUN_ID_ENV = "DATABRICKS_E2E_RUN_ID"

BUDGET_MARKER = "[13-8] Budget pre-flight (hard ceiling BEFORE any create)..."
CREATE_MARKER = "[13-8] Creating the sandbox workspace..."
SUITE_MARKER = "[13-8] Running the live suite: pytest tests/integration/databricks_e2e -q --timeout=1800"
DESTROY_MARKER = "[13-8] Auto-destroy (always)..."
AUDIT_MARKER = "[13-8] Audit envelope (always)..."

REPORT_REL_DIR = Path("tests/integration/databricks_e2e/report")


def gate_skip_reason(env: Mapping[str, str]) -> str | None:
    """Why the live run cannot proceed — None when the environment is armed.

    Pure: the W16 policy governs the suite's own guards; THIS gate decides
    whether the local wrapper touches real infrastructure at all.
    """
    if str(env.get(GATE_ENV, "")).strip() != "1":
        return (
            f"{GATE_ENV}=1 is required — the live Databricks E2E run is gated "
            "(see the databricks-e2e-nightly workflow + the P9 operations runbook)"
        )
    missing = [
        name
        for name in (ACCOUNT_ID_ENV, ACCOUNT_TOKEN_ENV)
        if not str(env.get(name, "")).strip()
    ]
    if missing:
        return (
            f"missing account credentials: {', '.join(missing)} "
            "(the sandbox create/destroy steps need them)"
        )
    return None


def make_run_id(env: Mapping[str, str], *, now: datetime | None = None) -> str:
    """The run identity: operator-pinned id, then GITHUB_RUN_ID (workflow
    reuse), else a compact UTC timestamp. Feeds GITHUB_RUN_ID in the child
    env so the sandbox convention name and the audit envelope agree."""
    pinned = str(env.get(RUN_ID_ENV, "")).strip()
    if pinned:
        return pinned
    github = str(env.get("GITHUB_RUN_ID", "")).strip()
    if github:
        return github
    current = now if now is not None else datetime.now(UTC)
    return current.strftime("%Y%m%d%H%M%S")


def suite_argv(report_dir: Path) -> list[str]:
    """The suite step argv — mirrors the nightly's pytest step."""
    return [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/databricks_e2e/",
        "-q",
        "--timeout=1800",
        f"--junitxml={report_dir / 'junit.xml'}",
    ]


def _child_env(env: Mapping[str, str]) -> dict[str, str]:
    """Child env: the caller's env plus the repo root on PYTHONPATH so the
    module mains resolve from any cwd."""
    child = dict(env)
    existing = child.get("PYTHONPATH", "")
    child["PYTHONPATH"] = (
        f"{REPO_ROOT}{os.pathsep}{existing}" if existing else str(REPO_ROOT)
    )
    return child


def _step(argv: list[str], env: Mapping[str, str], cwd: Path) -> int:
    """Run one module main as a real subprocess; replay its output."""
    completed = subprocess.run(
        argv,
        env=_child_env(env),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    return completed.returncode


def run(env: Mapping[str, str] | None = None, *, cwd: Path | None = None) -> int:
    """The gated sequence.

    Returns the first failing step's exit code; 0 on success; 0 on
    gate-skip. Destroy + audit ALWAYS run once the gate passes — no
    failure path leaves a sandbox behind or loses the run evidence.
    """
    environment: Mapping[str, str] = os.environ if env is None else env
    workdir = Path.cwd() if cwd is None else Path(cwd)

    reason = gate_skip_reason(environment)
    if reason is not None:
        print(f"[13-8] SKIPPED: {reason}")
        return 0

    run_id = make_run_id(environment)
    child_env = {**environment, "GITHUB_RUN_ID": run_id}
    report_dir = workdir / REPORT_REL_DIR

    print(BUDGET_MARKER)
    budget_rc = _step(
        [sys.executable, "-m", "scripts.databricks_e2e.budget"], child_env, workdir
    )

    create_rc: int | None = None
    suite_rc: int | None = None
    if budget_rc == 0:
        print(CREATE_MARKER)
        create_rc = _step(
            [
                sys.executable,
                "-m",
                "hub.apps.databricks_admin.e2e_tooling.sandbox",
                "create",
            ],
            child_env,
            workdir,
        )
        if create_rc == 0:
            print(SUITE_MARKER)
            report_dir.mkdir(parents=True, exist_ok=True)
            suite_rc = _step(suite_argv(report_dir), child_env, workdir)

    # ALWAYS — the idempotent sweep and the bookend, mirroring the
    # nightly's `if: always()` steps.
    print(DESTROY_MARKER)
    destroy_rc = _step(
        [
            sys.executable,
            "-m",
            "hub.apps.databricks_admin.e2e_tooling.sandbox",
            "destroy",
        ],
        child_env,
        workdir,
    )

    print(AUDIT_MARKER)
    _step(
        [
            sys.executable,
            "-m",
            "hub.apps.databricks_admin.e2e_tooling.audit",
            "--report",
            str(report_dir / "e2e_report.json"),
            "--run-id",
            run_id,
        ],
        child_env,
        workdir,
    )

    first_failure = budget_rc or create_rc or suite_rc or destroy_rc or 0
    print(f"[13-8] run complete: rc={first_failure}")
    return first_failure


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
