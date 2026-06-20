"""
Phase 260.3 — file virus-scan observability metrics.

Bounded-cardinality label fallback (UNKNOWN) per the L7 helpers
convention (see ``hub/apps/search/metrics.py``). All ``record_*``
functions are best-effort — metric-backend outage MUST NOT fail
the scan job or audit emission.
"""

from __future__ import annotations

import contextlib
from typing import Protocol


class _MetricLike(Protocol):
    def labels(self, **kwargs: str) -> _MetricLike: ...

    def inc(self, amount: float = 1) -> None: ...

    def observe(self, amount: float) -> None: ...


class _MetricStub:
    def labels(self, **_: object) -> _MetricStub:
        return self

    def inc(self, _amount: float = 1) -> None:
        return None

    def observe(self, _amount: float) -> None:
        return None

    def set(self, _value: float) -> None:
        return None


# ── Metric definitions ─────────────────────────────────────────────────

try:
    from prometheus_client import Counter, Gauge, Histogram

    file_scan_duration_seconds: Histogram | _MetricLike = Histogram(
        "file_scan_duration_seconds",
        "Phase 260.3 — virus scan job wall-clock duration histogram.",
        ["outcome"],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    )

    file_scan_results_total: Counter | _MetricLike = Counter(
        "file_scan_results_total",
        "Phase 260.3 — virus scan outcome counter.",
        ["outcome"],
    )

    file_scan_queue_depth: Gauge | _MetricLike = Gauge(
        "file_scan_queue_depth",
        "Phase 260.3 — pending scan jobs in the RQ job_default queue.",
    )

    file_scan_bytes_total: Counter | _MetricLike = Counter(
        "file_scan_bytes_total",
        "Phase 260.3 — total bytes scanned by ClamAV.",
        ["outcome"],
    )

except Exception:  # pragma: no cover
    file_scan_duration_seconds = _MetricStub()
    file_scan_results_total = _MetricStub()
    file_scan_queue_depth = _MetricStub()
    file_scan_bytes_total = _MetricStub()


_VALID_OUTCOMES = frozenset(
    {"clean", "infected", "unavailable", "error", "skipped"}
)


# ── Recording helpers ──────────────────────────────────────────────────


def record_scan_completed(
    *,
    outcome: str,
    duration_s: float,
    bytes_scanned: int = 0,
) -> None:
    """Record scan job completion metrics.

    Args:
        outcome: One of ``clean``, ``infected``, ``unavailable``, ``error``.
        duration_s: Wall-clock seconds from enqueue to result persistence.
        bytes_scanned: Number of bytes sent to ClamAV (or 0 if scan skipped).
    """
    _outcome = outcome if outcome in _VALID_OUTCOMES else "error"

    with contextlib.suppress(Exception):
        file_scan_results_total.labels(outcome=_outcome).inc()
    with contextlib.suppress(Exception):
        file_scan_duration_seconds.labels(outcome=_outcome).observe(duration_s)
    if bytes_scanned > 0:
        with contextlib.suppress(Exception):
            file_scan_bytes_total.labels(outcome=_outcome).inc(float(bytes_scanned))


def record_scan_queue_depth(depth: int) -> None:
    """Record the current depth of the RQ ``job_default`` scan queue."""
    with contextlib.suppress(Exception):
        file_scan_queue_depth.set(float(depth))
