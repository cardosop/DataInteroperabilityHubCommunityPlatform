"""Skip-event recorder for the PR 10 skip-counter gate.

Problem this solves
-------------------
PR 9 converted several bare `except Exception: pass` sites in
tests/e2e/conftest.py into `pytest.skip(reason="S3 not reachable")`
(and similar). That's a strict improvement — outages are now visible
in the test report — but if 90% of E2E tests skip because MinIO is
down, the suite goes green while testing nothing.

Solution
--------
This module registers a pytest hook that appends one JSONL line per
skip event to `test-results/skip-events.jsonl`. A post-run CI script
(`scripts/check_skip_counter.py`) then groups by skip reason and fails
the build if any *single* reason exceeds the configured threshold
(default 5% of total tests).

Design notes
------------
* Append-only JSONL so parallel workers (pytest-xdist, if enabled
  later) can each own a file segment without locking — the aggregator
  doesn't care about ordering.
* Per-reason threshold rather than global so a 4% S3-skip rate and a
  4% semantic-skip rate don't mask each other (both must stay below
  the limit individually).
* The exact reason string is the pytest.skip() message verbatim. Tests
  should use the same reason prefix for related skip conditions
  ("S3 not reachable", "Semantic service not importable") so the
  grouping aggregates cleanly.

Output schema
-------------
Each line of skip-events.jsonl is:
    {"test": "<nodeid>", "reason": "<skip message>",
     "file": "<relative path>", "when": "<ISO-8601 UTC>"}
"""

from __future__ import annotations

import json
import os
import pathlib
from datetime import UTC, datetime

SKIP_EVENTS_DIR_NAME = "test-results"
SKIP_EVENTS_FILE_NAME = "skip-events.jsonl"

# Canonical skip-reason prefix for the Phase 226.H bug-fix bandwidth gate.
#
# This MUST match the constant of the same name in
# `scripts/check_audit_bug_ledger.py`. The cross-validation test
# `TestAuditBugSkipHelper.test_prefix_matches_canonical_source_of_truth`
# in `scripts/tests/test_check_audit_bug_ledger.py` enforces parity, so
# editing one without the other fails CI immediately.
#
# Test authors do NOT typically reference this constant directly —
# `audit_bug_skip_reason()` below produces the canonical reason string.
AUDIT_BUG_SKIP_REASON_PREFIX = "audit-exposed bug awaiting fix"

# Bug ids in the ledger have the form `AUDIT-BUG-NNN`. We don't enforce
# the numeric tail (it might evolve to `AUDIT-BUG-2026-001` etc.), but the
# `AUDIT-BUG-` prefix is the contract that links a skip back to a row in
# the ledger. Anything else is a typo and must fail loudly.
_AUDIT_BUG_ID_PREFIX = "AUDIT-BUG-"


def audit_bug_skip_reason(bug_id: str, detail: str | None = None) -> str:
    """Build a canonical reason string for an audit-exposed-bug skip.

    Use as::

        if not_yet_fixed:
            pytest.skip(audit_bug_skip_reason(
                "AUDIT-BUG-001",
                "tenant switch is not audited (backend gap)",
            ))

    The returned string starts with `AUDIT_BUG_SKIP_REASON_PREFIX`, which
    is exactly the prefix the skip-counter is configured to recognise via
    its `--category` flag. The bug id is included verbatim so the close
    gate can correlate the skip with the ledger entry that owns it.

    Empty/whitespace bug ids and ids missing the `AUDIT-BUG-` prefix are
    rejected at construction time — silent typos here would silently
    bypass the gate, which is the failure mode this whole sub-track
    exists to kill.
    """
    if not isinstance(bug_id, str) or not bug_id.strip():
        raise ValueError("bug_id must be a non-empty string")
    bug_id = bug_id.strip()
    if not bug_id.startswith(_AUDIT_BUG_ID_PREFIX):
        raise ValueError(
            f"bug_id must start with {_AUDIT_BUG_ID_PREFIX!r} "
            f"to match the ledger format (got {bug_id!r})"
        )
    if detail:
        return f"{AUDIT_BUG_SKIP_REASON_PREFIX}: {bug_id} — {detail}"
    return f"{AUDIT_BUG_SKIP_REASON_PREFIX}: {bug_id}"


def _artifact_path() -> pathlib.Path:
    """Resolve the skip-events artifact path.

    Honours `PYTEST_SKIP_EVENTS_PATH` when set (primarily for the hook
    self-test and CI post-steps); falls back to
    `test-results/skip-events.jsonl` relative to the current working
    directory otherwise.
    """
    override = os.environ.get("PYTEST_SKIP_EVENTS_PATH")
    if override:
        return pathlib.Path(override)
    return pathlib.Path.cwd() / SKIP_EVENTS_DIR_NAME / SKIP_EVENTS_FILE_NAME


def record_skip(*, nodeid: str, reason: str, file: str | None = None) -> None:
    """Append one skip event to the JSONL artifact.

    Exposed separately from the pytest hook so CI scripts and unit tests
    can drive it without a running pytest session.
    """
    path = _artifact_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "test": nodeid,
        "reason": reason,
        "file": file,
        "when": datetime.now(UTC).isoformat(),
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry) + "\n")


def pytest_runtest_logreport(report):
    """pytest hook: capture skip events to the JSONL artifact.

    Wired from tests/e2e/conftest.py so pytest's hook discovery finds it.
    Only fires on "call" phase skips (not collection-time) and only when
    the skip has a non-empty reason — preserves one-record-per-skip
    semantics without duplicating on setup/teardown phases.
    """
    if report.when != "call":
        return
    if not report.skipped:
        return
    # `report.longrepr` for skips is a triple: (file, line, reason).
    reason: str
    file: str | None
    if isinstance(report.longrepr, tuple) and len(report.longrepr) >= 3:
        file = report.longrepr[0]
        reason = str(report.longrepr[2])
    else:
        file = getattr(report, "fspath", None)
        reason = str(report.longrepr) if report.longrepr else "(no reason)"
    record_skip(nodeid=report.nodeid, reason=reason, file=file)
