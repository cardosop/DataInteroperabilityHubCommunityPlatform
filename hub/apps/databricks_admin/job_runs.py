"""Phase 4 (openspec add-databricks-jobs task 4.4) — the run-now flow.

A run-now maps onto the Hub ``Job`` machinery (``JobType.DATABRICKS_JOB_RUN``
— design D4): the service dispatches through the 4.3 ``DatabricksJobsClient``
(``run_now``), records the Databricks run id on the additive Job column,
then a BACKOFF poller follows ``runs/get`` (the 0.7 executor's poll
discipline: initial interval x factor, capped, with a wall-clock budget)
until a terminal lifecycle state (TERMINATED / INTERNAL_ERROR / SKIPPED).
The terminal transition emits:

- the run's audit event — ``DATABRICKS_JOB_RUN_STARTED`` when the run
  dispatches, ``DATABRICKS_JOB_RUN_SUCCEEDED`` / ``DATABRICKS_JOB_RUN_FAILED``
  at the terminal state (resource_type=DATABRICKS_JOB, one row per Hub-side
  transition; best-effort — an audit outage never blocks the transition);
- an OpenLineage run event — COMPLETE on success, FAIL with the
  errorMessage facet on failure (capability-gated behind
  ``lineage.openlineage_export``, dispatched fire-and-forget, fail-soft —
  the contracts/lineage_sync convention);
- a duration-x-size cost ESTIMATE — computed from the run payload's real
  ``run_duration`` (falling back to the part durations) and the run's
  ``cluster_spec`` worker count, stored in ``Job.result_json``. The
  estimate is STORED, not billed — cost ATTRIBUTION lands with P7.

Contracts:

- **The caller owns the client** (the 3.3 contract) — the 4.3 client is
  the required keyword; identity resolution is the caller's concern.
- **Fail-closed dispatch**: a rejected run-now marks the Hub Job FAILED
  with the classified code and emits ``RUN_FAILED`` — no ``RUN_STARTED``
  row for a run that never dispatched, ZERO polling. A MALFORMED
  run-now answer (a non-numeric or out-of-range run id) is the SAME
  dispatch failure — never a ValueError/DataError leak with the Hub Job
  stranded in PENDING.
- **The poll budget fails closed**: exhausting the budget marks the Job
  FAILED ("poll budget exhausted") — a run that never reaches a terminal
  state is never reported as a success.
- **A mid-poll client failure fails closed**: a classified
  ``Databricks*Error`` from ``runs/get`` (a persistent 5xx/429 after the
  retry budget) marks the Job FAILED with the classified code — the
  poller never strands a RUNNING Job with an unhandled error.
- **Never-invented states**: every ``result_state`` in the 4.2 vocabulary
  maps to a documented Job status; an absent result at TERMINATED is a
  failure (fail-closed, not a fabricated success); a malformed (non
  object / missing) ``state`` payload is never a terminal state — the
  budget governs it.
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import timezone

from hub.apps.databricks_admin.client import DatabricksApiError
from hub.apps.databricks_admin.models import DatabricksJob, DatabricksJobRunResultState
from hub.apps.jobs.models import Job, JobStatus, JobType

if TYPE_CHECKING:
    from collections.abc import Callable

    from hub.apps.databricks_admin.jobs_client import DatabricksJobsClient
    from hub.apps.databricks_admin.models import DatabricksWorkspace

logger = logging.getLogger(__name__)

# The outbound OpenLineage dispatch (the contracts/lineage_sync seam):
# lazy-imported so the module imports without the integrations app, and
# a MODULE-LEVEL attribute so the sanctioned patch point in tests
# (monkeypatching ``job_runs.send_openlineage_event_async``) reaches
# every dispatch.
send_openlineage_event_async: Any | None = None
with contextlib.suppress(ImportError):
    from hub.apps.integrations.openlineage.tasks import (
        send_openlineage_event_async,
    )

# 4.5 — the databricks.job.run.failed webhook notifier (landed after 4.4;
# wired at the terminal-failure chokepoints). Lazy-imported with the
# same sanctioned-patch-point shape as the lineage seam.
notify_job_run_failed: Any | None = None
with contextlib.suppress(ImportError):
    from hub.apps.databricks_admin.job_webhooks import (
        notify_job_run_failed,
    )

# The poll discipline (design D4 — the executor's backoff shape, sized
# for job runs): 2s initial, x1.5 per step, capped at 30s, against a
# wall-clock budget the caller overrides via poll_timeout_s.
_POLL_INITIAL_INTERVAL_S = 2.0
_POLL_BACKOFF_FACTOR = 1.5
_POLL_MAX_INTERVAL_S = 30.0
_DEFAULT_POLL_TIMEOUT_S = 3600.0

# Terminal lifecycle states — polling stops on these (TERMINATED is the
# normal path; INTERNAL_ERROR and SKIPPED are anomalous terminals that
# must never hang the poller).
_POLL_TERMINAL_LIFECYCLE_STATES = frozenset({"TERMINATED", "INTERNAL_ERROR", "SKIPPED"})

# The WHOLE 4.2 result vocabulary → Hub Job status (never invented).
# SUCCESS_WITH_FAILURES is a completed run (the details carry the state);
# EXCLUDED is a run the queueing policy refused — never executed, so the
# Hub Job is CANCELLED (the result state is recorded in result_json).
_RESULT_TO_JOB_STATUS: dict[str, str] = {
    DatabricksJobRunResultState.SUCCESS: JobStatus.COMPLETED,
    DatabricksJobRunResultState.SUCCESS_WITH_FAILURES: JobStatus.COMPLETED,
    DatabricksJobRunResultState.FAILED: JobStatus.FAILED,
    DatabricksJobRunResultState.TIMEDOUT: JobStatus.FAILED,
    DatabricksJobRunResultState.MAXIMUM_CONCURRENT_RUNS_REACHED: JobStatus.FAILED,
    DatabricksJobRunResultState.UPSTREAM_FAILED: JobStatus.FAILED,
    DatabricksJobRunResultState.CANCELED: JobStatus.CANCELLED,
    DatabricksJobRunResultState.UPSTREAM_CANCELED: JobStatus.CANCELLED,
    DatabricksJobRunResultState.EXCLUDED: JobStatus.CANCELLED,
}

# The cost-estimate heuristic base rate (USD per DBH). P7 replaces the
# estimate with real attribution; until then this documented constant
# feeds the stored estimate.
_DEFAULT_DBH_RATE = 0.55


def run_databricks_job_now(
    *,
    workspace: DatabricksWorkspace,
    mirror_job: DatabricksJob,
    actor_user,
    client: DatabricksJobsClient,
    poll_timeout_s: float | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> Job:
    """Dispatch a run-now for the mirrored job and follow it to its
    terminal state (design D4).

    Returns the Hub ``Job`` row in its terminal state. All emissions are
    best-effort: an audit/lineage/metric failure never blocks the
    transition (the Phase 273 contract).
    """
    timeout = float(poll_timeout_s if poll_timeout_s is not None else _DEFAULT_POLL_TIMEOUT_S)

    job = Job.objects.create(
        tenant=workspace.tenant,
        type=JobType.DATABRICKS_JOB_RUN,
        status=JobStatus.PENDING,
        resource_type="DATABRICKS_JOB",
        resource_id=mirror_job.id,
        created_by=actor_user,
        timeout_seconds=int(timeout),
        details_json={
            "workspace_id": str(workspace.id),
            "databricks_job_id": str(mirror_job.job_id),
            "job_name": mirror_job.name,
        },
    )

    try:
        run_id = client.run_now(str(mirror_job.job_id))
    except DatabricksApiError as exc:
        # Fail-closed dispatch: the run never dispatched — no STARTED row,
        # no polling, the Hub Job records the terminal failure.
        _fail_dispatch(job, workspace, actor_user, mirror_job, run_id=None, exc=exc)
        return job
    try:
        numeric_run_id = _require_numeric_run_id(run_id)
    except DatabricksApiError as exc:
        # A malformed run-now answer (non-numeric / out-of-range id) is
        # the SAME dispatch failure — never a leak with the Job stranded.
        _fail_dispatch(job, workspace, actor_user, mirror_job, run_id=run_id, exc=exc)
        return job

    job.databricks_run_id = numeric_run_id
    job.status = JobStatus.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["databricks_run_id", "status", "started_at"])
    _emit_run_audit(
        "RUN_STARTED",
        job=job,
        workspace=workspace,
        actor_user=actor_user,
        extra={
            "databricks_job_id": str(mirror_job.job_id),
            "databricks_run_id": run_id,
        },
    )

    try:
        run_payload = _poll_until_terminal(client, run_id, timeout_s=timeout, sleeper=sleeper)
    except _PollBudgetExhausted as exc:
        _mark_failed(
            job,
            f"poll budget exhausted after {timeout:.0f}s — the run never reached a terminal state",
            extra={"databricks_run_id": run_id, "last_lifecycle_state": exc.last_state},
        )
        _emit_run_audit(
            "RUN_FAILED",
            job=job,
            workspace=None,
            actor_user=None,
            extra={"databricks_run_id": run_id, "reason": "poll_budget_exhausted"},
        )
        _emit_run_lineage(job, failed=True)
        _notify_failure(job, result_state="", message=job.error_message)
        return job
    except DatabricksApiError as exc:
        # A classified mid-poll failure (a persistent 5xx/429 after the
        # retry budget, or a workspace rejection) fails the Job closed —
        # never a stranded RUNNING Job with an unhandled client error.
        _mark_failed(
            job,
            f"polling failed: {getattr(exc, 'code', '')} {exc}",
            extra={
                "databricks_run_id": run_id,
                "poll_error_code": getattr(exc, "code", ""),
            },
        )
        _emit_run_audit(
            "RUN_FAILED",
            job=job,
            workspace=None,
            actor_user=None,
            extra={"databricks_run_id": run_id, "reason": "poll_error"},
        )
        _emit_run_lineage(job, failed=True)
        _notify_failure(job, result_state="", message=job.error_message)
        return job

    _mark_terminal(job, run_payload)
    return job


def _poll_until_terminal(
    client: DatabricksJobsClient,
    run_id: str,
    *,
    timeout_s: float,
    sleeper: Callable[[float], None],
) -> dict:
    """Follow ``runs/get`` with backoff until a terminal lifecycle state
    or the wall-clock budget (the sentinel — the caller fails the Job
    closed)."""
    started = time.monotonic()
    interval = _POLL_INITIAL_INTERVAL_S
    while True:
        payload = client.get_run(run_id)
        state = payload.get("state")
        lifecycle = str(state.get("life_cycle_state") or "") if isinstance(state, dict) else ""
        if lifecycle in _POLL_TERMINAL_LIFECYCLE_STATES:
            return payload
        if time.monotonic() - started > timeout_s:
            raise _PollBudgetExhausted(timeout_s, lifecycle)
        sleeper(interval)
        interval = min(interval * _POLL_BACKOFF_FACTOR, _POLL_MAX_INTERVAL_S)


class _PollBudgetExhausted(Exception):
    """Internal sentinel — the budget path fails the Job closed."""

    def __init__(self, timeout_s: float, last_state: str | None):
        super().__init__(f"poll budget exhausted after {timeout_s:.0f}s")
        self.last_state = last_state


def _require_numeric_run_id(run_id: str) -> int:
    """The Hub column is BigInteger — the jobs API's run ids are int64.
    A malformed run-now answer (non-numeric, negative, or out of the
    64-bit range) is a CLASSIFIED dispatch failure: never a ValueError
    or DataError leak with the Hub Job stranded (fail-closed)."""
    try:
        value = int(run_id)
    except (TypeError, ValueError):
        raise DatabricksApiError(f"run-now returned a non-numeric run id '{run_id}'") from None
    if not 0 <= value < 2**63:
        raise DatabricksApiError(f"run-now returned an out-of-range run id '{run_id}'")
    return value


def _fail_dispatch(
    job: Job,
    workspace: DatabricksWorkspace,
    actor_user,
    mirror_job: DatabricksJob,
    *,
    run_id: str | None,
    exc: DatabricksApiError,
) -> None:
    """The fail-closed dispatch chokepoint — a rejected or malformed
    run-now answer marks the Hub Job FAILED with the classified code
    and emits the terminal-failure set: the RUN_FAILED audit (no
    STARTED row for a run that never dispatched), the FAIL lineage
    event (the 4.8 review fix — lineage fires at ALL terminal-failure
    chokepoints), and the 4.5 webhook. The raw run id is kept in the
    audit details for diagnosis — never invented."""
    _mark_failed(
        job,
        f"run-now dispatch failed: {getattr(exc, 'code', '')} {exc}",
        extra={
            "dispatch_error_code": getattr(exc, "code", ""),
            "databricks_run_id": run_id,
        },
    )
    _emit_run_audit(
        "RUN_FAILED",
        job=job,
        workspace=workspace,
        actor_user=actor_user,
        extra={
            "databricks_job_id": str(mirror_job.job_id),
            "databricks_run_id": run_id or "",
        },
    )
    _emit_run_lineage(job, failed=True)
    _notify_failure(job, result_state="", message=job.error_message)


def _mark_terminal(job: Job, run_payload: dict) -> None:
    """Map the run's terminal state onto the Hub Job and emit the
    terminal audit + OpenLineage + the stored cost estimate."""
    state = run_payload.get("state") or {}
    result = str(state.get("result_state") or "")
    message = str(state.get("state_message") or "")
    lifecycle = str(state.get("life_cycle_state") or "")

    status = _RESULT_TO_JOB_STATUS.get(result)
    if status is None:
        # An absent/unknown result at a terminal lifecycle state is a
        # failure — never a fabricated success (the 3.3 discipline).
        status = JobStatus.FAILED
        message = message or f"terminal lifecycle state '{lifecycle}' without a result state"

    job.status = status
    job.completed_at = timezone.now()
    if status == JobStatus.FAILED or (status == JobStatus.CANCELLED and message):
        job.error_message = message
    result_json = dict(job.result_json or {})
    result_json["databricks_run_state"] = result or None
    result_json["cost_estimate"] = estimate_run_cost(run_payload)
    if status == JobStatus.COMPLETED and result == "SUCCESS_WITH_FAILURES":
        result_json["partial_failures"] = True
    job.result_json = result_json
    job.save(update_fields=["status", "completed_at", "error_message", "result_json"])

    audit_action = "RUN_SUCCEEDED" if status == JobStatus.COMPLETED else "RUN_FAILED"
    _emit_run_audit(
        audit_action,
        job=job,
        workspace=None,
        actor_user=None,
        extra={
            "databricks_run_id": str(run_payload.get("run_id") or ""),
            "databricks_run_state": result or None,
        },
    )
    _emit_run_lineage(job, failed=status != JobStatus.COMPLETED)
    if status != JobStatus.COMPLETED:
        _notify_failure(job, result_state=result, message=job.error_message)


def _notify_failure(job: Job, *, result_state: str, message: str | None) -> None:
    """4.5 — the ``databricks.job.run.failed`` webhook at the terminal
    failure chokepoints (dispatch rejection, terminal failure, poll
    budget). Best-effort: the helper itself never raises by contract,
    and the call is guarded regardless."""
    if notify_job_run_failed is None:
        return
    try:
        details = job.details_json or {}
        notify_job_run_failed(
            tenant_id=str(job.tenant_id or ""),
            workspace_id=str(details.get("workspace_id") or ""),
            job_id=str(details.get("databricks_job_id") or ""),
            run_id=str(job.databricks_run_id or ""),
            result_state=result_state,
            error_message=message,
        )
    except Exception:
        logger.warning(
            "databricks_job_run_webhook_failed",
            extra={"job_id": str(job.id)},
        )


def _mark_failed(job: Job, message: str, *, extra: dict | None = None) -> None:
    job.status = JobStatus.FAILED
    job.completed_at = timezone.now()
    job.error_message = message
    result_json = dict(job.result_json or {})
    result_json.update(extra or {})
    job.result_json = result_json
    job.save(update_fields=["status", "completed_at", "error_message", "result_json"])


def estimate_run_cost(run_payload: dict) -> dict:
    """The duration-x-size cost ESTIMATE (design D4 — stored, not
    billed; P7 replaces it with real attribution).

    duration comes from the run payload's REAL ``run_duration`` (ms),
    falling back to setup+execution+cleanup when absent; the size factor
    derives from the run's ``cluster_spec.num_workers`` (0.5 DBH per
    worker — a documented heuristic), 1.0 when the spec is absent or
    malformed.
    """
    duration_ms = run_payload.get("run_duration")
    if duration_ms is None:
        duration_ms = sum(
            int(run_payload.get(key) or 0)
            for key in ("setup_duration", "execution_duration", "cleanup_duration")
        )
    try:
        duration_seconds = float(duration_ms) / 1000.0
    except (TypeError, ValueError):
        duration_seconds = 0.0

    cluster_spec = run_payload.get("cluster_spec")
    workers = 0
    if isinstance(cluster_spec, dict):
        try:
            workers = max(0, int(cluster_spec.get("num_workers") or 0))
        except (TypeError, ValueError):
            workers = 0
    size_factor = 1.0 + 0.5 * workers

    rate = float(getattr(settings, "DATABRICKS_JOB_COST_ESTIMATE_DBH_RATE", _DEFAULT_DBH_RATE))
    cost = (duration_seconds / 3600.0) * rate * size_factor
    return {
        "duration_seconds": duration_seconds,
        "size_factor": size_factor,
        "dbh_rate": rate,
        "estimated_cost": round(cost, 6),
        "formula": "duration_hours x dbh_rate x (1 + 0.5 x num_workers)",
    }


def _emit_run_audit(action: str, *, job: Job, workspace, actor_user, extra: dict) -> None:
    """The run lifecycle chokepoint — one row per Hub-side transition
    (best-effort: an audit-DB outage never blocks the operation)."""
    try:
        from hub.apps.audit.utils import create_audit_event

        tenant = workspace.tenant if workspace is not None else job.tenant
        details = {
            "databricks_job_id": str((job.details_json or {}).get("databricks_job_id") or ""),
            "databricks_run_id": str(job.databricks_run_id or ""),
        }
        details.update(extra)
        create_audit_event(
            resource_type="DATABRICKS_JOB",
            action=action,
            actor_user=actor_user or job.created_by,
            tenant=tenant,
            resource_id=str(job.id),
            details=details,
        )
    except Exception:
        logger.warning(
            "databricks_job_run_audit_failed",
            extra={"action": action, "job_id": str(job.id)},
        )


def _emit_run_lineage(job: Job, *, failed: bool) -> None:
    """The terminal OpenLineage run event — COMPLETE on success, FAIL
    with the errorMessage facet on failure. Capability-gated
    (``lineage.openlineage_export``) and fail-soft (the contracts/
    lineage_sync convention); the dispatch is fire-and-forget."""
    try:
        from hub.apps.api.capabilities import is_capability_enabled
    except Exception:
        return
    if not is_capability_enabled("lineage.openlineage_export"):
        return

    if send_openlineage_event_async is None:
        return

    from hub.apps.integrations.openlineage.translator import OPENLINEAGE_SCHEMA_URL

    job_id = str((job.details_json or {}).get("databricks_job_id") or "")
    run_id = str(job.databricks_run_id or "")
    producer = getattr(
        settings,
        "OPENLINEAGE_PRODUCER_NAME",
        "https://meshant.com/jobs/openlineage",
    )
    run_facets: dict[str, Any] = {}
    if failed:
        message = job.error_message or "the Databricks run failed"
        run_facets["errorMessage"] = {
            "message": message,
            "programmingLanguage": None,
            "stackTrace": None,
        }
    event = {
        "eventType": "FAIL" if failed else "COMPLETE",
        "eventTime": timezone.now().isoformat(),
        "producer": producer,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
        "run": {
            "runId": f"databricks:{job_id}:{run_id}",
            "facets": run_facets,
        },
        "job": {
            "namespace": "meshant.databricks",
            "name": str((job.details_json or {}).get("job_name") or job_id),
        },
        "inputs": [],
        "outputs": [],
    }
    try:
        dispatch_fn = getattr(send_openlineage_event_async, "delay", send_openlineage_event_async)
        dispatch_fn(
            event=event,
            target_url=getattr(settings, "OPENLINEAGE_URL", None),
            tenant_id=str(job.tenant_id or ""),
        )
    except Exception as exc:
        logger.warning(
            "databricks_job_run_lineage_dispatch_failed",
            extra={"job_id": str(job.id), "error": str(exc)},
        )
