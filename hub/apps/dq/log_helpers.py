"""
Phase 240.5.F.2 — Hub-side log redaction helpers.

Mirror of [services/dq-service/structured_logging.py](../../../services/dq-service/structured_logging.py)
``_redact()``.  Both sides need redaction because they have
independent log-emitting code paths:

* dq-service (FastAPI microservice) — scans customer DataFrames and
  may surface row contents in failure paths.  Its ``_redact`` lives
  alongside the scan-execution code.
* Hub (Django) — receives DQ run results from dq-service via HTTP,
  persists ``DQRun.details_json`` (which CAN contain sample row
  values, per-issue ``sample_value`` cells, and other
  customer-derived strings), and orchestrates alert delivery.  Any
  ``logger.info("...", extra={"details": dq_run.details_json})`` in
  the Hub side leaks the same PII surface as the microservice.

This helper is the Hub's defence-in-depth: every ``logger.*`` call
in [hub/apps/dq/{views,services,service_client,alerting,tasks}.py]
that emits a structured ``extra={...}`` payload SHOULD pass it
through ``_redact()`` first.  A pre-commit + CI lint rule
(see [scripts/check_dq_log_extras.py](../../../scripts/check_dq_log_extras.py))
fails any future PR that introduces a raw, redacted-key-bearing
``extra={}`` argument to a logger call inside ``hub/apps/dq/``.

Why a SEPARATE Hub-side module vs reusing the dq-service one:

1. **Import path** — dq-service is a self-contained package under
   ``services/dq-service/`` with its own ``requirements.txt`` and
   sys.path.  Hub-side code can't ``from services.dq_service...``
   without breaking the import isolation that the microservice
   architecture is built on.
2. **Drift safeguard** — keeping two independent implementations
   pinned to the same key-set by a parity test
   (``TestRedactedKeysParity`` in
   [tests/test_log_helpers.py](tests/test_log_helpers.py)) makes a
   future divergence fail CI rather than silently leak.
3. **Test isolation** — the dq-service test suite imports the
   FastAPI module which requires a different conftest setup; the
   Hub redact test imports the Django app and uses the existing
   ``hub/apps/dq/tests/`` infrastructure.

Mirror of compliance Phase 19 ``_sanitize()`` per spec wording — the
compliance app eventually used ``redact_pii`` from
``hub/apps/audit/utils.py``, which redacts BY VALUE PATTERN
(emails / SSNs / etc.) rather than BY KEY.  240.5.F.2 calls for the
key-based pattern (matches dq-service) because (a) the DQ payloads
have well-known key names like ``row_samples``, ``sample_value``,
``details_json`` that always contain customer-derived content; (b)
key-based redaction is cheaper than value-pattern matching at
log-emission time on the Hub critical path.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Phase 240.5.F.2 — redacted-key inventory.
# ---------------------------------------------------------------------------
#
# Keys whose VALUES are dropped from any structured payload before
# the log write.  Conservative — when in doubt, redact.  Call sites
# can always log specific scalar fields explicitly (counts /
# durations / scores / category names / IDs).
#
# Mirror of ``_REDACTED_KEYS`` in the dq-service ``structured_logging``
# module.  The parity test ``TestRedactedKeysParity`` in
# ``test_log_helpers.py`` asserts the Hub set is a SUPERSET of the
# dq-service set so a future divergence in one direction surfaces in
# CI.  The Hub MAY redact more keys than dq-service (more conservative
# is fine), but it MUST never redact fewer.
#
# Adding a key: append it here AND extend
# ``test_log_helpers.py::TestRedact::test_strips_known_pii_bearing_keys``.
_REDACTED_KEYS: frozenset[str] = frozenset({
    # ── customer row content (top-priority redaction) ──
    "row_samples",         # sampled rows from the input dataset
    "sample_value",        # per-issue sample value (e.g. a failing cell's literal value)
    "sample_data_json",    # a dataset's sample-data blob
    "file_content",        # base64-encoded file body
    # ── generic raw-content bags (be conservative) ──
    "body",                # raw HTTP body
    "raw_data",            # generic raw-data bag
    "data",                # generic data bag
    # ── persisted blobs that aggregate the above ──
    "details_json",        # DQRun.details_json — contains row samples,
                           # check details, anomaly detail bags, ML
                           # backstage metadata.  Already persisted in
                           # the DB; no log-side use case justifies
                           # the PII surface area.
})


def _redact(obj: Any) -> Any:
    """Return ``obj`` with every redacted-key (``_REDACTED_KEYS``)
    stripped, recursively.

    Behaviour by type:

    * ``dict``: drop keys in ``_REDACTED_KEYS``; recurse into remaining
      values.
    * ``list``: recurse into each element (preserve order).
    * ``tuple``: recurse into each element, return tuple.
    * scalar (str / int / float / bool / None): pass through unchanged.

    The result is always a fresh object — callers can safely log the
    output without mutating their own data structures.

    Use it like::

        logger.info(
            "dq_run_completed",
            extra=_redact({
                "tenant_id": str(tenant.id),
                "dq_run_id": str(dq_run.id),
                "details_json": dq_run.details_json,  # ← redacted away
                "duration_ms": elapsed_ms,
            }),
        )
    """
    if isinstance(obj, dict):
        return {
            k: _redact(v)
            for k, v in obj.items()
            if k not in _REDACTED_KEYS
        }
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_redact(item) for item in obj)
    return obj


__all__ = ["_redact", "_REDACTED_KEYS"]
