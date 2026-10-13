"""Databricks job/run state mirror (openspec add-databricks-jobs task 4.2).

The mirror is a READ cache of the Databricks-owned job state: the sync
lists the workspace's jobs through the pinned jobs surface
(``jobs.list``, 2.1), then lists its runs (``jobs.runs.list``, 2.1), and
delta-diffs them into ``DatabricksJob``/``DatabricksJobRun`` rows —
created/updated/unchanged/deleted per surface, with the freshness stamp
touched ONLY on change (the 1.5 UC-sync convention). The Hub NEVER
invents a state:

- an API-reported lifecycle/result state the vocabulary does not know is
  SKIPPED with a warning (the row is not created),
- a run whose job is not mirrored is SKIPPED (a run is never hung on an
  invented job),
- malformed shapes are SKIPPED never coerced (the 3.2 review discipline),
- absent jobs/runs leave the mirror without any compensating action,
- a reported-but-skipped id is recorded as SEEN before the skip decision
  (the 3.2 ordering that keeps a skipped row from being swept).

Pagination follows ``next_page_token`` chains exactly (the UC REST
contract) with the repeating-token guard (the 1.12 hardening).

The caller owns the client (identity resolution is the 4.3 jobs
client's contract); this service only maps reported state.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from django.utils import timezone

from hub.apps.databricks_admin.metrics import (
    record_job_run_started_since,
    record_job_run_state_counts,
    record_jobs_mirror_success,
)
from hub.apps.databricks_admin.models import (
    DatabricksJob,
    DatabricksJobRun,
    DatabricksJobRunLifecycleState,
    DatabricksJobRunResultState,
    DatabricksWorkspace,
)

if TYPE_CHECKING:
    from hub.apps.databricks_admin.client import DatabricksApiClient

logger = logging.getLogger(__name__)

# The mirrorable job fields (job_id is the identity, never rewritten).
_JOB_FIELDS = ("name", "task_config", "schedule")
# The mirrorable run fields (run_id is the identity, never rewritten).
_RUN_FIELDS = ("lifecycle_state", "result_state", "duration_ms", "error_message")
# The terminal lifecycle vocabulary — a run in any other state is still
# in flight (the long-running anchor's terminal boundary).
_TERMINAL_LIFECYCLE_STATES = frozenset({"TERMINATED", "SKIPPED", "INTERNAL_ERROR"})


def _json_object(client: DatabricksApiClient, operation: str, params: dict) -> dict:
    """One version-pinned GET with the 0.7 JSON discipline: a malformed
    2xx body is a classified error, never a leaked JSONDecodeError."""
    from hub.apps.databricks_admin.client import DatabricksApiError

    response = client.request("GET", operation, params=dict(params))
    try:
        payload = response.json()
    except ValueError as exc:
        raise DatabricksApiError(f"{operation} returned a non-JSON body") from exc
    if not isinstance(payload, dict):
        raise DatabricksApiError(f"{operation} returned a non-object body")
    return payload


def _list_pages(client: DatabricksApiClient, operation: str, list_key: str) -> list:
    """Follow ``next_page_token`` chains exactly (the UC REST contract).

    1.12 hardening: a repeating ``next_page_token`` (a real workspace bug
    surface) would loop FOREVER — the seen-token guard fails the sync with
    a classified error instead of hanging the worker.
    """
    from hub.apps.databricks_admin.client import DatabricksApiError

    items: list = []
    seen_tokens: set[str] = set()
    request_params: dict = {}
    while True:
        payload = _json_object(client, operation, request_params)
        reported = payload.get(list_key)
        if reported is None:
            return items
        if not isinstance(reported, list):
            raise DatabricksApiError(f"{operation} returned a non-list {list_key}")
        items.extend(reported)
        next_token = payload.get("next_page_token")
        if not next_token:
            return items
        if next_token in seen_tokens:
            raise DatabricksApiError(
                f"{operation} returned a repeating next_page_token "
                f"({next_token!r}) — refusing to loop the pagination"
            )
        seen_tokens.add(next_token)
        request_params["page_token"] = next_token


def _identity(value, *, label: str, workspace_id: str) -> str:
    """The API's id field coerced to the mirror identity string. A
    non-scalar id is a malformed shape — the caller skips the row."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return ""
    result = str(value).strip()
    if not result:
        logger.warning(
            "databricks_jobs_mirror_skip_missing_id",
            extra={"workspace": workspace_id, "id_field": label},
        )
    return result


def refresh_jobs_mirror(workspace: DatabricksWorkspace, *, client: DatabricksApiClient) -> dict:
    """One jobs list + one runs list → delta-diff into the mirror.

    Returns ``{"jobs": {...counters}, "runs": {...counters}}`` — each
    surface carries the created/updated/unchanged/deleted counters. The
    caller runs under the tenant context (RLS) and owns the client
    identity — this service never selects credentials.
    """
    workspace_id = str(workspace.id)
    jobs_counters = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}
    runs_counters = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}

    # ── jobs ──────────────────────────────────────────────────────────
    seen_job_ids: set[str] = set()
    for item in _list_pages(client, "jobs.list", "jobs"):
        if not isinstance(item, dict):
            logger.warning(
                "databricks_jobs_mirror_skip_junk_row",
                extra={"workspace": workspace_id},
            )
            continue
        job_id = _identity(item.get("job_id"), label="job_id", workspace_id=workspace_id)
        if not job_id:
            continue
        # SEEN before the shape guards: a reported-but-skipped job keeps
        # its existing mirror row (never invented, never swept).
        seen_job_ids.add(job_id)

        settings = item.get("settings")
        if not isinstance(settings, dict):
            logger.warning(
                "databricks_jobs_mirror_skip_missing_settings",
                extra={"workspace": workspace_id, "job_id": job_id},
            )
            continue
        name = settings.get("name")
        if not isinstance(name, str) or not name.strip():
            logger.warning(
                "databricks_jobs_mirror_skip_missing_name",
                extra={"workspace": workspace_id, "job_id": job_id},
            )
            continue
        tasks = settings.get("tasks", [])
        if not isinstance(tasks, list) or any(not isinstance(t, dict) for t in tasks):
            logger.warning(
                "databricks_jobs_mirror_skip_non_list_tasks",
                extra={"workspace": workspace_id, "job_id": job_id},
            )
            continue
        schedule = settings.get("schedule")
        if schedule is not None and not isinstance(schedule, dict):
            logger.warning(
                "databricks_jobs_mirror_skip_non_object_schedule",
                extra={"workspace": workspace_id, "job_id": job_id},
            )
            continue

        defaults = {"name": name, "task_config": tasks, "schedule": schedule}
        row = DatabricksJob.objects.filter(workspace=workspace, job_id=job_id).first()
        if row is None:
            DatabricksJob.objects.create(workspace=workspace, job_id=job_id, **defaults)
            jobs_counters["created"] += 1
            continue
        changed = False
        for field, value in defaults.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed = True
        if changed:
            row.synced_at = timezone.now()
            row.save()
            jobs_counters["updated"] += 1
        else:
            jobs_counters["unchanged"] += 1

    # Absent-on-the-workspace jobs leave the mirror — derived, never
    # compensated (their runs die with them via the mirror cascade).
    for row in DatabricksJob.objects.filter(workspace=workspace):
        if row.job_id not in seen_job_ids:
            for run in row.runs.all():
                record_job_run_started_since(
                    run_id=run.run_id,
                    tenant_id=str(workspace.tenant_id),
                    workspace_id=str(workspace.id),
                    seconds_since_epoch=0,
                )
            row.delete()
            jobs_counters["deleted"] += 1

    # ── runs ──────────────────────────────────────────────────────────
    job_rows = {j.job_id: j for j in DatabricksJob.objects.filter(workspace=workspace)}
    seen_run_ids: set[str] = set()
    for item in _list_pages(client, "jobs.runs.list", "runs"):
        if not isinstance(item, dict):
            logger.warning(
                "databricks_jobs_mirror_skip_junk_run_row",
                extra={"workspace": workspace_id},
            )
            continue
        run_id = _identity(item.get("run_id"), label="run_id", workspace_id=workspace_id)
        if not run_id:
            continue
        seen_run_ids.add(run_id)

        job_id = _identity(item.get("job_id"), label="run_job_id", workspace_id=workspace_id)
        job = job_rows.get(job_id)
        if job is None:
            logger.warning(
                "databricks_jobs_mirror_skip_run_of_unmirrored_job",
                extra={"workspace": workspace_id, "run_id": run_id, "job_id": job_id},
            )
            continue

        state = item.get("state")
        if not isinstance(state, dict):
            logger.warning(
                "databricks_jobs_mirror_skip_missing_run_state",
                extra={"workspace": workspace_id, "run_id": run_id},
            )
            continue
        lifecycle = state.get("life_cycle_state")
        if not isinstance(lifecycle, str) or lifecycle not in DatabricksJobRunLifecycleState.values:
            logger.warning(
                "databricks_jobs_mirror_skip_unknown_lifecycle_state",
                extra={"workspace": workspace_id, "run_id": run_id, "state": lifecycle},
            )
            continue
        result = state.get("result_state")
        if result is not None and (
            not isinstance(result, str) or result not in DatabricksJobRunResultState.values
        ):
            logger.warning(
                "databricks_jobs_mirror_skip_unknown_result_state",
                extra={"workspace": workspace_id, "run_id": run_id, "state": result},
            )
            continue
        duration = item.get("run_duration")
        if duration is not None and (not isinstance(duration, int) or isinstance(duration, bool)):
            logger.warning(
                "databricks_jobs_mirror_skip_non_numeric_duration",
                extra={"workspace": workspace_id, "run_id": run_id},
            )
            continue
        message = state.get("state_message")
        if message is not None and not isinstance(message, str):
            logger.warning(
                "databricks_jobs_mirror_skip_non_string_state_message",
                extra={"workspace": workspace_id, "run_id": run_id},
            )
            continue

        defaults = {
            "lifecycle_state": lifecycle,
            "result_state": result or None,
            "duration_ms": duration,
            "error_message": message or None,
        }
        row = DatabricksJobRun.objects.filter(job=job, run_id=run_id).first()
        if row is None:
            DatabricksJobRun.objects.create(job=job, run_id=run_id, **defaults)
            if lifecycle not in _TERMINAL_LIFECYCLE_STATES:
                record_job_run_started_since(
                    run_id=run_id,
                    tenant_id=str(workspace.tenant_id),
                    workspace_id=str(workspace.id),
                    seconds_since_epoch=time.time(),
                )
            runs_counters["created"] += 1
            continue
        old_lifecycle = row.lifecycle_state
        changed = False
        for field, value in defaults.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed = True
        if changed:
            row.synced_at = timezone.now()
            row.save()
            # The terminal transition resets the long-running anchor
            # (the 3.8 STARTING-anchor pattern).
            if (
                old_lifecycle not in _TERMINAL_LIFECYCLE_STATES
                and row.lifecycle_state in _TERMINAL_LIFECYCLE_STATES
            ):
                record_job_run_started_since(
                    run_id=run_id,
                    tenant_id=str(workspace.tenant_id),
                    workspace_id=str(workspace.id),
                    seconds_since_epoch=0,
                )
            runs_counters["updated"] += 1
        else:
            runs_counters["unchanged"] += 1

    # Absent runs leave the mirror — derived, never compensated.
    for row in DatabricksJobRun.objects.filter(job__workspace=workspace):
        if row.run_id not in seen_run_ids:
            record_job_run_started_since(
                run_id=row.run_id,
                tenant_id=str(workspace.tenant_id),
                workspace_id=str(workspace.id),
                seconds_since_epoch=0,
            )
            row.delete()
            runs_counters["deleted"] += 1

    # 4.5 — the fleet observability stamps (best-effort by the record
    # functions' own contract; a metric-backend outage never fails the
    # refresh).
    record_jobs_mirror_success(tenant_id=str(workspace.tenant_id), workspace_id=str(workspace.id))
    record_job_run_state_counts(workspace)

    return {"jobs": jobs_counters, "runs": runs_counters}
