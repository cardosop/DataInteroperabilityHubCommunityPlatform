"""Phase 1 (openspec add-databricks-uc-read task 1.10) — UC metadata sync
metrics.

Consumed by ``monitoring/grafana/dashboards/databricks-uc-sync.json``
and ``monitoring/prometheus/alerts/databricks-uc-sync.yml``. The
``record_*`` wrappers are the module boundary tests patch (the
search/metrics convention) and are best-effort — a metric-backend
outage MUST NOT fail the sync.
"""

from __future__ import annotations

from typing import Protocol

from prometheus_client import Counter, Gauge, Histogram


class _MetricLike(Protocol):
    def labels(self, **kwargs: str) -> _MetricLike: ...

    def inc(self, amount: float = 1) -> None: ...

    def observe(self, amount: float) -> None: ...

    def set(self, amount: float) -> None: ...


class _MetricStub:
    """No-op fallback (the search/metrics convention) — keeps the metric
    ``_name`` so the 1.10 drift pin (test_uc_sync_alerts) still reads it."""

    def __init__(self, name: str) -> None:
        self._name = name

    def labels(self, **_: object) -> _MetricStub:
        return self

    def inc(self, _amount: float = 1) -> None:
        return None

    def observe(self, _amount: float) -> None:
        return None

    def set(self, _amount: float) -> None:
        return None


try:
    databricks_uc_sync_runs_total: Counter | _MetricStub = Counter(
        "databricks_uc_sync_runs_total",
        "UC metadata sync runs by outcome (success/failure/skipped)",
        ["outcome", "tenant_id"],
    )
    databricks_uc_sync_duration_seconds: Histogram | _MetricStub = Histogram(
        "databricks_uc_sync_duration_seconds",
        "Per-workspace UC metadata sync duration",
        buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600),
    )
    databricks_uc_sync_rows_total: Counter | _MetricStub = Counter(
        "databricks_uc_sync_rows_total",
        "Mirror rows written by the UC metadata sync, per operation",
        ["operation", "tenant_id"],
    )
    databricks_uc_sync_last_success_timestamp: Gauge | _MetricStub = Gauge(
        "databricks_uc_sync_last_success_timestamp",
        "Unix timestamp of the last successful sync per workspace "
        "(the staleness anchor for DatabricksUCMetadataSyncStale)",
        ["tenant_id", "workspace"],
    )
except Exception:
    # dev autoreload): prometheus_client raises on the same name twice, and
    # RE-INSTANTIATING the names here would raise the same ValueError —
    # degrade to no-op stubs instead of crashing the module import.
    databricks_uc_sync_runs_total = _MetricStub("databricks_uc_sync_runs_total")
    databricks_uc_sync_duration_seconds = _MetricStub("databricks_uc_sync_duration_seconds")
    databricks_uc_sync_rows_total = _MetricStub("databricks_uc_sync_rows_total")
    databricks_uc_sync_last_success_timestamp = _MetricStub(
        "databricks_uc_sync_last_success_timestamp"
    )


def record_sync_outcome(outcome: str, *, tenant_id: str | None = None) -> None:
    """Record one sync run's outcome. Best-effort — never raises."""
    try:
        databricks_uc_sync_runs_total.labels(
            outcome=outcome, tenant_id=tenant_id or "UNKNOWN"
        ).inc()
    except Exception:
        return


def record_sync_duration(*, seconds: float) -> None:
    """Record a per-workspace sync duration. Best-effort — never raises."""
    try:
        databricks_uc_sync_duration_seconds.observe(max(seconds, 0.0))
    except Exception:
        return


def record_sync_rows(operation: str, count: int, *, tenant_id: str | None = None) -> None:
    """Record mirror rows written per operation (created/updated/deleted).
    Best-effort — never raises."""
    if count <= 0:
        return
    try:
        databricks_uc_sync_rows_total.labels(
            operation=operation, tenant_id=tenant_id or "UNKNOWN"
        ).inc(count)
    except Exception:
        return


def record_sync_success_timestamp(*, tenant_id: str, workspace_id: str, value: float) -> None:
    """Stamp the last-success anchor for the staleness alert.
    Best-effort — never raises."""
    try:
        databricks_uc_sync_last_success_timestamp.labels(
            tenant_id=tenant_id, workspace=workspace_id
        ).set(value)
    except Exception:
        return


# ── 2.8 — UC change approval pipeline ────────────────────────────────────────

try:
    databricks_uc_change_requests_total: Counter | _MetricStub = Counter(
        "databricks_uc_change_requests_total",
        "UC change-request lifecycle transitions by event "
        "(submitted/approved/rejected/executed/failed/rolled_back)",
        ["event", "tenant_id"],
    )
    databricks_uc_approval_duration_seconds: Histogram | _MetricStub = Histogram(
        "databricks_uc_approval_duration_seconds",
        "UC change-request approval latency (created → approved/rejected)",
        buckets=(60, 300, 900, 1800, 3600, 7200, 14400, 43200, 86400),
    )
    databricks_uc_change_pending_approvals: Gauge | _MetricStub = Gauge(
        "databricks_uc_change_pending_approvals",
        "UC change requests awaiting approval per tenant (the backlog alert)",
        ["tenant_id"],
    )
    databricks_uc_change_oldest_pending_seconds: Gauge | _MetricStub = Gauge(
        "databricks_uc_change_oldest_pending_seconds",
        "Age of the tenant's oldest pending UC change request (the staleness alert)",
        ["tenant_id"],
    )
except Exception:
    # dev autoreload): degrade to no-op stubs instead of crashing the import
    # (the 1.10 pattern — the 9.4 review extended it to the 2.8 section).
    databricks_uc_change_requests_total = _MetricStub("databricks_uc_change_requests_total")
    databricks_uc_approval_duration_seconds = _MetricStub("databricks_uc_approval_duration_seconds")
    databricks_uc_change_pending_approvals = _MetricStub("databricks_uc_change_pending_approvals")
    databricks_uc_change_oldest_pending_seconds = _MetricStub(
        "databricks_uc_change_oldest_pending_seconds"
    )


def record_uc_change_request(event: str, *, tenant_id: str | None = None) -> None:
    """Record one lifecycle transition. Best-effort — never raises."""
    try:
        databricks_uc_change_requests_total.labels(
            event=event, tenant_id=tenant_id or "UNKNOWN"
        ).inc()
    except Exception:
        return


def record_uc_approval_duration(*, seconds: float) -> None:
    """Record the created → approved/rejected latency. Best-effort."""
    try:
        databricks_uc_approval_duration_seconds.observe(max(seconds, 0.0))
    except Exception:
        return


def refresh_uc_approval_gauges(tenant_id: str) -> None:
    """Recompute the tenant's pending count + oldest-pending age from the
    REAL rows and set both gauges (called on every transition — the
    gauges track the live backlog). Best-effort — never raises."""
    try:
        from django.utils import timezone

        from hub.apps.databricks_admin.models import (
            UCChangeRequest,
            UCChangeRequestStatus,
        )

        pending = UCChangeRequest.objects.filter(
            tenant_id=tenant_id,
            status__in=(
                UCChangeRequestStatus.PENDING_APPROVAL,
                UCChangeRequestStatus.PENDING_NEXT_APPROVER,
            ),
        )
        count = pending.count()
        oldest = pending.order_by("created_at").values_list("created_at", flat=True).first()
        oldest_age = max(0.0, (timezone.now() - oldest).total_seconds()) if oldest else 0.0
        databricks_uc_change_pending_approvals.labels(tenant_id=tenant_id).set(count)
        databricks_uc_change_oldest_pending_seconds.labels(tenant_id=tenant_id).set(oldest_age)
    except Exception:
        return


# ── 3.8 — SQL warehouse fleet observability ───────────────────────────────────

try:
    databricks_warehouse_mirror_last_success_timestamp: Gauge | _MetricStub = Gauge(
        "databricks_warehouse_mirror_last_success_timestamp",
        "Unix timestamp of the last successful mirror refresh per workspace "
        "(the staleness anchor for DatabricksWarehouseMirrorStale)",
        ["tenant_id", "workspace_id"],
    )
    databricks_warehouse_state_count: Gauge | _MetricStub = Gauge(
        "databricks_warehouse_state_count",
        "Mirrored SQL warehouses per lifecycle state per workspace",
        ["state", "tenant_id", "workspace_id"],
    )
    databricks_warehouse_starting_since_timestamp: Gauge | _MetricStub = Gauge(
        "databricks_warehouse_starting_since_timestamp",
        "Unix timestamp when the warehouse FIRST entered STARTING "
        "(0 = not starting; the long-STARTING alert anchor)",
        ["warehouse_id", "tenant_id", "workspace_id"],
    )
    databricks_warehouse_pool_borrows_total: Counter | _MetricStub = Counter(
        "databricks_warehouse_pool_borrows_total",
        "SQL-warehouse connection-pool borrows per tenant",
        ["tenant_id"],
    )
    databricks_warehouse_pool_exhausted_total: Counter | _MetricStub = Counter(
        "databricks_warehouse_pool_exhausted_total",
        "SQL-warehouse connection-pool exhaustion refusals per tenant",
        ["tenant_id"],
    )
    databricks_warehouse_pool_in_use: Gauge | _MetricStub = Gauge(
        "databricks_warehouse_pool_in_use",
        "Connections currently borrowed per tenant (the pool-pressure gauge)",
        ["tenant_id"],
    )
except Exception:
    # dev autoreload): degrade to no-op stubs instead of crashing the import
    # (the 1.10 pattern).
    databricks_warehouse_mirror_last_success_timestamp = _MetricStub(
        "databricks_warehouse_mirror_last_success_timestamp"
    )
    databricks_warehouse_state_count = _MetricStub("databricks_warehouse_state_count")
    databricks_warehouse_starting_since_timestamp = _MetricStub(
        "databricks_warehouse_starting_since_timestamp"
    )
    databricks_warehouse_pool_borrows_total = _MetricStub("databricks_warehouse_pool_borrows_total")
    databricks_warehouse_pool_exhausted_total = _MetricStub(
        "databricks_warehouse_pool_exhausted_total"
    )
    databricks_warehouse_pool_in_use = _MetricStub("databricks_warehouse_pool_in_use")


def record_warehouse_mirror_success(*, tenant_id: str, workspace_id: str) -> None:
    """Stamp the last-success anchor for the stale-mirror alert.
    Best-effort — never raises."""
    try:
        import time

        databricks_warehouse_mirror_last_success_timestamp.labels(
            tenant_id=tenant_id, workspace_id=workspace_id
        ).set(time.time())
    except Exception:
        return


def record_warehouse_state_counts(workspace) -> None:
    """Set the per-state count gauges for the workspace's REAL mirror rows
    (all five states, 0 for absent ones). Best-effort — never raises."""
    try:
        from hub.apps.databricks_admin.models import (
            DatabricksSqlWarehouse,
            DatabricksSqlWarehouseState,
        )

        counts = dict.fromkeys(DatabricksSqlWarehouseState.values, 0)
        for state in DatabricksSqlWarehouse.objects.filter(workspace=workspace).values_list(
            "state", flat=True
        ):
            counts[state] = counts.get(state, 0) + 1
        for state, count in counts.items():
            databricks_warehouse_state_count.labels(
                state=state,
                tenant_id=str(workspace.tenant_id),
                workspace_id=str(workspace.id),
            ).set(count)
    except Exception:
        return


def record_warehouse_starting_since(
    *, warehouse_id: str, tenant_id: str, workspace_id: str, seconds_since_epoch: float
) -> None:
    """Set the STARTING-since anchor: the first-seen epoch when the
    warehouse entered STARTING, 0 when it left (or is not starting).
    Best-effort — never raises."""
    try:
        databricks_warehouse_starting_since_timestamp.labels(
            warehouse_id=warehouse_id, tenant_id=tenant_id, workspace_id=workspace_id
        ).set(seconds_since_epoch)
    except Exception:
        return


def record_pool_borrow(*, tenant_id: str) -> None:
    """Record one successful pool borrow. Best-effort — never raises."""
    try:
        databricks_warehouse_pool_borrows_total.labels(tenant_id=tenant_id).inc()
    except Exception:
        return


def record_pool_exhausted(*, tenant_id: str) -> None:
    """Record one exhaustion refusal. Best-effort — never raises."""
    try:
        databricks_warehouse_pool_exhausted_total.labels(tenant_id=tenant_id).inc()
    except Exception:
        return


def set_pool_in_use(*, tenant_id: str, count: int) -> None:
    """Set the tenant's in-use gauge (the pool-pressure anchor).
    Best-effort — never raises."""
    try:
        databricks_warehouse_pool_in_use.labels(tenant_id=tenant_id).set(count)
    except Exception:
        return


# ── 4.5 — Databricks job-fleet observability ──────────────────────────────────

try:
    databricks_jobs_mirror_last_success_timestamp: Gauge | _MetricStub = Gauge(
        "databricks_jobs_mirror_last_success_timestamp",
        "Unix timestamp of the last successful job/run mirror refresh per workspace "
        "(the staleness anchor for DatabricksJobMirrorStale)",
        ["tenant_id", "workspace_id"],
    )
    databricks_job_run_state_count: Gauge | _MetricStub = Gauge(
        "databricks_job_run_state_count",
        "Mirrored job runs per lifecycle state per workspace",
        ["lifecycle_state", "tenant_id", "workspace_id"],
    )
    databricks_job_run_started_since_timestamp: Gauge | _MetricStub = Gauge(
        "databricks_job_run_started_since_timestamp",
        "Unix timestamp when the run FIRST appeared in a non-terminal state "
        "(0 = terminal/absent; the long-running alert anchor)",
        ["run_id", "tenant_id", "workspace_id"],
    )
    databricks_job_runs_total: Counter | _MetricStub = Counter(
        "databricks_job_runs_total",
        "Terminal job runs per reported outcome per workspace (the 4.4 poller "
        "records the terminal transition; the failure-rate alert anchor)",
        ["outcome", "tenant_id", "workspace_id"],
    )
except Exception:
    # dev autoreload): degrade to no-op stubs instead of crashing the import
    # (the 1.10 pattern).
    databricks_jobs_mirror_last_success_timestamp = _MetricStub(
        "databricks_jobs_mirror_last_success_timestamp"
    )
    databricks_job_run_state_count = _MetricStub("databricks_job_run_state_count")
    databricks_job_run_started_since_timestamp = _MetricStub(
        "databricks_job_run_started_since_timestamp"
    )
    databricks_job_runs_total = _MetricStub("databricks_job_runs_total")


def record_jobs_mirror_success(*, tenant_id: str, workspace_id: str) -> None:
    """Stamp the last-success anchor for the stale-mirror alert.
    Best-effort — never raises."""
    try:
        import time

        databricks_jobs_mirror_last_success_timestamp.labels(
            tenant_id=tenant_id, workspace_id=workspace_id
        ).set(time.time())
    except Exception:
        return


def record_job_run_state_counts(workspace) -> None:
    """Set the per-lifecycle-state count gauges for the workspace's REAL
    run mirror rows (all states, 0 for absent ones). Best-effort —
    never raises."""
    try:
        from hub.apps.databricks_admin.models import (
            DatabricksJobRun,
            DatabricksJobRunLifecycleState,
        )

        counts = dict.fromkeys(DatabricksJobRunLifecycleState.values, 0)
        for state in DatabricksJobRun.objects.filter(job__workspace=workspace).values_list(
            "lifecycle_state", flat=True
        ):
            counts[state] = counts.get(state, 0) + 1
        for state, count in counts.items():
            databricks_job_run_state_count.labels(
                lifecycle_state=state,
                tenant_id=str(workspace.tenant_id),
                workspace_id=str(workspace.id),
            ).set(count)
    except Exception:
        return


def record_job_run_started_since(
    *, run_id: str, tenant_id: str, workspace_id: str, seconds_since_epoch: float
) -> None:
    """Set the running-since anchor: the first-seen epoch when the run
    appeared in a non-terminal state, 0 when it reached a terminal state
    (or left the mirror). Best-effort — never raises."""
    try:
        databricks_job_run_started_since_timestamp.labels(
            run_id=run_id, tenant_id=tenant_id, workspace_id=workspace_id
        ).set(seconds_since_epoch)
    except Exception:
        return


def record_job_run_outcome(*, outcome: str, tenant_id: str, workspace_id: str) -> None:
    """Record one terminal run outcome (the 4.4 poller's terminal
    transition). Best-effort — never raises."""
    try:
        databricks_job_runs_total.labels(
            outcome=outcome, tenant_id=tenant_id, workspace_id=workspace_id
        ).inc()
    except Exception:
        return


# ── Phase 7 (add-databricks-cost-guardrails 7.6) — cost-budget window ──

try:
    databricks_cost_budget_consumed_ratio: Gauge | _MetricStub = Gauge(
        "databricks_cost_budget_consumed_ratio",
        "Rolling-hour consumed/budget ratio per budget scope (1.0 = at budget)",
        ["tenant_id", "scope"],
    )
    databricks_cost_budget_crossings_total: Counter | _MetricStub = Counter(
        "databricks_cost_budget_crossings_total",
        "Budget crossings observed by the enforcement (fires once per crossing)",
        ["tenant_id", "scope"],
    )
except Exception:
    # dev autoreload): degrade to no-op stubs instead of crashing the import
    # (the 1.10 pattern — the 9.4 review extended it to the 7.6 section).
    databricks_cost_budget_consumed_ratio = _MetricStub("databricks_cost_budget_consumed_ratio")
    databricks_cost_budget_crossings_total = _MetricStub("databricks_cost_budget_crossings_total")


def record_budget_consumed_ratio(*, tenant_id: str, scope: str, ratio: float) -> None:
    """Set the consumed/budget ratio for one budget scope — the SAME
    window read the enforcement/page computed (dashboards + alerts feed
    this). Best-effort — never raises."""
    try:
        databricks_cost_budget_consumed_ratio.labels(tenant_id=tenant_id, scope=scope).set(ratio)
    except Exception:
        return


def record_budget_crossing(*, tenant_id: str, scope: str) -> None:
    """Record one budget crossing (fires when the webhook fires).
    Best-effort — never raises."""
    try:
        databricks_cost_budget_crossings_total.labels(tenant_id=tenant_id, scope=scope).inc()
    except Exception:
        return


# ── Phase 10 (add-databricks-dlt-pipelines 10.6) — DLT update fleet ──

try:
    databricks_dlt_updates_total: Counter | _MetricStub = Counter(
        "databricks_dlt_updates_total",
        "DLT pipeline update terminal outcomes by reported state "
        "(COMPLETED/FAILED/CANCELED/TIMED_OUT)",
        ["outcome", "tenant_id", "workspace_id"],
    )
except Exception:
    # dev autoreload): degrade to no-op stubs instead of crashing the import
    # (the 1.10 pattern). The stub MUST mirror the Counter's Python-side
    # name — prometheus strips the ``_total`` suffix there, and the drift
    # pin (test_dlt_update_observability) reads ``._name`` as the wire
    # truth, so a stub keeping the suffix breaks the pin in the fallback
    # branch (the order-dependent full-suite failure class).
    databricks_dlt_updates_total = _MetricStub("databricks_dlt_updates")


def record_dlt_update_outcome(
    outcome: str, *, tenant_id: str | None, workspace_id: str | None
) -> None:
    """Record one terminal update outcome at the finalize chokepoint.
    Best-effort — never raises (the dashboards + alerts feed this)."""
    try:
        databricks_dlt_updates_total.labels(
            outcome=outcome,
            tenant_id=tenant_id or "UNKNOWN",
            workspace_id=workspace_id or "UNKNOWN",
        ).inc()
    except Exception:
        return
