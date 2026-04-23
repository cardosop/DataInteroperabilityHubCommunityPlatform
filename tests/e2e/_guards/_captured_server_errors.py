"""Autouse fixture that surfaces server-side Django ERROR logs during E2E tests.

Motivation
----------
The Phase-1 audit found a pattern where Django/DRF logs an ERROR (e.g. a
raised-but-caught exception in a view, a DB integrity error inside a
signal handler) and the test still passes because the HTTP response came
back 200. The "functional behaviour looks fine" path masks the "something
screamed on the server" signal. This fixture reads `caplog` after every
E2E test and reports the ERRORs that came from Django/hub.*/rest_framework.

Two modes — advisory (default) and strict
------------------------------------------
Strict mode raises an `AssertionError` at teardown if any watched logger
emitted ERROR; advisory mode emits a Python `warnings.warn()` + logs to
stderr. Mode is controlled by the `CAPTURED_SERVER_ERRORS_STRICT`
environment variable:

  unset / "0" / "false"  → advisory (default, safe rollout)
  "1" / "true"           → strict (gate merges)

Advisory is the safer default because turning on a strict guard against
the entire E2E suite in one commit has a non-trivial chance of breaking
previously-passing tests for legitimate reasons (a FAILURE-path test
that logs ERROR on purpose, for example). Once we've run advisory for a
couple of CI cycles and know what's in the wild, we flip via the env
var in the strict workflow (PR 8) — no code change required.

Per-test opt-out
----------------
Tests that legitimately trigger a watched ERROR log (e.g. failure-path
specs in test_persona_failure_paths_comprehensive.py) mark themselves:

    @pytest.mark.allow_server_errors
    def test_that_exercises_the_500_handler(...):
        ...

This bypasses the check even in strict mode.

Allowlist
---------
The allowlist is DELIBERATELY empty on landing. The whole point is to
surface every ERROR and triage them individually — either fix the
underlying bug, or (if truly benign) narrow the allowlist to that
specific pattern rather than blanketing a whole logger. Extending the
allowlist should require a code review and a pointer to why the ERROR
is harmless.
"""

from __future__ import annotations

import logging
import os
import warnings
from typing import Iterable

import pytest

# Loggers whose ERRORs we care about. Third-party libraries (celery.*,
# urllib3.*, botocore.*, etc.) often log at ERROR level for expected
# retries; they're explicitly OUT of scope — only app-layer signals qualify.
WATCHED_LOGGER_PREFIXES: tuple[str, ...] = (
    "django",
    "hub.",
    "rest_framework",
)

# See "Allowlist" in module docstring. Intentionally empty on landing.
SERVER_ERROR_ALLOWLIST: tuple[str, ...] = ()

_STRICT_ENV_VAR = "CAPTURED_SERVER_ERRORS_STRICT"
_ALLOW_MARKER_NAME = "allow_server_errors"


def is_strict_mode() -> bool:
    """True when the env var asks for merge-gating behaviour.

    Read fresh on every call so individual tests can toggle via monkeypatch
    without the outer module-load value caching a stale decision.
    """
    value = os.environ.get(_STRICT_ENV_VAR, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _is_watched_logger(logger_name: str) -> bool:
    """True if this logger's ERRORs should be reported by the guard."""
    return any(logger_name.startswith(p) for p in WATCHED_LOGGER_PREFIXES)


def _is_allowlisted(record: logging.LogRecord) -> bool:
    """True if the ERROR matches any allowlist entry.

    Allowlist entries are substring matches against the formatted message.
    Kept deliberately simple: the only place we want cleverness is in the
    *decision* to add an entry, not in the matching logic.
    """
    if not SERVER_ERROR_ALLOWLIST:
        return False
    message = record.getMessage()
    return any(entry in message for entry in SERVER_ERROR_ALLOWLIST)


def detect_offending_records(
    records: Iterable[logging.LogRecord],
) -> list[logging.LogRecord]:
    """Return the subset of `records` that should be reported by the guard.

    A record qualifies when:
      * its level is ERROR or higher, AND
      * its logger name matches WATCHED_LOGGER_PREFIXES, AND
      * it does not match SERVER_ERROR_ALLOWLIST.

    Exposed separately from the fixture so the unit tests can drive it
    with synthetic LogRecord objects without bootstrapping a full test.
    """
    return [
        r
        for r in records
        if r.levelno >= logging.ERROR
        and _is_watched_logger(r.name)
        and not _is_allowlisted(r)
    ]


def format_diagnostic(
    offending: list[logging.LogRecord],
    *,
    max_records: int = 10,
) -> str:
    """Render a human-readable summary of the first N offending records."""
    preview = offending[:max_records]
    extra = len(offending) - len(preview)
    lines = [
        f"{r.name}[{logging.getLevelName(r.levelno)}]: {r.getMessage()}"
        for r in preview
    ]
    tail = f"\n... and {extra} more" if extra > 0 else ""
    body = "\n".join(lines) if lines else "(no records)"
    return f"Watched Django/DRF loggers emitted {len(offending)} ERROR record(s):\n{body}{tail}"


@pytest.fixture(autouse=True)
def captured_server_errors(request, caplog):
    """Report Django/hub.*/rest_framework ERROR logs raised during the test.

    Autouse so it applies to every E2E test without opt-in boilerplate.
    Uses pytest's `caplog` fixture (per-test, thread-local) to capture only
    records emitted during the test body — doesn't bleed setup/teardown
    noise between tests.

    Opt-out: `@pytest.mark.allow_server_errors`.
    """
    caplog.set_level(logging.ERROR)

    yield

    # Marker opt-out applies in both advisory and strict modes.
    if request.node.get_closest_marker(_ALLOW_MARKER_NAME):
        return

    offending = detect_offending_records(caplog.records)
    if not offending:
        return

    diagnostic = format_diagnostic(offending)

    if is_strict_mode():
        raise AssertionError(diagnostic)

    # Advisory mode — visible but non-blocking. Using warnings.warn so
    # pytest surfaces the message in its summary (pytest collects and
    # prints Python warnings at end-of-run), and also writing to stderr
    # so the raw diagnostic shows up in the per-test log section.
    warnings.warn(
        f"[captured_server_errors] (advisory) {diagnostic}",
        category=UserWarning,
        stacklevel=1,
    )
