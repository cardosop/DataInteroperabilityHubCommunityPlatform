"""Phase 2 (openspec add-databricks-uc-write task 2.5) — the RQ job handler
for the stuck-EXECUTING reaper.

``_execute_databricks_uc_change_reaper_job`` is the executor surface the
jobs dispatcher calls for ``JobType.DATABRICKS_UC_CHANGE_REAPER`` (the
per-type handler lives HERE, inside ``databricks_admin`` — the provider
boundary holds; the jobs app imports only this handler function).

One job row = ONE tenant. The handler wraps the whole reap in
``tenant_context(tenant_id)`` (the worker contract — RLS-scoped request
reads and writes) and resolves every stuck request of that tenant.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hub.apps.databricks_admin.uc_change_reaper import (
    find_stuck_requests,
    resolve_stuck_request,
)

if TYPE_CHECKING:
    from hub.apps.jobs.models import Job

logger = logging.getLogger(__name__)


def _execute_databricks_uc_change_reaper_job(job_obj: Job) -> dict:
    """Resolve every stuck EXECUTING request of the job's tenant.

    Returns ``{"reaped", "rollbacks", "failures"}``. One request's
    outcome never blocks another (the reaper resolves per request).
    """
    from hub.apps.tenants.request_tenant import tenant_context

    tenant_id = str(job_obj.tenant_id)
    rollbacks = 0
    failures = 0

    with tenant_context(tenant_id):
        stuck = find_stuck_requests(tenant_id)
        for request in stuck:
            outcome = resolve_stuck_request(request)
            if outcome.get("skipped"):
                continue
            if outcome["terminal"] == "ROLLED_BACK":
                rollbacks += 1
            else:
                failures += 1
            logger.info(
                "databricks_uc_change_reaper_resolved",
                extra={
                    "request": str(request.id),
                    "tenant_id": tenant_id,
                    "terminal": outcome["terminal"],
                },
            )

    return {"reaped": len(stuck), "rollbacks": rollbacks, "failures": failures}
