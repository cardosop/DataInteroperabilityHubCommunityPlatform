"""
Phase 228 F4 (228.F4.23) — Marquez integration test.

Exercises the FULL outbound path against a real Marquez container.
The test is **skipped** when ``MARQUEZ_INTEGRATION_TEST_URL`` is not
set — a clean local pytest run skips this suite, while CI (which
spins up a Marquez container per workflow run) sets the env var
and exercises the live path.

Usage in CI::

    docker compose -f docker-compose.test.marquez.yml up -d marquez
    MARQUEZ_INTEGRATION_TEST_URL=http://marquez:5000/api/v1/lineage \\
        python -m pytest hub/apps/integrations/openlineage/tests/test_openlineage_marquez_integration.py

The test asserts:

* The adapter POSTs the event and Marquez returns 200/201.
* A subsequent ``GET /api/v1/jobs/<namespace>/<job-name>`` returns
  the job populated by our event.
* ``DeliveryOutcome == DELIVERED`` (not DEAD_LETTERED).
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests

MARQUEZ_URL = os.environ.get("MARQUEZ_INTEGRATION_TEST_URL")

# Skip the entire module unless the env var is set so a clean
# local run doesn't hit a non-existent Marquez.
pytestmark = pytest.mark.skipif(
    not MARQUEZ_URL,
    reason=(
        "MARQUEZ_INTEGRATION_TEST_URL not set — Phase 228 F4 integration "
        "test skipped. CI sets this; local runs target the unit tests."
    ),
)


def _build_event() -> dict:
    from hub.apps.integrations.openlineage.translator import (
        meshant_edge_to_openlineage,
    )

    edge = {
        "id": str(uuid.uuid4()),
        "source_contract": str(uuid.uuid4()),
        "target_contract": str(uuid.uuid4()),
        "source_model": "orders",
        "source_field": "order_id",
        "target_model": "fulfillment",
        "target_field": "order_ref",
        "edge_type": "transformation",
        "transformation_ref": "dbt://orders_fulfillment.sql",
        "job_ref": "airflow://etl/orders",
        "valid_from": "2026-04-30T12:00:00+00:00",
        "valid_to": None,
    }
    return meshant_edge_to_openlineage(edge, producer="https://meshant.com/")


@pytest.mark.django_db(transaction=True)
def test_outbound_event_lands_in_marquez():
    from hub.apps.integrations.openlineage.adapter import (
        DeliveryOutcome,
        OpenLineageAdapter,
    )
    from hub.apps.tenants.models import Tenant

    # Create a real tenant — the adapter persists DLQ rows scoped
    # by tenant; we don't need a subscription because the adapter
    # never goes through the API auth path.
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Integ Co {suffix}",
        slug=f"integ-{suffix}",
    )

    event = _build_event()
    outcome = OpenLineageAdapter().deliver(
        event=event,
        target_url=MARQUEZ_URL,
        tenant=tenant,
    )

    assert outcome == DeliveryOutcome.DELIVERED, (
        f"adapter.deliver expected DELIVERED against live Marquez at "
        f"{MARQUEZ_URL}; got {outcome}. Marquez may be unreachable / "
        f"down / mis-configured."
    )

    # Verify the job exists in Marquez via its own API. The event
    # we sent declared ``job.namespace=meshant.lineage`` +
    # ``job.name=<transformation_ref>`` so the lookup is deterministic.
    # URL-encode path segments: job names may contain :// and other
    # characters that break unencoded URL paths.
    from urllib.parse import quote

    job_namespace = event["job"]["namespace"]
    job_name = event["job"]["name"]
    base = MARQUEZ_URL.rsplit("/api/v1/", 1)[0] + "/api/v1"
    encoded_ns = quote(job_namespace, safe="")
    encoded_job = quote(job_name, safe="")
    resp = requests.get(
        f"{base}/namespaces/{encoded_ns}/jobs/{encoded_job}",
        timeout=10,
    )
    assert resp.status_code == 200, (
        f"Marquez did not register the job: status={resp.status_code} body={resp.text[:300]}"
    )
