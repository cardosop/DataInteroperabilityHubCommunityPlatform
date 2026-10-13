"""Phase 9 (openspec add-databricks-live-ci-sandbox task 9.6) — the run
bookend audit emitter.

The workflow's final step runs this module AFTER the journey/contract
suites: it reads the journey report (`report/e2e_report.json`), composes
ONE audit envelope per run — `DATABRICKS_E2E_RUN_PASSED` or
`DATABRICKS_E2E_RUN_FAILED` (the 9.6 vocabulary events) with the run
outcome, the sandbox identity, and the run duration — and writes it next
to the report (`report/e2e_audit_event.json`) so the always-published
artifact carries the house audit vocabulary's record of the run.

Best-effort by construction (the Phase 273 discipline): the emitter
NEVER raises out of ``main`` and NEVER exits non-zero. A missing or
corrupt report still yields a FAILED envelope with the evidence — no
failure path loses the evidence of the failure, and the report publish
step is never blocked.

The sandbox identity derives through the ONE naming convention
(``sandbox.sandbox_name`` — ``meshant_e2e_<run_id>``); the workspace host
rides the envelope when the environment carries it
(``DATABRICKS_E2E_WORKSPACE_HOST``). No credential material is ever read
or written. Pure stdlib — runs on the GitHub runner without the repo's
Django environment.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hub.apps.databricks_admin.e2e_tooling.sandbox import sandbox_name

ENVELOPE_FILENAME = "e2e_audit_event.json"
WORKSPACE_HOST_ENV = "DATABRICKS_E2E_WORKSPACE_HOST"

#: The 9.6 vocabulary events (name == value, mirroring
#: hub/apps/audit/event_types.py — this module intentionally does NOT
#: import Django, so the literals are pinned by the TDD suite instead).
EVENT_PASSED = "DATABRICKS_E2E_RUN_PASSED"
EVENT_FAILED = "DATABRICKS_E2E_RUN_FAILED"


def _parse_started_at(value: str | None) -> datetime | None:
    """Parse the workflow's ``github.run_started_at`` (ISO 8601, UTC).
    Returns None on any malformed input — a broken timestamp must never
    crash the bookend, only the duration degrades to None."""
    if not value or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def duration_seconds(
    started_at: str | None, *, now: datetime | None = None
) -> float | None:
    """Elapsed run seconds since the workflow started; None when the
    started-at is absent or unparseable (never fabricated)."""
    started = _parse_started_at(started_at)
    if started is None:
        return None
    current = now if now is not None else datetime.now(UTC)
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return round(max(0.0, (current - started).total_seconds()), 3)


def determine_outcome(report: dict[str, Any] | None) -> str:
    """PASSED only when the journey stamped it; anything else — a FAILED
    outcome, a missing report, an unparseable one — fails closed."""
    if not isinstance(report, dict):
        return "FAILED"
    if report.get("outcome") != "PASSED":
        return "FAILED"
    legs = report.get("legs")
    if (
        isinstance(legs, dict)
        and legs
        and all(
            isinstance(entry, dict) and entry.get("status") == "passed"
            for entry in legs.values()
        )
    ):
        return "PASSED"
    return "FAILED"


def compose_event(
    report: dict[str, Any] | None,
    *,
    run_id: str,
    duration_seconds: float | None,
    workspace_host: str | None,
    evidence: str | None = None,
) -> dict[str, Any]:
    """ONE audit envelope per run: the vocabulary event, the outcome, the
    sandbox identity (convention-derived), and the duration."""
    outcome = determine_outcome(report)
    envelope: dict[str, Any] = {
        "event_type": EVENT_PASSED if outcome == "PASSED" else EVENT_FAILED,
        "outcome": outcome,
        "run_id": run_id,
        "sandbox": {
            # The convention is the single source of truth (sandbox.py);
            # the Databricks-side workspace id is resolvable only by the
            # account API and stays null until the wiring lands.
            "workspace_name": sandbox_name(run_id),
            "workspace_id": None,
            "workspace_host": workspace_host,
        },
        "duration_seconds": duration_seconds,
        "evidence": {},
        "emitted_at": datetime.now(UTC).isoformat(),
    }
    if evidence is not None:
        envelope["evidence"]["report"] = evidence
    elif isinstance(report, dict):
        # The per-leg statuses + request counts travel with the envelope —
        # the report artifact's full detail stays in e2e_report.json.
        legs = report.get("legs")
        if isinstance(legs, dict):
            envelope["evidence"]["legs"] = {
                leg: {
                    "status": entry.get("status") if isinstance(entry, dict) else None,
                    "requests": (
                        entry.get("requests") if isinstance(entry, dict) else None
                    ),
                }
                for leg, entry in legs.items()
            }
        envelope["evidence"]["outcome"] = report.get("outcome")
    return envelope


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--report", required=True, help="path to report/e2e_report.json"
    )
    parser.add_argument(
        "--run-id", required=True, help="the workflow's run id (GITHUB_RUN_ID)"
    )
    parser.add_argument(
        "--run-started-at", default=None, help="github.run_started_at (ISO 8601, UTC)"
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    report: dict[str, Any] | None = None
    evidence: str | None = None

    try:
        if report_path.is_file():
            try:
                report = json.loads(report_path.read_text())
                if not isinstance(report, dict):
                    evidence = "unparseable"
                    report = None
            except ValueError:
                evidence = "unparseable"
                report = None
        else:
            evidence = "missing"
    except OSError:
        evidence = "unreadable"
        report = None

    elapsed = duration_seconds(args.run_started_at)
    host = os.environ.get(WORKSPACE_HOST_ENV, "").strip() or None
    envelope = compose_event(
        report,
        run_id=args.run_id.strip(),
        duration_seconds=elapsed,
        workspace_host=host,
        evidence=evidence,
    )

    # Best-effort write: a write failure must never block the report
    # publish step — but it is always attempted, and every path above
    # already degraded to a well-formed FAILED envelope.
    try:
        target = report_path.parent / ENVELOPE_FILENAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(envelope, sort_keys=True, indent=2, default=str))
    except OSError:
        pass


if __name__ == "__main__":
    main()
