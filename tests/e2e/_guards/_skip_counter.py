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
from datetime import datetime, timezone

SKIP_EVENTS_DIR_NAME = "test-results"
SKIP_EVENTS_FILE_NAME = "skip-events.jsonl"


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
        "when": datetime.now(timezone.utc).isoformat(),
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
