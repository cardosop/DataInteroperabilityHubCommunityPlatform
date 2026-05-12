"""
Phase 270.B.2.6 — governance Prometheus metrics.

Exposes ``governance_access_requests_pending`` — a tenant-labelled
gauge bucketed by request age. The matching alert
``AccessRequestSLABreach`` in
``monitoring/prometheus/alerts/marketplace-compliance-deltas.yml``
fires when any tenant's ``gt_7d`` bucket is non-zero for an hour,
signalling that the provider's data-owner queue is past warning
threshold for the configurable PENDING SLA (default 14 d — the
``gt_7d`` boundary is intentionally tighter than the default SLA
so ops sees the breach trending BEFORE the daily sweep auto-
expires the request).

Sampled by the ``revoke_expired_access`` management command at the
end of each daily run (after the sweep, the gauges reflect the
post-sweep steady state). The command is the canonical writer:
no API hot-path emits to these gauges, so cardinality stays bounded
to ``len(active_tenants) × len(buckets)``.

Bounded-cardinality labels:
* ``tenant_id`` — one label value per active tenant (typically
  low-thousands at most)
* ``age_bucket`` — fixed 4-value enumeration (``le_1d``, ``le_3d``,
  ``le_7d``, ``gt_7d``)

Defensive fallback: if ``prometheus_client`` is not installed
(test environments, isolated CI runners), the gauge is a stub
with ``labels()`` + ``set()`` no-ops. Mirrors the pattern in
``hub.apps.webhooks.metrics``.
"""
from __future__ import annotations

from typing import Protocol


class _GaugeLike(Protocol):
    """Structural type covering both prometheus_client.Gauge and the stub."""

    def labels(self, **kwargs: str) -> "_GaugeLike": ...

    def set(self, value: float) -> None: ...


# Bucket boundaries (days). The boundaries map cleanly to the SLA
# breach surface:
#   - le_1d:   freshly-submitted, no concern
#   - le_3d:   normal queue depth
#   - le_7d:   getting old; alert WARNING territory if the bucket
#              is non-empty AND the tenant's SLA is the default 14 d
#   - gt_7d:   past the AccessRequestSLABreach alert threshold
ACCESS_REQUEST_AGE_BUCKETS: tuple = ("le_1d", "le_3d", "le_7d", "gt_7d")


def bucket_for_age_days(age_days: float) -> str:
    """Map an age in days (fractional OK) to the bucket label.

    Pure function — used both by the sweep command (to set gauge
    values) and by the test suite (to verify bucket assignment
    without touching prometheus_client internals).
    """
    if age_days <= 1.0:
        return "le_1d"
    if age_days <= 3.0:
        return "le_3d"
    if age_days <= 7.0:
        return "le_7d"
    return "gt_7d"


try:
    from prometheus_client import Gauge

    governance_access_requests_pending: _GaugeLike = Gauge(
        "governance_access_requests_pending",
        (
            "Phase 270.B.2.6 — count of ``AccessRequest`` rows currently "
            "in PENDING state, labelled by tenant_id + age_bucket. "
            "Sampled by the daily ``revoke_expired_access`` sweep AFTER "
            "the SLA sweep runs, so the gauge reflects the steady-state "
            "queue depth (not transient pre-sweep counts). The "
            "AccessRequestSLABreach alert fires when "
            "``{age_bucket='gt_7d'} > 0`` for 1h."
        ),
        ["tenant_id", "age_bucket"],
    )

except Exception:  # pragma: no cover — defensive fallback
    class _GaugeStub:
        def labels(self, **_: object) -> "_GaugeStub":  # noqa: ARG002
            return self

        def set(self, _value: float) -> None:  # noqa: ARG002
            return None

    governance_access_requests_pending = _GaugeStub()


def record_pending_count(tenant_id: str, age_bucket: str, count: int) -> None:
    """Best-effort gauge update — a metric-backend outage MUST NOT
    fail the sweep's audit-emit + DB-update path.

    Called by ``revoke_expired_access`` after each per-tenant pass
    completes, with one call per ``(tenant_id, age_bucket)`` so the
    gauge is fully refreshed (stale buckets get explicit ``set(0)``
    rather than stale carry-over from a previous sweep).
    """
    try:
        governance_access_requests_pending.labels(
            tenant_id=str(tenant_id),
            age_bucket=str(age_bucket),
        ).set(float(count))
    except Exception:  # pragma: no cover — defensive
        # Swallow — the metric is observability, not source of truth.
        return


# ── Phase 272.2 — compliance gate metrics ──────────────────────────────

try:
    from prometheus_client import Counter

    governance_approval_compliance_blocked_total: Counter | _GaugeLike = Counter(
        "governance_approval_compliance_blocked_total",
        "Phase 272.2 — approval blocked by compliance gate, labelled by reason.",
        ["tenant_id", "reason"],
    )
except Exception:  # pragma: no cover
    governance_approval_compliance_blocked_total = _GaugeStub()


def record_compliance_blocked(tenant_id: str, reason: str) -> None:
    """Emit a counter increment when the compliance gate blocks approval."""
    try:
        governance_approval_compliance_blocked_total.labels(
            tenant_id=str(tenant_id),
            reason=str(reason),
        ).inc()
    except Exception:  # pragma: no cover
        return


# ── Phase 272.3 — ABAC decision metrics ────────────────────────────────

try:
    governance_abac_decisions_total: Counter | _GaugeLike = Counter(
        "governance_abac_decisions_total",
        "Phase 272.3 — ABAC policy decisions during approval.",
        ["decision", "policy_id"],
    )
except Exception:
    governance_abac_decisions_total = _GaugeStub()

# ── Phase 272.4 — approval step duration histogram ─────────────────────

try:
    from prometheus_client import Histogram

    governance_approval_step_duration_seconds: Histogram | _GaugeLike = Histogram(
        "governance_approval_step_duration_seconds",
        "Phase 272.4 — approval step duration histogram.",
        ["from_step", "to_step"],
        buckets=(60, 300, 900, 3600, 86400, 172800, 604800),
    )
except Exception:
    governance_approval_step_duration_seconds = _GaugeStub()
