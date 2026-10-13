"""Databricks DLT pipeline/update state mirror (openspec
add-databricks-dlt-pipelines task 10.3).

The mirror is a READ cache of the Databricks-owned pipeline state: the
sync lists the workspace's pipelines through the pinned pipelines
surface (``pipelines.list``, 2.0 — the ``statuses`` array), fetches each
pipeline's payload (``pipelines.get``, 2.0 — the spec/settings and the
channel live there; the list statuses do not carry them), then lists
each pipeline's updates (``pipelines.updates.list``, page_token chains
with the repeating-token guard) and delta-diffs them into
``DatabricksDltPipeline``/``DatabricksDltPipelineUpdate`` rows —
created/updated/unchanged/deleted per surface, with the freshness stamp
touched ONLY on change (the 1.5 UC-sync convention). The Hub NEVER
invents a state:

- an API-reported pipeline/update state (or channel) the vocabulary
  does not know is SKIPPED with a warning (the row is not created),
- junk statuses, missing identities, and missing names are SKIPPED,
- a pipeline deleted between list and get (a 404) skips the row WITHOUT
  sweeping an existing one (never a destructive wipe on a race),
- a transient 404 on a pipeline's updates list keeps that pipeline's
  existing update rows untouched (the sweep is skipped on errors),
- absent pipelines leave the mirror without any compensating action,
- a reported-but-skipped id is recorded as SEEN before the skip
  decision (the 3.2 ordering that keeps a skipped row from being
  swept).

The dbu/error_message columns stay NULL here — the events-derived cost
and failure detail are the 10.6 observability job's surface, not the
state mirror's.

The caller owns the client (identity resolution is the 10.3 pipelines
client's contract); this service only maps reported state. The caller
runs under the tenant context (RLS) — this service never selects
credentials.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.utils import timezone

from hub.apps.databricks_admin.models import (
    DatabricksDltChannel,
    DatabricksDltPipeline,
    DatabricksDltPipelineState,
    DatabricksDltPipelineUpdate,
    DatabricksDltPipelineUpdateState,
    DatabricksWorkspace,
)

if TYPE_CHECKING:
    from hub.apps.databricks_admin.client import DatabricksApiClient

logger = logging.getLogger(__name__)


def _json_object(
    client: DatabricksApiClient,
    operation: str,
    *,
    params: dict | None = None,
    path_params: dict | None = None,
) -> dict:
    """One version-pinned GET with the 0.7 JSON discipline: a malformed
    2xx body is a classified error, never a leaked JSONDecodeError."""
    from hub.apps.databricks_admin.client import DatabricksApiError

    response = client.request("GET", operation, params=params or {}, path_params=path_params or {})
    try:
        payload = response.json()
    except ValueError as exc:
        raise DatabricksApiError(
            f"{operation} returned a non-JSON body", status_code=response.status_code
        ) from exc
    if not isinstance(payload, dict):
        raise DatabricksApiError(
            f"{operation} returned a non-object body", status_code=response.status_code
        )
    return payload


def _list_pages(
    client: DatabricksApiClient, operation: str, list_key: str, path_params: dict
) -> list:
    """Follow ``next_page_token`` chains exactly (the UC REST contract),
    with the 1.12 repeating-token guard."""
    from hub.apps.databricks_admin.client import DatabricksApiError

    items: list = []
    seen_tokens: set[str] = set()
    request_params: dict = {}
    while True:
        payload = _json_object(client, operation, params=request_params, path_params=path_params)
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
            "databricks_dlt_mirror_skip_missing_id",
            extra={"workspace": workspace_id, "id_field": label},
        )
    return result


def _is_404(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 404


def refresh_dlt_mirror(workspace: DatabricksWorkspace, *, client: DatabricksApiClient) -> dict:
    """Pipelines list + one get per pipeline + one updates list per
    pipeline → delta-diff into the mirror.

    Returns ``{"pipelines": {...counters}, "updates": {...counters}}`` —
    each surface carries the created/updated/unchanged/deleted counters.
    The caller runs under the tenant context (RLS) and owns the client
    identity — this service never selects credentials.
    """
    from hub.apps.databricks_admin.client import DatabricksApiError

    workspace_id = str(workspace.id)
    pipelines_counters = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}
    updates_counters = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}

    # ── pipelines ──────────────────────────────────────────────────────
    payload = _json_object(client, "pipelines.list")
    statuses = payload.get("statuses")
    if statuses is None:
        statuses = []
    if not isinstance(statuses, list):
        raise DatabricksApiError("pipelines.list returned a non-list 'statuses' field")

    seen_pipeline_ids: set[str] = set()
    for status in statuses:
        if not isinstance(status, dict):
            logger.warning(
                "databricks_dlt_mirror_skip_junk_status",
                extra={"workspace": workspace_id},
            )
            continue
        pipeline_id = _identity(
            status.get("pipeline_id"), label="pipeline_id", workspace_id=workspace_id
        )
        if not pipeline_id:
            continue
        # SEEN before the shape guards: a reported-but-skipped pipeline
        # keeps its existing mirror row (never invented, never swept).
        seen_pipeline_ids.add(pipeline_id)

        try:
            detail = _json_object(client, "pipelines.get", path_params={"pipeline_id": pipeline_id})
        except DatabricksApiError as exc:
            if _is_404(exc):
                logger.warning(
                    "databricks_dlt_mirror_skip_deleted_in_flight",
                    extra={"workspace": workspace_id, "pipeline_id": pipeline_id},
                )
                continue
            raise

        name = detail.get("name")
        if not isinstance(name, str) or not name.strip():
            logger.warning(
                "databricks_dlt_mirror_skip_missing_name",
                extra={"workspace": workspace_id, "pipeline_id": pipeline_id},
            )
            continue
        state = detail.get("state")
        if state not in DatabricksDltPipelineState.values:
            logger.warning(
                "databricks_dlt_mirror_skip_unknown_state",
                extra={"workspace": workspace_id, "pipeline_id": pipeline_id, "state": state},
            )
            continue
        spec = detail.get("spec")
        if not isinstance(spec, dict):
            logger.warning(
                "databricks_dlt_mirror_missing_spec",
                extra={"workspace": workspace_id, "pipeline_id": pipeline_id},
            )
            spec = {}
        channel = spec.get("channel")
        if channel is not None and channel not in DatabricksDltChannel.values:
            logger.warning(
                "databricks_dlt_mirror_skip_unknown_channel",
                extra={"workspace": workspace_id, "pipeline_id": pipeline_id, "channel": channel},
            )
            continue

        defaults = {"name": name, "state": state, "settings": spec, "channel": channel}
        pipeline_row = DatabricksDltPipeline.objects.filter(
            workspace=workspace, pipeline_id=pipeline_id
        ).first()
        if pipeline_row is None:
            DatabricksDltPipeline.objects.create(
                workspace=workspace, pipeline_id=pipeline_id, **defaults
            )
            pipelines_counters["created"] += 1
            continue
        changed = False
        for field, value in defaults.items():
            if getattr(pipeline_row, field) != value:
                setattr(pipeline_row, field, value)
                changed = True
        if changed:
            pipeline_row.synced_at = timezone.now()
            pipeline_row.save()
            pipelines_counters["updated"] += 1
        else:
            pipelines_counters["unchanged"] += 1

    # Absent-on-the-workspace pipelines leave the mirror — derived,
    # never compensated (their updates die with them via the cascade).
    for stale_pipeline_row in DatabricksDltPipeline.objects.filter(workspace=workspace):
        if stale_pipeline_row.pipeline_id not in seen_pipeline_ids:
            stale_pipeline_row.delete()
            pipelines_counters["deleted"] += 1

    # ── updates ────────────────────────────────────────────────────────
    for pipeline in DatabricksDltPipeline.objects.filter(workspace=workspace):
        try:
            reported_updates = _list_pages(
                client,
                "pipelines.updates.list",
                "updates",
                {"pipeline_id": pipeline.pipeline_id},
            )
        except DatabricksApiError as exc:
            if _is_404(exc):
                logger.warning(
                    "databricks_dlt_mirror_skip_updates_deleted_in_flight",
                    extra={"workspace": workspace_id, "pipeline_id": pipeline.pipeline_id},
                )
                continue
            raise

        seen_update_ids: set[str] = set()
        for item in reported_updates:
            if not isinstance(item, dict):
                logger.warning(
                    "databricks_dlt_mirror_skip_junk_update",
                    extra={"workspace": workspace_id, "pipeline_id": pipeline.pipeline_id},
                )
                continue
            update_id = _identity(
                item.get("update_id"), label="update_id", workspace_id=workspace_id
            )
            if not update_id:
                continue
            seen_update_ids.add(update_id)

            state = item.get("state")
            if state not in DatabricksDltPipelineUpdateState.values:
                logger.warning(
                    "databricks_dlt_mirror_skip_unknown_update_state",
                    extra={
                        "workspace": workspace_id,
                        "pipeline_id": pipeline.pipeline_id,
                        "update_id": update_id,
                        "state": state,
                    },
                )
                continue
            full_refresh = item.get("full_refresh")
            if full_refresh is not None and not isinstance(full_refresh, bool):
                logger.warning(
                    "databricks_dlt_mirror_skip_non_bool_full_refresh",
                    extra={
                        "workspace": workspace_id,
                        "pipeline_id": pipeline.pipeline_id,
                        "update_id": update_id,
                    },
                )
                continue
            refresh_selection = item.get("refresh_selection")
            if refresh_selection is not None and not isinstance(refresh_selection, (dict, list)):
                logger.warning(
                    "databricks_dlt_mirror_skip_non_json_refresh_selection",
                    extra={
                        "workspace": workspace_id,
                        "pipeline_id": pipeline.pipeline_id,
                        "update_id": update_id,
                    },
                )
                continue

            defaults = {
                "state": state,
                "full_refresh": bool(full_refresh),
                "refresh_selection": refresh_selection,
            }
            update_row = DatabricksDltPipelineUpdate.objects.filter(
                pipeline=pipeline, update_id=update_id
            ).first()
            if update_row is None:
                DatabricksDltPipelineUpdate.objects.create(
                    pipeline=pipeline, update_id=update_id, **defaults
                )
                updates_counters["created"] += 1
                continue
            changed = False
            for field, value in defaults.items():
                if getattr(update_row, field) != value:
                    setattr(update_row, field, value)
                    changed = True
            if changed:
                update_row.synced_at = timezone.now()
                update_row.save()
                updates_counters["updated"] += 1
            else:
                updates_counters["unchanged"] += 1

        # Absent updates leave the mirror — derived, never compensated.
        for stale_row in DatabricksDltPipelineUpdate.objects.filter(pipeline=pipeline):
            if stale_row.update_id not in seen_update_ids:
                stale_row.delete()
                updates_counters["deleted"] += 1

    return {"pipelines": pipelines_counters, "updates": updates_counters}
