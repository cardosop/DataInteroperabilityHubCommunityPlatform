"""Execution-target selection + the dbt-as-job dispatch facade
(openspec run-transformation-on-databricks task 11.2, design D1).

- ``ExecutionTarget`` — the D1 vocabulary: ``local`` (the unchanged
  default — DuckDB/Polars profiles), ``databricks_warehouse`` (the
  dbt-databricks adapter profile against a SQL warehouse — the D3
  profile swap), ``databricks_job`` (the staged project runs as a
  Databricks job through the shipped 4.3 client + the 4.4 poll
  discipline).
- ``resolve_execution_target`` — strict parsing; an unknown value
  refuses with ``DATABRICKS_EXECUTION_TARGET_INVALID`` (never a silent
  local fallback — the D1 contract); unset/empty resolves LOCAL (D6).
- The dbt-as-job dispatch facade — the provider-boundary inversion
  (the 7.5 cost-recording convention): this module defines the
  CONSUMER side only; ``databricks_admin`` registers the REAL
  dispatcher at app-ready (``register_dbt_job_dispatcher``). An
  unregistered facade refuses with
  ``DATABRICKS_DBT_JOB_DISPATCH_UNAVAILABLE`` — never a silent local
  fallback. The dispatcher's classified refusal code rides through
  into the transformation error family (the executor's failure
  classification is unchanged — D3).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from hub.apps.transformation.exceptions import TransformationExecutionError

if TYPE_CHECKING:
    from collections.abc import Callable


class ExecutionTarget(StrEnum):
    LOCAL = "local"
    DATABRICKS_WAREHOUSE = "databricks_warehouse"
    DATABRICKS_JOB = "databricks_job"


_TARGET_VOCABULARY = {
    ExecutionTarget.LOCAL.value: ExecutionTarget.LOCAL,
    ExecutionTarget.DATABRICKS_WAREHOUSE.value: ExecutionTarget.DATABRICKS_WAREHOUSE,
    ExecutionTarget.DATABRICKS_JOB.value: ExecutionTarget.DATABRICKS_JOB,
}


def resolve_execution_target(value: str | None) -> ExecutionTarget:
    """Resolve a run config's execution-target value.

    Unset/empty → ``LOCAL`` (the shipped default — D6). An unknown
    value refuses with the classified code naming the value — NEVER a
    silent local fallback (the D1 contract).
    """
    if value is None or value == "":
        return ExecutionTarget.LOCAL
    normalized = value.strip().lower()
    target = _TARGET_VOCABULARY.get(normalized)
    if target is None:
        raise TransformationExecutionError(
            f"Unknown execution target '{value}' — expected one of {sorted(_TARGET_VOCABULARY)}",
            error_code="DATABRICKS_EXECUTION_TARGET_INVALID",
        )
    return target


# ── dbt-as-job dispatch facade (the provider inversion) ────────────────

#: The registered dispatchers — exactly ONE provider registers the real
#: implementation (``databricks_admin`` at app-ready, the 7.5
#: convention). Tests register a consumer-side stand-in.
_JOB_DISPATCHERS: list[Callable[..., dict[str, Any]]] = []


def register_dbt_job_dispatcher(dispatcher: Callable[..., dict[str, Any]]) -> None:
    """Register the provider's real dbt-as-job dispatcher.

    Keyword-only contract: ``(tenant_id, workspace_id, runner_job_id,
    select, target, actor_user, sleeper) -> dict`` — the returned dict
    carries at minimum ``job_id``/``status``/``run_id``/``resource_type``.
    """
    if dispatcher not in _JOB_DISPATCHERS:
        _JOB_DISPATCHERS.append(dispatcher)


def get_dbt_job_dispatcher() -> Callable[..., dict[str, Any]] | None:
    """The most recently registered dispatcher (None when unregistered)."""
    return _JOB_DISPATCHERS[-1] if _JOB_DISPATCHERS else None


def dispatch_dbt_as_databricks_job(
    *,
    tenant_id: str,
    workspace_id: str,
    runner_job_id: str,
    select: list[str] | None,
    target: str,
    actor_user=None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Dispatch a dbt run/test as a Databricks job through the
    registered provider dispatcher.

    An unregistered facade refuses with
    ``DATABRICKS_DBT_JOB_DISPATCH_UNAVAILABLE``; the dispatcher's own
    classified code rides through into the transformation error family
    (D3 — the executor's failure classification is unchanged).
    """
    dispatcher = get_dbt_job_dispatcher()
    if dispatcher is None:
        raise TransformationExecutionError(
            "No dbt-as-job dispatcher is registered — the Databricks job "
            "execution target is unavailable",
            error_code="DATABRICKS_DBT_JOB_DISPATCH_UNAVAILABLE",
        )
    try:
        return dispatcher(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            runner_job_id=runner_job_id,
            select=select,
            target=target,
            actor_user=actor_user,
            sleeper=sleeper,
        )
    except TransformationExecutionError:
        raise
    except Exception as exc:
        # provider's classified code into the transformation family.
        code = getattr(exc, "code", None)
        raise TransformationExecutionError(
            f"dbt-as-job dispatch failed: {exc}",
            error_code=code or "DATABRICKS_DBT_JOB_DISPATCH_FAILED",
        ) from exc
