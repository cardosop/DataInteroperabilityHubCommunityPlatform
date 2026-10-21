"""CVE triage process pins (close-oss-release-conditions P0-3) — Django-free,
CI no-django lint.

These pins keep the regrowth blocker HONEST — the wave (P0-2) restored
the state; these pins enforce the PROCESS that keeps it restored:

* a WEEKLY scheduled workflow exists (not monthly-only — the 2026-05→10
  rot outran a monthly signal) and its strict step runs the REAL
  checker (`audit_pinned_cves.py --strict`);
* that workflow opens/updates a tracking issue on failure (a failing
  cron that nobody hears about is the rot's exact shape);
* GOVERNANCE's maintenance model records the weekly gate AND the
  monthly triage ritual, so the cadence is a governance commitment,
  not a workflow side effect;
* the triage runbook exists with the sections that make the cadence
  executable: triggers, the bucket procedure, the tooling commands,
  escalation, and the default-branch caveat (scheduled jobs run only
  from the default branch's copy of the workflow — the root cause of
  the rot).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEEKLY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cve-triage-weekly.yml"
GOVERNANCE = REPO_ROOT / "GOVERNANCE.md"
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "cve-triage.md"


def _text(path: Path) -> str:
    assert path.is_file(), f"expected committed artifact: {path}"
    return path.read_text(encoding="utf-8")


def _workflow() -> dict:
    return yaml.safe_load(_text(WEEKLY_WORKFLOW))


def _steps() -> list[dict]:
    job = _workflow().get("jobs", {}).get("weekly-gate", {})
    assert job, "cve-triage-weekly.yml must define the weekly-gate job"
    return job.get("steps", [])


def test_weekly_schedule_exists():
    workflow = _workflow()
    # PyYAML 1.1 parses the unquoted ``on:`` key as boolean True — the
    # repo's workflow style keeps ``on`` unquoted, so read both shapes.
    trigger = workflow.get("on") or workflow.get(True) or {}
    schedule = trigger.get("schedule", []) or []
    crons = [item.get("cron", "") for item in schedule]
    assert crons, "cve-triage-weekly.yml must have a scheduled trigger"
    weekly = [cron for cron in crons if cron and cron.split()[-1] != "*"]
    assert weekly, f"expected a weekly (day-of-week pinned) cron, got: {crons}"


def test_strict_step_runs_the_real_checker():
    commands = " ".join(
        str(step.get("run", "")) for step in _steps() if isinstance(step, dict)
    )
    assert "scripts/audit_pinned_cves.py" in commands, "strict step must run the real checker"
    assert "--strict" in commands, "the weekly gate must use --strict"


def test_failure_step_opens_a_tracking_issue():
    failure_steps = [step for step in _steps() if step.get("if") == "failure()"]
    assert failure_steps, "the weekly workflow must have a failure() step"
    script = str(failure_steps[0].get("with", {}).get("script", ""))
    assert "issues.create" in script, "the failure step must open a tracking issue"
    assert "docs/runbooks/cve-triage.md" in script, (
        "the issue body must point at the triage runbook"
    )


def test_governance_records_the_weekly_gate_and_monthly_ritual():
    text = _text(GOVERNANCE)
    for expected in (
        "cve-triage-weekly.yml",
        "dependency-review.yml",
        "docs/runbooks/cve-triage.md",
    ):
        assert expected in text, f"GOVERNANCE must record the cadence artifact: {expected}"


def test_runbook_covers_the_executable_sections():
    text = _text(RUNBOOK)
    for section in (
        "## When this runbook applies",
        "## Triage procedure",
        "## Tooling",
        "## Escalation",
    ):
        assert section in text, f"runbook must carry {section!r}"
    for command in (
        "scripts/triage_pinned_cves.py",
        "scripts/audit_pinned_cves.py --strict",
        "scripts/tests/test_cve_triage_waves.py",
        "scripts/tests/test_cve_triage_process.py",
    ):
        assert command in text, f"runbook must document the tooling: {command}"
    assert "default branch" in text, (
        "runbook must record the default-branch caveat (scheduled jobs run "
        "only from the default branch's copy of the workflow)"
    )
