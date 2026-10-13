"""The REAL dbt-as-job dispatcher (openspec run-transformation-on-databricks
task 11.2, design D1) — the registered provider implementation of the
transformation facade
(``hub.apps.transformation.execution_targets.dispatch_dbt_as_databricks_job``).

The dispatcher resolves the tenant's workspace + the mirrored runner
job inside ``tenant_context`` (the CLAUDE.md worker contract), builds
the PRODUCTION ``DatabricksJobsClient`` through the 0.8 factory seam
(``_build_dbt_dispatch_client`` — tests redirect it to a local
transport, the client itself is production), and rides the REAL 4.4
``run_databricks_job_now`` spine — the Hub ``Job`` row
(``JobType.DATABRICKS_JOB_RUN``), the RUN_STARTED audit at dispatch,
the backoff poll to the terminal state, the terminal audit + lineage +
cost estimate (the 4.4 emission set, unchanged).

Fail-closed: a missing workspace / a missing runner job refuses with
``DATABRICKS_DBT_RUNNER_JOB_MISSING`` and ZERO API calls — the
transformation facade converts this code into its own error family
(D3: the executor's failure classification is unchanged).

The provider-boundary inversion (the 7.5 cost-recording convention):
``transformation`` NEVER imports this module; ``databricks_admin``
registers the dispatcher at app-ready.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

from hub.apps.tenants.request_tenant import tenant_context

logger = structlog.get_logger(__name__)


class DatabricksDbtDispatchError(Exception):
    """The dispatcher's classified refusal family — the facade converts
    the ``code`` into the transformation error family."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _build_dbt_dispatch_client(workspace):
    """The REAL jobs client in workspace mode (the 0.8
    ``_build_probe_client`` convention). Tests redirect this factory to
    a local transport — the client itself is the production client."""
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.jobs_client import DatabricksJobsClient

    credential = (
        workspace.credentials.filter(auth_mode__in=["PAT", "OAUTH_M2M"])
        .order_by("-created_at")
        .first()
    )
    kwargs: dict = {}
    if credential is not None:
        kwargs["credential_config"] = credential.get_config()
        kwargs["auth_mode"] = credential.auth_mode
    return DatabricksJobsClient(
        DatabricksApiClient(
            workspace=workspace,
            tenant_id=str(workspace.tenant_id),
            **kwargs,
        )
    )


def dispatch_dbt_run_as_databricks_job(
    *,
    tenant_id: str,
    workspace_id: str,
    runner_job_id: str,
    select: list[str] | None,
    target: str,
    actor_user=None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Dispatch a dbt run/test as the tenant's mirrored runner job and
    follow it to its terminal state (the 4.4 spine).

    Returns ``{"job_id", "status", "run_id", "resource_type"}``.
    Raises ``DatabricksDbtDispatchError`` (classified) on a missing
    workspace/runner job — with ZERO API calls.
    """
    from hub.apps.databricks_admin.job_runs import run_databricks_job_now
    from hub.apps.databricks_admin.models import (
        DatabricksJob,
        DatabricksWorkspace,
    )

    with tenant_context(tenant_id):
        workspace = DatabricksWorkspace.objects.filter(tenant_id=tenant_id, id=workspace_id).first()
        if workspace is None:
            raise DatabricksDbtDispatchError(
                "DATABRICKS_DBT_RUNNER_JOB_MISSING",
                f"workspace {workspace_id} is not registered for this tenant",
            )

        mirror_job = DatabricksJob.objects.filter(workspace=workspace, job_id=runner_job_id).first()
        if mirror_job is None:
            raise DatabricksDbtDispatchError(
                "DATABRICKS_DBT_RUNNER_JOB_MISSING",
                f"runner job {runner_job_id} is not mirrored for workspace {workspace_id}",
            )

        client = _build_dbt_dispatch_client(workspace)
        job = run_databricks_job_now(
            workspace=workspace,
            mirror_job=mirror_job,
            actor_user=actor_user,
            client=client,
            sleeper=sleeper if sleeper is not None else time.sleep,
        )

    logger.info(
        "dbt_run_as_databricks_job_completed",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        runner_job_id=runner_job_id,
        select=select,
        target=target,
        hub_job_id=str(job.id),
        status=job.status,
        databricks_run_id=job.databricks_run_id,
    )
    return {
        "job_id": str(job.id),
        "status": job.status,
        "run_id": job.databricks_run_id,
        "resource_type": "DATABRICKS_JOB",
    }
