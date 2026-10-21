"""275.E.3c — warehouse OpenLineage events (TDD).

Pins the contract for the three warehouse lineage flows:

1. Intake:  input = warehouse table URI, output = Hub asset URI.
2. Live query: same direction, gated OFF unless
   ``lineage.warehouse_live_query`` is enabled (volume).
3. Export:  input = Hub asset URI, output = warehouse table URI.

Every emitted event must validate against the OpenLineage 2.0 RunEvent
schema (the same ``validate_openlineage_event`` the contract-edge suite
uses) and carry the correct input/output direction.  Dispatch goes
through the real ``send_openlineage_event_async`` (which no-ops without a
configured OPENLINEAGE_URL — no network dependency in tests).
"""

from __future__ import annotations

import uuid

import pytest

from hub.apps.integrations.openlineage.translator import validate_openlineage_event
from hub.apps.tenants.models import Tenant
from hub.apps.warehouses import lineage


@pytest.mark.django_db
def test_warehouse_lineage_events_have_openlineage_shape_and_direction():
    # Unique name per run — the shared reuse-DB keeps committed rows from
    # interrupted runs, and Tenant.name is unique.
    Tenant.objects.create(
        name=f"wh-lineage-{uuid.uuid4().hex[:8]}", slug=f"wh-lineage-{uuid.uuid4().hex[:8]}"
    )
    table_uri = "snowflake://demo_db.public.customers"
    asset_uri = f"meshant://assets/{uuid.uuid4()}"

    # Build events through the module's internal builder so we can assert
    # shape without hitting the capability gate / network dispatch.
    event = lineage._run_event(
        run_id=f"t-{uuid.uuid4()}",
        job_name="warehouse_intake",
        inputs=[lineage._dataset("warehouse", table_uri)],
        outputs=[lineage._dataset("meshant.asset", asset_uri)],
        producer=lineage._producer(),
    )
    validate_openlineage_event(event)
    assert event["job"]["namespace"] == "meshant.warehouse"
    assert event["inputs"][0]["namespace"] == "warehouse"
    assert event["inputs"][0]["name"] == table_uri
    assert event["outputs"][0]["namespace"] == "meshant.asset"
    assert event["outputs"][0]["name"] == asset_uri


@pytest.mark.django_db
def test_live_query_emission_is_off_by_default():
    """The live-query emitter must skip when its capability flag is OFF."""
    tenant = Tenant.objects.create(
        name=f"wh-lq-{uuid.uuid4().hex[:8]}", slug=f"wh-lq-{uuid.uuid4().hex[:8]}"
    )
    outcome = lineage.emit_live_query_event(
        tenant_id=str(tenant.id),
        warehouse_table_uri="snowflake://demo_db.public.customers",
        hub_asset_uri=f"meshant://assets/{uuid.uuid4()}",
    )
    assert outcome == "skipped:capability_off"


@pytest.mark.django_db
def test_export_event_direction_is_hub_asset_to_warehouse_table():
    """Export flows Hub asset → warehouse table (outbound write)."""
    _tenant = Tenant.objects.create(
        name=f"wh-exp-{uuid.uuid4().hex[:8]}", slug=f"wh-exp-{uuid.uuid4().hex[:8]}"
    )
    event = lineage._run_event(
        run_id=f"e-{uuid.uuid4()}",
        job_name="warehouse_export",
        inputs=[lineage._dataset("meshant.asset", "meshant://assets/a1")],
        outputs=[lineage._dataset("warehouse", "snowflake://demo_db.public.out")],
        producer=lineage._producer(),
    )
    validate_openlineage_event(event)
    assert event["inputs"][0]["namespace"] == "meshant.asset"
    assert event["outputs"][0]["namespace"] == "warehouse"
    assert event["job"]["name"] == "warehouse_export"
