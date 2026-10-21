"""275.E.3c — OpenLineage emission for the warehouse connectivity surface.

Three flows emit OpenLineage ``RunEvent``s, mirroring the contract-edge
emitter in :mod:`hub.apps.contracts.lineage_sync` (same capability gate,
same fire-and-forget delivery, same fail-soft contract):

* **Warehouse intake** — input = warehouse table URI, output = Hub Asset
  URI (data moves into the Hub's catalog view).
* **Live query** — input = warehouse table URI, output = Hub Asset URI.
  OFF by default (volume); gated on ``lineage.warehouse_live_query``.
* **Outbound write / export** — input = Hub Asset URI, output = target
  warehouse table URI (data moves into the customer's warehouse).

All three are fire-and-forget: the relational resource rows are the
load-bearing record; the OpenLineage event is a downstream signal
redeliverable via the existing DLQ replay path.  Failures are logged and
never propagate to the caller.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.utils import timezone

logger = __import__("logging").getLogger(__name__)

# Mirrors hub.apps.integrations.openlineage.translator.
OPENLINEAGE_SCHEMA_URL = "https://openlineage.io/spec/2-0-0/OpenLineage.json"

_WAREHOUSE_NAMESPACE = "meshant.warehouse"


def _dataset(namespace: str, name: str) -> dict[str, Any]:
    return {"namespace": namespace, "name": name}


def _run_event(
    *,
    run_id: str,
    job_name: str,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    producer: str,
) -> dict[str, Any]:
    return {
        "eventType": "COMPLETE",
        "eventTime": timezone.now().isoformat(),
        "producer": producer,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
        "run": {"runId": run_id},
        "job": {"namespace": _WAREHOUSE_NAMESPACE, "name": job_name},
        "inputs": inputs,
        "outputs": outputs,
    }


def _producer() -> str:
    from django.conf import settings

    return getattr(
        settings,
        "OPENLINEAGE_PRODUCER_NAME",
        "https://meshant.com/lineage/openlineage",
    )


def _capability_enabled(name: str) -> bool:
    """Capability-flag gate — no dispatch when OFF (fail closed)."""
    try:
        from hub.apps.api.capabilities import is_capability_enabled

        return bool(is_capability_enabled(name))
    except Exception:
        return False


def _dispatch(event: dict[str, Any], tenant_id: str | None) -> str:
    from hub.apps.integrations.openlineage.tasks import send_openlineage_event_async

    if not tenant_id:
        return "skipped:no_tenant"
    try:
        return send_openlineage_event_async(event, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "warehouse_openlineage_emit_failed",
            extra={"error": str(exc), "tenant_id": str(tenant_id)},
        )
        return f"failed:{type(exc).__name__}"


def emit_warehouse_intake_event(
    *,
    tenant_id: str,
    warehouse_table_uri: str,
    hub_asset_uri: str,
    run_id: str | None = None,
) -> str:
    """Warehouse intake: warehouse table → Hub asset."""
    if not _capability_enabled("lineage.openlineage_export"):
        return "skipped:capability_off"
    event = _run_event(
        run_id=run_id or f"warehouse-intake:{uuid.uuid4()}",
        job_name="warehouse_intake",
        inputs=[_dataset("warehouse", warehouse_table_uri)],
        outputs=[_dataset("meshant.asset", hub_asset_uri)],
        producer=_producer(),
    )
    return _dispatch(event, tenant_id)


def emit_live_query_event(
    *,
    tenant_id: str,
    warehouse_table_uri: str,
    hub_asset_uri: str,
    run_id: str | None = None,
) -> str:
    """Live query: warehouse table → Hub asset.  OFF by default.

    Volume-gated on ``lineage.warehouse_live_query`` (default OFF) in
    addition to the general export capability.
    """
    if not _capability_enabled("lineage.warehouse_live_query"):
        return "skipped:capability_off"
    event = _run_event(
        run_id=run_id or f"warehouse-live-query:{uuid.uuid4()}",
        job_name="warehouse_live_query",
        inputs=[_dataset("warehouse", warehouse_table_uri)],
        outputs=[_dataset("meshant.asset", hub_asset_uri)],
        producer=_producer(),
    )
    return _dispatch(event, tenant_id)


def emit_warehouse_export_event(
    *,
    tenant_id: str,
    hub_asset_uri: str,
    warehouse_table_uri: str,
    run_id: str | None = None,
) -> str:
    """Outbound write/export: Hub asset → warehouse table."""
    if not _capability_enabled("lineage.openlineage_export"):
        return "skipped:capability_off"
    event = _run_event(
        run_id=run_id or f"warehouse-export:{uuid.uuid4()}",
        job_name="warehouse_export",
        inputs=[_dataset("meshant.asset", hub_asset_uri)],
        outputs=[_dataset("warehouse", warehouse_table_uri)],
        producer=_producer(),
    )
    return _dispatch(event, tenant_id)
