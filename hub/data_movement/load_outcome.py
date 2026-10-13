"""W3.4 (oss-release-remediation R2-P3) — canonical load-outcome extraction.

dlt 1.30 ground truth (probed live — the pre-fix code and the W3.3
fixture both contradicted it):

  * ``pipeline.run()`` returns a ``LoadInfo`` OBJECT — not a Mapping:
    ``result.get("loads", [])`` raises AttributeError, so the pre-fix
    execution took the error path on EVERY real run (zero counts,
    keys never marked, every re-run re-dispatched the full batch).
  * The load list lives at ``.load_packages`` (``LoadPackageInfo``
    objects); each package's terminal state is ``.state``
    (``loaded`` / ``failed`` / ``aborted``) — there is no ``.status``.
  * ``.has_failed_jobs`` is the canonical failure signal;
    ``asdict()["load_packages"]`` serializes each package with its
    ``state``.

The legacy fixture shape ``{"loads": [{"status": "completed"|"failed"}]}``
(the W3.3 recording handles) stays accepted so the seam-based pins keep
driving the decision logic.

Contract (R2-P3 — cursor-on-success): success means EVERY accounted
load reported success.  Any non-success state (failed/aborted/unknown)
counts as failed; a result accounting for ZERO loads counts as NOTHING
— callers must fail-closed and never advance a cursor on an empty
account.

The module deliberately imports nothing from dlt: it duck-types the
result, so it stays importable in environments without the full
requirement set (the lazy-dlt discipline of the 285 scaffold).
"""

from __future__ import annotations

from typing import Any

_SUCCESS_STATES = {"loaded", "completed"}


def _load_state(load: Any) -> str | None:
    """The terminal state of one accounted load, across the real
    LoadPackageInfo object and the serialized dict shapes."""
    if isinstance(load, dict):
        return load.get("status") or load.get("state")
    return getattr(load, "state", None) or getattr(load, "status", None)


def load_outcome(result: Any) -> dict[str, int]:
    """Return ``{"succeeded": int, "failed": int}`` for a pipeline.run
    result — the REAL dlt 1.30 ``LoadInfo`` object, its serialized
    ``asdict()``, or the legacy fixture dict shape."""
    if result is None:
        return {"succeeded": 0, "failed": 0}

    if isinstance(result, dict):
        loads = list(result.get("loads") or result.get("load_packages") or [])
    else:
        loads = list(getattr(result, "load_packages", None) or [])

    succeeded = 0
    failed = 0
    for load in loads:
        if _load_state(load) in _SUCCESS_STATES:
            succeeded += 1
        else:
            failed += 1
    return {"succeeded": succeeded, "failed": failed}
