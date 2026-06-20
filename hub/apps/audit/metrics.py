"""
Audit-domain observability metrics (Phase 234.6 + 234.7).

This module hosts the audit app's Prometheus / OTel histograms + counters.
It defers metric instance creation to
:mod:`hub.apps.observability.otel_metrics` (the canonical OTel wrapper
layer) so the metric registers under the same meter as the rest of the
platform — Grafana / Prometheus see one consistent name space.

Metric naming convention
========================

The Phase 234.7.2 spec text refers to metrics with the prefix
``meshant_audit_*`` (e.g. ``meshant_audit_chain_break_total``). The
existing codebase convention — pinned across 50+ metrics in
:mod:`hub.apps.observability.otel_metrics` and
:mod:`services.shared.metrics` — uses BARE metric names without a
product prefix (``audit_events_total``, ``http_requests_total``,
``jobs_started_total`` …). To avoid fracturing the namespace and
breaking every existing Grafana panel / alert / SLO that references
the bare convention, the audit metrics ship with bare names. The
Grafana dashboard `audit-health.json` and the Prometheus alert rules
`audit.yml` reference these bare names accordingly.

Surfaced metrics
================

* :data:`audit_search_query_duration_seconds` (Phase 234.6.AUDIT.4) —
  wall-clock duration of the FTS path served by
  ``AuditEventViewSet.list`` when ``?q=`` is present. Drives the
  on-call alert ``histogram_quantile(0.95,
  audit_search_query_duration_seconds) > 5s for 5m`` — "audit FTS
  slow; the GIN index is probably bloated, consider
  ``REINDEX CONCURRENTLY``".

* :data:`audit_chain_break_total` (Phase 234.7.2) — count of
  tamper-evidence mismatches detected by the chain verifier. Labels:
  ``tenant_id`` (or ``"__platform__"``), ``reason`` (``chain_hash_mismatch``
  / ``prev_link_mismatch`` / ``snapshot_root_mismatch``). Non-zero on
  this counter is a PagerDuty signal — see the
  ``AuditChainBreakDetected`` alert in
  ``monitoring/prometheus/alerts/audit.yml``.

* :data:`audit_merkle_snapshot_duration_seconds` (Phase 234.7.2) —
  wall-clock duration of one tenant-window Merkle snapshot
  (``hub.apps.audit.merkle.snapshot_tenant_window``). Labels:
  ``tenant_id``. Histogram p99 > 30s = "snapshot pipeline slow,
  likely S3 Object-Lock PUT latency"; the alert fires on a sustained
  breach.

* :data:`audit_retention_purged_total` (Phase 234.7.2) — count of
  audit rows hard-deleted by the Phase 234.4 permanent-delete sweep.
  Labels: ``tenant_id``, ``dry_run`` (``"true"`` / ``"false"``). The
  counter is the authoritative deletion-rate signal for the audit
  trail; the matching ``AUDIT_RETENTION_PURGED`` audit event is the
  forensic record but doesn't aggregate well for ops dashboards.

Helpers
=======

* :func:`time_search_query` — context manager around the FTS query
  path; observes on ``finally`` so a 500-ing query still contributes
  to the latency curve.

* :func:`time_merkle_snapshot` — analogous context manager for the
  Merkle snapshot pipeline.

* :func:`observe_chain_break` — convenience wrapper around the
  chain-break counter; takes a ``reason`` plus optional tenant label.

* :func:`observe_retention_purged` — convenience wrapper around the
  purge counter; takes a row count + tenant label + ``dry_run`` flag.

* :func:`search_query_observation_count` / :func:`chain_break_observation_count`
  / :func:`merkle_snapshot_observation_count` /
  :func:`retention_purged_observation_count` — exposed for test
  pinning of the metric-emission contracts. The OTel histogram /
  counter wrappers track per-labeled-instance observation counts,
  but the module-level counters here are the simplest stable
  introspection surface.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from hub.apps.observability.otel_metrics import _CounterWrapper, _HistogramWrapper

# ---------------------------------------------------------------------------
# Bucket profiles
# ---------------------------------------------------------------------------

# Latency buckets tuned for the FTS path: sub-second is the happy path,
# the 5s boundary aligns with the slow-query alert threshold, and the
# 10s tail catches GIN-bloat / lock-wait pathological cases.
_AUDIT_SEARCH_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

# Merkle snapshot pipeline runs the hash tree build + sign + S3 PUT
# in one tenant-window. p99 typically sub-second; the 30s boundary
# aligns with the slow-snapshot alert; the 120s tail catches S3
# Object-Lock PUT latency excursions.
_AUDIT_MERKLE_BUCKETS = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
)


# ---------------------------------------------------------------------------
# Metric instances (Phase 234.6 + 234.7.2)
# ---------------------------------------------------------------------------

audit_search_query_duration_seconds = _HistogramWrapper(
    "audit_search_query_duration_seconds",
    (
        "Wall-clock duration of the audit-events FTS path (?q=) "
        "end-to-end. Slow-query alert: p95 > 5s for 5m → audit FTS slow."
    ),
    unit="s",
    buckets=_AUDIT_SEARCH_BUCKETS,
    expected_labels=("tenant_id",),
)

audit_chain_break_total = _CounterWrapper(
    "audit_chain_break_total",
    (
        "Tamper-evidence mismatches detected by the audit chain verifier. "
        "Labels: tenant_id (or '__platform__'), reason "
        "(chain_hash_mismatch / prev_link_mismatch / "
        "snapshot_root_mismatch). Non-zero is a PagerDuty signal — see "
        "the AuditChainBreakDetected alert."
    ),
    unit="1",
    expected_labels=("tenant_id", "reason"),
)

audit_merkle_snapshot_duration_seconds = _HistogramWrapper(
    "audit_merkle_snapshot_duration_seconds",
    (
        "Wall-clock duration of one tenant-window Merkle snapshot "
        "(hash-tree build + signing + S3 Object-Lock PUT). Slow-snapshot "
        "alert: p99 > 30s for 10m → snapshot pipeline slow, likely S3 "
        "PUT latency."
    ),
    unit="s",
    buckets=_AUDIT_MERKLE_BUCKETS,
    expected_labels=("tenant_id",),
)

audit_retention_purged_total = _CounterWrapper(
    "audit_retention_purged_total",
    (
        "Audit rows hard-deleted by the Phase 234.4 permanent-delete "
        "sweep. Labels: tenant_id (or '__platform__'), dry_run "
        "('true' / 'false'). The matching AUDIT_RETENTION_PURGED audit "
        "event is the forensic record; this counter is the aggregate "
        "deletion-rate signal."
    ),
    unit="1",
    expected_labels=("tenant_id", "dry_run"),
)


# ---------------------------------------------------------------------------
# Module-level observation counters (test surface)
# ---------------------------------------------------------------------------
#
# The OTel histogram/counter wrappers track per-labeled-instance
# observation counts internally, but those live inside ``_LabeledMetric``
# instances that aren't reliably enumerable across test runs / process
# restarts. Module-level counters here are the simplest stable read
# surface for both tests and ops smoke checks. Increments are atomic
# under the CPython GIL (single STORE_FAST bytecode).

_search_observation_count: int = 0
_chain_break_observation_count: int = 0
_merkle_snapshot_observation_count: int = 0
_retention_purged_observation_count: int = 0


# ---------------------------------------------------------------------------
# Phase 234.6 — search-duration helpers
# ---------------------------------------------------------------------------


def observe_search_duration(*, seconds: float, tenant_id: str) -> None:
    """Record a search duration on the histogram + bump the visible counter.

    ``tenant_id`` is propagated as a label so Grafana can break the
    slow-query alert down per-tenant when a single noisy tenant
    correlates with elevated p95s. Cardinality is bounded by the
    tenant count.
    """
    global _search_observation_count
    audit_search_query_duration_seconds.labels(tenant_id=tenant_id).observe(seconds)
    _search_observation_count += 1


def search_query_observation_count() -> int:
    """Cumulative observation count of ``audit_search_query_duration_seconds``."""
    return _search_observation_count


@contextmanager
def time_search_query(*, tenant_id: str) -> Iterator[None]:
    """Time a block of work and record the elapsed seconds on the histogram.

    Observation fires on context exit whether the wrapped block
    succeeded or raised — a 500-ing FTS query still belongs on the
    latency curve (a query that takes 8 seconds before crashing is
    operationally identical to one that takes 8 seconds and returns).
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        observe_search_duration(seconds=time.perf_counter() - start, tenant_id=tenant_id)


# ---------------------------------------------------------------------------
# Phase 234.7.2 — chain-break, Merkle-snapshot, retention-purge helpers
# ---------------------------------------------------------------------------


def observe_chain_break(*, tenant_id: str, reason: str) -> None:
    """Increment :data:`audit_chain_break_total` for one detected mismatch.

    Called from the verifier endpoint (and any other detection
    surface) once per mismatch row. ``reason`` is the verifier's
    classification: ``chain_hash_mismatch`` (content tamper),
    ``prev_link_mismatch`` (splice/insertion without erasure gap),
    or ``snapshot_root_mismatch`` (the Merkle cross-check disagrees
    with the stored row hashes).
    """
    global _chain_break_observation_count
    audit_chain_break_total.labels(tenant_id=tenant_id, reason=reason).inc()
    _chain_break_observation_count += 1


def chain_break_observation_count() -> int:
    """Cumulative observation count of ``audit_chain_break_total``."""
    return _chain_break_observation_count


@contextmanager
def time_merkle_snapshot(*, tenant_id: str) -> Iterator[None]:
    """Time a Merkle-snapshot pipeline call and emit on context exit."""
    global _merkle_snapshot_observation_count
    start = time.perf_counter()
    try:
        yield
    finally:
        audit_merkle_snapshot_duration_seconds.labels(tenant_id=tenant_id).observe(
            time.perf_counter() - start
        )
        _merkle_snapshot_observation_count += 1


def merkle_snapshot_observation_count() -> int:
    """Cumulative observation count of ``audit_merkle_snapshot_duration_seconds``."""
    return _merkle_snapshot_observation_count


def observe_retention_purged(
    *,
    tenant_id: str,
    deleted_count: int,
    dry_run: bool,
) -> None:
    """Add ``deleted_count`` to :data:`audit_retention_purged_total`.

    The counter is incremented by the deletion count (NOT 1-per-call)
    so the rate query ``sum(rate(audit_retention_purged_total[1h]))``
    yields "deletions per hour" — the authoritative deletion-rate
    signal. In ``dry_run=True`` mode the increment still happens with
    the ``dry_run="true"`` label so Grafana can show preview-vs-actual
    side-by-side; alerts filter on ``dry_run="false"``.
    """
    global _retention_purged_observation_count
    # ``_LabeledMetric.inc(amount)`` is the wrapper's "add to counter by
    # amount" surface — the underlying OTel counter's ``add(N)`` is
    # called inside (see hub/apps/observability/otel_metrics.py line 229).
    audit_retention_purged_total.labels(tenant_id=tenant_id, dry_run=str(dry_run).lower()).inc(
        int(deleted_count)
    )
    _retention_purged_observation_count += 1


def retention_purged_observation_count() -> int:
    """Cumulative observation count of ``audit_retention_purged_total``."""
    return _retention_purged_observation_count
