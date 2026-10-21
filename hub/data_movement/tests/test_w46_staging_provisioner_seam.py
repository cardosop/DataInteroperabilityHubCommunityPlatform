"""W4.6 (openspec oss-release-remediation, G1) — TDD pins for the
staging-volume provisioner seam.

No mocks: the REAL registry. The ready()-wiring pin proves the
inversion end-to-end — after Django app population the estate's REAL
provisioner (``staging_provisioner.provision_staging_volume``) IS
registered; the end-to-end executor pin lives in ``test_staging.py``
(the REAL executor over a REAL threaded HTTP server now dispatches
THROUGH the seam). The stand-in dispatch pin proves the seam passes the
caller-owned client + the resolved identifiers, and restores the estate
provisioner in ``finally`` (module-global registries persist across a
batch). The unregistered refusal is pinned in
``scripts/tests/test_w46_provider_seams_standalone.py`` — under Django
the estate always registers at app-ready.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import override_settings

from hub.data_movement.staging import (
    ensure_staging_volume,
    get_staging_volume_provisioner,
    register_staging_volume_provisioner,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def redis_13(test_redis_endpoint):
    """The shared test cache on db 13 (the test_staging.py convention —
    flushed per fixture so the sentinel never leaks between tests)."""
    import redis

    host, port = test_redis_endpoint
    client = redis.Redis(host=host, port=port, db=13)
    client.flushdb()
    yield client
    client.flushdb()


class _BareTenant:
    """A tenant stand-in with only the staging fields the seam reads
    (the staging policy reads attributes, not the model)."""

    def __init__(self, tenant_id: str):
        self.id = tenant_id
        self.databricks_staging_volume_name = ""
        self.databricks_s3_external_location_enabled = False


def _restore_estate_provisioner():
    from hub.apps.databricks_admin.staging_provisioner import (
        provision_staging_volume,
    )

    register_staging_volume_provisioner(provision_staging_volume)


class TestStagingProvisionerSeam:
    def test_ready_wiring_registers_the_estate_provisioner(self):
        provisioner = get_staging_volume_provisioner()
        assert provisioner is not None
        assert provisioner.__module__ == "hub.apps.databricks_admin.staging_provisioner"

    @override_settings(DLT_STAGING_VOLUME_CACHE_TTL_SECONDS=60)
    def test_ensure_dispatches_through_the_registered_provisioner(self, redis_13):
        """The seam hands the provisioner the caller-owned client + the
        resolved (catalog, schema, volume) — and the sentinel then holds
        the once-per-tenant skip (the unchanged policy)."""
        seen = {}
        tenant = _BareTenant(f"tenant-{uuid.uuid4().hex[:8]}")

        def stand_in(client, *, tenant, catalog, schema, volume, **kwargs):
            seen.update(
                catalog=catalog,
                schema=schema,
                volume=volume,
                tenant_id=tenant.id,
                has_client=client is not None,
                warehouse_id=kwargs.get("warehouse_id"),
            )

        try:
            register_staging_volume_provisioner(stand_in)
            assert (
                ensure_staging_volume(
                    tenant=tenant,
                    catalog="cat",
                    schema="sch",
                    client=object(),  # the caller-owned client token
                    cache=redis_13,
                    warehouse_id="wh-1",
                )
                == "_dlt_staging_load_volume"
            )
            assert seen == {
                "catalog": "cat",
                "schema": "sch",
                "volume": "_dlt_staging_load_volume",
                "tenant_id": tenant.id,
                "has_client": True,
                "warehouse_id": "wh-1",
            }
            # The sentinel now holds — the second call never reaches the
            # provisioner (the once-per-tenant contract).
            calls_before = len(seen)
            ensure_staging_volume(
                tenant=tenant,
                catalog="cat",
                schema="sch",
                client=object(),
                cache=redis_13,
            )
            assert len(seen) == calls_before
        finally:
            _restore_estate_provisioner()
