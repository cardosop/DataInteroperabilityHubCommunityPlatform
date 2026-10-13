"""W4.6 (openspec oss-release-remediation, G1) — the estate side of the
staging-volume provisioner seam (openspec wire-databricks-dlt-movement
task 6.4).

The executor construction (``UCChangeExecutor`` + ``UCDdlPayload``) is
provider estate code and stays HERE; the provider-agnostic consumer
(``hub.data_movement.staging.ensure_staging_volume``) dispatches
through the registry at app-ready — it never imports estate modules.
The caller owns the client (the 2.2 executor contract — identity
resolution is the caller's concern); this provisioner only runs the
REST-first ``uc.volumes.create`` the executor's own CREATE idempotency
makes safe to re-run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hub.apps.databricks_admin.client import DatabricksApiClient


def provision_staging_volume(
    client: DatabricksApiClient,
    *,
    tenant,
    catalog: str,
    schema: str,
    volume: str,
    statement_executor=None,
    warehouse_id: str | None = None,
) -> None:
    """Create the tenant's managed staging volume through the P2
    executor (the ``register_staging_volume_provisioner`` contract)."""
    from hub.apps.databricks_admin.models import UCChangeAction, UCObjectType
    from hub.apps.databricks_admin.uc_change_executor import (
        UCChangeExecutor,
        UCDdlPayload,
    )

    executor = UCChangeExecutor(
        client=client,
        statement_executor=statement_executor,
        warehouse_id=warehouse_id,
        tenant=tenant,
    )
    executor.execute(
        UCDdlPayload(
            object_type=UCObjectType.VOLUME,
            action=UCChangeAction.CREATE,
            identifiers=(catalog, schema, volume),
            options={"volume_type": "MANAGED"},
        )
    )
